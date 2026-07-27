"""
Horse Racing Bot - Cherry Pick Mode.

Scans ALL UK/Irish cards daily, scores everything, then cherry-picks
the best 3 selections + 3 NBs + a double across all meetings.
Quality over quantity — only pick races with genuine edge.

Scraping/parsing: pure Python.
Judgement: Claude API (with programmatic fallback).
"""

import asyncio
import logging
import os
import re
import sys
from datetime import date, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from zoneinfo import ZoneInfo

import schedule

from config.settings import TIMEZONE, ANALYSIS_TIME, RESULTS_TIME, LOG_LEVEL, ANTHROPIC_API_KEY, FOCUS_COURSES, AUTO_SCHEDULE, AUTO_RESULTS
from src.database import init_db, save_meeting, save_selections, is_bot_paused, _set_state, _get_state
from src.scraper import Scraper
from src.analyst import analyse_all_meetings, format_selections_telegram
from src.telegram_bot import create_app, send_message

logger = logging.getLogger(__name__)
tz = ZoneInfo(TIMEZONE)


def setup_logging():
    """Configure rotating log files and console output."""
    log_dir = Path("/app/logs") if os.path.exists("/app") else Path("logs")
    log_dir.mkdir(exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    fh = RotatingFileHandler(log_dir / "bot.log", maxBytes=5_000_000, backupCount=3)
    fh.setFormatter(formatter)

    ch = logging.StreamHandler()
    ch.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    root.addHandler(fh)
    root.addHandler(ch)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)


async def run_daily_pipeline(focus_courses: list[str] = None, n_races: int = None):
    """
    Cherry-pick pipeline:
    1. Scan UK/Irish meetings (optionally filtered to specific courses)
    2. Scrape all racecards (pure Python)
    3. Score everything programmatically
    4. Send top races to Claude for judgement
    5. Output: best 4 selections + 4 NBs + double

    If n_races is set (2-8), the pipeline ranks races by their top-runner
    score (gap-to-2nd as tiebreak) and cherry-picks the top N races,
    returning one SEL + one NB per race. Operating Policy still applies —
    races whose top scorer is below 70 are dropped from the N count.
    """
    if is_bot_paused():
        logger.info("Bot is paused, skipping pipeline")
        return

    # Resolve focus: explicit arg > database state > env var
    if focus_courses is None:
        db_focus = _get_state("focus_courses")
        if db_focus:
            focus_courses = [c.strip() for c in db_focus.split(",") if c.strip()]
        elif FOCUS_COURSES:
            focus_courses = [c.strip() for c in FOCUS_COURSES.split(",") if c.strip()]

    logger.info("=" * 60)
    if focus_courses:
        logger.info(f"STARTING PIPELINE — FOCUS: {', '.join(focus_courses)}")
    else:
        logger.info("STARTING CHERRY-PICK PIPELINE — ALL MEETINGS")
    logger.info("=" * 60)

    today = date.today()
    scraper = Scraper()

    try:
        # Step 1+2: Fetch racecards (filtered if focus set)
        focus_label = f" for {', '.join(c.title() for c in focus_courses)}" if focus_courses else ""
        await send_message(f"🔍 Fetching racecards{focus_label} from Racing API...")
        all_meetings = scraper.fetch_all_uk_irish_races(today, focus_courses=focus_courses)

        if not all_meetings:
            await send_message(
                "📭 No meetings loaded. Either there's no UK/Irish racing "
                "today, or the Racing API was slow to respond — if you know "
                "there's a card on, just run /run again."
            )
            return

        course_names = [m.course for m in all_meetings]
        total_races = sum(len(m.races) for m in all_meetings)
        total_runners = sum(sum(len(r.runners) for r in m.races) for m in all_meetings)
        await send_message(
            f"📋 {len(all_meetings)} meetings: {', '.join(course_names)}\n"
            f"📊 {total_races} races, {total_runners} runners loaded.\n"
            f"Scoring and analysing..."
        )

        # Enrich with recent race classes for authoritative class-drop detection
        # (last 3 runs per runner via /horses/{id}/results, parallelised)
        try:
            scraper.enrich_with_recent_classes(all_meetings, limit=3)
        except Exception as e:
            logger.warning(f"Recent classes enrichment failed: {e}")

        # Fetch Timeform verdicts for each meeting
        try:
            timeform_verdicts = scraper.fetch_timeform_verdicts(all_meetings)
            if timeform_verdicts:
                tips_text = "\n\nTIMEFORM ANALYST VERDICTS:\n" + "\n".join(
                    f"\n{course}:\n{text[:2000]}" for course, text in timeform_verdicts.items()
                )
                logger.info(f"Timeform verdicts fetched for {len(timeform_verdicts)} meetings")
            else:
                tips_text = ""
        except Exception as e:
            logger.warning(f"Timeform fetch failed: {e}")
            tips_text = ""

        going_reports = {}

        # Step 3: Score everything + Claude judgement → 3 selections
        selections = analyse_all_meetings(
            all_meetings, tips_text, going_reports, n_races=n_races
        )

        if not selections or not selections.get("selections"):
            note = selections.get("notes") if selections else None
            if note:
                await send_message(f"⚠️ {note}")
            else:
                await send_message("⚠️ No selections generated today.")
            return

        # Step 4: Save to database
        for meeting in all_meetings:
            save_meeting(meeting.course, today, meeting.going, len(meeting.races))

        # Save selections
        _save_cherry_picks(today, selections)

        # Step 5: Send to Telegram
        formatted = format_selections_telegram(selections)

        # Split if too long
        if len(formatted) > 4000:
            chunks = _split_message(formatted, 4000)
            for chunk in chunks:
                await send_message(chunk)
        else:
            await send_message(formatted)

        num_sels = len(selections.get("selections", []))
        _set_state("last_analysis_time", datetime.now(tz).strftime("%Y-%m-%d %H:%M"))
        logger.info(f"Pipeline complete: {num_sels} selections sent")

    except Exception as e:
        logger.error(f"Pipeline error: {e}", exc_info=True)
        await send_message(f"❌ Pipeline error: {e}")
    finally:
        scraper.close()


