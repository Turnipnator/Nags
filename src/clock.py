"""One definition of "today" for the whole bot: the LONDON racing day.

⚠ WHY THIS MODULE EXISTS (14 Aug 2026). The container runs UTC. British racing
runs on London time. Between 00:00 and 01:00 London during BST the two dates
DISAGREE -- the container's `date.today()` still reads the previous day -- so a
run in that window fetched the WRONG DAY'S CARD entirely. Observed at 00:42
London: `date.today()` = 2026-08-13 while London was already 2026-08-14.

⚠ THE TRAP THAT MAKES THIS DANGEROUS TO HALF-FIX. Before this change there were
three sources of "today" and ALL THREE were UTC:

    1. Python   `date.today()`
    2. SQLite   `date('now')`
    3. Storage  `created_at TEXT DEFAULT CURRENT_TIMESTAMP`

Being uniformly wrong, they were at least MUTUALLY CONSISTENT, which is why
nothing had broken. Moving only the Python side to London would have broken that
consistency: `date(created_at) = date('now')` (both UTC) would no longer match
the London date the pipeline ran under, and in that midnight hour
`supersede_todays_selections()` and the nightly settler would silently target
the WRONG DAY -- on the money ledger. So all three move together, or none do.

Outside 00:00-01:00 London (BST) this is a no-op: 15:50 London is 14:50 UTC and
both give the same DATE. Only the stored time-of-day string changes.

Everything that means "the current racing day" must come from here.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from config.settings import TIMEZONE

_TZ = ZoneInfo(TIMEZONE)


def london_now() -> datetime:
    """Timezone-aware current time on the racing clock."""
    return datetime.now(_TZ)


def london_today():
    """The current RACING day. Use instead of `date.today()` everywhere."""
    return london_now().date()


def london_stamp() -> str:
    """Naive 'YYYY-MM-DD HH:MM:SS' on the racing clock, for SQLite columns.

    Naive on purpose: SQLite's own date()/datetime() helpers do not understand
    offsets, and every existing `created_at` is stored naive. Storing the LONDON
    wall time means `date(created_at)` IS the racing date, so the SQL side keeps
    agreeing with the Python side without any timezone arithmetic in queries.
    """
    return london_now().replace(tzinfo=None).isoformat(sep=" ", timespec="seconds")
