"""
SQLite database for selections, results, and P&L tracking.
"""

import json
import logging
import re
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from config.settings import DB_PATH

logger = logging.getLogger(__name__)

_conn: Optional[sqlite3.Connection] = None


def init_db():
    """Initialise database and create tables."""
    global _conn
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    _conn.row_factory = sqlite3.Row
    _conn.execute("PRAGMA journal_mode=WAL")

    _conn.executescript("""
        CREATE TABLE IF NOT EXISTS meetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course TEXT NOT NULL,
            date TEXT NOT NULL,
            going TEXT,
            num_races INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(course, date)
        );

        CREATE TABLE IF NOT EXISTS selections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meeting_id INTEGER REFERENCES meetings(id),
            race_time TEXT NOT NULL,
            race_name TEXT,
            horse TEXT NOT NULL,
            selection_type TEXT NOT NULL,  -- 'nap', 'next_best', 'selection', 'race_nb'
            odds_guide TEXT,
            each_way BOOLEAN DEFAULT FALSE,
            stake_pts REAL,
            reasoning TEXT,
            confidence TEXT,
            danger TEXT,
            score REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            selection_id INTEGER REFERENCES selections(id),
            finish_position INTEGER,
            result TEXT,  -- 'won', 'placed', 'lost', 'nr', 'void'
            sp_odds TEXT,
            returns_pts REAL DEFAULT 0,
            pnl_pts REAL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS bot_state (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS daily_summary (
            date TEXT PRIMARY KEY,
            total_selections INTEGER DEFAULT 0,
            winners INTEGER DEFAULT 0,
            placed INTEGER DEFAULT 0,
            total_stake_pts REAL DEFAULT 0,
            total_returns_pts REAL DEFAULT 0,
            pnl_pts REAL DEFAULT 0,
            nap_result TEXT,
            nb_result TEXT,
            notes TEXT
        );
    """)
    _conn.commit()
    logger.info(f"Database initialised at {DB_PATH}")


def save_meeting(course: str, meeting_date: date, going: str = None,
                 num_races: int = 0) -> int:
    """Save a meeting, return meeting_id."""
    cursor = _conn.execute(
        "INSERT OR REPLACE INTO meetings (course, date, going, num_races) VALUES (?, ?, ?, ?)",
        (course, meeting_date.isoformat(), going, num_races),
    )
    _conn.commit()
    return cursor.lastrowid


def save_selections(meeting_id: int, selections: dict):
    """Save full selections dict from analyst."""
    nap = selections.get("nap", {})
    nb = selections.get("next_best", {})
    race_sels = selections.get("race_selections", [])

    # Save NAP
    if nap:
        _save_selection(meeting_id, nap, "nap", 2.0)

    # Save Next Best
    if nb:
        _save_selection(meeting_id, nb, "next_best", 1.5)

    # Save per-race selections
    for rs in race_sels:
        sel = rs.get("selection", {})
        rnb = rs.get("next_best", {})
        if sel:
            _save_selection(
                meeting_id,
                {**sel, "race_time": rs.get("race_time"), "race_name": rs.get("race_name")},
                "selection", 1.0,
            )
        if rnb:
            _save_selection(
                meeting_id,
                {**rnb, "race_time": rs.get("race_time"), "race_name": rs.get("race_name")},
                "race_nb", 0.5,
            )

    _conn.commit()