def _save_cherry_picks(today: date, selections: dict):
    """Save cherry-picked selections to database."""
    from src.database import _conn
    if _conn is None:
        return

    sels = selections.get("selections", [])
    nap_idx = selections.get("nap_index", 0)

    for sel in sels:
        if nap_idx >= 0 and sel["rank"] == nap_idx + 1:
            sel_type = "nap"
        elif sel["rank"] == 2:
            sel_type = "next_best"
        else:
            sel_type = "selection"
        # No NAP (nap_idx == -1) means flat 1pt stakes across all selections
        stake = 2.0 if sel_type == "nap" else 1.5 if sel_type == "next_best" else 1.0
        if nap_idx < 0:
            stake = 1.0  # Flat stakes when no NAP qualifies (nothing scored 78+)
        each_way = sel.get("each_way", False)

        reasoning = sel.get("reasoning", [])
        if isinstance(reasoning, list):
            reasoning = "; ".join(reasoning)

        _conn.execute(
            """INSERT INTO selections
               (meeting_id, race_time, race_name, horse, selection_type,
                odds_guide, each_way, stake_pts, reasoning, confidence, danger, score)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                None,  # Not tied to a single meeting
                sel.get("race_time", ""),
                f"{sel.get('course', '')} - {sel.get('race_name', '')}",
                sel.get("horse", ""),
                sel_type,
                sel.get("odds_guide", ""),
                each_way,
                stake * (2 if each_way else 1),
                reasoning,
                sel.get("confidence", ""),
                sel.get("danger", ""),
                sel.get("adjusted_score", 0),
            ),
        )

        # Save next best for this race
        rnb = sel.get("next_best", {})
        if rnb and rnb.get("horse") and rnb["horse"] != "N/A":
            nb_ew = rnb.get("each_way", False)
            _conn.execute(
                """INSERT INTO selections
                   (meeting_id, race_time, race_name, horse, selection_type,
                    odds_guide, each_way, stake_pts, reasoning, confidence, danger, score)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    None,
                    sel.get("race_time", ""),
                    f"{sel.get('course', '')} - {sel.get('race_name', '')}",
                    rnb.get("horse", ""),
                    "race_nb",
                    rnb.get("odds_guide", ""),
                    nb_ew,
                    0.5 * (2 if nb_ew else 1),
                    rnb.get("reasoning", ""),
                    "",
                    "",
                    0,
                ),
            )

    _conn.commit()
    logger.info(f"Saved {len(sels)} selections + NBs to database")


