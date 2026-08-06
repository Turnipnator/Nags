"""Tests for the 6 Aug 2026 C5/C6 rule retirement.

Six rules were removed because the class floor (Option X, 9 May 2026) blocks
every Class 5/6 race at race-ranking, so none of them could reach a bet:

  Drift 1  _score_course C5/6 decay          (12/9/6/5 instead of 15/12/8/5)
  Drift 2  _score_class  C5/6 caps           (8/7/6/5/3 instead of 12/10/8/6/4)
  Drift 3  _score_edges  Flat C5/6 long-absence penalty
  Drift 4  system-prompt rule 14 (C5/6 Spotlight red-flag downgrade)
  CHECK 8  AW C5/6 weight-rise blocker
  CHECK 9  AW C5/6 no-NAP-on-favourite

They were superseded ONE DAY after being written and nobody noticed for three
months. Measured C5/6 x floor-pass = 0 across 209 real races.

⚠ The retirement is NOT score-neutral: 534 Class 5/6 runners score HIGHER
without the deflation. It is neutral where it matters — verified end-to-end
over 1-6 Aug 2026: same 25 races reach judgement, same order, no top scorer
changed inside any qualifying race, ZERO moved runners in the live path.

CHECK 10 deliberately SURVIVES: the 30 Jun 2026 generalisation made it fire at
all classes (82 score / 9.0 odds), so it is a live gate, not a C5/6 rule.

Run: python tests/test_c56_retirement.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.analyst as A  # noqa: E402
import src.scorer as S  # noqa: E402
from src.scorer import Scorer  # noqa: E402
from src.scraper import Race, Runner  # noqa: E402

results = []


def chk(label, cond):
    results.append(bool(cond))
    print(f"   {'PASS' if cond else 'FAIL'}  {label}")


sc = Scorer()


def race(cls, rtype="Flat", **kw):
    kw.setdefault("runners", [])
    return Race(time="19:30", name="Test Handicap", course="Southwell (AW)",
                distance="1m", race_type=rtype, race_class=cls, going="Standard",
                surface="All-Weather", **kw)


print("\n1. THE RETIRED HELPERS ARE GONE")

for name in ("_is_c5_or_c6",):
    chk(f"scorer.{name} removed", not hasattr(S, name))
for name in ("_is_aw_course", "_is_aw_c5_or_c6_handicap",
             "_extract_weight_rise_lb", "_RISE_PATTERNS",
             "_AW_ONLY_COURSES", "_DUAL_AW_COURSES"):
    chk(f"analyst.{name} removed", not hasattr(A, name))

print("\n2. WHAT SURVIVES MUST SURVIVE")

chk("analyst._is_c5_or_c6_any KEPT (CHECK 10 uses it)",
    hasattr(A, "_is_c5_or_c6_any"))
chk("analyst._is_premium_race KEPT (F3 uses it)",
    hasattr(A, "_is_premium_race"))
chk("CHECK 10 general gate constants intact",
    hasattr(A, "GENERAL_GATE_SCORE") and hasattr(A, "GENERAL_GATE_ODDS"))
chk("CHECK 10 general score floor is 82", A.GENERAL_GATE_SCORE == 82)
chk("CHECK 10 odds floor is 9.0", A.GENERAL_GATE_ODDS == 9.0)
chk("_is_c5_or_c6_any still identifies a Class 5 race",
    A._is_c5_or_c6_any({"race_class": "Class 5"}) is True)

print("\n3. THE CLASS FLOOR — the reason all six were unreachable")

chk("Flat Class 5 blocked", A._meets_class_floor(race("Class 5")) is False)
chk("Flat Class 6 blocked", A._meets_class_floor(race("Class 6")) is False)
chk("Flat Class 7 blocked", A._meets_class_floor(race("Class 7")) is False)
chk("NH Class 5 blocked",
    A._meets_class_floor(race("Class 5", "Hurdle")) is False)
chk("NH Class 4 blocked",
    A._meets_class_floor(race("Class 4", "Chase")) is False)
chk("Flat Class 4 PASSES", A._meets_class_floor(race("Class 4")) is True)
chk("NH Class 3 PASSES",
    A._meets_class_floor(race("Class 3", "Hurdle")) is True)
chk("Group race PASSES",
    A._meets_class_floor(race("Class 1", pattern="Group 3")) is True)

print("\n4. THE DEFLATION IS GONE — C5/6 now scores on the standard scale")

# Drift 1: course bonus. Was capped 12/9/6/5 in C5/6; now the full 15/12/8/5.
cd = Runner(name="CD", cd_winner=True, course_winner=True, distance_winner=True)
cw = Runner(name="CW", course_winner=True)
dw = Runner(name="DW", distance_winner=True)
for r5, r4, label in ((cd, cd, "C&D winner"), (cw, cw, "course winner"),
                      (dw, dw, "distance winner")):
    a = sc._score_course(r5, race("Class 5"))
    b = sc._score_course(r4, race("Class 4"))
    chk(f"Drift 1 gone: {label} scores the same in C5 and C4 ({a})", a == b)
chk("Drift 1 gone: C&D winner gets the full 15",
    sc._score_course(cd, race("Class 5")) == 15.0)

# Drift 2: class score. Was capped at 8 for top-rated in C5/6; now 12.
top = Runner(name="Top", rpr=100)
field = [top] + [Runner(name=f"F{i}", rpr=80) for i in range(4)]
r5 = race("Class 5", runners=field)
r4 = race("Class 4", runners=field)
chk("Drift 2 gone: top-rated scores 12 in a Class 5",
    sc._score_class(top, r5) == 12.0)
chk("Drift 2 gone: Class 5 and Class 4 class scores match",
    sc._score_class(top, r5) == sc._score_class(top, r4))

# Drift 3: Flat C5/6 long-absence penalty.
from src.scorer import RunnerScore  # noqa: E402
absent = Runner(name="Absent", days_since_run=200, rpr=90)
r5b = race("Class 5", runners=[absent, Runner(name="O", rpr=90)])
sco = RunnerScore(runner=absent)
sc._score_edges(absent, r5b, sco)
chk("Drift 3 gone: no Flat C5/C6 long-absence penalty line",
    not any("C5/C6" in d for d in sco.edge_details))

print("\n5. CHECK NUMBERS 8 AND 9 ARE GAPS, NOT REUSED")

src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "src", "analyst.py")).read()
chk("no '# CHECK 8:' block remains", "# CHECK 8:" not in src)
chk("no '# CHECK 9:' block remains", "# CHECK 9:" not in src)
chk("CHECK 10 still present", "# CHECK 10:" in src)
chk("a retirement note explains the gap", "RETIRED on 6 Aug 2026" in src)

print("\n6. THE LLM PROMPT NO LONGER INSTRUCTS ON RULES IT CANNOT APPLY")

chk("prompt rule 12 (AW C5/6 weight-rise) removed",
    "12. AW CLASS 5/6 WEIGHT-RISE BLOCKER" not in src)
chk("prompt rule 13 (AW C5/6 no-NAP-on-fav) removed",
    "13. AW CLASS 5/6 NO-NAP-ON-FAVOURITE" not in src)
chk("prompt rule 14 (C5/6 Spotlight red flags) removed",
    "14. C5/C6 SPOTLIGHT RED-FLAG DOWNGRADE" not in src)
chk("judgement-block AW C5/6 rules removed",
    "5. AW CLASS 5/6 TARGETED RULES" not in src)
chk("checklist line removed", "CHECK 5 AW C5/6" not in src)
chk("prompt rule 16 (class floor) KEPT — it is the live rule",
    "16. CLASS FLOOR FOR BOT SELECTIONS" in src)
chk("prompt rule 15 (score-vs-market gate) KEPT — CHECK 10 is live",
    "15. C5/C6 SCORE-VS-MARKET GATE" in src)

print()
print(f"RESULT: {sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
