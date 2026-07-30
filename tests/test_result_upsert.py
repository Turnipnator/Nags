"""Re-settling a selection must CORRECT its result, never add a second row.

29 Jul 2026: a crashed manual settle script settled Pershaada, then a rerun
settled all 8 picks again -- two result rows for one selection, and the day's
P&L read +23.2pts instead of the true +16.0. The nightly settler guards with
`id NOT IN (SELECT selection_id FROM results)`, but the DB let it happen.

  python3 tests/test_result_upsert.py
"""
import os, tempfile, sys

os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")
import src.database as D
D.DB_PATH = os.environ["DB_PATH"]
D.init_db()

PASS = FAIL = 0
def check(label, got, want):
    global PASS, FAIL
    ok = got == want
    print(f"  {'PASS' if ok else 'FAIL'}  {label}: got {got!r} want {want!r}")
    PASS += ok; FAIL += not ok

mid = D.save_meeting("Goodwood", __import__("datetime").date(2026, 7, 29), "Good To Firm")
D._conn.execute(
    "INSERT INTO selections (meeting_id,race_time,race_name,horse,selection_type,odds_guide,each_way,stake_pts,score)"
    " VALUES (?,?,?,?,?,?,?,?,?)", (mid, "15:35", "Molecomb", "Pershaada", "nap", "3/1", 1, 4.0, 88.0))
D._conn.commit()
sid = D._conn.execute("SELECT id FROM selections WHERE horse='Pershaada'").fetchone()["id"]

def rows():
    return D._conn.execute("SELECT * FROM results WHERE selection_id=?", (sid,)).fetchall()

print("first settle")
D.settle_and_save(sid, 1, "11/4", 11, is_handicap=False, bog=True)
check("one result row", len(rows()), 1)
check("pnl +7.2pts (BOG 3/1, 4pt E/W)", round(rows()[0]["pnl_pts"], 3), 7.2)

print("re-settle the SAME selection (the 29 Jul double-count scenario)")
D.settle_and_save(sid, 1, "11/4", 11, is_handicap=False, bog=True)
check("STILL one result row (no duplicate)", len(rows()), 1)
check("pnl unchanged, not doubled", round(rows()[0]["pnl_pts"], 3), 7.2)

print("re-settle with a CORRECTED finish (amended result / disqualification)")
D.settle_and_save(sid, 4, "11/4", 11, is_handicap=False, bog=True)
check("one row", len(rows()), 1)
check("row was corrected to the new finish", rows()[0]["finish_position"], 4)
check("4th of 11 E/W = lost", rows()[0]["result"], "lost")
check("pnl now the loss", round(rows()[0]["pnl_pts"], 3), -4.0)

print("day total sums each selection once")
tot = D._conn.execute(
    "SELECT ROUND(SUM(r.pnl_pts),3) t FROM selections s JOIN results r ON r.selection_id=s.id"
).fetchone()["t"]
check("no double-count in the join", tot, -4.0)

print(f"\nRESULT: {PASS}/{PASS + FAIL} passed")
sys.exit(1 if FAIL else 0)