_COUNTRY_SUFFIX = re.compile(r"\s*\([A-Z]{2,4}\)\s*$")


def _norm_horse(name: str) -> str:
    """Normalise a horse name for matching.

    The /results endpoint returns names WITH a country suffix
    ('Hale End (IRE)', 'Garden Oasis (GB)') while racecards/selections store
    the bare name ('Hale End'). Without stripping it, exact matching never
    succeeds and every selection is logged 'no result yet' forever.
    """
    return _COUNTRY_SUFFIX.sub("", name or "").strip().lower()


async def run_results_check():
    """Auto-check results using the Racing API."""
    if is_bot_paused():
        return

    logger.info("Running auto-results check...")
    today = date.today()
    scraper = Scraper()

    try:
        # Fetch today's results from API
        gb_results = scraper.fetch_results(today, region="gb")
        ire_results = scraper.fetch_results(today, region="ire")
        all_results = gb_results + ire_results

        if not all_results:
            await send_message("📊 No results available yet.")
            return

        # Get today's selections from database
        from src.database import _conn
        if not _conn:
            return

        # Scope to TODAY's selections only. Results are only ever fetched for
        # `today`, so any past pick left unresolved (silent send failure, name
        # mismatch, evening race) can never be matched — without this filter it
        # accumulates forever and the 18:00 check re-lists months of horses.
        rows = _conn.execute(
            """SELECT id, horse, race_time, selection_type, odds_guide, stake_pts, each_way
               FROM selections
               WHERE race_time != ''
                 AND date(created_at) = date('now')
                 AND id NOT IN (SELECT selection_id FROM results)
               ORDER BY race_time"""
        ).fetchall()

        if not rows:
            await send_message("📊 No pending selections to check.")
            return

        msg = "📊 *Results Update*\n\n"
        total_pnl = 0.0
        winners = 0
        placed = 0
        pending = 0

        for sel_row in rows:
            sel_id = sel_row["id"]
            horse_name = sel_row["horse"]
            sel_type = sel_row["selection_type"]
            odds_guide = sel_row["odds_guide"] or ""
            stake = sel_row["stake_pts"] or 1.0
            each_way = sel_row["each_way"]

            # Settle this selection against today's results. All P&L now goes
            # through database.settle_and_save(bog=True) so it is booked at BOG
            # (better of morning `odds_guide` and SP -- worth ~9pts of ROI and
            # what CLAUDE.md mandates), with place terms from place_terms() and
            # field size = actual runners. Two passes so a genuine finisher
            # always beats a same-named non-runner in an earlier-iterated race.
            from src.database import settle_and_save
            type_label = {"nap": "NAP", "next_best": "NB", "selection": "SEL", "race_nb": "RNB"}.get(sel_type, sel_type)
            found = False

            # Pass 1 -- did the horse run? (finisher, or PU/F/UR = lost)
            for result in all_results:
                runners = result.get("runners", [])
                is_handicap = "handicap" in (result.get("race_name", "") or "").lower()
                for runner in runners:
                    if _norm_horse(runner.get("horse", "")) == _norm_horse(horse_name):
                        pos = str(runner.get("position", "") or "")
                        sp = runner.get("sp", "") or ""
                        # PU / F / UR / any non-digit (or a bogus 0) -> did not
                        # complete = LOST. Use a sentinel ABOVE any place count:
                        # NEVER None (settle() reads that as a non-runner refund)
                        # and NEVER 0 (0 <= n_places, so settle() would mis-book
                        # a pulled-up horse as PLACED and pay the place leg).
                        finish_pos = int(pos) if (pos.isdigit() and int(pos) >= 1) else 999
                        s = settle_and_save(sel_id, finish_pos, sp, len(runners),
                                            is_handicap=is_handicap, bog=True)
                        pnl = s["pnl_pts"]
                        total_pnl += pnl
                        if s["result"] == "won":
                            winners += 1
                            emoji = "✅"
                        elif s["result"] == "placed":
                            placed += 1
                            emoji = "🔸"
                        else:
                            emoji = "❌"
                        pos_lbl = pos if pos else "-"
                        msg += (f"{emoji} {type_label}: {horse_name} - {pos_lbl} "
                                f"(SP {sp}, paid {s['price_used']:.2f}) {pnl:+.2f}pts\n")
                        found = True
                        break
                if found:
                    break

            # Pass 2 -- authoritative non-runner (results carry a `non_runners`
            # name string). Void: full stake returned, pnl 0. Only if it did not
            # run above, so a same-named finisher can never be voided by mistake.
            if not found:
                for result in all_results:
                    nrs = [_norm_horse(x) for x in (result.get("non_runners", "") or "").split(",") if x.strip()]
                    if _norm_horse(horse_name) in nrs:
                        is_handicap = "handicap" in (result.get("race_name", "") or "").lower()
                        s = settle_and_save(sel_id, None, "", len(result.get("runners", [])),
                                            is_handicap=is_handicap, bog=True)
                        total_pnl += s["pnl_pts"]  # 0.0 -- stake returned
                        msg += f"➖ {type_label}: {horse_name} - NON-RUNNER (void, stake returned)\n"
                        found = True
                        break

            if not found:
                pending += 1

        msg += f"\n*Day P&L: {total_pnl:+.1f}pts*"
        msg += f"\n✅ {winners} winners | 🔸 {placed} placed"
        if pending:
            msg += f"\n⏳ {pending} awaiting results (races not yet run / no result published)"
        await send_message(msg)

    except Exception as e:
        logger.error(f"Results check error: {e}", exc_info=True)
        await send_message(f"⚠️ Results check error: {e}")
    finally:
        scraper.close()

    _set_state("last_results_time", datetime.now(tz).strftime("%Y-%m-%d %H:%M"))


