import copy
import importlib
import sys

import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config.settings as S


def build():
    """NAP = Captain Cool 13/8 in a Class 2 (premium). Pick 2 = 5/1 Class 5."""
    sels = {
        "selections": [
            {"horse": "Captain Cool", "odds_guide": "13/8", "adjusted_score": 82,
             "race_time": "15:58", "course": "Stratford", "each_way": True,
             "race_name": "Silver Fox Classic Handicap Steeple Chase",
             "next_best": {}, "reasoning": []},
            {"horse": "Big Gossey", "odds_guide": "5/1", "adjusted_score": 74,
             "race_time": "15:15", "course": "Curragh", "each_way": True,
             "race_name": "Minstrel Stakes", "next_best": {}, "reasoning": []},
        ],
        "nap_index": 0,
    }
    lookup = {
        "silver fox classic handicap steeple chase": {
            "num_runners": 5, "race_type": "Chase", "pattern": "",
            "race_class": "Class 2", "course": "Stratford", "race_time": "15:58",
            "surface": "Turf", "going": "Good", "going_detailed": "", "distance": "2m",
            "api_tip": "", "runners": [("captain cool", 1.625), ("in the air", 2.75)],
        },
        "minstrel stakes": {
            "num_runners": 7, "race_type": "Flat", "pattern": "",
            "race_class": "Class 5", "course": "Curragh", "race_time": "15:15",
            "surface": "Turf", "going": "Good", "going_detailed": "", "distance": "7f",
            "api_tip": "", "runners": [("big gossey", 5.0)],
        },
    }
    return sels, lookup


def run(env):
    for k, v in env.items():
        setattr(S, k, v)
    import src.analyst as A
    importlib.reload(A)
    sels, lookup = build()
    out = A._enforce_compliance(copy.deepcopy(sels), {}, lookup)
    return out if isinstance(out, dict) else sels


results = []


def chk(name, cond):
    print(("  PASS  " if cond else "  FAIL  ") + name)
    results.append(cond)


BASE = dict(FILTER_SHADOW_MODE=False,
            FILTER_LONGSHOT_ENABLED=True, FILTER_LONGSHOT_SHADOW=False,
            FILTER_HIGHSCORE_ENABLED=True, FILTER_HIGHSCORE_SHADOW=True,
            FILTER_SHORTNAP_ENABLED=True, SHORTNAP_MIN_ODDS=4.0)

print("1. F3 OFF entirely (baseline)")
off = run({**BASE, "FILTER_SHORTNAP_ENABLED": False, "FILTER_SHORTNAP_SHADOW": True})

print("2. F3 SHADOW — must be byte-identical to baseline")
shadow = run({**BASE, "FILTER_SHORTNAP_SHADOW": True})
chk("nap_index unchanged (0)", shadow.get("nap_index") == 0)
chk("selection count unchanged", len(shadow["selections"]) == len(off["selections"]))
chk("NAP not demoted", not shadow["selections"][0].get("nb_price_capped"))
sh_cmp = copy.deepcopy(shadow); off_cmp = copy.deepcopy(off)
for d in (sh_cmp, off_cmp):
    d.pop("filter_shadow_log", None)
chk("gate output byte-identical to F3-off", sh_cmp == off_cmp)
log = " ".join(shadow.get("filter_shadow_log", []))
chk("but it DID log the detection", "F3 SHORT-PREMIUM-NAP" in log and "Captain Cool" in log)
chk("logged with SHADOW prefix", "[FILTER-SHADOW]" in log)

print("3. F3 LIVE — must demote the NAP")
live = run({**BASE, "FILTER_SHORTNAP_SHADOW": False})
chk("NAP cleared (nap_index -1)", live.get("nap_index") == -1)
chk("NAP demoted to race SEL stake", live["selections"][0].get("nb_price_capped") is True)
chk("selection NOT dropped (demote, not drop)", len(live["selections"]) == 2)
chk("logged with LIVE prefix", "[FILTER]" in " ".join(live.get("filter_shadow_log", [])))

print("4. non-premium short NAP must NOT fire (Class 5)")
sels, lookup = build()
sels["selections"][0]["race_name"] = "Minstrel Stakes"
sels["selections"][0]["race_time"] = "15:15"
sels["selections"][0]["course"] = "Curragh"
for k, v in {**BASE, "FILTER_SHORTNAP_SHADOW": False}.items():
    setattr(S, k, v)
import src.analyst as A
importlib.reload(A)
o = A._enforce_compliance(copy.deepcopy(sels), {}, lookup)
chk("Class 5 short NAP untouched", o.get("nap_index") == 0)

print("5. LONG-priced premium NAP must NOT fire (7/1)")
sels, lookup = build()
sels["selections"][0]["odds_guide"] = "7/1"
o = A._enforce_compliance(copy.deepcopy(sels), {}, lookup)
chk("7/1 premium NAP untouched", o.get("nap_index") == 0)

print("6. premium detection via `pattern` (Group 2, race_class='Class 1')")
sels, lookup = build()
lookup["silver fox classic handicap steeple chase"]["pattern"] = "Group 2"
lookup["silver fox classic handicap steeple chase"]["race_class"] = "Class 1"
o = A._enforce_compliance(copy.deepcopy(sels), {}, lookup)
chk("Group 2 short NAP demoted", o.get("nap_index") == -1)

print("7. unresolvable race must FAIL OPEN")
sels, lookup = build()
sels["selections"][0]["race_name"] = "Nonexistent Race"
sels["selections"][0]["course"] = "Nowhere"
sels["selections"][0]["race_time"] = "99:99"
o = A._enforce_compliance(copy.deepcopy(sels), {}, lookup)
chk("unresolvable race keeps its NAP", o.get("nap_index") == 0)

print("8. non-NAP short premium selection must NOT fire")
sels, lookup = build()
sels["nap_index"] = 1                      # NAP is now the 5/1 Curragh pick
sels["selections"][1]["adjusted_score"] = 78   # >=75 so the NAP survives the
                                               # Operating Policy threshold and
                                               # we isolate F3's behaviour alone
o = A._enforce_compliance(copy.deepcopy(sels), {}, lookup)
chk("short premium NON-nap not demoted", not o["selections"][0].get("nb_price_capped"))
chk("F3 did not fire at all", "F3 SHORT-PREMIUM-NAP" not in
    " ".join(o.get("filter_shadow_log", []) or []))
chk("its NAP survives", o.get("nap_index") == 1)

print("9. master kill-switch reverts F3")
o = run({**BASE, "FILTER_SHORTNAP_SHADOW": False, "FILTER_SHADOW_MODE": True})
chk("FILTER_SHADOW_MODE=true suppresses F3", o.get("nap_index") == 0)

print()
print(f"RESULT: {sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
