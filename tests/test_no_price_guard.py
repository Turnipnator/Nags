"""CHECK 22 — a selection with no price is dropped (18 Sep 2026).

WHY: nothing stopped the judgement layer picking a runner the bookmakers had
not priced. It has happened 8 times, logged with odds_guide "CHECK PRICE",
including a 4pt NAP (Fillyoureye, 4 Apr, started 3/1F and lost): 12.5pt staked
for -7.6pt. A no-price pick is also invisible to every price gate -- the
sub-evens block, the 11/1 longshot filter and the 10/1 NAP cap all read its
price as 0 and wave it through, which is how a horse that went off 4/6 became
a NAP (Minnie Hauk, 4 May).

Shipped with the field_size reconciliation, which deliberately KEEPS unpriced
runners in the field, so the model now sees more of them: on 18 Sep, Ayr 15:40
would have shown 15 unpriced runners instead of none.

⚠ RunnerScore.total must match adjusted_score or the ANCHOR CLAMP pre-empts
the check under test (13 Aug method note).

Run:  python tests/test_no_price_guard.py
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


def sel(horse, odds, score=78, rank=1, nb=None):
    s = {"rank": rank, "horse": horse, "odds_guide": odds, "adjusted_score": score,
         "each_way": False, "reasoning": ["for and against"], "confidence": "",
         "danger": "", "next_best": {}, "course": "Ayr", "race_time": f"1{rank}:00",
         "race_name": f"Race {rank}"}
    if nb:
        s["next_best"] = {"horse": nb[0], "odds_guide": nb[1], "adjusted_score": nb[2],
                          "reasoning": "", "each_way": False}
    return s


def run(sels, nap_idx=0, flag=True):
    lookup, meta = {}, {}
    for s in sels:
        pairs = [(s["horse"], s["adjusted_score"], s["odds_guide"])]
        if s.get("next_best", {}).get("horse"):
            nb = s["next_best"]
            pairs.append((nb["horse"], nb["adjusted_score"], nb["odds_guide"]))
        for h, sc, od in pairs:
            r = Runner(name=h, odds=od if od != "CHECK PRICE" else None)
            r.sl_comment = "Sporting Life read present"
            lookup[h.lower()] = RunnerScore(runner=r, total=sc or 0)
        meta[s["race_name"].lower()] = {
            "num_runners": 10, "race_type": "Flat", "pattern": "", "distance": "6f",
            "race_class": "Class 2", "course": "Ayr", "race_time": s["race_time"],
            "surface": "Turf", "going": "Good", "going_detailed": "", "api_tip": "",
            "runners": [(p[0].lower(), A._parse_odds_to_decimal(p[2])) for p in pairs]
                       + [("filler a", 4.0), ("filler b", 8.0)],
            "top2_flag": False}
    d = {"selections": copy.deepcopy(sels), "nap_index": nap_idx, "compliance_log": []}
    old = A.NO_PRICE_SELECTION_DROP
    A.NO_PRICE_SELECTION_DROP = flag
    try:
        return A._enforce_compliance(d, lookup, meta)
    finally:
        A.NO_PRICE_SELECTION_DROP = old


def horses(out):
    return [s["horse"] for s in out["selections"]]


def notes(out):
    return out.get("compliance_log", [])


PRICED = sel("Priced Pick", "4/1", 78, 1)
SECOND = sel("Second Pick", "5/1", 76, 2)

print("\n1. A PRIMARY WITH NO PRICE IS DROPPED")
out = run([PRICED, SECOND, sel("No Price", "CHECK PRICE", 74, 3)])
chk("CHECK PRICE selection removed", "No Price" not in horses(out))
chk("priced selections untouched", horses(out) == ["Priced Pick", "Second Pick"])
chk("note names the horse", any("NO PRICE" in n and "No Price" in n for n in notes(out)))
out = run([PRICED, SECOND, sel("Blank", "", 74, 3)])
chk("empty odds selection removed", "Blank" not in horses(out))

print("\n2. THE FILLYOUREYE CASE — an unpriced NAP")
out = run([sel("Fillyoureye", "CHECK PRICE", 80, 1), SECOND], nap_idx=0)
chk("unpriced NAP dropped", "Fillyoureye" not in horses(out))
chk("nap_index remapped, never left pointing at a dropped pick",
    out["nap_index"] == -1 or horses(out)[out["nap_index"]] != "Fillyoureye")

print("\n3. RACE NBs TOO (Canary Island, Dunkeld Dreamer)")
out = run([sel("Priced Pick", "4/1", 78, 1, nb=("Canary Island", "CHECK PRICE", 66)), SECOND])
kept = out["selections"][0].get("next_best") or {}
chk("unpriced race NB cleared", kept.get("horse") != "Canary Island")
chk("note names the race NB", any("NO PRICE" in n and "Canary Island" in n for n in notes(out)))
out = run([sel("Priced Pick", "4/1", 78, 1, nb=("Real NB", "6/1", 66)), SECOND])
chk("priced race NB survives (no-regression)",
    (out["selections"][0].get("next_best") or {}).get("horse") == "Real NB")

print("\n4. PRICES THAT ARE NOT MISSING ARE NOT TOUCHED BY CHECK 22")
for price in ("Evens", "4/6", "11/10", "100/1", "1/2"):
    out = run([PRICED, sel("Edge Price", price, 72, 2)])
    fired = [n for n in notes(out) if "NO PRICE" in n and "Edge Price" in n]
    chk(f"{price}: CHECK 22 does not fire (other gates may still act)", fired == [])

print("\n5. FLAG OFF => pre-18-Sep behaviour")
out = run([PRICED, SECOND, sel("No Price", "CHECK PRICE", 74, 3)], flag=False)
chk("CHECK PRICE selection survives when the guard is off", "No Price" in horses(out))
chk("...and no NO PRICE note is written", not any("NO PRICE" in n for n in notes(out)))

print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