def schedule_jobs():
    """Set up daily schedule.

    Two independent flags:
    * AUTO_SCHEDULE schedules the analysis pipeline (uses Claude API → £).
    * AUTO_RESULTS schedules the results fetch (uses Racing API → free).
      Defaults ON so the results table stays populated for backtesting
      and live P&L tracking, regardless of whether analysis is automated.
    """
    # Fire jobs against UK wall-clock, not the container clock (which is
    # UTC). Passing tz keeps RESULTS_TIME/ANALYSIS_TIME meaning UK time
    # year-round, surviving the BST->GMT switch. TIMEZONE = Europe/London.
    tz = TIMEZONE or None

    if AUTO_SCHEDULE:
        schedule.every().day.at(ANALYSIS_TIME, tz).do(
            lambda: asyncio.get_event_loop().create_task(run_daily_pipeline())
        )
        logger.info(f"Scheduled: analysis at {ANALYSIS_TIME} {tz or '(container clock)'}")
    else:
        logger.info("Auto-schedule DISABLED. Use /run via Telegram for on-demand analysis.")

    if AUTO_RESULTS:
        schedule.every().day.at(RESULTS_TIME, tz).do(
            lambda: asyncio.get_event_loop().create_task(run_results_check())
        )
        logger.info(f"Scheduled: results at {RESULTS_TIME} {tz or '(container clock)'}")
    else:
        logger.info("Auto-results DISABLED.")


async def run_scheduler():
    """Schedule loop."""
    while True:
        schedule.run_pending()
        await asyncio.sleep(30)


def _split_message(text: str, max_len: int) -> list[str]:
    """Split long message at newline boundaries."""
    chunks = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, max_len)
        if split_at == -1:
            split_at = max_len
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks


async def main():
    """Main entry point."""
    setup_logging()
    logger.info("🏇 Horse Racing Bot starting (cherry-pick mode)...")

    lock_path = Path("/app/data/bot.lock") if os.path.exists("/app") else Path("data/bot.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.touch()

    init_db()
    app = create_app()
    schedule_jobs()

    logger.info("Bot ready. Telegram polling + scheduler running.")

    async with app:
        await app.start()
        await app.updater.start_polling()

        api_status = "with Claude judgement" if ANTHROPIC_API_KEY else "programmatic only"
        await send_message(
            f"🏇 Horse Racing Bot started ({api_status}).\n"
            "Cherry-pick mode: best 6 across all UK/Irish cards.\n"
            "Use /help for commands."
        )

        try:
            await run_scheduler()
        except asyncio.CancelledError:
            pass
        finally:
            await app.updater.stop()
            await app.stop()
            lock_path.unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
