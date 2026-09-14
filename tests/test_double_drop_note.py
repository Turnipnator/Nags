"""CHECK 15 — the DOUBLE DROPPED note must name the REAL reason (14 Sep 2026).

WHY IT EXISTS: _rebuild_double clears the double for TWO different reasons —
(a) there is no NAP (the renderer gates on nap_index >= 0), or (b) there IS a
NAP but no eligible second leg (every other selection was dropped by the gate,
or is odds-on). CHECK 15 labelled both "no NAP today". Caught in the 14 Sep 2026
offline opus-4.8 replay: 4.8 filed Song Of The Clouds as National Honour's
cross-race NB, CHECK 0b stripped it, the card was NAP-only — and the log read
"double dropped (no NAP)" beside a live NAP. The same text reaches the card notes.

SCOPE UNDER TEST (wording only — no selection, stake or nap_index may change):
  1. NAP + nothing else, stale double   -> "no second leg", names the NAP, never "no NAP"
  2. no NAP, stale double               -> "no NAP today" (unchanged)
  3. NAP + only an odds-on other pick   -> "no second leg", never "no NAP"
  4. stale double pointing at wrong leg -> "DOUBLE REBUILT" (unchanged)
  5. double already correct            -> no double note at all (unchanged)
  6. no square brackets in any note (Telegram eats them)

⚠ RunnerScore.total MUST match adjusted_score or the ANCHOR CLAMP (CHECK 0)
pre-empts the check under test (see the 13 Aug method note).

Run:  python tests/test_double_drop_note.py
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


def _sel(horse, odds, score, course, time, name):
    return {"horse": horse, "odds_guide": odds, "adjusted_score": score, "each_way": False,
            "reasoning": [], "confidence": "", "danger": "", "next_best": {},
            "course": course, "race_time": time, "race_name": name}


def _run(sels, nap_idx, double):
    lookup, meta = {}, {}
    for s in sels:
        r = Runner(name=s["horse"]); r.sl_comment = ""
        lookup[s["horse"].lower()] = RunnerScore(runner=r, total=s["adjusted_score"])
        meta[s["race_name"].lower()] = {
            "num_runners": 9, "race_type": "Flat", "pattern": "", "distance": "7f",
            "race_class": "Class 4", "course": s["course"], "race_time": s["race_time"],
            "surface": "AW", "going": "Standard", "going_detailed": "", "api_tip": "",
            "runners": [(s["horse"].lower(), 6.0), ("filler a", 6.0), ("filler b", 6.0)],
            "top2_flag": False, "_name": s["race_name"]}
    d = {"selections": copy.deepcopy(sels), "nap_index": nap_idx,
         "double": dict(double), "compliance_log": []}
    return A._enforce_compliance(d, lookup, meta)


def double_notes(out):
    return [n for n in out.get("compliance_log", []) if "DOUBLE" in n]


NH = _sel("National Honour", "15/8", 78, "Kempton (AW)", "18:30", "Kempton Novice Stakes")
SOTC = _sel("Song Of The Clouds", "9/4", 72, "Windsor", "14:42", "Windsor Novice Stakes")
# _rebuild_double writes legs as "Horse (time course)" — match it, or an already
# correct double reads as stale and CHECK 15 logs a spurious DOUBLE REBUILT.
NH_LEG = "National Honour (18:30 Kempton (AW))"
SOTC_LEG = "Song Of The Clouds (14:42 Windsor)"
STALE = {"leg1": NH_LEG, "leg2": SOTC_LEG}
ODDS_ON_DOUBLE = {"leg1": NH_LEG, "leg2": "Short Thing (14:42 Windsor)"}

print("\n1. NAP and nothing else (the 14 Sep 4.8 replay card) -> 'no second leg', never 'no NAP'")
out = _run([NH], 0, STALE)
dn = double_notes(out)
chk("double cleared", not (out.get("double") or {}).get("leg1"))
chk("exactly one DOUBLE note", len(dn) == 1)
chk("note says DOUBLE DROPPED", dn and "DOUBLE DROPPED" in dn[0])
chk("note says no second leg", dn and "no second leg" in dn[0])
chk("note names the NAP", dn and "National Honour" in dn[0])
chk("note does NOT claim there is no NAP", dn and "no NAP" not in dn[0])
chk("nap_index untouched", out["nap_index"] == 0)

print("\n2. NO NAP, stale double -> 'no NAP today' (unchanged)")
out = _run([SOTC], -1, STALE)
dn = double_notes(out)
chk("double cleared", not (out.get("double") or {}).get("leg1"))
chk("note says no NAP today", len(dn) == 1 and "DOUBLE DROPPED: no NAP today" in dn[0])

print("\n3. NAP + only an odds-on other pick -> 'no second leg', never 'no NAP'")
odds_on = _sel("Short Thing", "4/5", 72, "Windsor", "14:42", "Windsor Novice Stakes")
out = _run([NH, odds_on], 0, ODDS_ON_DOUBLE)
dn = double_notes(out)
chk("double cleared (odds-on leg not eligible)", not (out.get("double") or {}).get("leg1"))
chk("note says no second leg", len(dn) == 1 and "no second leg" in dn[0])
chk("note does NOT claim there is no NAP", dn and "no NAP" not in dn[0])

print("\n4. Stale double pointing at the wrong leg -> DOUBLE REBUILT (unchanged)")
out = _run([NH, SOTC], 0, {"leg1": NH_LEG, "leg2": "Somebody Else (18:30 Kempton (AW))"})
dn = double_notes(out)
chk("double rebuilt to the real second selection",
    ((out.get("double") or {}).get("leg2") or "").startswith("Song Of The Clouds"))
chk("note says DOUBLE REBUILT, not DROPPED", len(dn) == 1 and "DOUBLE REBUILT" in dn[0])

print("\n5. Double already correct -> no double note (unchanged)")
out = _run([NH, SOTC], 0, STALE)
chk("no DOUBLE note", double_notes(out) == [])
chk("double intact", (out.get("double") or {}).get("leg2") == SOTC_LEG)

print("\n6. No square brackets inside any double note text (Telegram)")
all_notes = []
for sels, nap, dbl in ([[NH], 0, STALE], [[SOTC], -1, STALE],
                       [[NH, odds_on], 0, ODDS_ON_DOUBLE]):
    all_notes += [n.replace("[GATE FIX] ", "", 1) for n in double_notes(_run(sels, nap, dbl))]
chk("no [ or ] in note bodies", all_notes and not any("[" in n or "]" in n for n in all_notes))

print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
