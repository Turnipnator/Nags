"""A/B: SCORER_RECAL_ENABLED (30 Jun 2026 Bug-3 form weighting + ability anchor).

Re-scores every cached gate-passing race in the window with the flag ON (live)
and OFF (pre-30-Jun scorer), takes the top BETABLE scorer in each arm as the
deterministic proxy for the pick, joins results on (race_id, horse_id), and
prices both as 1pt win bets at SP. Deterministic layer only, no enrichment.

Usage: .venv/bin/python scripts/recal_ab.py --from 2026-07-01 --to 2026-09-10
"""
import argparse
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scripts.t14_edge_review as R  # noqa: E402
import src.scorer as SC  # noqa: E402
import src.analyst as A  # noqa: E402


def frac_to_dec(sp):
    """'9/2' -> 5.5, '11/4F' -> 3.75, 'Evens' -> 2.0; None if unparseable."""
    if not sp:
        return None
    t = str(sp).strip().upper().rstrip("FJC").strip()
    if t in ("EVENS", "EVS", "EVEN"):
        return 2.0
    try:
        a, b = t.split("/")
        return float(a) / float(b) + 1.0
    except (ValueError, ZeroDivisionError):
        return None


def top_betable(scored):
    best, bt = None, 0.0
    for sr in scored:
        dec = A._parse_odds_to_decimal(getattr(sr.runner, "odds", "") or "")
        if dec > 1.0 and sr.total > bt:
            best, bt = sr, sr.total
    if best is None:
        return None, 0.0, False
    blocked, _ = A._blocked_favourite_dominates(scored)
    return best, bt, (bt >= 70.0 and not blocked)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="d_from", default="2026-07-01")
    ap.add_argument("--to", dest="d_to", default="2026-09-10")
    a = ap.parse_args()
    d, end = date.fromisoformat(a.d_from), date.fromisoformat(a.d_to)
    stats = {"ON": [0, 0, 0.0, 0], "OFF": [0, 0, 0.0, 0]}   # races, wins, pnl, sum_sp
    changed = same = 0
    changed_rows = []
    while d <= end:
        ds = d.isoformat(); d += timedelta(days=1)
        cards, res = R._load_day(ds)
        if cards is None:
            continue
        for mt in R._meetings_from_cards(ds, cards):
            for race in mt.races:
                if not A._meets_class_floor(race):
                    continue
                tops = {}
                for arm, flag in (("ON", True), ("OFF", False)):
                    SC.SCORER_RECAL_ENABLED = flag
                    tops[arm] = top_betable(SC.Scorer().score_race(race))
                SC.SCORER_RECAL_ENABLED = True
                rr = res.get(race.race_id, {"pos": {}, "sp": {}})
                for arm in ("ON", "OFF"):
                    top, tot, passes = tops[arm]
                    if not passes:
                        continue
                    pos = rr["pos"].get(top.runner.horse_id)
                    sp = rr["sp"].get(top.runner.horse_id)
                    spd = frac_to_dec(sp)
                    if pos is None or spd is None:
                        continue
                    s = stats[arm]; s[0] += 1; s[3] += spd
                    if pos == 1:
                        s[1] += 1; s[2] += spd - 1.0
                    else:
                        s[2] -= 1.0
                on, off = tops["ON"], tops["OFF"]
                if on[2] and off[2]:
                    if on[0].runner.horse_id == off[0].runner.horse_id:
                        same += 1
                    else:
                        changed += 1
                        changed_rows.append((ds, mt.course, race.time,
                                             on[0].runner.name, rr["pos"].get(on[0].runner.horse_id),
                                             off[0].runner.name, rr["pos"].get(off[0].runner.horse_id)))
    print(f"window {a.d_from}..{a.d_to}")
    for arm in ("ON", "OFF"):
        n, w, pl, ssp = stats[arm]
        print(f"  RECAL {arm:3}: gate-passing races {n:3} | top scorer WON {w:3} ({100*w/max(n,1):.1f}%) | 1pt SP P&L {pl:+7.2f} ({100*pl/max(n,1):+.1f}%) | avg SP {ssp/max(n,1):.2f}")
    print(f"  both arms pass: same top {same}, DIFFERENT top {changed}")
    won_on = sum(1 for r in changed_rows if r[4] == 1); won_off = sum(1 for r in changed_rows if r[6] == 1)
    print(f"  in the {changed} races where the top changes: live-arm top won {won_on}, old-arm top won {won_off}")
    for r in changed_rows[:40]:
        print(f"    {r[0]} {r[1][:12]:12} {r[2]:5} live: {r[3][:20]:20} {str(r[4] or '-'):3} | old: {r[5][:20]:20} {str(r[6] or '-'):3}")


if __name__ == "__main__":
    main()
