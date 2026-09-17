"""No-NAP header wording (17 Sep 2026).

WHY: the no-NAP card said "Top pick scored 75/100 but the NAP was blocked by
the compliance gate" whenever the top score reached 75 -- including when the
gate had done nothing and the judgement model simply chose not to NAP. On the
17 Sep re-run Financer scored 75, the model declined the NAP (lowest-rated on
RPR), and the card blamed the gate. The gate can clear a NAP in nine places, so
the wrapper records the before/after nap_index instead of tracking each one.

⚠ RunnerScore.total must match adjusted_score or the ANCHOR CLAMP pre-empts
the check under test (13 Aug method note).

Run:  python tests/test_nap_header.py
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


def sel(horse, odds, score, time, name):
    return {"rank": 1, "horse": horse, "odds_guide": odds, "adjusted_score": score,
            "each_way": False, "reasoning": ["case for and against"], "confidence": "",
            "danger": "", "next_best": {}, "course": "Ayr", "race_time": time,
            "race_name": name}


def card(sels):
    lookup, meta = {}, {}
    for s in sels:
        r = Runner(name=s["horse"]); r.sl_comment = "Sporting Life read present"
        lookup[s["horse"].lower()] = RunnerScore(runner=r, total=s["adjusted_score"])
        meta[s["race_name"].lower()] = {
            "num_runners": 11, "race_type": "Flat", "pattern": "", "distance": "1m",
            "race_class": "Class 2", "course": "Ayr", "race_time": s["race_time"],
            "surface": "Turf", "going": "Good", "going_detailed": "", "api_tip": "",
            "runners": [(s["horse"].lower(), A._parse_odds_to_decimal(s["odds_guide"])),
                        ("filler a", 3.0), ("filler b", 5.0)],
            "top2_flag": False}
    return lookup, meta


def render(sels, nap_idx, blocked=None):
    d = {"selections": sels, "nap_index": nap_idx, "double": {}, "notes": "n",
         "compliance_log": []}
    if blocked is not None:
        d["nap_blocked_by_gate"] = blocked
    return A.format_selections_telegram(d)


FIN = sel("Financer", "10/1", 75, "15:00", "Ayr Handicap")
SEA = sel("Sea Lantern", "11/4", 70, "15:08", "Pontefract Handicap")
SEA["rank"] = 2

print("\n1. RENDERER")
msg = render([FIN, SEA], -1)
chk("model declined the NAP (no flag): does NOT blame the gate",
    "blocked by the compliance gate" not in msg)
chk("...and says no NAP was called", "no NAP was called" in msg)
msg = render([FIN, SEA], -1, blocked=False)
chk("flag False: does NOT blame the gate", "blocked by the compliance gate" not in msg)
msg = render([FIN, SEA], -1, blocked=True)
chk("flag True: says the gate blocked it", "blocked by the compliance gate" in msg)
low = dict(FIN, adjusted_score=72)
msg = render([low, SEA], -1)
chk("top score under 75: 'Nothing scored 75+'", "Nothing scored 75+" in msg)

print("\n2. _apply_compliance RECORDS WHETHER THE GATE REMOVED THE NAP")
lookup, meta = card([FIN, SEA])
out = A._apply_compliance({"selections": copy.deepcopy([FIN, SEA]), "nap_index": -1,
                           "compliance_log": []}, lookup, meta)
chk("model sent no NAP => flag False", out.get("nap_blocked_by_gate") is False)

capped = sel("Long Nap", "21/2", 80, "15:00", "Ayr Handicap")   # 10.5 > 10/1 cap, < F2 11/1
lookup, meta = card([capped, SEA])
out = A._apply_compliance({"selections": copy.deepcopy([capped, SEA]), "nap_index": 0,
                           "compliance_log": []}, lookup, meta)
chk("NAP at 21/2 is cleared by the NAP price cap", out.get("nap_index", 0) < 0)
chk("...and the flag records the gate did it", out.get("nap_blocked_by_gate") is True)

ok_nap = sel("Good Nap", "3/1", 80, "15:00", "Ayr Handicap")
lookup, meta = card([ok_nap, SEA])
out = A._apply_compliance({"selections": copy.deepcopy([ok_nap, SEA]), "nap_index": 0,
                           "compliance_log": []}, lookup, meta)
chk("a NAP the gate keeps => nap_index 0 is NOT read as blocked",
    out.get("nap_index") == 0 and out.get("nap_blocked_by_gate") is False)

print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
