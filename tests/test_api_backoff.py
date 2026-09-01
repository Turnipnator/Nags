"""Racing API rate-limit handling (1 Sep 2026).

WHY IT EXISTS: between 10 Aug and 1 Sep the enrichment thread pool hit 913
HTTP 429s (bursts of 150-244 per card). A 429 burned one of the 3 timeout
attempts and an exhausted budget returned None with NO log line -- the
runner's history was simply missing, and Rule 18b / the class-drop kicker
went blind for that horse with nothing to show for it.

SCOPE UNDER TEST:
  1. 429s have their own budget with back-off; exhaustion logs a WARNING.
  2. A 429 does not consume a timeout attempt; timeouts still retry.
  3. Pacing spaces calls to <= API_RATE_LIMIT_RPS; 0 disables it.
  4. Enrichment counts histories / empty / FAILED and exposes a status.
  5. The status lands in the card notes; empty status is a no-op.
  6. No-429 path returns exactly what it always did.

Run:  python tests/test_api_backoff.py
"""
import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("RACING_API_USERNAME", "x")
os.environ.setdefault("RACING_API_PASSWORD", "x")

import httpx  # noqa: E402

import src.scraper as S  # noqa: E402
import src.analyst as A  # noqa: E402
from src.scraper import Runner, Scraper  # noqa: E402

results = []


def chk(label, cond):
    results.append(bool(cond))
    print(f"   {'PASS' if cond else 'FAIL'}  {label}")


class _Resp:
    def __init__(self, status, body=None):
        self.status_code = status
        self._body = body if body is not None else {}

    def json(self):
        return self._body


