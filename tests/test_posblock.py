"""Tests for F5 POSITIONAL BLOCK — SHADOW ONLY (13 Aug 2026).

F5 logs each selection's Course+Going+Distance total (42 of the scorer's 100
points), which measurement shows is NEGATIVELY associated with performance
against price:

  RAW SCORER, highest C+G+D in a race vs lowest (n=683 / 686):
      A-E/bet -0.0513 v -0.0087, difference 95% CI [-0.076, -0.008]
      -- EXCLUDES ZERO, and holds in both windows.
  REAL PICKS, block >= 30 v < 30 (n=153 / 199):
      ROI -41.4% v +19.0%; but the difference CI SPANS ZERO, and
      `next_best` inverts. Hence SHADOW.

THE LOAD-BEARING TEST is the last one: gate output must be byte-identical with
the flag ON and OFF. A shadow filter that mutates anything is not a shadow
filter, and this one would touch 43% of picks if it leaked.

Run:  python tests/test_posblock.py
"""
import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("RACING_API_USERNAME", "x")
os.environ.setdefault("RACING_API_PASSWORD", "x")

import src.analyst as A  # noqa: E402
from src.scorer import RunnerScore  # noqa: E402
from src.scraper import Runner  # noqa: E402

results = []


def chk(label, cond):
    results.append(bool(cond))
    print(f"   {'PASS' if cond else 'FAIL'}  {label}")


def sr(name, total, course, going, dist):
    return RunnerScore(runner=Runner(name=name), total=total,
                       course_score=course, going_score=going,
                       distance_score=dist)


print("\n1. THE HELPER SUMS THE RIGHT THREE FACTORS")

chk("C+G+D only — class/speed/form excluded",
    A._positional_block(sr("X", 80.0, 15.0, 10.0, 12.0)) == 37.0)
chk("today's winners' shape (18) computed correctly",
    A._positional_block(sr("Y", 57.0, 5.0, 7.0, 6.0)) == 18.0)
chk("maximum possible block is 42",
    A._positional_block(sr("Z", 90.0, 15.0, 15.0, 12.0)) == 42.0)
chk("tolerates a RunnerScore with missing fields",
    A._positional_block(RunnerScore(runner=Runner(name="W"))) == 0.0)

print("\n2. THRESHOLD BEHAVIOUR")

chk("flag threshold defaults to 30", A.POSBLOCK_FLAG_AT == 30.0)
chk("Rossa Raheen's 37 is above the line",
    A._positional_block(sr("Rossa Raheen", 77.8, 15.0, 10.0, 12.0)) >= A.POSBLOCK_FLAG_AT)
chk("Ruby Wedding's 18 is below the line",
    A._positional_block(sr("Ruby Wedding", 57.3, 5.0, 7.0, 6.0)) < A.POSBLOCK_FLAG_AT)

print("\n3. ⭐ LOAD-BEARING — SHADOW MUTATES NOTHING")

# Today's real card: Rossa Raheen (block 37) NAP, Auld Toon Loon (block 37) NB.
# Both would flag. If F5 leaked, this is exactly where it would show.
SELS = [
    {"horse": "Rossa Raheen", "odds_guide": "10/1", "adjusted_score": 77.8,
     "each_way": True, "race_time": "19:34", "course": "Salisbury",
     "next_best": {"horse": "Liveinthelight", "odds_guide": "13/2",
                   "adjusted_score": 71.1}},
    {"horse": "Auld Toon Loon", "odds_guide": "7/2", "adjusted_score": 74.2,
     "each_way": True, "race_time": "19:41", "course": "Windsor",
     "next_best": {"horse": "Parlando", "odds_guide": "14/1",
                   "adjusted_score": 75.6}},
]
LOOKUP = {
    "rossa raheen": sr("Rossa Raheen", 77.8, 15.0, 10.0, 12.0),
    "liveinthelight": sr("Liveinthelight", 71.1, 8.0, 8.0, 12.0),
    "auld toon loon": sr("Auld Toon Loon", 74.2, 15.0, 10.0, 12.0),
    "parlando": sr("Parlando", 75.6, 15.0, 10.0, 12.0),
}


def run(enabled):
    _e, _s = A.FILTER_POSBLOCK_ENABLED, A.FILTER_POSBLOCK_SHADOW
    try:
        A.FILTER_POSBLOCK_ENABLED = enabled
        A.FILTER_POSBLOCK_SHADOW = True
        d = {"selections": copy.deepcopy(SELS), "nap_index": 0,
             "compliance_log": []}
        return A._enforce_compliance(d, copy.deepcopy(LOOKUP), {})
    finally:
        A.FILTER_POSBLOCK_ENABLED, A.FILTER_POSBLOCK_SHADOW = _e, _s


on, off = run(True), run(False)
chk("selections byte-identical with flag on vs off",
    on["selections"] == off["selections"])
chk("nap_index identical", on["nap_index"] == off["nap_index"])
chk("compliance_log identical (nothing appended)",
    on.get("compliance_log") == off.get("compliance_log"))
chk("double identical", on.get("double") == off.get("double"))
chk("full gate output identical", on == off)
chk("the NAP survives despite flagging (shadow takes no action)",
    on["nap_index"] == 0)
chk("no F5 text leaked into the user-facing compliance log",
    not any("POSBLOCK" in f for f in (on.get("compliance_log") or [])))

print("\n4. A SELECTION MISSING FROM scored_lookup MUST NOT RAISE")

_e, _s = A.FILTER_POSBLOCK_ENABLED, A.FILTER_POSBLOCK_SHADOW
try:
    A.FILTER_POSBLOCK_ENABLED, A.FILTER_POSBLOCK_SHADOW = True, True
    d = {"selections": [{"horse": "Ghost Horse", "odds_guide": "5/1",
                         "adjusted_score": 70.0, "each_way": True,
                         "next_best": {}}],
         "nap_index": -1, "compliance_log": []}
    out = A._enforce_compliance(d, {}, {})
    chk("unknown horse is skipped, no exception", out["selections"][0]["horse"] == "Ghost Horse")
finally:
    A.FILTER_POSBLOCK_ENABLED, A.FILTER_POSBLOCK_SHADOW = _e, _s

print(f"\nRESULT: {sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
