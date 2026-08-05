"""Tests for the 4 Aug 2026 signal-alignment fixes.

All four defects were found on the 4 Aug 2026 card, where deterministic code
read a different signal from the one CLAUDE.md specifies:

  1. Going-volatility gate read `going + weather` instead of the real
     `going_detailed` -> fired on a WEATHER FORECAST at Ffos Las and blocked
     the day's only 75+ NAP; simultaneously blind to Catterick's genuine
     "Good to firm in places".
  2. `_parse_runner` dropped priced runners with no declared jockey ->
     Roscommon 18:00 scored as 12 runners against field_size=15.
  3. `each_way` set with no field-size test -> unplaceable E/W flag in a
     4-runner handicap at Lingfield 19:18.
  4. `_meets_class_floor` failed OPEN on empty race_class -> every unclassed
     Irish race bypassed the floor.

Run: python tests/test_going_gate_field.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.analyst import (  # noqa: E402
    _going_volatility_phrases,
    _meets_class_floor,
    _should_be_each_way_from_odds,
)
from src.scraper import Race, Scraper  # noqa: E402

results = []


def chk(label, cond):
    results.append(bool(cond))
    print(f"   {'PASS' if cond else 'FAIL'}  {label}")


def parse_race(data):
    """Call _parse_race without running Scraper.__init__ (no API client)."""
    return Scraper._parse_race(Scraper.__new__(Scraper), data)


# --------------------------------------------------------------------------
print("1. GOING GATE — real going_detailed, not going + weather")
# --------------------------------------------------------------------------
# The 4 Aug regression: real report stable, weather said Showers. Pre-fix the
# synthetic string was "Good Showers" -> matched "showers" -> NAP Perfect
# Nation (76, 13/8) blocked.
chk("Ffos Las real report is NOT volatile",
    _going_volatility_phrases("GOOD (GoingStick: 6.0)") is False)

# SUPERSEDED 5 Aug 2026. On 4 Aug this asserted True -- Catterick's "in places"
# was read as a hedge the old synthetic string could never see. It was never a
# signal worth seeing: it describes variation ACROSS the track on a stable
# surface, not a forecast of change. Now spatial => no demote.
chk("Catterick 'in places' does NOT fire (spatial, not temporal)",
    _going_volatility_phrases(
        "GOOD, Good to firm in places (GoingStick: 7.2)") is False)

chk("empty going_detailed fails OPEN", _going_volatility_phrases("") is False)
chk("None going_detailed fails OPEN", _going_volatility_phrases(None) is False)

for phrase in ("watered", "watering", "becoming softer", "drying out",
               "rain forecast", "could change"):
    chk(f"listed phrase still matches: {phrase}",
        _going_volatility_phrases(f"GOOD, {phrase}") is True)

race = parse_race({
    "off_time": "15:00", "race_name": "Ebf Novice Stakes", "course": "Ffos Las",
    "going": "Good", "going_detailed": "GOOD (GoingStick: 6.0)",
    "weather": "Showers", "runners": [],
})
chk("scraper captures going_detailed",
    race.going_detailed == "GOOD (GoingStick: 6.0)")
chk("weather kept as a SEPARATE signal", race.weather == "Showers")
chk("going unchanged", race.going == "Good")
chk("gate reads the report, not the forecast",
    _going_volatility_phrases(race.going_detailed) is False)


# --------------------------------------------------------------------------
print("2. NON-RUNNER FILTER — price is authoritative, not jockey")
# --------------------------------------------------------------------------
def runner_data(name, jockey, priced):
    return {
        "horse": name, "jockey": jockey, "lbs": "140",
        "odds": ([{"fractional": "50/1", "decimal": "51.0"}] if priced
                 else [{"fractional": "-", "decimal": "-"}]),
    }


def roscommon(runners):
    return parse_race({
        "off_time": "18:00", "race_name": "Maiden Hurdle",
        "course": "Roscommon", "going": "Yielding",
        "field_size": str(sum(1 for r in runners
                              if r["odds"][0]["fractional"] != "-")),
        "runners": runners,
    })


# The 4 Aug regression: Ataboymiley, John Gun, Goeasyonme — priced, but no
# jockey declared yet. The legacy heuristic binned all three.
r = roscommon([
    runner_data("Clay Pigeons", "Brian Hayes", True),
    runner_data("Ataboymiley", "", True),
    runner_data("John Gun", "", True),
    runner_data("Goeasyonme", "", True),
])
chk("priced runner with no jockey is KEPT", r.num_runners == 4)
chk("named runner present", "Ataboymiley" in [x.name for x in r.runners])

# The 9 Jul rule stands: no price while a rival IS priced = withdrawn.
r = roscommon([
    runner_data("Clay Pigeons", "Brian Hayes", True),
    runner_data("Earthwatch", "Darragh O'Keeffe", False),
])
chk("unpriced runner WITH jockey still dropped",
    r.num_runners == 1 and r.runners[0].name == "Clay Pigeons")

r = roscommon([
    runner_data("Clay Pigeons", "Brian Hayes", True),
    runner_data("Ghost Entry", "", False),
])
chk("unpriced AND no jockey dropped", r.num_runners == 1)

# No runner priced => price filter self-disables. This is why the no-jockey
# drop is narrowed rather than deleted.
r = roscommon([
    runner_data("A", "Jockey One", False),
    runner_data("B", "Jockey Two", False),
])
chk("market not open keeps full field", r.num_runners == 2)

# Regression: 12 kept vs field_size=15 triggered the NR warning.
runners = [runner_data(f"H{i}", f"J{i}", True) for i in range(12)]
runners += [runner_data(f"U{i}", "", True) for i in range(3)]
runners += [runner_data(f"NR{i}", f"JN{i}", False) for i in range(4)]
chk("Roscommon field_size now agrees (15)", roscommon(runners).num_runners == 15)


# --------------------------------------------------------------------------
print("3. EACH-WAY — a place market must exist")
# --------------------------------------------------------------------------
chk("4-runner handicap gets NO E/W (Russian Rumour 17/2)",
    _should_be_each_way_from_odds("17/2", "Handicap Stakes", 4) is False)
chk("5 runners is the boundary",
    _should_be_each_way_from_odds("17/2", "Handicap Stakes", 5) is True)
chk("8-runner field unchanged",
    _should_be_each_way_from_odds("8/1", "Handicap Stakes", 8) is True)
chk("short price still win-only",
    _should_be_each_way_from_odds("2/1", "Handicap Stakes", 12) is False)
chk("unknown field size keeps old behaviour (no regression)",
    _should_be_each_way_from_odds("8/1", "Handicap Stakes", 0) is True)


# --------------------------------------------------------------------------
print("4. CLASS FLOOR — unclassed no longer fails open")
# --------------------------------------------------------------------------
def mk(race_class="", race_type="Hurdle", pattern=""):
    return Race(time="18:00", name="R", course="Roscommon", distance="2m",
                race_class=race_class, race_type=race_type, pattern=pattern)


chk("unclassed Irish race BLOCKED (Roscommon 18:00)",
    _meets_class_floor(mk()) is False)
chk("Irish Grade 1 still passes", _meets_class_floor(mk(pattern="Grade 1")) is True)
chk("Irish Group 2 still passes", _meets_class_floor(mk(pattern="Group 2")) is True)
chk("Irish Listed still passes", _meets_class_floor(mk(pattern="Listed")) is True)
chk("GB Flat C4 passes", _meets_class_floor(mk("Class 4", "Flat")) is True)
chk("GB Flat C5 blocked", _meets_class_floor(mk("Class 5", "Flat")) is False)
chk("GB Flat C6 blocked", _meets_class_floor(mk("Class 6", "Flat")) is False)
chk("GB NH C3 passes", _meets_class_floor(mk("Class 3", "Hurdle")) is True)
chk("GB NH C4 blocked", _meets_class_floor(mk("Class 4", "Hurdle")) is False)
chk("GB NH C5 blocked", _meets_class_floor(mk("Class 5", "Chase")) is False)
chk("Flat pattern race (Class 1 + Group 3) passes",
    _meets_class_floor(mk("Class 1", "Flat", "Group 3")) is True)


# --------------------------------------------------------------------------
print("5. CHECK 17 — place-market clamp on the LLM's own each_way")
# --------------------------------------------------------------------------
import copy  # noqa: E402
import src.analyst as A  # noqa: E402


def sels_4r(each_way=True, nb_ew=True):
    """Russian Rumour, 17/2, FOUR-runner Lingfield handicap (4 Aug 2026)."""
    return {
        "selections": [{
            "horse": "Russian Rumour", "odds_guide": "17/2",
            "adjusted_score": 77, "each_way": each_way,
            "race_time": "19:18", "course": "Lingfield",
            "race_name": "Trusted Betting Site Comparison Handicap Stakes",
            "reasoning": [],
            "next_best": {"horse": "Taritino", "odds_guide": "5/2",
                          "adjusted_score": 62, "each_way": nb_ew},
        }],
        "nap_index": -1,
    }


LOOKUP_4R = {
    "trusted betting site comparison handicap stakes": {
        "num_runners": 4, "race_type": "Flat", "pattern": "",
        "race_class": "Class 4", "course": "Lingfield", "race_time": "19:18",
        "surface": "Turf", "going": "Good To Firm",
        "going_detailed": "GOOD TO FIRM", "distance": "1m6f", "api_tip": "",
        "runners": [("russian rumour", 8.5), ("taritino", 2.5),
                    ("scarlet moon", 8.0), ("tabasko", 0.727)],
    },
}
LOOKUP_8R = {k: {**v, "num_runners": 8} for k, v in LOOKUP_4R.items()}

out = A._enforce_compliance(copy.deepcopy(sels_4r()), {}, LOOKUP_4R)
chk("LLM each_way CLEARED in 4-runner field",
    out["selections"][0]["each_way"] is False)
chk("next_best each_way CLEARED too",
    out["selections"][0]["next_best"]["each_way"] is False)
chk("clamp is logged",
    any("NO PLACE MARKET" in x for x in out.get("compliance_log", [])))

out = A._enforce_compliance(copy.deepcopy(sels_4r()), {}, LOOKUP_8R)
chk("8-runner field keeps E/W (no regression)",
    out["selections"][0]["each_way"] is True)

out = A._enforce_compliance(copy.deepcopy(sels_4r(each_way=False, nb_ew=False)),
                            {}, LOOKUP_4R)
chk("already win-only stays win-only, no spurious fix",
    out["selections"][0]["each_way"] is False
    and not any("NO PLACE MARKET" in x for x in out.get("compliance_log", [])))

out = A._enforce_compliance(copy.deepcopy(sels_4r()), {}, {})
chk("unresolvable race does NOT clamp (never guess)",
    out["selections"][0]["each_way"] is True)

# --------------------------------------------------------------------------
print("6. GOING GATE — temporal vs spatial split (5 Aug 2026)")
# --------------------------------------------------------------------------
# Pontefract 5 Aug: a firm, settled surface described precisely. Blocked the
# day's only 75+ NAP (The Good Biscuit 77.2, 3/1) with measured drift of ZERO.
chk("Pontefract 'Good in places' does NOT fire",
    _going_volatility_phrases(
        "GOOD TO FIRM, Good in places (GoingStick: 8.4)") is False)
chk("Brighton 'Good in places' does NOT fire",
    _going_volatility_phrases(
        "GOOD TO FIRM, Good in places (GoingStick: 6.6)") is False)
chk("'in the back straight' does NOT fire",
    _going_volatility_phrases("GOOD, soft in the back straight") is False)

# Every temporal phrase must survive -- these forecast CHANGE, which is the
# whole point of Option Y.
for phrase in ("watered", "watering", "showers", "rain forecast",
               "could change", "becoming softer", "drying out"):
    chk(f"temporal phrase still fires: {phrase}",
        _going_volatility_phrases(f"GOOD, {phrase} before racing") is True)

# A report can be both. Temporal must still win.
chk("mixed spatial+temporal still fires",
    _going_volatility_phrases(
        "GOOD TO FIRM, Good in places, watered overnight") is True)

# Flag restores the old behaviour in one move (the documented revert).
A.GOING_VOLATILITY_SPATIAL_PHRASES = True
try:
    chk("flag ON restores old behaviour for 'in places'",
        _going_volatility_phrases(
            "GOOD TO FIRM, Good in places (GoingStick: 8.4)") is True)
    chk("flag ON keeps temporal firing",
        _going_volatility_phrases("GOOD, watered") is True)
finally:
    A.GOING_VOLATILITY_SPATIAL_PHRASES = False
chk("flag restored to default after revert test",
    _going_volatility_phrases("GOOD TO FIRM, Good in places") is False)

# The drift half is untouched: Hexham 9 May 2026 (Good -> Soft, 2 steps) is
# what Option Y is actually for, and it must still demote.
chk("Hexham-style Good->Soft is still a 2-step drift",
    abs(A._going_step("Good") - A._going_step("Soft")) == 2)
chk("Good->Heavy is still 3 steps",
    abs(A._going_step("Good") - A._going_step("Heavy")) == 3)
chk("1-step drift stays below the threshold",
    abs(A._going_step("Good") - A._going_step("Good To Soft")) == 1)

print()
print(f"RESULT: {sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
