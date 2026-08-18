#!/usr/bin/env python3
"""MARKET-SWAP GAP RE-RUN — should the swap gap be widened past 5 points?

The market swap (CLAUDE.md factor 22, branch (a)) fires when a race NB is
shorter-priced than our SEL AND the two scores are within 5 points. Paul asked
on 28 Jul 2026 whether that 5 should be wider. It could not be measured then:
`_save_cherry_picks` hard-coded the race_nb `score` to 0, so every historical
gap read as SEL_score - 0. Fixed 28 Jul (`2052586`); this re-run was scheduled
for on/after 18 Aug to let real race_nb scores accrue.

⚠ THIS SCRIPT LIVES IN THE REPO ON PURPOSE. The 28 Jul version was written to a
session scratchpad and was gone by the time the re-run came due, so the method
had to be reconstructed from a memory note. Analysis scripts that carry a
scheduled re-run are code, not scratch.

THE EXPERIMENT. The swap has already fired in the logged data, so pairs with
gap <= 5 and the NB shorter are POST-swap and tell us nothing about widening.
The clean cases are pairs where the NB was shorter but the gap EXCEEDED 5 --
the swap declined to fire. For those, back-test both legs: if the NB (the
shorter-priced horse the gate passed over) beats our SEL there, widening has a
case. If not, keep 5.

Returns are per point of total outlay (`pnl_pts / stake_pts`), which normalises
E/W (where stake_pts is already doubled) and the 17 Aug stake-ladder change.

Usage:  python scripts/swap_gap.py [path/to/racing.db]
"""
import sqlite3
import sys
from collections import defaultdict

DB = sys.argv[1] if len(sys.argv) > 1 else "data/racing.db"

TOP_LEVEL = ("nap", "next_best", "selection")


def parse_odds(s):
    """Fractional multiplier, matching analyst._parse_odds_to_decimal.
    11/1 -> 11.0, 5/2 -> 2.5, evens -> 1.0. 0.0 when unparseable."""
    if not s:
        return 0.0
    t = str(s).strip().lower().replace("evs", "evens")
    if "evens" in t or t == "1/1":
        return 1.0
    t = t.split()[0] if " " in t else t
    try:
        if "/" in t:
            a, b = t.split("/", 1)
            return float(a) / float(b)
        return float(t)
    except (ValueError, ZeroDivisionError):
        return 0.0


def main():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = con.execute("""
        SELECT s.id, date(s.created_at) d, s.race_time, s.race_name, s.horse,
               s.selection_type, s.odds_guide, s.score, s.stake_pts,
               r.result, r.pnl_pts
        FROM selections s
        JOIN results r ON r.selection_id = s.id
        WHERE s.superseded_at IS NULL
          AND (s.source IS NULL OR s.source = 'bot')
          AND r.result NOT IN ('nr', 'void')
          AND s.race_name NOT LIKE '%Position Payout%'
          AND s.stake_pts > 0
    """).fetchall()

    races = defaultdict(dict)
    for r in rows:
        key = (r["d"], r["race_time"], r["race_name"])
        slot = "nb" if r["selection_type"] == "race_nb" else (
            "sel" if r["selection_type"] in TOP_LEVEL else None)
        if slot:
            races[key][slot] = r

    pairs = []
    for key, v in races.items():
        if "sel" not in v or "nb" not in v:
            continue
        sel, nb = v["sel"], v["nb"]
        if not (sel["score"] and nb["score"]):      # need BOTH scores
            continue
        so, no = parse_odds(sel["odds_guide"]), parse_odds(nb["odds_guide"])
        if so <= 0 or no <= 0:
            continue
        pairs.append({
            "key": key, "gap": abs(sel["score"] - nb["score"]),
            "nb_shorter": no < so,
            "sel_ret": sel["pnl_pts"] / sel["stake_pts"],
            "nb_ret": nb["pnl_pts"] / nb["stake_pts"],
            "sel_won": sel["result"] == "won", "nb_won": nb["result"] == "won",
            "sel": sel, "nb": nb, "so": so, "no": no,
        })

    print(f"DB: {DB}")
    print(f"settled rows: {len(rows)} | races with a scored SEL+NB pair: {len(pairs)}")
    if not pairs:
        print("\nNOT ENOUGH DATA. Need settled races carrying BOTH a top-level "
              "selection and a race_nb, each with score > 0.")
        return

    dates = sorted(p["key"][0] for p in pairs)
    print(f"window: {dates[0]} .. {dates[-1]}")

    def summarise(label, ps):
        if not ps:
            print(f"  {label:<34} n=0")
            return
        n = len(ps)
        sr, nr = sum(p["sel_ret"] for p in ps), sum(p["nb_ret"] for p in ps)
        print(f"  {label:<34} n={n:<4} "
              f"SEL {sr:+7.2f}pt ({sr/n*100:+7.1f}%, {sum(p['sel_won'] for p in ps)}W)   "
              f"NB {nr:+7.2f}pt ({nr/n*100:+7.1f}%, {sum(p['nb_won'] for p in ps)}W)   "
              f"delta {(nr-sr)/n*100:+7.1f}%")

    print("\n=== ALL PAIRS ===")
    summarise("all", pairs)

    print("\n=== THE EXPERIMENT: NB SHORTER-PRICED (the swap condition) ===")
    short = [p for p in pairs if p["nb_shorter"]]
    summarise("NB shorter, ANY gap", short)
    summarise("  gap <= 5  (swap ALREADY fired)",
              [p for p in short if p["gap"] <= 5])
    print("  --- the widening question is decided below this line ---")
    for lo, hi in ((5, 10), (10, 15), (15, 999)):
        summarise(f"  gap {lo}-{hi if hi < 999 else '+'} (swap DECLINED)",
                  [p for p in short if lo < p["gap"] <= hi])
    summarise("  gap > 5 (all declined swaps)",
              [p for p in short if p["gap"] > 5])

    print("\n=== CONTROL: NB LONGER-PRICED (swap can never fire) ===")
    summarise("NB longer, any gap", [p for p in pairs if not p["nb_shorter"]])

    dec = [p for p in short if p["gap"] > 5]
    if dec:
        print(f"\n=== THE {len(dec)} DECLINED SWAPS, BET BY BET ===")
        print(f"  {'date':<11}{'race':<34}{'SEL':<22}{'NB':<22}{'gap':>5}"
              f"{'SELret':>8}{'NBret':>8}")
        for p in sorted(dec, key=lambda x: x["key"][0]):
            s, n = p["sel"], p["nb"]
            print(f"  {p['key'][0]:<11}"
                  f"{(p['key'][2] or '')[:32]:<34}"
                  f"{s['horse'][:14]:<15}{s['odds_guide'][:6]:<7}"
                  f"{n['horse'][:14]:<15}{n['odds_guide'][:6]:<7}"
                  f"{p['gap']:>5.0f}{p['sel_ret']:>+8.2f}{p['nb_ret']:>+8.2f}")

    print("\nDECISION RULE: widen only if the declined-swap band shows the NB "
          "beating the SEL by a wide margin on a decent n. A thin or negative "
          "delta means keep the gap at 5.")


if __name__ == "__main__":
    main()
