"""Tests for F4 TOP-2 PRICE RED FLAG (added 10 Aug 2026) — SHADOW ONLY.

The flag marks a race where, among BETABLE runners (above evens), our top
DETERMINISTIC scorer is LONGER-priced at morning odds than our second.

Measured over 499 premium gate-passing races (1 Apr - 9 Aug 2026): in the 189
flagged races the top scorer wins 6.4% (discovery) / 6.1% (holdout) against a
~15% base rate. It is SHADOW because the same rule INVERTS on our own logged
picks in the holdout.

The load-bearing test here is the last one: with the flag enabled the
compliance gate's output must be BYTE-IDENTICAL to the flag disabled. A shadow
filter that mutates anything is not a shadow filter.

Run: python tests/test_top2_flag.py
"""
import copy
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.analyst as analyst  # noqa: E402
from src.analyst import _top2_price_flag, _enforce_compliance  # noqa: E402

results = []


def chk(label, cond):
    results.append(bool(cond))
    print(f"   {'PASS' if cond else 'FAIL'}  {label}")


class FakeRunner:
    def __init__(self, name, odds):
        self.name = name
        self.odds = odds


class FakeScore:
    """Stands in for RunnerScore — the flag only reads .runner and .total."""
    def __init__(self, name, odds, total):
        self.runner = FakeRunner(name, odds)
        self.total = total


# --------------------------------------------------------------------------
print("1. FLAG FIRES — top scorer longer-priced than #2")
scored = [
    FakeScore("Top Scorer", "8/1", 82.0),      # highest score, LONGER price
    FakeScore("Second", "5/2", 78.0),          # lower score, SHORTER price
    FakeScore("Third", "12/1", 60.0),
]
f = _top2_price_flag(scored)
chk("flag returned", bool(f))
chk("names the top scorer", f.get("top_horse") == "Top Scorer")
chk("names the second", f.get("second_horse") == "Second")
chk("gap is score difference (82.0 - 78.0)", f.get("gap") == 4.0)

# --------------------------------------------------------------------------
print("\n2. NO FLAG — top scorer is already the shorter one")
scored = [
    FakeScore("Top Scorer", "5/2", 82.0),
    FakeScore("Second", "8/1", 78.0),
]
chk("no flag when top scorer is shorter", _top2_price_flag(scored) == {})

print("\n   equal prices are NOT a flag (needs strictly shorter #2)")
scored = [FakeScore("A", "4/1", 80.0), FakeScore("B", "4/1", 75.0)]
chk("equal prices -> no flag", _top2_price_flag(scored) == {})

# --------------------------------------------------------------------------
print("\n3. RANKING IS ON DETERMINISTIC SCORE AMONG BETABLE RUNNERS ONLY")
print("   a sub-evens horse cannot be #1 or #2 — it is blocked at SEL stage")
scored = [
    FakeScore("Odds On", "4/6", 95.0),         # sub-evens: excluded entirely
    FakeScore("Top Betable", "9/1", 80.0),     # longer
    FakeScore("Second Betable", "3/1", 76.0),  # shorter -> flag
]
f = _top2_price_flag(scored)
chk("sub-evens runner excluded from the ranking", f.get("top_horse") == "Top Betable")
chk("flag still fires on the betable pair", f.get("second_horse") == "Second Betable")

print("\n   ...and if excluding it leaves only one betable runner, no flag")
scored = [FakeScore("Odds On", "4/6", 95.0), FakeScore("Only One", "5/1", 70.0)]
chk("fewer than 2 betable -> fails silent", _top2_price_flag(scored) == {})

print("\n   unpriced runners are not betable either")
scored = [FakeScore("No Price", "", 90.0), FakeScore("Priced", "5/1", 70.0)]
chk("unpriced excluded, single betable -> no flag", _top2_price_flag(scored) == {})

# --------------------------------------------------------------------------
print("\n4. EMPTY / DEGENERATE INPUT")
chk("empty field -> {}", _top2_price_flag([]) == {})
chk("single runner -> {}", _top2_price_flag([FakeScore("Solo", "2/1", 70.0)]) == {})

# --------------------------------------------------------------------------
print("\n5. NO-REGRESSION — shadow must not mutate the gate output")
selections = {
    "selections": [
        {
            "horse": "Second", "odds_guide": "5/2", "adjusted_score": 78,
            "race_name": "The Test Stakes", "race_time": "3:30",
            "course": "Newmarket", "each_way": False,
            "next_best": {"horse": "Third", "odds_guide": "12/1",
                          "adjusted_score": 60},
        },
    ],
    "nap_index": -1,
}
race_meta = {
    "the test stakes": {
        "num_runners": 8, "race_type": "Flat", "pattern": "Listed",
        "distance": "1m", "race_class": "Class 1", "course": "Newmarket",
        "race_time": "3:30", "surface": "Turf", "going": "Good",
        "going_detailed": "Good", "api_tip": "",
        "runners": [("top scorer", 8.0), ("second", 2.5), ("third", 12.0)],
        "top2_flag": {
            "top_horse": "Top Scorer", "top_odds": "8/1", "top_score": 82.0,
            "second_horse": "Second", "second_odds": "5/2", "second_score": 78.0,
            "gap": 4.0,
        },
    }
}
scored_lookup = {
    "top scorer": FakeScore("Top Scorer", "8/1", 82.0),
    "second": FakeScore("Second", "5/2", 78.0),
    "third": FakeScore("Third", "12/1", 60.0),
}

analyst.FILTER_TOP2FLAG_ENABLED = False
off = _enforce_compliance(copy.deepcopy(selections), scored_lookup,
                          copy.deepcopy(race_meta))
analyst.FILTER_TOP2FLAG_ENABLED = True
analyst.FILTER_TOP2FLAG_SHADOW = True
on = _enforce_compliance(copy.deepcopy(selections), scored_lookup,
                         copy.deepcopy(race_meta))

chk("gate output byte-identical with flag ON vs OFF",
    json.dumps(off, sort_keys=True, default=str)
    == json.dumps(on, sort_keys=True, default=str))
chk("no gate fix was recorded for the flag",
    not any("TOP2" in str(x).upper()
            for x in (on.get("compliance_log") or [])))
chk("selection horse untouched", on["selections"][0]["horse"] == "Second")
chk("nap_index untouched", on.get("nap_index") == selections["nap_index"])

# --------------------------------------------------------------------------
print("\n6. A RACE WITH NO FLAG PRODUCES NO LOG AND NO CHANGE")
meta_noflag = copy.deepcopy(race_meta)
meta_noflag["the test stakes"]["top2_flag"] = {}
plain = _enforce_compliance(copy.deepcopy(selections), scored_lookup,
                            meta_noflag)
chk("unflagged race still byte-identical",
    json.dumps(plain, sort_keys=True, default=str)
    == json.dumps(off, sort_keys=True, default=str))

# --------------------------------------------------------------------------
print(f"\n{'='*60}")
print(f"{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
