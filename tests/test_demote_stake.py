"""_save_cherry_picks must honour the compliance demote flag (28 Jul 2026).

Every demote check (NB field-size floor, price cap, NB score floor, F2/F3,
going gate) sets `nb_price_capped` meaning "0.75pt race SEL stake". Before this
fix the stake was derived from selection_type alone, so a demoted NB persisted
at its full 1.5pt E/W and lost double the intended stake (Pearl Eye, £30 vs £15).

Run: PYTHONPATH=. .venv/bin/python tests/test_demote_stake.py
"""
import sqlite3
from datetime import date

import src.database as db
import main


def _fresh_db():
    db._conn = sqlite3.connect(":memory:")
    db._conn.row_factory = sqlite3.Row
    db._conn.executescript(
        """CREATE TABLE selections (id INTEGER PRIMARY KEY, meeting_id INT, race_time TEXT,
             race_name TEXT, horse TEXT, selection_type TEXT, odds_guide TEXT, each_way BOOLEAN,
             stake_pts REAL, reasoning TEXT, confidence TEXT, danger TEXT, score REAL,
             created_at TEXT DEFAULT CURRENT_TIMESTAMP);"""
    )


def _mk(rank, horse, ew=True, capped=False):
    return {
        "rank": rank, "horse": horse, "race_time": "16:15", "course": "Ayr",
        "race_name": "Handicap", "odds_guide": "5/2", "each_way": ew,
        "adjusted_score": 82, "reasoning": [], "confidence": "", "danger": "",
        "next_best": {}, "nb_price_capped": capped,
    }


def stake_of(horse):
    return db._conn.execute(
        "SELECT stake_pts, each_way FROM selections WHERE horse = ?", (horse,)
    ).fetchone()


PASS = FAIL = 0
def check(label, got, want):
    global PASS, FAIL
    ok = abs(got - want) < 1e-9
    print(f"  {'PASS' if ok else 'FAIL'}  {label}: got {got} want {want}")
    PASS += ok; FAIL += not ok


# NAP present at rank 1; rank-2 pick is the NB-of-day. Demote the NB.
print("1. demoted NB (Pearl Eye case) -> 0.75pt race SEL, E/W => 1.5 outlay")
_fresh_db()
main._save_cherry_picks(date(2026, 7, 28), {
    "selections": [_mk(1, "TheNap", ew=True, capped=False),
                   _mk(2, "PearlEye", ew=True, capped=True)],
    "nap_index": 0,
})
check("PearlEye stake_pts (0.75 E/W)", stake_of("PearlEye")["stake_pts"], 1.5)
check("TheNap stake_pts (2.0 E/W)", stake_of("TheNap")["stake_pts"], 4.0)

print("2. no-regression: undemoted NB keeps full 1.5pt E/W => 3.0 outlay")
_fresh_db()
main._save_cherry_picks(date(2026, 7, 28), {
    "selections": [_mk(1, "TheNap2", ew=True, capped=False),
                   _mk(2, "RealNB", ew=True, capped=False)],
    "nap_index": 0,
})
check("RealNB stake_pts (1.5 E/W)", stake_of("RealNB")["stake_pts"], 3.0)

print("3. demoted win-only pick -> 0.75 win => 0.75 outlay")
_fresh_db()
main._save_cherry_picks(date(2026, 7, 28), {
    "selections": [_mk(1, "TheNap3", ew=True, capped=False),
                   _mk(2, "WinOnlyCap", ew=False, capped=True)],
    "nap_index": 0,
})
check("WinOnlyCap stake_pts (0.75 win)", stake_of("WinOnlyCap")["stake_pts"], 0.75)

print(f"\nRESULT: {PASS}/{PASS + FAIL} passed")
raise SystemExit(1 if FAIL else 0)
