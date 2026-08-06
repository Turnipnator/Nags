"""Tests for the 6 Aug 2026 T14 minimum-runs guard.

CLAUDE.md factor 21 has always said "Minimum 5 runs in 14 days for the bonus",
but `scraper.py` kept only `percent` from the API's trainer_14_days dict and
threw the `runs` count away, so a 67% strike rate off THREE runs scored exactly
like 28% off sixty. Two scoring sites were affected:

  (a) _score_trainer -- 5 of the 100 points
  (b) _score_edges   -- hot-stable +3/+2 and cold-stable -1

Caught auditing the bot's own NAP: Leopardstown 6:00 Desmond Stakes (Group 3)
on 6 Aug 2026, Sparan Nua 11/8, scored 75.6 and NAP'd at 2pts, where the
"Hot stable (67% 14d)" was J S Bolger 2 wins from 3 runs. Guarded she scores
70.1 -- below the 75 NAP line and no longer top of her own race.

Run: python tests/test_t14_min_runs.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.scorer as S  # noqa: E402
from src.scorer import Scorer, _t14_trustworthy  # noqa: E402
from src.scraper import Race, Runner, Scraper  # noqa: E402

results = []


def chk(label, cond):
    results.append(bool(cond))
    print(f"   {'PASS' if cond else 'FAIL'}  {label}")


def runner(pct=None, runs=None, trainer="A N Other", **kw):
    return Runner(name=kw.pop("name", "Test Horse"), trainer=trainer,
                  trainer_14d_pct=pct, trainer_14d_runs=runs, **kw)


def flat_race(**kw):
    return Race(time="18:00", name="Test Stakes", course="Leopardstown",
                distance="1m", race_type="Flat", race_class="Class 1",
                going="Good", **kw)


sc = Scorer()


def trainer_score(r):
    return sc._score_trainer(r, flat_race())


def edge_bonus(r, race=None):
    from src.scorer import RunnerScore
    score = RunnerScore(runner=r)
    return sc._score_edges(r, race or flat_race(), score), score


print("\n1. THE FOUNDING CASE — Bolger 2 wins from 3 runs = 67%")

bolger = runner(pct=67, runs=3, trainer="J S Bolger")
chk("67% off 3 runs is NOT trustworthy", _t14_trustworthy(bolger) is False)
chk("trainer score falls to the static-list default 2.5",
    trainer_score(bolger) == 2.5)
b_bonus, b_score = edge_bonus(bolger)
chk("no 'Hot stable' line in the edge details",
    not any("Hot stable" in d for d in b_score.edge_details))

big = runner(pct=28, runs=60, trainer="W P Mullins")
chk("28% off 60 runs IS trustworthy", _t14_trustworthy(big) is True)
chk("a real hot yard keeps its 5.0 trainer score", trainer_score(big) == 5.0)
_, big_score = edge_bonus(big)
chk("a real hot yard keeps its +2 edge bonus",
    any("Hot stable (28% 14d) +2" in d for d in big_score.edge_details))

print("\n2. THRESHOLD IS EXACT AT 5 RUNS")

chk("4 runs is below the line", _t14_trustworthy(runner(pct=50, runs=4)) is False)
chk("5 runs is on the line", _t14_trustworthy(runner(pct=50, runs=5)) is True)
chk("6 runs is above the line", _t14_trustworthy(runner(pct=50, runs=6)) is True)

print("\n3. FAILS OPEN ON MISSING DATA (never invent a suppression)")

chk("runs=None keeps current behaviour",
    _t14_trustworthy(runner(pct=50, runs=None)) is True)
chk("runs=None still scores off the percentage",
    trainer_score(runner(pct=50, runs=None)) == 5.0)
chk("no pct at all -> untouched static-list path",
    trainer_score(runner(pct=None, runs=None)) == 2.5)
chk("DEFAULT IS SUBTRACTIVE: no small-sample case can raise a trainer score",
    all(trainer_score(runner(pct=p, runs=1, trainer=t))
        <= Scorer._score_trainer_from_t14(p)
        for p in (0, 4, 5, 9, 10, 14, 15, 24, 25, 67, 100)
        for t in ("Small Yard", "Charlie Appleby", "Aidan O'Brien")))
chk("no pct, listed top trainer -> 5.0",
    trainer_score(runner(pct=None, runs=None, trainer="Aidan O'Brien")) == 5.0)

print("\n4. FALLBACK IS CLAMPED SUBTRACTIVE WHILE THE COLD HALF IS HELD BACK")

# The static-list fallback runs in BOTH directions: a 0%-off-1-run yard would
# RISE 1.5 -> 2.5, which is an additive change smuggled in under a subtractive
# one. While T14_MIN_RUNS_APPLY_COLD is off the fallback is clamped so it can
# only ever lower the score.
chk("small-sample 0% yard does NOT rise above its 1.5",
    trainer_score(runner(pct=0, runs=1, trainer="Small Yard")) == 1.5)
chk("small-sample 10% yard does NOT rise above its 3.0... it falls to 2.5",
    trainer_score(runner(pct=10, runs=1, trainer="Small Yard")) == 2.5)
chk("small-sample listed trainer is clamped, not lifted to 5.0",
    trainer_score(runner(pct=10, runs=1, trainer="Charlie Appleby")) == 3.0)
chk("small-sample unlisted high-pct trainer falls to 2.5",
    trainer_score(runner(pct=100, runs=1, trainer="Some Small Yard")) == 2.5)
chk("small-sample listed high-pct trainer holds 5.0 (no change either way)",
    trainer_score(runner(pct=100, runs=1, trainer="Charlie Appleby")) == 5.0)
try:
    S.T14_MIN_RUNS_APPLY_COLD = True
    chk("with APPLY_COLD on the clamp lifts: 0% yard rises to the static 2.5",
        trainer_score(runner(pct=0, runs=1, trainer="Small Yard")) == 2.5)
    chk("with APPLY_COLD on a listed trainer gets the full static 5.0",
        trainer_score(runner(pct=10, runs=1, trainer="Charlie Appleby")) == 5.0)
finally:
    S.T14_MIN_RUNS_APPLY_COLD = False
chk("clamp restored after revert test",
    trainer_score(runner(pct=0, runs=1, trainer="Small Yard")) == 1.5)

print("\n5. COLD HALF IS OFF BY DEFAULT (additive, so it waits)")

cold_small = runner(pct=0, runs=1, trainer="Small Yard")
chk("cold -1 STILL applies on a small sample by default",
    any("Cold stable" in d for d in edge_bonus(cold_small)[1].edge_details))
try:
    S.T14_MIN_RUNS_APPLY_COLD = True
    chk("with APPLY_COLD on, the phantom -1 is suppressed",
        not any("Cold stable" in d
                for d in edge_bonus(cold_small)[1].edge_details))
    chk("with APPLY_COLD on, a genuine cold yard keeps its -1",
        any("Cold stable" in d for d in
            edge_bonus(runner(pct=0, runs=30))[1].edge_details))
finally:
    S.T14_MIN_RUNS_APPLY_COLD = False
chk("APPLY_COLD restored to default",
    any("Cold stable" in d for d in edge_bonus(cold_small)[1].edge_details))

print("\n6. NO-REGRESSION — flag off must be byte-identical to pre-6-Aug")

before = {}
try:
    S.T14_MIN_RUNS_ENABLED = False
    for pct, runs in ((67, 3), (25, 4), (100, 1), (0, 1), (28, 60)):
        r = runner(pct=pct, runs=runs)
        before[(pct, runs)] = (trainer_score(r),
                               sorted(edge_bonus(r)[1].edge_details))
    chk("flag off: 67%/3 runs scores 5.0 again",
        before[(67, 3)][0] == 5.0)
    chk("flag off: 67%/3 runs keeps its Hot stable +3",
        any("Hot stable (67% 14d) +3" in d for d in before[(67, 3)][1]))
    chk("flag off: 0%/1 run keeps its Cold stable -1",
        any("Cold stable" in d for d in before[(0, 1)][1]))
    chk("flag off: trustworthy check is a no-op",
        _t14_trustworthy(runner(pct=50, runs=1)) is True)
finally:
    S.T14_MIN_RUNS_ENABLED = True
chk("flag restored to default after revert test",
    _t14_trustworthy(runner(pct=50, runs=1)) is False)

print("\n7. COMPOUND-SIGNAL KNOCK-ON IS ACCOUNTED FOR")

# Removing a hot bonus decrements intent_signals, which can drop a horse from
# 3 signals (+5 compound) to 2 (no compound). That is CORRECT -- the phantom
# signal should never have counted -- but it means the true delta on such a
# horse is the bonus PLUS 5, and it must not be a silent surprise.
sig = runner(pct=67, runs=3, first_time_headgear=True, headgear="b", age=3,
             sex="colt", trainer="J S Bolger")
_, sig_score = edge_bonus(sig)
chk("small-sample horse cannot bank a hot-stable intent signal",
    not any("Hot stable" in d for d in sig_score.edge_details))
try:
    S.T14_MIN_RUNS_ENABLED = False
    _, sig_off = edge_bonus(sig)
    n_on = sum(1 for d in sig_score.edge_details if "COMPOUND" in d)
    n_off = sum(1 for d in sig_off.edge_details if "COMPOUND" in d)
    chk("guard can only remove a compound bonus, never add one", n_on <= n_off)
finally:
    S.T14_MIN_RUNS_ENABLED = True

print("\n8. SCRAPER CAPTURES THE RUNS COUNT")

parse_runner = Scraper.__dict__["_parse_runner"]
obj = Scraper.__new__(Scraper)
parsed = parse_runner(obj, {
    "horse": "Sparan Nua", "trainer": "J S Bolger", "jockey": "D McDonogh",
    "trainer_14_days": {"runs": "3", "wins": "2", "percent": "67"},
    "odds": [{"bookmaker": "bet365", "fractional": "11/8", "decimal": "2.38"}],
})
chk("runs parsed off the API dict", parsed.trainer_14d_runs == 3)
chk("percent still parsed", parsed.trainer_14d_pct == 67)
parsed_missing = parse_runner(obj, {
    "horse": "No Data", "trainer": "X", "jockey": "Y",
    "trainer_14_days": {"percent": "20"},
    "odds": [{"bookmaker": "bet365", "fractional": "5/1", "decimal": "6.0"}],
})
chk("missing runs key parses to None (fails open)",
    parsed_missing.trainer_14d_runs is None)

print()
print(f"RESULT: {sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
