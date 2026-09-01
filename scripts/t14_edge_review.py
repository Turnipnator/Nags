"""Paper-trade review: T14 min-runs guard + edge-block removals (due 13 Aug 2026).

Re-scores every cached racecard (data/harvest/<date>_cards.json.gz) through the
LIVE scorer with the review flags toggled, joins to cached results on
(race_id, horse_id), and counts the pre-registered triggers:

  T14 guard  -> "3+ suppressed horses WIN where they would otherwise have been
                selections" => lower T14_MIN_RUNS to 3 before reverting.
  Speed dom. -> "3+ races where the horse that lost SPEED DOMINANCE points WINS
                and our replacement top scorer LOSES" => re-enable the bonus.

"Would otherwise have been a selection" is operationalised as: the horse is the
top BETABLE (above-evens) scorer in a gate-passing race (class floor, betable
>= 70, not dominant-fav-blocked) with the flag OFF, and is NOT the top scorer
(or the race no longer passes) with the flag ON. That is the deterministic
proxy for the LLM's pick.

Caveats, stated up front: no Rule 18b enrichment (identical in both arms, so
flag deltas are exact; absolute top-scorer identity can differ from the live
run where 18b fired), no Sporting Life, no LLM. Deterministic layer only.

Usage:
  .venv/bin/python scripts/t14_edge_review.py --from 2026-08-06 --to 2026-08-31 \
      [--run-dates 2026-08-12,2026-08-19,...]
"""
import argparse
import glob
import gzip
import json
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("RACING_API_USERNAME", "x")
os.environ.setdefault("RACING_API_PASSWORD", "x")

import src.scorer as SC  # noqa: E402
import src.analyst as A  # noqa: E402
from src.scraper import Scraper  # noqa: E402

HARVEST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "data", "harvest")

ARMS = {
    # name: (T14 guard, speed-dominance, unknown-headgear, OR-above-field)
    "LIVE":    (True,  False, False, False),   # as deployed since 6 Aug
    "T14OFF":  (False, False, False, False),   # guard off (pre-6-Aug T14)
    "SDON":    (True,  True,  False, False),   # speed-dominance bonus back on
    "EDGEOLD": (True,  True,  True,  True),    # all three removed bonuses back
}


def _set_flags(t14, sd, hg, orf):
    SC.T14_MIN_RUNS_ENABLED = t14
    SC.SPEED_DOMINANCE_BONUS_ENABLED = sd
    SC.UNKNOWN_HEADGEAR_BONUS_ENABLED = hg
    SC.OR_ABOVE_FIELD_INTENT_SIGNAL = orf


def _load_day(ds):
    cf = os.path.join(HARVEST, f"{ds}_cards.json.gz")
    if not os.path.exists(cf):
        return None, {}
    cards = json.load(gzip.open(cf))
    res = {}
    for rf in sorted(glob.glob(os.path.join(HARVEST, f"{ds}_res_*.json.gz"))):
        for race in json.load(gzip.open(rf)).get("results", []):
            pos = {}
            for rn in race.get("runners", []):
                p = str(rn.get("position", "")).strip()
                pos[rn.get("horse_id")] = int(p) if p.isdigit() else None
            res[race.get("race_id")] = {"pos": pos, "sp": {rn.get("horse_id"): rn.get("sp")
                                                          for rn in race.get("runners", [])}}
    return cards, res


def _meetings_from_cards(ds, cards):
    sc = Scraper()
    sc._api_get = lambda endpoint, max_attempts=3: (
        cards if endpoint.startswith("/racecards/pro") else None)
    y, m, d = (int(x) for x in ds.split("-"))
    return sc.fetch_all_uk_irish_races(date(y, m, d))


def _arm_view(scored):
    """(top_runner_score, top_total, passes_gates) for one arm."""
    best, best_total = None, 0.0
    for sr in scored:
        dec = A._parse_odds_to_decimal(getattr(sr.runner, "odds", "") or "")
        if dec > 1.0 and sr.total > best_total:
            best, best_total = sr, sr.total
    if best is None:
        return None, 0.0, False
    blocked, _ = A._blocked_favourite_dominates(scored)
    return best, best_total, (best_total >= 70.0 and not blocked)


def _pos_str(p):
    return "WON" if p == 1 else (f"{p}" if p else "nr/np")


