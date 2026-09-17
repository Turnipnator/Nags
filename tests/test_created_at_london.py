"""Bot selections stamp created_at on the LONDON racing clock (17 Sep 2026).

WHY: the 14 Aug 2026 clock fix moved Python "today" and the SQL date bindings to
London, and stamped created_at in London time -- but only in the legacy
database._save_selection path. The LIVE path, main._save_cherry_picks, never
passed created_at, so every bot pick took SQLite's CURRENT_TIMESTAMP (UTC).

Outside 00:00-01:00 London the dates agree and nothing breaks. Inside that hour
(BST) a /run is stamped with the PREVIOUS UTC date, so:
  - the settler (bound to the London date) never settles those picks,
  - a later same-day /run cannot supersede them (two live cards, the 1 Aug bug),
  - the Betfair bot (UTC date('now')) stops seeing them at 01:00 London.
No live row has hit this yet (0 bot rows ever saved 23:00-01:00 UTC).

The clock is PINNED, never read from the wall (14 Aug method note).

Run:  PYTHONPATH=. .venv/bin/python tests/test_created_at_london.py
"""
import os
import sys
from datetime import date, datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("RACING_API_USERNAME", "x")
os.environ.setdefault("RACING_API_PASSWORD", "x")

import src.database as db  # noqa: E402
import main  # noqa: E402

results = []


def chk(label, cond):
    results.append(bool(cond))
    print(f"   {'PASS' if cond else 'FAIL'}  {label}")


def pin(stamp):
    """Pin the racing clock for main and database to a naive London stamp."""
    d = date.fromisoformat(stamp[:10])
    main.london_stamp = lambda: stamp
    db.london_stamp = lambda: stamp
    db.london_today = lambda: d


def card(horse, nb):
    return {"nap_index": -1, "selections": [{
        "rank": 1, "horse": horse, "race_time": "15:00", "course": "Ayr",
        "race_name": "Handicap", "odds_guide": "5/1", "each_way": False,
        "adjusted_score": 72, "reasoning": [], "confidence": "", "danger": "",
        "next_best": {"horse": nb, "odds_guide": "8/1", "each_way": False,
                      "adjusted_score": 60, "reasoning": ""}}]}


def rows():
    return db._conn.execute(
        "SELECT horse, created_at, superseded_at FROM selections ORDER BY id").fetchall()


db.DB_PATH = ":memory:"
db.init_db()

print("\n1. A /run at 00:30 LONDON on 18 Sep (= 23:30 UTC on 17 Sep)")
utc_of_run = datetime(2026, 9, 18, 0, 30, tzinfo=ZoneInfo("Europe/London")).astimezone(ZoneInfo("UTC"))
chk("premise: the UTC date of that instant is 17 Sep", utc_of_run.date() == date(2026, 9, 17))
pin("2026-09-18 00:30:00")
main._save_cherry_picks(date(2026, 9, 18), card("Midnight Pick", "Midnight Nb"))
r = rows()
chk("selection stamped in London time", r[0][1] == "2026-09-18 00:30:00")
chk("race NB stamped in London time", r[1][1] == "2026-09-18 00:30:00")
chk("date(created_at) is the RACING day (18 Sep)",
    db._conn.execute("SELECT count(*) FROM selections WHERE date(created_at)='2026-09-18'").fetchone()[0] == 2)

print("\n2. A second /run at 09:00 London the same day REPLACES that card")
pin("2026-09-18 09:00:00")
main._save_cherry_picks(date(2026, 9, 18), card("Morning Pick", "Morning Nb"))
r = rows()
chk("both 00:30 rows superseded", r[0][2] is not None and r[1][2] is not None)
chk("both 09:00 rows live", r[2][2] is None and r[3][2] is None)

print("\n3. The nightly settler (bound to the London date) finds the live card")
settler = db._conn.execute(
    """SELECT horse FROM selections WHERE race_time != '' AND date(created_at) = ?
       AND superseded_at IS NULL AND id NOT IN (SELECT selection_id FROM results)""",
    ("2026-09-18",)).fetchall()
chk("settler sees exactly the 09:00 card", sorted(h for (h,) in settler) == ["Morning Nb", "Morning Pick"])

print("\n4. The Betfair bot's UTC date filter finds it once UTC reaches 18 Sep (01:00 London)")
betfair = db._conn.execute(
    """SELECT horse FROM selections WHERE date(created_at) = ?
       AND superseded_at IS NULL AND (source IS NULL OR source = 'bot')""",
    ("2026-09-18",)).fetchall()
chk("Betfair query shape returns the live card", len(betfair) == 2)

print("\n5. NO-REGRESSION outside the midnight hour: the stored DATE is unchanged")
for hh in range(1, 24):
    ldn = datetime(2026, 9, 18, hh, 5, tzinfo=ZoneInfo("Europe/London"))
    if ldn.astimezone(ZoneInfo("UTC")).date() != ldn.date():
        chk(f"{hh:02d}:05 London has the same UTC date", False)
        break
else:
    chk("01:00-23:59 London always share the UTC date (BST)", True)
winter = datetime(2026, 12, 18, 0, 30, tzinfo=ZoneInfo("Europe/London"))
chk("in GMT (December) London == UTC, so the change is a no-op", winter.utcoffset().total_seconds() == 0)

print("\n6. Manual logger falls back to LONDON time, not UTC")
pin("2026-09-18 00:40:00")
mid = db.log_manual_selection("15:00", "Ayr - Handicap", "Manual No Date", "selection",
                              "5/1", False, 1.0)
got = db._conn.execute("SELECT created_at FROM selections WHERE id=?", (mid,)).fetchone()[0]
chk("no created_date => London stamp", got == "2026-09-18 00:40:00")
mid = db.log_manual_selection("15:00", "Ayr - Handicap", "Manual Dated", "selection",
                              "5/1", False, 1.0, created_date="2026-09-15 12:00:00")
got = db._conn.execute("SELECT created_at FROM selections WHERE id=?", (mid,)).fetchone()[0]
chk("explicit created_date is still respected", got == "2026-09-15 12:00:00")

print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