class _StubClient:
    """Scripted responses: each item is an int status, a dict body (=200),
    or an Exception instance to raise."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def get(self, url):
        self.calls.append(url)
        item = self.script.pop(0) if self.script else 200
        if isinstance(item, Exception):
            raise item
        if isinstance(item, dict):
            return _Resp(200, item)
        return _Resp(item, {"ok": True})


class _LogCapture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


def _scraper(script, rps=0.0, retries=2):
    sc = Scraper()
    sc.client = _StubClient(script)
    S.API_RATE_LIMIT_RPS = rps
    S.API_429_MAX_RETRIES = retries
    return sc


sleeps = []
_real_sleep = S.time_mod.sleep
S.time_mod.sleep = lambda secs: sleeps.append(secs)   # never actually wait
cap = _LogCapture()
S.logger.addHandler(cap)
S.logger.setLevel(logging.DEBUG)


def _warnings():
    return [r.getMessage() for r in cap.records if r.levelno >= logging.WARNING]


print("\n1. 429 STORM -- own budget, back-off, and exhaustion SHOUTS")
cap.records.clear(); sleeps.clear()
sc = _scraper([429] * 10, retries=2)
out = sc._api_get("/horses/h1/results?limit=3")
chk("exhausted budget returns None", out is None)
chk("stops after API_429_MAX_RETRIES + 1 calls", len(sc.client.calls) == 3)
chk("back-off 2s then 4s", sleeps == [2, 4])
chk("logs a WARNING naming the endpoint on exhaustion",
    any("EXHAUSTED" in w and "/horses/h1/results" in w for w in _warnings()))

print("\n2. 429 then 200 -- recovers inside the budget, no exhaustion warning")
cap.records.clear(); sleeps.clear()
sc = _scraper([429, 429, {"results": [1]}], retries=2)
out = sc._api_get("/x")
chk("returns the body", out == {"results": [1]})
chk("no EXHAUSTED warning", not any("EXHAUSTED" in w for w in _warnings()))

print("\n3. 429s do NOT eat timeout attempts; timeouts still retry")
cap.records.clear(); sleeps.clear()
sc = _scraper([429, httpx.ReadTimeout("t"), 429, httpx.ReadTimeout("t"), {"ok": 1}],
              retries=6)
out = sc._api_get("/y", max_attempts=3)
chk("2 timeouts + 2 rate-limits then success still returns data", out == {"ok": 1})
chk("timeout back-off 3s/6s present alongside 429 back-off",
    3 in sleeps and 6 in sleeps)
cap.records.clear(); sleeps.clear()
sc = _scraper([httpx.ReadTimeout("t")] * 3)
chk("3 timeouts => None (attempt budget unchanged)",
    sc._api_get("/z", max_attempts=3) is None and len(sc.client.calls) == 3)

print("\n4. PACING -- calls are spaced to the configured rate; 0 disables")
S.time_mod.sleep = _real_sleep
sc = _scraper([200] * 5, rps=20.0)   # 50ms interval
t0 = time.monotonic()
for _ in range(5):
    sc._api_get("/p")
spaced = time.monotonic() - t0
chk(f"5 calls at 20 rps take >= 4 intervals ({spaced*1000:.0f}ms >= 200ms)",
    spaced >= 0.19)
sc = _scraper([200] * 5, rps=0.0)
t0 = time.monotonic()
for _ in range(5):
    sc._api_get("/p")
chk("rps=0 => no pacing delay", time.monotonic() - t0 < 0.05)
S.time_mod.sleep = lambda secs: sleeps.append(secs)

print("\n5. ENRICHMENT -- counts histories / empty / FAILED, exposes status")


def _runner(name, hid):
    r = Runner(name=name)
    r.horse_id = hid
    r.form = "0000"           # poor recent form => Rule 18b candidate
    r.comment = ""
    return r


class _Race:
    race_class = "Class 3"; race_type = "Flat"; pattern = ""
    name = "x"; time = "14:00"

    def __init__(self, runners):
        self.runners = runners


class _Meeting:
    def __init__(self, runners):
        self.races = [_Race(runners)]


hist = {"results": [{"class": "Class 3", "pattern": "", "type": "Flat",
                     "date": "2026-08-20", "race_name": "r", "course": "Ripon",
                     "dist_f": "8f",
                     "runners": [{"horse_id": "h_ok", "position": "5", "ovr_btn": "3"}]}]}
r_ok, r_fail, r_empty = _runner("Ok", "h_ok"), _runner("Fail", "h_fail"), _runner("Empty", "h_empty")
orig_cand = S._runner_rule18b_candidate
S._runner_rule18b_candidate = lambda runner, race: True
try:
    sc = _scraper([], retries=1)
    bodies = {"h_ok": hist, "h_fail": None, "h_empty": {"results": []}}

    def _get(url):
        sc.client.calls.append(url)
        hid = url.split("/horses/")[1].split("/")[0]
        b = bodies[hid]
        return _Resp(429) if b is None else _Resp(200, b)
    sc.client.get = _get
    cap.records.clear()
    sc.enrich_with_recent_classes([_Meeting([r_ok, r_fail, r_empty])], limit=3, max_workers=2)
    chk("history stored for the successful runner", len(r_ok.recent_results) == 1)
    chk("failed runner gets [] (scorer behaviour unchanged)", r_fail.recent_results == [])
    chk("summary line reports 1 histories, 1 empty, 1 FAILED",
        any("1 histories, 1 empty, 1 FAILED" in r.getMessage() for r in cap.records))
    chk("last_enrichment_status names the gap",
        "1 of 3 runner histories missing" in sc.last_enrichment_status)
    chk("...and is logged at WARNING",
        any("histories missing" in w for w in _warnings()))

    # all good => status empty (no note on a clean card)
    r2 = _runner("Ok2", "h_ok")
    sc2 = _scraper([hist], retries=1)
    sc2.enrich_with_recent_classes([_Meeting([r2])], limit=3)
    chk("clean enrichment => empty status", sc2.last_enrichment_status == "")
finally:
    S._runner_rule18b_candidate = orig_cand

print("\n6. CARD NOTES -- status is prepended; empty status is a no-op")
sel = {"notes": "Skipped Sligo."}
A._note_enrichment_status(sel, "Racing API enrichment incomplete: 2 of 9 runner histories missing")
chk("prepended above existing notes",
    sel["notes"].startswith("⚠ Racing API enrichment incomplete") and sel["notes"].endswith("Skipped Sligo."))
sel = {"notes": "n"}
A._note_enrichment_status(sel, "")
chk("empty status leaves notes untouched", sel["notes"] == "n")
sel = {}
A._note_enrichment_status(sel, "x")
chk("no existing notes => note alone", sel["notes"] == "⚠ x.")

print("\n7. NO-REGRESSION -- plain 200 path unchanged")
sc = _scraper([{"racecards": []}])
chk("200 returns body, one call", sc._api_get("/racecards/pro") == {"racecards": []} and len(sc.client.calls) == 1)
sc = _scraper([500])
chk("non-200/429 returns None after one call", sc._api_get("/q") is None and len(sc.client.calls) == 1)
chk("fetch_recent_race_classes contract: [] on failure",
    _scraper([429] * 5, retries=1).fetch_recent_race_classes("h", 3) == [])

print(f"\nRESULT: {sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
