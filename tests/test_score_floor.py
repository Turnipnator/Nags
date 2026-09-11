"""CHECK 21 — score floor on every slot (11 Sep 2026).

WHY IT EXISTS: CHECK 13 floored the NB-of-day slot only. On 8 Sep 2026 a 61
(Spring Bloom) was saved as a full 1pt E/W selection because the market swap
fired between a 63 and a 61 and no other slot had a floor; on 11 Sep a 41
(Nightime Dancer) was saved as a race NB. Operating Policy: below 70 is not a
selection, below 55 is a pass.

SCOPE UNDER TEST:
  1. primary 55-69 -> demoted (nb_price_capped, E/W forced where 5+ runners)
  2. primary < 55  -> DROPPED, nap_index remapped, double rebuilt
  3. race NB < 55  -> dropped; race NB 55-64 untouched (+15.8% n=13, keep)
  4. NB-of-day 66  -> CHECK 13 owns it: exactly one demote note
  5. missing score -> fail open
  6. flag off / clean card -> byte-identical (no-regression)
  7. F2 still drops >= 11/1 through the shared helper

⚠ RunnerScore.total MUST match adjusted_score or the ANCHOR CLAMP (CHECK 0)
pre-empts the check under test (see the 13 Aug method note).

Run:  python tests/test_score_floor.py
"""
import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("RACING_API_USERNAME", "x")
os.environ.setdefault("RACING_API_PASSWORD", "x")

import src.analyst as A  # noqa: E402
from src.scraper import Runner  # noqa: E402
from src.scorer import RunnerScore  # noqa: E402

results = []


def chk(label, cond):
    results.append(bool(cond))
    print(f"   {'PASS' if cond else 'FAIL'}  {label}")


def _race(course, time, name, runners):
    return {"num_runners": 8, "race_type": "Flat", "pattern": "", "distance": "1m",
            "race_class": "Class 3", "course": course, "race_time": time, "surface": "Turf",
            "going": "Good", "going_detailed": "", "api_tip": "",
            "runners": [(n.lower(), 6.0) for n in runners], "top2_flag": False, "_name": name}


def _sel(horse, odds, score, course, time, name, nb=None):
    s = {"horse": horse, "odds_guide": odds, "adjusted_score": score, "each_way": False,
         "reasoning": [], "confidence": "", "danger": "", "next_best": {},
         "course": course, "race_time": time, "race_name": name}
    if nb:
        s["next_best"] = {"horse": nb[0], "odds_guide": nb[1], "adjusted_score": nb[2],
                          "reasoning": "", "each_way": False}
    return s


def _card(sels):
    lookup, meta = {}, {}
    for s in sels:
        for h, sc in [(s["horse"], s["adjusted_score"])] + (
                [(s["next_best"]["horse"], s["next_best"]["adjusted_score"])] if s.get("next_best") else []):
            r = Runner(name=h); r.sl_comment = ""
            lookup[h.lower()] = RunnerScore(runner=r, total=sc or 0)
        names = [s["horse"]] + ([s["next_best"]["horse"]] if s.get("next_best") else []) + ["Filler A", "Filler B"]
        m = _race(s["course"], s["race_time"], s["race_name"], names)
        meta[s["race_name"].lower()] = m
    return lookup, meta


def _run(sels, nap_idx, flag=True):
    lookup, meta = _card(sels)
    d = {"selections": copy.deepcopy(sels), "nap_index": nap_idx, "compliance_log": []}
    old = A.SCORE_FLOOR_ALL_SLOTS
    A.SCORE_FLOOR_ALL_SLOTS = flag
    try:
        return A._enforce_compliance(d, lookup, meta)
    finally:
        A.SCORE_FLOOR_ALL_SLOTS = old


NAP = _sel("Big Nap", "4/1", 79, "York", "2:00", "York Stakes A", ("Nap Rival", "8/1", 70))
NBD = _sel("Day Nb", "9/4", 72, "York", "2:35", "York Stakes B", ("Nb Rival", "7/1", 66))


def notes(out):
    return out.get("compliance_log", [])


print("\n1. PRIMARY 55-69 -> demoted to 0.75pt, E/W forced (the Spring Bloom case)")
low = _sel("Spring Bloom", "3/1", 61, "Goodwood", "3:15", "Goodwood Hcap", ("U S S Charleston", "5/1", 63))
out = _run([NAP, NBD, low], 0)
sb = next(s for s in out["selections"] if s["horse"] == "Spring Bloom")
chk("61 selection kept on the card", sb is not None)
chk("...but flagged nb_price_capped (0.75pt stake)", sb.get("nb_price_capped") is True)
chk("...and E/W forced on (8 runners)", sb.get("each_way") is True)
chk("SCORE FLOOR note in the compliance log", any("SCORE FLOOR" in n and "Spring Bloom" in n for n in notes(out)))
chk("race NB at 63 (55-64) untouched", sb["next_best"].get("horse") == "U S S Charleston")
chk("NAP untouched", out["nap_index"] == 0 and out["selections"][0].get("nb_price_capped") is not True)

