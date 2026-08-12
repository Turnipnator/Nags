"""Tests for the 6 Aug 2026 edge-block rubric alignment.

Three bonuses `_score_edges` awarded that CLAUDE.md's edge-factor list does not
contain, found by auditing the block line-by-line against the rubric:

  1. SPEED DOMINANCE  +5/+3/+1 on a field-relative max(RPR, TS) lead.
     Nowhere in CLAUDE.md; also double-counts _score_class.
  2. "unknown headgear" +2 -- the first-time-headgear else branch, which paid
     for hoods and eyeshields. The rubric grades four types only.
  3. A silent intent signal for OR >= field average + 8, labelled "class drop
     detection" while measuring the OPPOSITE of a class drop.

All three are pure removals behind independent flags. Run:
    python tests/test_edge_block_rubric.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.scorer as S  # noqa: E402
from src.scorer import RunnerScore, Scorer  # noqa: E402
from src.scraper import Race, Runner  # noqa: E402

results = []


def chk(label, cond):
    results.append(bool(cond))
    print(f"   {'PASS' if cond else 'FAIL'}  {label}")


sc = Scorer()


def race_with(runners, **kw):
    kw.setdefault("race_class", "Class 4")
    kw.setdefault("race_type", "Flat")
    return Race(time="15:00", name="Test Handicap", course="Sandown",
                distance="1m", going="Good",
                runners=runners, num_runners=len(runners), **kw)


def edges(target, race):
    """Return (bonus, details) for `target` inside `race`."""
    score = RunnerScore(runner=target)
    bonus = sc._score_edges(target, race, score)
    return bonus, score.edge_details


def dominant_field():
    """Star leads the field by 20 on RPR -> old code paid +5."""
    star = Runner(name="Star", rpr=120, speed_figure=110, official_rating=100)
    rivals = [Runner(name=f"R{i}", rpr=100, speed_figure=95,
                     official_rating=100) for i in range(5)]
    return star, race_with([star] + rivals)


print("\n1. SPEED DOMINANCE — POINTS GONE, NOTE KEPT")

star, r = dominant_field()
bonus, det = edges(star, r)
chk("no points awarded for a 20pt field lead",
    not any("+5" in d and "leads field" in d for d in det))
chk("the lead is still reported as a note",
    any("leads field by 20pts" in d and "note only" in d for d in det))
chk("edge bonus contains no speed component", bonus == 0.0)

try:
    S.SPEED_DOMINANCE_BONUS_ENABLED = True
    b_on, det_on = edges(star, r)
    chk("flag ON restores the +5", b_on == 5.0)
    chk("flag ON restores the SPEED DOMINANCE label",
        any("SPEED DOMINANCE" in d and "+5" in d for d in det_on))
finally:
    S.SPEED_DOMINANCE_BONUS_ENABLED = False
chk("flag restored to default", edges(star, r)[0] == 0.0)

# The three bands all had to go, not just the headline one.
for lead, band in ((20, "+5"), (10, "+3"), (5, "+1")):
    s = Runner(name="Lead", rpr=100 + lead, official_rating=90)
    others = [Runner(name=f"O{i}", rpr=100, official_rating=90)
              for i in range(4)]
    chk(f"{lead}pt lead (was {band}) scores 0",
        edges(s, race_with([s] + others))[0] == 0.0)

# ...and a horse with no lead is untouched either way.
flat_a = Runner(name="A", rpr=100, official_rating=90)
flat_b = Runner(name="B", rpr=100, official_rating=90)
chk("no lead -> no note, no points",
    edges(flat_a, race_with([flat_a, flat_b])) == (0.0, []))

print("\n1b. NOTE NAMES THE METRIC IT ACTUALLY COMPUTES (relabel, 12 Aug 2026)")

# The note used to say "Speed leader" while computing max(RPR, TS). On 12 Aug
# the judgement layer read that as the clock and published "Sovereign View is
# the clock's outright leader" -- his TS was THIRD in the race. Zero points, so
# the string's only job is informing the LLM; a name that misidentifies the
# metric is the whole defect.


def lead_note(target, race):
    return next((d for d in edges(target, race)[1] if "leads field by" in d), "")


# RPR is the source (today's Sovereign View shape: RPR high, TS low).
rpr_led = Runner(name="RprLed", rpr=96, speed_figure=78, official_rating=82)
rpr_rivals = [Runner(name=f"X{i}", rpr=90, speed_figure=79, official_rating=80)
              for i in range(4)]
note = lead_note(rpr_led, race_with([rpr_led] + rpr_rivals))
chk("names RPR when RPR is the better figure", "(RPR)" in note)
chk("does not call an RPR lead a speed lead", "Speed leader" not in note)
chk("explicitly disclaims the clock", "NOT the Topspeed clock" in note)

# TS is the source.
ts_led = Runner(name="TsLed", rpr=80, speed_figure=100, official_rating=75)
ts_rivals = [Runner(name=f"Y{i}", rpr=85, speed_figure=88, official_rating=75)
             for i in range(4)]
chk("names TS when TS is the better figure",
    "(TS)" in lead_note(ts_led, race_with([ts_led] + ts_rivals)))

# Load-bearing: relabel must not move a single point, in either flag state.
chk("relabel is score-neutral (flag off)",
    edges(rpr_led, race_with([rpr_led] + rpr_rivals))[0] == 0.0)
try:
    S.SPEED_DOMINANCE_BONUS_ENABLED = True
    b_on, det_on = edges(star, r)
    chk("flag ON wording still byte-identical (regression guard)",
        det_on == ["SPEED DOMINANCE: best fig 120 leads field by 20pts +5"])
    chk("flag ON points unchanged by the relabel", b_on == 5.0)
finally:
    S.SPEED_DOMINANCE_BONUS_ENABLED = False

print("\n2. UNRECOGNISED FIRST-TIME HEADGEAR — NO INVENTED BONUS")


def hg_runner(code):
    return Runner(name="HG", headgear=code, first_time_headgear=True,
                  age=6, sex="gelding", rpr=100, official_rating=90)


hood = hg_runner("h")
rival = Runner(name="Rival", rpr=100, official_rating=90)
b, det = edges(hood, race_with([hood, rival]))
chk("first-time hood scores 0", b == 0.0)
chk("hood still noted, flagged as ungraded",
    any("not graded in rubric" in d for d in det))
try:
    S.UNKNOWN_HEADGEAR_BONUS_ENABLED = True
    chk("flag ON restores the +2",
        edges(hood, race_with([hood, rival]))[0] == 2.0)
finally:
    S.UNKNOWN_HEADGEAR_BONUS_ENABLED = False

# The four GRADED types must be completely untouched by this change.
for code, pts, label in (("b", 3.0, "blinkers"), ("v", 3.0, "visor"),
                         ("p", 2.0, "cheekpieces"), ("t", 1.0, "tongue-tie")):
    rr = hg_runner(code)
    chk(f"graded first-time {label} still scores +{pts:.0f}",
        edges(rr, race_with([rr, rival]))[0] == pts)

young = Runner(name="Colt", headgear="b", first_time_headgear=True, age=3,
               sex="colt", rpr=100, official_rating=90)
chk("young-colt blinkers still +5",
    edges(young, race_with([young, rival]))[0] == 5.0)
old_mare = Runner(name="Mare", headgear="b", first_time_headgear=True, age=6,
                  sex="mare", rpr=100, official_rating=90)
chk("older-mare blinkers still -2",
    edges(old_mare, race_with([old_mare, rival]))[0] == -2.0)

print("\n3. FAKE CLASS-DROP INTENT SIGNAL — REMOVED")

# Rated 20lb above the field average: the old code called this a class drop.
top = Runner(name="TopWeight", official_rating=120, rpr=110,
             headgear="v", first_time_headgear=True, age=5, sex="gelding")
low = [Runner(name=f"L{i}", official_rating=95, rpr=110) for i in range(5)]
r3 = race_with([top] + low)
b3, det3 = edges(top, r3)
chk("no compound bonus off the phantom signal",
    not any("COMPOUND" in d for d in det3))
chk("only the genuine headgear signal is counted",
    any("2 intent signals" not in d for d in det3))
try:
    S.OR_ABOVE_FIELD_INTENT_SIGNAL = True
    _, det_on = edges(top, r3)
    chk("flag ON restores the second (phantom) signal",
        any("2 intent signals" in d for d in det_on))
finally:
    S.OR_ABOVE_FIELD_INTENT_SIGNAL = False
chk("flag restored to default",
    not any("2 intent signals" in d for d in edges(top, r3)[1]))

# A genuine class-drop kicker must still count toward compounding -- the real
# rubric item was never the thing being removed.
kick = Runner(name="Dropper", official_rating=95, rpr=110,
              comment="Ran a creditable second in a Grade 2 last time out.")
r4 = race_with([kick] + [Runner(name=f"F{i}", official_rating=95, rpr=110)
                         for i in range(4)], race_class="Class 4",
               race_type="Hurdle")
_, det4 = edges(kick, r4)
chk("genuine class-drop kicker still fires and still counts as intent",
    any("Class-drop kicker" in d for d in det4))

print("\n4. NO-REGRESSION — all three flags on == pre-6-Aug behaviour")

try:
    S.SPEED_DOMINANCE_BONUS_ENABLED = True
    S.UNKNOWN_HEADGEAR_BONUS_ENABLED = True
    S.OR_ABOVE_FIELD_INTENT_SIGNAL = True
    _s, _r = dominant_field()
    chk("speed +5 back", edges(_s, _r)[0] == 5.0)
    chk("hood +2 back", edges(hood, race_with([hood, rival]))[0] == 2.0)
    chk("phantom intent signal back",
        any("2 intent signals" in d for d in edges(top, r3)[1]))
finally:
    S.SPEED_DOMINANCE_BONUS_ENABLED = False
    S.UNKNOWN_HEADGEAR_BONUS_ENABLED = False
    S.OR_ABOVE_FIELD_INTENT_SIGNAL = False
chk("all three restored to corrected defaults",
    edges(dominant_field()[0], dominant_field()[1])[0] == 0.0
    and edges(hood, race_with([hood, rival]))[0] == 0.0
    and not any("2 intent signals" in d for d in edges(top, r3)[1]))

print("\n5. DIRECTION — the change can only ever LOWER a score")

cases = []
for lead in (0, 5, 10, 20, 30):
    s = Runner(name="X", rpr=100 + lead, official_rating=120,
               headgear="h", first_time_headgear=True, age=6, sex="gelding")
    f = [Runner(name=f"Y{i}", rpr=100, official_rating=95) for i in range(4)]
    rr = race_with([s] + f)
    off = edges(s, rr)[0]
    try:
        S.SPEED_DOMINANCE_BONUS_ENABLED = True
        S.UNKNOWN_HEADGEAR_BONUS_ENABLED = True
        S.OR_ABOVE_FIELD_INTENT_SIGNAL = True
        on = edges(s, rr)[0]
    finally:
        S.SPEED_DOMINANCE_BONUS_ENABLED = False
        S.UNKNOWN_HEADGEAR_BONUS_ENABLED = False
        S.OR_ABOVE_FIELD_INTENT_SIGNAL = False
    cases.append(off <= on)
chk("corrected score <= old score in every case", all(cases))

print()
print(f"RESULT: {sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
