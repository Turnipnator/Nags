"""Regression tests for the BOG auto-settler contract (main.py run_results_check).

The settler routes every pick through database.settle_and_save(bog=True). These
tests lock the three behaviours that were wrong before 27 Jul 2026:

  1. BOG  -- a winner is paid the BETTER of morning `odds_guide` and SP, not SP.
  2. PU   -- a pulled-up / fell / unseated horse (non-digit position) must settle
            LOST. It is passed to settle() as 999, NOT 0. finish_position 0 is
            <= n_places, so settle() would mis-book a PU as PLACED and pay the
            place leg (the exact bug this suite guards).
  3. NR   -- a non-runner (finish_position None) is VOID: full stake returned,
            pnl 0. Detected from the results `non_runners` field.

Run: PYTHONPATH=. .venv/bin/python tests/test_settler_bog.py
"""
import sqlite3
from src import database as db


def _fresh_db():
    db._conn = sqlite3.connect(":memory:")
    db._conn.row_factory = sqlite3.Row
    db._conn.executescript(
        """
        CREATE TABLE selections (id INTEGER PRIMARY KEY, meeting_id INT, race_time TEXT,
          race_name TEXT, horse TEXT, selection_type TEXT, odds_guide TEXT,
          each_way BOOLEAN, stake_pts REAL, reasoning TEXT, confidence TEXT,
          danger TEXT, score REAL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE results (id INTEGER PRIMARY KEY, selection_id INT, finish_position INT,
          result TEXT, sp_odds TEXT, returns_pts REAL DEFAULT 0, pnl_pts REAL DEFAULT 0,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        """
    )


def _add(sid, horse, stype, morning, ew, stake):
    db._conn.execute(
        "INSERT INTO selections (id,race_time,horse,selection_type,odds_guide,each_way,stake_pts)"
        " VALUES (?,?,?,?,?,?,?)",
        (sid, "17:30", horse, stype, morning, 1 if ew else 0, stake),
    )
    db._conn.commit()


PASS = FAIL = 0


def check(label, got, want):
    global PASS, FAIL
    ok = abs(got - want) < 1e-6 if isinstance(want, float) else got == want
    print(f"  {'PASS' if ok else 'FAIL'}  {label}: got {got!r} want {want!r}")
    PASS += ok
    FAIL += not ok


print("1. BOG -- winner paid better of morning 11/8 and SP evens")
_fresh_db()
_add(1, "The Good Biscuit", "race_nb", "11/8", False, 0.5)   # win-only 0.5pt
s = db.settle_and_save(1, 1, "1/1F", 4, is_handicap=True, bog=True)
check("result", s["result"], "won")
check("pnl at BOG 11/8 not SP evens", s["pnl_pts"], 0.6875)   # 0.5*(11/8)
check("price_used = 11/8 multiplier", s["price_used"], 1.375)

print("2. PU sentinel 999 -> LOST, place leg NOT paid (the trap)")
_fresh_db()
_add(2, "Sunray Shadow", "selection", "9/4", True, 2.0)       # 1pt E/W = 2.0 outlay
s = db.settle_and_save(2, 999, "9/4F", 7, is_handicap=True, bog=True)
check("result", s["result"], "lost")
check("pnl = full stake lost", s["pnl_pts"], -2.0)
# and prove the trap: finish_position 0 would WRONGLY place in a 7-runner E/W
trap = db.settle(2.0, True, 0, "9/4F", 7, is_handicap=True)
check("finish 0 mis-books as placed (why we use 999)", trap["result"], "placed")

print("3. NON-RUNNER (None) -> VOID, stake returned, pnl 0")
_fresh_db()
_add(3, "Trilby", "selection", "3/1", True, 2.0)
s = db.settle_and_save(3, None, "", 4, is_handicap=True, bog=True)
check("result", s["result"], "nr")
check("pnl 0", s["pnl_pts"], 0.0)
check("returns = stake back", s["returns_pts"], 2.0)

print("4. Genuine placed E/W (2nd of 9 handicap) still pays")
_fresh_db()
_add(4, "Placer", "selection", "5/1", True, 2.0)
s = db.settle_and_save(4, 2, "5/1", 9, is_handicap=True, bog=True)
check("result", s["result"], "placed")   # place_terms(9,H)=(3,0.20); 2<=3

print("5. Loser out of the places (6th of 9) -> lost")
_fresh_db()
_add(5, "Karnaval Point", "next_best", "5/1", True, 2.0)
s = db.settle_and_save(5, 6, "11/2", 9, is_handicap=True, bog=True)
check("result", s["result"], "lost")
check("pnl", s["pnl_pts"], -2.0)

print(f"\nRESULT: {PASS}/{PASS + FAIL} passed")
raise SystemExit(1 if FAIL else 0)
