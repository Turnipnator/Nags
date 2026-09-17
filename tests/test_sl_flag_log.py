"""Sporting Life flag log (17 Sep 2026) — LOG ONLY, mutates nothing.

WHY: on 17 Sep both favourites Sporting Life flagged AHEAD_OF_THE_HANDICAPPER
were 3-year-olds the deterministic scorer put near the bottom (Level Look 44.5,
last of 4; Wild Thoughts 53.1, 10th of 11 -- WON Ayr 15:00 at 11/4F while our
two top scorers, C&D winners on 37 course/going/distance points each, finished
8th and 11th). One race proves nothing, and SL pages are not cached, so there is
no history to measure. This starts the record.

One JSONL line per gate-passing race per run, with EVERY runner (score, rank,
Bet365 price, median price, whether a Sporting Life read arrived, its flags) --
the unflagged runners are the comparison group. Results are joined later.

Run:  python tests/test_sl_flag_log.py
"""
import json
import os
import sys
import tempfile
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("RACING_API_USERNAME", "x")
os.environ.setdefault("RACING_API_PASSWORD", "x")

import src.analyst as A  # noqa: E402
from src.scraper import Meeting, Race, Runner, Scraper  # noqa: E402
from src.scorer import RunnerScore  # noqa: E402

results = []


def chk(label, cond):
    results.append(bool(cond))
    print(f"   {'PASS' if cond else 'FAIL'}  {label}")


def ayr():
    spec = [("Financer", "10/1", 75.3, "Winner of this event in 2024.", []),
            ("Altareq", "11/1", 66.8, "Laid out for this.", []),
            ("Impartiality", "4/1", 57.2, "May go one better.", []),
            ("Wild Thoughts", "5/2", 53.1, "Back on the up.", ["AHEAD_OF_THE_HANDICAPPER"]),
            ("No Read", "20/1", 40.0, "", [])]
    runners, scored = [], []
    for name, odds, total, comment, flags in spec:
        r = Runner(name=name, odds=odds, odds_median=None)
        r.sl_comment, r.sl_insights = comment, flags
        runners.append(r)
        scored.append(RunnerScore(runner=r, total=total))
    race = Race(time="15:00", name="Kilkerran Handicap", course="Ayr", distance="1m2f",
                race_id="rac_1", race_class="Class 2", race_type="Flat",
                num_runners=len(runners), runners=runners)
    meeting = Meeting(course="Ayr", date=date(2026, 9, 17), races=[race])
    return [(scored, race, meeting)]