print("\n2. PRIMARY < 55 -> DROPPED, nap_index remapped, double consistent")
bad = _sel("No Hoper", "5/1", 54, "Ayr", "4:00", "Ayr Hcap")
out = _run([NAP, NBD, bad], 0)
chk("54 selection removed from the card", all(s["horse"] != "No Hoper" for s in out["selections"]))
chk("card is now 2 picks", len(out["selections"]) == 2)
chk("DROPPED note logged", any("SCORE FLOOR" in n and "No Hoper" in n and "DROPPED" in n for n in notes(out)))
chk("nap_index still points at the NAP", out["nap_index"] == 0 and out["selections"][0]["horse"] == "Big Nap")
out = _run([bad, NBD, NAP], 2)
chk("NAP at index 2 remaps to 1 after the drop", out["nap_index"] == 1 and out["selections"][1]["horse"] == "Big Nap")

print("\n3. RACE NB < 55 -> dropped (the Nightime Dancer case); 55-64 kept")
weak_nb = _sel("Solid Sel", "7/2", 74, "Salisbury", "5:58", "Salisbury Hcap", ("Nightime Dancer", "12/1", 41))
out = _run([NAP, NBD, weak_nb], 0)
ss = next(s for s in out["selections"] if s["horse"] == "Solid Sel")
chk("41 race NB blanked", not ss["next_best"])
chk("its primary (74) untouched", ss.get("nb_price_capped") is not True)
chk("RACE NB note logged", any("SCORE FLOOR" in n and "Nightime Dancer" in n for n in notes(out)))
ok_nb = _sel("Solid Sel", "7/2", 74, "Salisbury", "5:58", "Salisbury Hcap", ("Race To The Stars", "9/4", 60))
out = _run([NAP, NBD, ok_nb], 0)
chk("60 race NB kept (no floor at 65)", out["selections"][2]["next_best"].get("horse") == "Race To The Stars")

print("\n4. NB-OF-DAY 66 -> CHECK 13 owns it: demoted once, one note")
nbd66 = _sel("Day Nb", "9/4", 66, "York", "2:35", "York Stakes B")
out = _run([NAP, nbd66, weak_nb], 0)
chk("NB-of-day demoted", out["selections"][1].get("nb_price_capped") is True)
chk("exactly one demote note for it", sum(1 for n in notes(out) if "Day Nb" in n and ("FLOOR" in n)) == 1)

print("\n5. MISSING score -> fail open")
nos = _sel("Unknown", "5/1", 0, "Ayr", "4:00", "Ayr Hcap")   # 0 = "no score" in this codebase (`or 0` everywhere)
out = _run([NAP, NBD, nos], 0)
chk("zero/missing score: kept, not demoted", len(out["selections"]) == 3 and out["selections"][2].get("nb_price_capped") is not True)

print("\n6. NO-REGRESSION: clean card byte-identical with flag on/off; flag off leaves a 61 alone")
clean = [NAP, NBD, _sel("Third", "5/1", 71, "Ayr", "4:00", "Ayr Hcap", ("Third Nb", "9/1", 66))]
on, off = _run(clean, 0, True), _run(clean, 0, False)
chk("clean card: gate output identical flag on vs off", on == off)
out = _run([NAP, NBD, low], 0, False)
chk("flag OFF: 61 selection not demoted (old behaviour)", out["selections"][2].get("nb_price_capped") is not True)

print("\n7. F2 LONGSHOT still drops >= 11/1 via the shared helper")
longshot = _sel("Long Shot", "12/1", 74, "Ayr", "4:00", "Ayr Hcap")
_e, _s, _m = A.FILTER_LONGSHOT_ENABLED, A.FILTER_LONGSHOT_SHADOW, A.FILTER_SHADOW_MODE
try:
    A.FILTER_LONGSHOT_ENABLED, A.FILTER_LONGSHOT_SHADOW, A.FILTER_SHADOW_MODE = True, False, False
    out = _run([longshot, NBD, NAP], 2)
    chk("12/1 dropped", all(s["horse"] != "Long Shot" for s in out["selections"]))
    chk("nap_index remapped 2 -> 1", out["nap_index"] == 1 and out["selections"][1]["horse"] == "Big Nap")
    chk("F2 note intact", any("F2 LONGSHOT" in n and "dropped" in n for n in notes(out)))
finally:
    A.FILTER_LONGSHOT_ENABLED, A.FILTER_LONGSHOT_SHADOW, A.FILTER_SHADOW_MODE = _e, _s, _m

print(f"\nRESULT: {sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