def _save_selection(meeting_id: int, sel: dict, sel_type: str, stake: float):
    """Save a single selection."""
    each_way = sel.get("each_way", False)
    _conn.execute(
        """INSERT INTO selections
           (meeting_id, race_time, race_name, horse, selection_type,
            odds_guide, each_way, stake_pts, reasoning, confidence, danger, score)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            meeting_id,
            sel.get("race_time", ""),
            sel.get("race_name", ""),
            sel.get("horse", ""),
            sel_type,
            sel.get("odds_guide", ""),
            each_way,
            stake * (2 if each_way else 1),  # E/W doubles outlay
            json.dumps(sel.get("reasoning", [])),
            sel.get("confidence", ""),
            sel.get("danger", ""),
            sel.get("adjusted_score") or sel.get("score", 0),
        ),
    )


# ---------------------------------------------------------------------------
# SETTLEMENT (added 19 Jul 2026)
# ---------------------------------------------------------------------------
# WHY THIS EXISTS: `save_result` takes returns/pnl PRE-COMPUTED and there was no
# calculator anywhere in the repo, so every row was settled by hand. The history
# is inconsistent as a result -- older *placed* rows split the E/W stake
# correctly (half win / half place), while older *winning* rows were logged as
# `stake_pts * SP`, i.e. as if win-only. That OVERSTATES every winner already in
# the table (e.g. Arapaho Gold, race_nb 0.5pt E/W, won at SP 4/1: logged +4.0,
# actually +2.4). Rows settled through `settle()` are correct; rows predating it
# are not. NEVER sum raw `pnl_pts` across the full table and call it system
# performance -- the headline ROI measurement recomputes from raw picks + API
# results independently, which is why it was unaffected by this.
#
# COLUMN SEMANTICS (fixed here, previously both were set to the net figure):
#   returns_pts = GROSS return -- stake back plus profit. 0.0 on a loser.
#   pnl_pts     = NET profit/loss -- returns_pts minus total outlay.
# Nothing read `returns_pts` before now (it is SELECTed in get_latest_results
# but never rendered), so correcting its meaning breaks no caller.

# stake_pts on a selection row is TOTAL OUTLAY -- `_save_selection` already
# doubles the unit stake for E/W. So an E/W bet splits stake_pts in half:
# half on the win leg, half on the place leg.


def _odds_to_multiplier(odds_str: str) -> float:
    """Fractional odds string -> profit multiplier per unit staked. 0 if unparseable.

    Mirrors `analyst._parse_odds_to_decimal` (kept local so this module stays
    free of analyst's anthropic/scraper/scorer import chain). Same contract:
    returns the FRACTIONAL multiplier, not decimal odds -- 11/1 -> 11.0, not
    12.0. Trailing favourite markers ("13/8F", "3/1J") parse fine.
    """
    if not odds_str or odds_str == "CHECK PRICE":
        return 0.0
    s = odds_str.strip().lower()
    if s.startswith("ev") or s == "e/fav":
        return 1.0
    match = re.match(r"(\d+)/(\d+)", odds_str.strip())
    if match:
        return int(match.group(1)) / int(match.group(2))
    return 0.0


def place_terms(num_runners: int, is_handicap: bool = False) -> tuple:
    """Bookmaker each-way terms -> (number_of_places, fraction_of_odds).

    Per CLAUDE.md "NB-of-day Field-Size Floor". Returns (0, 0.0) when no place
    market exists, which is the case that makes an E/W bet impossible to strike.
    """
    if num_runners < 5:
        return (0, 0.0)              # no place market at all
    if num_runners <= 7:
        return (2, 0.25)             # 2 places, 1/4
    if is_handicap and num_runners >= 12:
        return (4, 0.25)             # 4 places, 1/4 -- best terms we get
    return (3, 0.20)                 # 3 places, 1/5


def settle(stake_pts: float, each_way: bool, finish_position: Optional[int],
           sp_odds: str, num_runners: int, is_handicap: bool = False,
           morning_odds: str = "", bog: bool = True) -> dict:
    """Settle one bet. Returns {result, returns_pts, pnl_pts, price_used, terms}.

    BOG (Best Odds Guaranteed) is ON by default because CLAUDE.md mandates
    taking morning prices with a BOG bookmaker, so we are paid the BETTER of
    morning and SP. That is worth ~9 points of ROI to us and settling at SP
    alone understates the book. Pass bog=False to settle strictly at SP.

    finish_position None -> non-runner: full stake returned, pnl 0.
    """
    sp = _odds_to_multiplier(sp_odds)
    morn = _odds_to_multiplier(morning_odds)
    price = max(sp, morn) if bog else sp
    if price <= 0:
        price = max(sp, morn)  # unparseable SP -- fall back to whatever we have

    if finish_position is None:
        return {"result": "nr", "returns_pts": stake_pts, "pnl_pts": 0.0,
                "price_used": price, "terms": (0, 0.0)}

    n_places, fraction = place_terms(num_runners, is_handicap)

    if each_way:
        win_stake = place_stake = stake_pts / 2.0
    else:
        win_stake, place_stake = stake_pts, 0.0

    returns = 0.0
    if finish_position == 1:
        returns += win_stake * (1.0 + price)

    if place_stake:
        if n_places == 0:
            # An E/W bet cannot be struck in a field this small. Treat the place
            # leg as void (stake returned) rather than silently losing it, and
            # shout -- this means the selection layer produced an unplaceable bet.
            logger.warning(
                "E/W bet in a %d-runner field has no place market -- place leg "
                "settled as VOID. Check the selection's each_way flag.",
                num_runners,
            )
            returns += place_stake
        elif finish_position <= n_places:
            returns += place_stake * (1.0 + price * fraction)

    if finish_position == 1:
        result = "won"
    elif each_way and n_places and finish_position <= n_places:
        result = "placed"
    else:
        result = "lost"

    return {
        "result": result,
        "returns_pts": round(returns, 4),
        "pnl_pts": round(returns - stake_pts, 4),
        "price_used": price,
        "terms": (n_places, fraction),
    }


def settle_and_save(selection_id: int, finish_position: Optional[int],
                    sp_odds: str, num_runners: int, is_handicap: bool = False,
                    bog: bool = True) -> dict:
    """Settle a selection from its stored stake/each_way/odds_guide and save it.

    Reads `odds_guide` off the selection row as the morning price for BOG, so
    the caller only needs the result facts (finish, SP, field size, handicap?).
    """
    row = _conn.execute(
        "SELECT stake_pts, each_way, odds_guide, horse FROM selections WHERE id = ?",
        (selection_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"No selection with id {selection_id}")

    s = settle(
        stake_pts=row["stake_pts"],
        each_way=bool(row["each_way"]),
        finish_position=finish_position,
        sp_odds=sp_odds,
        num_runners=num_runners,
        is_handicap=is_handicap,
        morning_odds=row["odds_guide"] or "",
        bog=bog,
    )
    save_result(selection_id, finish_position, s["result"], sp_odds,
                s["returns_pts"], s["pnl_pts"])
    logger.info(
        "Settled %s (id %s): %s %s at %.2f -> %+.3fpts",
        row["horse"], selection_id, s["result"],
        f"{finish_position}/{num_runners}", s["price_used"], s["pnl_pts"],
    )
    return s


def save_result(selection_id: int, finish_pos: int, result: str,
                sp_odds: str, returns_pts: float, pnl_pts: float):
    """Save a result for a selection."""
    _conn.execute(
        """INSERT INTO results (selection_id, finish_position, result, sp_odds, returns_pts, pnl_pts)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (selection_id, finish_pos, result, sp_odds, returns_pts, pnl_pts),
    )
    _conn.commit()


def get_todays_selections() -> Optional[str]:
    """Get formatted selections for today."""
    today = date.today().isoformat()
    rows = _conn.execute(
        """SELECT s.* FROM selections s
           JOIN meetings m ON s.meeting_id = m.id
           WHERE m.date = ?
           ORDER BY s.race_time, s.selection_type""",
        (today,),
    ).fetchall()

    if not rows:
        return None

    return _format_selections(rows)


def get_todays_nap() -> Optional[str]:
    """Get today's NAP."""
    today = date.today().isoformat()
    row = _conn.execute(
        """SELECT s.* FROM selections s
           JOIN meetings m ON s.meeting_id = m.id
           WHERE m.date = ? AND s.selection_type = 'nap'""",
        (today,),
    ).fetchone()

    if not row:
        return None

    reasoning = json.loads(row["reasoning"]) if row["reasoning"] else []
    text = f"🏆 *NAP: {row['horse']}*\n"
    text += f"📍 {row['race_time']} - {row['race_name']}\n"
    text += f"💰 {row['odds_guide']}\n"
    text += f"📊 Confidence: {row['confidence']}\n"
    for r in reasoning:
        text += f"• {r}\n"
    text += f"⚠️ Danger: {row['danger']}"
    return text


def get_todays_next_best() -> Optional[str]:
    """Get today's Next Best."""
    today = date.today().isoformat()
    row = _conn.execute(
        """SELECT s.* FROM selections s
           JOIN meetings m ON s.meeting_id = m.id
           WHERE m.date = ? AND s.selection_type = 'next_best'""",
        (today,),
    ).fetchone()

    if not row:
        return None

    reasoning = json.loads(row["reasoning"]) if row["reasoning"] else []
    text = f"⭐ *NEXT BEST: {row['horse']}*\n"
    text += f"📍 {row['race_time']} - {row['race_name']}\n"
    text += f"💰 {row['odds_guide']}\n"
    for r in reasoning:
        text += f"• {r}\n"
    return text


def get_latest_results() -> Optional[str]:
    """Get latest results with P&L."""
    rows = _conn.execute(
        """SELECT s.horse, s.race_time, s.selection_type, s.odds_guide, s.stake_pts,
                  r.result, r.sp_odds, r.returns_pts, r.pnl_pts
           FROM results r
           JOIN selections s ON r.selection_id = s.id
           ORDER BY r.created_at DESC LIMIT 20""",
    ).fetchall()

    if not rows:
        return None

    text = "📊 *Latest Results*\n\n"
    total_pnl = 0
    for row in rows:
        emoji = "✅" if row["result"] == "won" else "🔸" if row["result"] == "placed" else "❌"
        text += (
            f"{emoji} {row['horse']} ({row['race_time']}) - "
            f"{row['result'].upper()} | "
            f"P&L: {row['pnl_pts']:+.1f}pts\n"
        )
        total_pnl += row["pnl_pts"]

    text += f"\n*Running P&L: {total_pnl:+.1f}pts*"
    return text


def get_stats() -> str:
    """Get overall stats."""
    row = _conn.execute(
        """SELECT
              COUNT(*) as total_sels,
              SUM(CASE WHEN r.result = 'won' THEN 1 ELSE 0 END) as winners,
              SUM(CASE WHEN r.result = 'placed' THEN 1 ELSE 0 END) as placed,
              SUM(r.pnl_pts) as total_pnl,
              SUM(s.stake_pts) as total_staked
           FROM results r
           JOIN selections s ON r.selection_id = s.id""",
    ).fetchone()

    total = row["total_sels"] or 0
    winners = row["winners"] or 0
    placed = row["placed"] or 0
    pnl = row["total_pnl"] or 0
    staked = row["total_staked"] or 0

    sr = (winners / total * 100) if total > 0 else 0
    roi = (pnl / staked * 100) if staked > 0 else 0

    # NAP record
    nap_row = _conn.execute(
        """SELECT
              COUNT(*) as total,
              SUM(CASE WHEN r.result = 'won' THEN 1 ELSE 0 END) as winners
           FROM results r
           JOIN selections s ON r.selection_id = s.id
           WHERE s.selection_type = 'nap'""",
    ).fetchone()

    nap_total = nap_row["total"] or 0
    nap_wins = nap_row["winners"] or 0
    nap_sr = (nap_wins / nap_total * 100) if nap_total > 0 else 0

    text = "📊 *Overall Stats*\n\n"
    text += f"Total selections: {total}\n"
    text += f"Winners: {winners} ({sr:.0f}% SR)\n"
    text += f"Placed: {placed}\n"
    text += f"Total P&L: {pnl:+.1f}pts\n"
    text += f"ROI: {roi:+.1f}%\n"
    text += f"\n🏆 NAP Record: {nap_wins}/{nap_total} ({nap_sr:.0f}%)\n"
    return text


def get_bot_status() -> str:
    """Get bot operational status."""
    paused = _get_state("paused") == "true"
    last_analysis = _get_state("last_analysis_time") or "Never"
    last_results = _get_state("last_results_time") or "Never"

    status = "PAUSED ⏸" if paused else "RUNNING ▶️"
    text = f"Status: {status}\n"
    text += f"Last analysis: {last_analysis}\n"
    text += f"Last results check: {last_results}\n"
    return text


def set_bot_paused(paused: bool):
    """Set bot paused state."""
    _set_state("paused", "true" if paused else "false")


def is_bot_paused() -> bool:
    """Check if bot is paused."""
    return _get_state("paused") == "true"


def _get_state(key: str) -> Optional[str]:
    """Get a bot state value."""
    row = _conn.execute("SELECT value FROM bot_state WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def _set_state(key: str, value: str):
    """Set a bot state value."""
    _conn.execute(
        "INSERT OR REPLACE INTO bot_state (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
        (key, value),
    )
    _conn.commit()


def _format_selections(rows) -> str:
    """Format selection rows into readable text."""
    text = "📋 *Today's Selections*\n\n"
    current_time = ""
    for row in rows:
        if row["race_time"] != current_time:
            current_time = row["race_time"]
            text += f"\n*{current_time}* {row['race_name'] or ''}\n"

        type_emoji = {
            "nap": "🏆 NAP",
            "next_best": "⭐ NB",
            "selection": "📌 SEL",
            "race_nb": "📎 RNB",
        }
        label = type_emoji.get(row["selection_type"], row["selection_type"])
        ew = " (E/W)" if row["each_way"] else ""
        text += f"  {label}: {row['horse']} {row['odds_guide']}{ew}\n"

    return text
