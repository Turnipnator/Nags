"""Tests for the PAST-POST filter (14 Aug 2026).

WHY: on 13 Aug a /run at 15:50 selected Beverley 14:15 -- gone off 95 minutes
earlier. The Betfair bot could not place it (market closed) but it was written
to racing.db and the settler marked it WON at 6/4 for +1.75pt. Profit entering
the ledger from a bet never struck, in the direction that flatters us.

THE THREE PROPERTIES THAT MATTER, each with its own failure mode:
  1. TIMEZONE  -- Race.time is LONDON, the container is UTC. Getting this wrong
     is silent: an hour out either keeps a run race or drops a live one.
  2. BACKTEST SAFETY -- must only fire on TODAY's card. Otherwise every
     historical replay drops every race, silently.
  3. FAILS OPEN -- any parse error keeps the race. A bug here could empty a
     whole card without a trace.

Run:  python tests/test_pastpost.py
"""
import os
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("RACING_API_USERNAME", "x")
os.environ.setdefault("RACING_API_PASSWORD", "x")

import src.analyst as A  # noqa: E402
from src.scraper import Race, Meeting, Runner  # noqa: E402

LON = ZoneInfo("Europe/London")
results = []


def chk(label, cond):
    results.append(bool(cond))
    print(f"   {'PASS' if cond else 'FAIL'}  {label}")


# FIXED reference instant, so this suite behaves identically at any hour.
# ⚠ Built as "now +/- N minutes" originally, which broke when run at 00:42:
# "95 minutes ago" wrapped to the previous day while the fixture kept today's
# date, describing a race 22 hours in the FUTURE. Three tests failed on the
# fixture, not the code. Hence the injected clock.
NOW = datetime(2026, 8, 13, 15, 50, tzinfo=LON)   # the 13 Aug /run, 15:50


def at(offset_minutes, on_date=None):
    """A race whose off time is `offset_minutes` from the fixed NOW."""
    t = NOW + timedelta(minutes=offset_minutes)
    d = on_date if on_date is not None else NOW.date()
    race = Race(time=t.strftime("%H:%M"), name="Test Handicap", course="Test",
                distance="1m", runners=[Runner(name="A")])
    return race, Meeting(course="Test", date=d, races=[race])


def started(race, meeting):
    return A._race_already_started(race, meeting, now=NOW)


print("\n1. THE BASIC GATE")

r, m = at(-95)   # Beverley 14:15 seen at 15:50 -- the founding case
chk("a race that went off 95 min ago is blocked", started(r, m))
r, m = at(+120)
chk("a race 2 hours away is kept", not started(r, m))
r, m = at(-1)
chk("a race that went off 1 min ago is blocked", started(r, m))
r, m = at(+2)
chk("a race 2 min away is kept", not started(r, m))

print("\n2. ⚠ BACKTEST SAFETY — historical cards must be untouched")

r, m = at(-95, on_date=date(2026, 4, 1))
chk("a race from 1 Apr is NOT filtered (whole day is 'past')",
    not started(r, m))
r, m = at(-600, on_date=date(2025, 6, 15))
chk("a race from last year is NOT filtered",
    not started(r, m))
r, m = at(-95, on_date=NOW.date() + timedelta(days=1))
chk("tomorrow's card is NOT filtered", not started(r, m))

print("\n3. ⚠ TIMEZONE — must use London, not the container's UTC clock")

# The container runs UTC; in BST that is London-1h. A race 30 minutes in the
# FUTURE (London) reads as 30 minutes in the PAST if you compare against UTC.
# This test fails if the helper ever reverts to a naive/UTC comparison.
r, m = at(+30)
chk("a race 30 min ahead (London) is kept — not read as 30 min past",
    not started(r, m))
# The decisive one: at 15:50 London (BST) the container's UTC clock reads
# 14:50. A race at 15:20 is 30 min PAST in London but 30 min FUTURE in UTC.
r, m = at(-30)
chk("a race 30 min PAST in London is blocked (UTC clock would keep it)",
    started(r, m))
chk("NOW is BST, so London and UTC genuinely differ in this fixture",
    NOW.utcoffset() != timedelta(0))

print("\n4. ⚠ FAILS OPEN")

bad = Race(time="not-a-time", name="X", course="T", distance="1m",
           runners=[Runner(name="A")])
chk("unparseable time keeps the race",
    not started(bad, Meeting(course="T", date=NOW.date(), races=[bad])))
empty = Race(time="", name="X", course="T", distance="1m", runners=[Runner(name="A")])
chk("empty time keeps the race",
    not started(empty, Meeting(course="T", date=NOW.date(), races=[empty])))
r, _ = at(-95)
chk("meeting with no date keeps the race",
    not started(r, Meeting(course="T", date=None, races=[r])))
chk("meeting object missing entirely keeps the race",
    not started(r, object()))

print("\n5. FLAG OFF => NO FILTERING (no-regression)")

_orig = A.PASTPOST_FILTER_ENABLED
try:
    A.PASTPOST_FILTER_ENABLED = False
    r, m = at(-95)
    chk("flag off keeps a race that went off 95 min ago",
        not started(r, m))
finally:
    A.PASTPOST_FILTER_ENABLED = _orig
r, m = at(-95)
chk("flag restored to default (blocking again)", started(r, m))

print("\n6. BUFFER")

_orig_b = A.PASTPOST_BUFFER_MINUTES
try:
    A.PASTPOST_BUFFER_MINUTES = 30.0
    r, m = at(-10)
    chk("+30 min buffer keeps a race that went off 10 min ago",
        not started(r, m))
    r, m = at(-45)
    chk("+30 min buffer still blocks one that went off 45 min ago",
        started(r, m))
finally:
    A.PASTPOST_BUFFER_MINUTES = _orig_b

print(f"\nRESULT: {sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
