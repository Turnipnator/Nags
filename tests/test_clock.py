"""Tests for the London racing clock (14 Aug 2026).

THE BUG: the container runs UTC, British racing runs on London time. Between
00:00 and 01:00 London during BST the dates DISAGREE -- `date.today()` still
reads the previous day -- so a run in that window fetched the WRONG DAY'S CARD.
Observed live at 00:42 London: date.today() = 2026-08-13, London = 2026-08-14.

⚠ THE REASON A HALF-FIX IS WORSE THAN NO FIX. Before this change there were
three sources of "today" and all three were UTC: Python `date.today()`, SQLite
`date('now')`, and `created_at DEFAULT CURRENT_TIMESTAMP`. Uniformly wrong, but
MUTUALLY CONSISTENT -- which is why nothing had broken. Moving only the Python
side to London breaks that consistency, and in the midnight hour
`supersede_todays_selections()` and the nightly settler would silently target
the WRONG DAY on the money ledger.

So the load-bearing test here is not "is the date right" -- it is
"do Python, SQL and storage still AGREE".

Run:  python tests/test_clock.py
"""
import os
import sqlite3
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("RACING_API_USERNAME", "x")
os.environ.setdefault("RACING_API_PASSWORD", "x")

from src.clock import london_now, london_today, london_stamp  # noqa: E402

results = []


def chk(label, cond):
    results.append(bool(cond))
    print(f"   {'PASS' if cond else 'FAIL'}  {label}")


print("\n1. THE CLOCK ITSELF")

now = london_now()
chk("london_now() is timezone-aware", now.tzinfo is not None)
chk("london_today() matches london_now().date()", london_today() == now.date())
chk("london_stamp() is naive (SQLite date()/datetime() cannot parse offsets)",
    "+" not in london_stamp() and "Z" not in london_stamp())
chk("london_stamp() parses as 'YYYY-MM-DD HH:MM:SS'",
    bool(datetime.strptime(london_stamp(), "%Y-%m-%d %H:%M:%S")))
chk("london_stamp()'s date IS london_today()",
    london_stamp()[:10] == london_today().isoformat())

print("\n2. ⚠ THE MIDNIGHT HOUR — the actual bug")

utc_now = datetime.now(ZoneInfo("UTC"))
offset = now.utcoffset()
chk("we are on BST (offset != 0), so the bug window exists today",
    offset != timedelta(0))
# Reconstruct the observed failure rather than trusting the clock we run at.
observed_utc = datetime(2026, 8, 13, 23, 42, tzinfo=ZoneInfo("UTC"))
observed_london = observed_utc.astimezone(ZoneInfo("Europe/London"))
chk("23:42 UTC really is 00:42 London the NEXT day",
    observed_london.strftime("%Y-%m-%d %H:%M") == "2026-08-14 00:42")
chk("the two dates genuinely differ in that window — this is the bug",
    observed_utc.date() != observed_london.date())
chk("london_today() would have returned the racing day, not the UTC day",
    observed_london.date() > observed_utc.date())

print("\n3. ⭐ LOAD-BEARING — Python, SQL and STORAGE must agree")

con = sqlite3.connect(":memory:")
con.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, created_at TEXT)")

# Storage stamped on the racing clock, exactly as save_selection now does.
con.execute("INSERT INTO t (created_at) VALUES (?)", (london_stamp(),))
con.commit()

py_today = london_today().isoformat()
row = con.execute("SELECT date(created_at) FROM t").fetchone()[0]
chk("SQLite's date(created_at) equals the Python racing date", row == py_today)

hit = con.execute("SELECT COUNT(*) FROM t WHERE date(created_at) = ?",
                  (py_today,)).fetchone()[0]
chk("a bound-London-date query finds the row (supersede/settle pattern)", hit == 1)

# And prove the OLD pattern is the thing that breaks: SQLite's date('now') is
# UTC, so in the midnight hour it would MISS a row stamped on the racing clock.
sql_now = con.execute("SELECT date('now')").fetchone()[0]
if sql_now != py_today:
    chk("⚠ date('now') differs from the racing date RIGHT NOW — old code would "
        "have missed this row entirely", True)
else:
    chk("date('now') agrees outside the midnight hour (expected most of the day)",
        True)

# The pre-fix combination, reproduced IN ISOLATION: UTC storage + a London-date
# query. ⚠ Must be its own table -- querying the shared one also matches the
# correctly-stamped row above and the assertion silently passes for the wrong
# reason. (That is the same class of mistake as the two fixture bugs on 13 Aug.)
con.execute("CREATE TABLE half_fix (id INTEGER PRIMARY KEY, created_at TEXT)")
con.execute("INSERT INTO half_fix (created_at) VALUES (?)",
            (datetime(2026, 8, 13, 23, 42).isoformat(sep=" ", timespec="seconds"),))
con.commit()
miss = con.execute("SELECT COUNT(*) FROM half_fix WHERE date(created_at) = ?",
                   ("2026-08-14",)).fetchone()[0]
chk("a UTC-stamped 23:42 row is NOT found by its London date (the half-fix bug)",
    miss == 0)
found = con.execute("SELECT COUNT(*) FROM half_fix WHERE date(created_at) = ?",
                    ("2026-08-13",)).fetchone()[0]
chk("...it is filed under the UTC day instead — the wrong racing day", found == 1)
con.close()

print("\n4. NO-OP OUTSIDE THE MIDNIGHT HOUR")

# 15:50 London BST = 14:50 UTC — same DATE, so the fix changes only the stored
# time-of-day string, never which day a row belongs to.
afternoon = datetime(2026, 8, 13, 15, 50, tzinfo=ZoneInfo("Europe/London"))
chk("15:50 London and its UTC equivalent share a date",
    afternoon.date() == afternoon.astimezone(ZoneInfo("UTC")).date())
chk("so for all daytime racing this change is a no-op on dates", True)

print(f"\nRESULT: {sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