def review(d_from, d_to, run_dates):
    days = []
    d = d_from
    while d <= d_to:
        days.append(d.isoformat())
        d += timedelta(days=1)

    stats = {"days": 0, "races_floor": 0, "races_pass_any": 0,
             "t14_moved_horses": 0, "sd_moved_horses": 0, "edge_moved_horses": 0}
    t14_cases, sd_cases, edge_cases = [], [], []

    for ds in days:
        cards, res = _load_day(ds)
        if cards is None:
            continue
        stats["days"] += 1
        meetings = _meetings_from_cards(ds, cards)
        for mt in meetings:
            for race in mt.races:
                if not A._meets_class_floor(race):
                    continue
                stats["races_floor"] += 1
                views, totals = {}, {}
                for arm, flags in ARMS.items():
                    _set_flags(*flags)
                    scored = SC.Scorer().score_race(race)
                    views[arm] = _arm_view(scored)
                    totals[arm] = {sr.runner.horse_id: sr.total for sr in scored}
                _set_flags(*ARMS["LIVE"])
                if not any(v[2] for v in views.values()):
                    continue
                stats["races_pass_any"] += 1
                rr = res.get(race.race_id, {"pos": {}, "sp": {}})
                live_top, live_total, live_pass = views["LIVE"]

                # movement counts (any horse whose total differs from LIVE)
                for arm, key in (("T14OFF", "t14_moved_horses"), ("SDON", "sd_moved_horses"),
                                 ("EDGEOLD", "edge_moved_horses")):
                    stats[key] += sum(1 for h, t in totals[arm].items()
                                      if abs(t - totals["LIVE"].get(h, t)) > 1e-9)

                def _case(arm, bucket):
                    top, total, passes = views[arm]
                    if not passes:
                        return
                    if live_pass and live_top.runner.horse_id == top.runner.horse_id:
                        return
                    h = top.runner
                    case = {
                        "date": ds, "course": mt.course, "time": race.time,
                        "cls": f"{race.pattern or ''} {race.race_class or ''}".strip(),
                        "horse": h.name, "odds": h.odds,
                        "arm_score": round(total, 1),
                        "live_score": round(totals["LIVE"].get(h.horse_id, 0.0), 1),
                        "pos": rr["pos"].get(h.horse_id),
                        "live_top": live_top.runner.name if (live_pass and live_top) else "(race skipped)",
                        "live_top_pos": rr["pos"].get(live_top.runner.horse_id) if (live_pass and live_top) else None,
                        "live_top_odds": live_top.runner.odds if (live_pass and live_top) else "",
                        "run_day": ds in run_dates,
                    }
                    bucket.append(case)

                _case("T14OFF", t14_cases)
                _case("SDON", sd_cases)
                _case("EDGEOLD", edge_cases)
    return stats, t14_cases, sd_cases, edge_cases


def _report(title, cases, trigger_desc):
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")
    if not cases:
        print("  (no race where the flag changed the top betable scorer in a gate-passing race)")
        return
    hdr = f"  {'date':10} {'course':12} {'time':5} {'class':12} {'horse':22} {'odds':6} {'flagOFF':7} {'live':6} {'result':7} | {'live top':22} {'res':6} run?"
    print(hdr)
    for c in cases:
        print(f"  {c['date']:10} {c['course'][:12]:12} {c['time']:5} {c['cls'][:12]:12} "
              f"{c['horse'][:22]:22} {str(c['odds'])[:6]:6} {c['arm_score']:7} {c['live_score']:6} "
              f"{_pos_str(c['pos']):7} | {c['live_top'][:22]:22} {_pos_str(c['live_top_pos']):6} "
              f"{'Y' if c['run_day'] else ''}")
    wins = [c for c in cases if c["pos"] == 1]
    trig = [c for c in wins if c["live_top"] != "(race skipped)" and c["live_top_pos"] != 1]
    skipped_wins = [c for c in wins if c["live_top"] == "(race skipped)"]
    helped = [c for c in cases if c["pos"] != 1 and c["live_top_pos"] == 1]
    print(f"\n  cases: {len(cases)} | flag-OFF horse WON: {len(wins)} "
          f"(of which live replacement LOST: {len(trig)}, race skipped live: {len(skipped_wins)}) "
          f"| guard HELPED (flag-OFF horse lost, live top WON): {len(helped)}")
    print(f"  {trigger_desc}")
    rd = [c for c in cases if c["run_day"]]
    print(f"  on real bot run days: cases {len(rd)}, flag-OFF horse won {sum(1 for c in rd if c['pos']==1)}, "
          f"guard helped {sum(1 for c in rd if c['pos']!=1 and c['live_top_pos']==1)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="d_from", default="2026-08-06")
    ap.add_argument("--to", dest="d_to", default="2026-08-31")
    ap.add_argument("--run-dates", default="")
    a = ap.parse_args()
    run_dates = {s.strip() for s in a.run_dates.split(",") if s.strip()}
    d_from = date.fromisoformat(a.d_from); d_to = date.fromisoformat(a.d_to)
    stats, t14, sd, edge = review(d_from, d_to, run_dates)
    print(f"window {a.d_from}..{a.d_to}: {stats['days']} days cached, "
          f"{stats['races_floor']} races above the class floor, "
          f"{stats['races_pass_any']} pass the 70/dom-fav gates in at least one arm")
    print(f"horses whose score moves: T14 guard {stats['t14_moved_horses']}, "
          f"speed-dominance {stats['sd_moved_horses']}, all-three-edge {stats['edge_moved_horses']}")
    _report("T14 MIN-RUNS GUARD — races where the guard changed the top betable scorer", t14,
            "TRIGGER: 3+ flag-OFF (suppressed) horses WIN where they'd have been the selection => lower T14_MIN_RUNS to 3")
    _report("SPEED DOMINANCE — races where restoring the bonus changes the top betable scorer", sd,
            "TRIGGER: 3+ races where the bonus horse WINS and the live replacement LOSES => SPEED_DOMINANCE_BONUS_ENABLED=true")
    _report("ALL THREE REMOVED EDGE BONUSES — context only", edge, "(no pre-registered trigger)")


if __name__ == "__main__":
    main()