def read(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


print("\n1. ONE LINE PER GATE-PASSING RACE, EVERY RUNNER")
tmp = tempfile.mkdtemp()
path = os.path.join(tmp, "sl_flag_log.jsonl")
n = A._log_sl_flags(ayr(), "", path=path, stamp="2026-09-17 12:38:58")
rows = read(path)
chk("returns the number of AHEAD_OF_THE_HANDICAPPER flags (1)", n == 1)
chk("exactly one line written", len(rows) == 1)
row = rows[0]
chk("race identity recorded", row["date"] == "2026-09-17" and row["course"] == "Ayr"
    and row["race_time"] == "15:00" and row["race_id"] == "rac_1" and row["race_class"] == "Class 2")
chk("run stamp recorded (London clock)", row["logged_at"] == "2026-09-17 12:38:58")
chk("all 5 runners recorded, not just the flagged one", len(row["runners"]) == 5)
wt = next(r for r in row["runners"] if r["horse"] == "Wild Thoughts")
chk("flagged horse: flag, score and rank recorded", wt["ahead_of_handicapper"] is True
    and wt["score"] == 53.1 and wt["rank"] == 4 and wt["odds"] == "5/2")
fin = next(r for r in row["runners"] if r["horse"] == "Financer")
chk("top scorer ranked 1, not flagged", fin["rank"] == 1 and fin["ahead_of_handicapper"] is False)
nr = next(r for r in row["runners"] if r["horse"] == "No Read")
chk("runner with no Sporting Life read is marked sl_read False (not 'unflagged')",
    nr["sl_read"] is False and wt["sl_read"] is True)
chk("top-level list of flagged horses", row["ahead_of_handicapper"] == ["Wild Thoughts"])

print("\n2. APPENDS ACROSS RUNS")
A._log_sl_flags(ayr(), "", path=path, stamp="2026-09-17 13:38:58")
chk("second run appends a second line", len(read(path)) == 2)

print("\n3. SL FAILURE IS RECORDED, NOT HIDDEN")
path2 = os.path.join(tmp, "b.jsonl")
A._log_sl_flags(ayr(), "Sporting Life partial: 1 fetched, 1 failed", path=path2, stamp="x")
chk("sl_status carried into the line", read(path2)[0]["sl_status"].startswith("Sporting Life partial"))

print("\n4. NEVER BREAKS A RUN")
try:
    out = A._log_sl_flags(ayr(), "", path="/nonexistent-dir/xyz/log.jsonl", stamp="x")
    chk("unwritable path => no exception, returns 0", out == 0)
except Exception as e:  # noqa: BLE001
    chk(f"unwritable path => no exception (raised {type(e).__name__})", False)
old = A.SL_FLAG_LOG_ENABLED
A.SL_FLAG_LOG_ENABLED = False
try:
    path3 = os.path.join(tmp, "c.jsonl")
    A._log_sl_flags(ayr(), "", path=path3, stamp="x")
    chk("flag off => no file written", not os.path.exists(path3))
finally:
    A.SL_FLAG_LOG_ENABLED = old


print("\n5. PIPELINE: the log is written and races to judgement are unchanged")


class FakeScorer:
    TOTALS = {"Clean Pick": 74.0, "Wild Thoughts": 53.1}

    def score_race(self, race):
        rs = [RunnerScore(runner=r, total=self.TOTALS.get(r.name, 50.0)) for r in race.runners]
        return sorted(rs, key=lambda x: -x.total)


class FakeSL(Scraper):
    def fetch_sportinglife(self, target_date, wanted):
        return ({("ayr", Scraper._sl_norm("Wild Thoughts")):
                 {"commentary": "Back on the up.", "insights": ["AHEAD_OF_THE_HANDICAPPER"]}}, "")


def card():
    race = Race(time="15:00", name="Kilkerran Handicap", course="Ayr", distance="1m2f",
                race_class="Class 2", race_type="Flat", num_runners=8,
                runners=[Runner(name="Clean Pick", odds="7/2"), Runner(name="Wild Thoughts", odds="5/2")]
                + [Runner(name=f"Filler {i}", odds="8/1") for i in range(6)])
    return [Meeting(course="Ayr", date=date(2026, 4, 1), races=[race])]


def run(log_on):
    captured = {}

    def fake_judgement(top, meetings, tips, going, n_races=None):
        captured["races"] = [r.time for _, r, _ in top]
        return {}

    saved = (A.Scorer, A.Scraper, A._run_claude_judgement, A._programmatic_cherry_pick,
             A._enforce_compliance, A.SL_FLAG_LOG_ENABLED, A.SL_FLAG_LOG_PATH, A.SPORTINGLIFE_ENABLED)
    p = os.path.join(tmp, f"pipe_{log_on}.jsonl")
    A.Scorer, A.Scraper = FakeScorer, FakeSL
    A._run_claude_judgement = fake_judgement
    A._programmatic_cherry_pick = lambda *a, **k: {"selections": [], "nap_index": -1}
    A._enforce_compliance = lambda s, *a, **k: s
    A.SL_FLAG_LOG_ENABLED, A.SL_FLAG_LOG_PATH, A.SPORTINGLIFE_ENABLED = log_on, p, True
    try:
        A.analyse_all_meetings(card())
    finally:
        (A.Scorer, A.Scraper, A._run_claude_judgement, A._programmatic_cherry_pick,
         A._enforce_compliance, A.SL_FLAG_LOG_ENABLED, A.SL_FLAG_LOG_PATH,
         A.SPORTINGLIFE_ENABLED) = saved
    return captured.get("races"), (read(p) if os.path.exists(p) else [])


races_on, lines_on = run(True)
races_off, lines_off = run(False)
chk("logging on: one line written for the gate-passing race", len(lines_on) == 1)
chk("...and it carries the Sporting Life flag", lines_on and lines_on[0]["ahead_of_handicapper"] == ["Wild Thoughts"])
chk("logging off: nothing written", lines_off == [])
chk("races sent to judgement identical on/off (no-regression)", races_on == races_off == ["15:00"])

print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
