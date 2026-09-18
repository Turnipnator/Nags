"""field_size reconciliation (18 Sep 2026) — the API's own count decides the field.

WHY: an early /run exposed both pre-NR-flag heuristics. On 18 Sep at 08:09 London:
  * Ayr 15:40 Bronze Cup -- 24 runners, field_size 24, only 9 PRICED. The price
    rule ("unpriced while a rival is priced = withdrawn") dropped 15 real
    runners and the race reached judgement scored as a 9-runner handicap.
  * Newbury 17:17 -- 30 runners, field_size 30, NOTHING priced, 16 with no
    jockey declared yet. The jockey rule dropped those 16.
Neither horse was withdrawn; the market simply had not opened.

THE RULE: drop NR-flagged runners first (they are named by the API). Then, only
if the card still holds MORE runners than field_size AND the unpriced runners
exactly account for that surplus, drop those. Otherwise keep everyone and let
the existing mismatch warning fire. Measured on 6,549 cached races: runner
lists change in 7 races, every one a case where the old code dropped a horse
that RAN; the 3 genuine catches (1 Jun, card > field_size) still fire.

Run:  python tests/test_field_size_reconcile.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("RACING_API_USERNAME", "x")
os.environ.setdefault("RACING_API_PASSWORD", "x")

import src.scraper as S  # noqa: E402

results = []


def chk(label, cond):
    results.append(bool(cond))
    print(f"   {'PASS' if cond else 'FAIL'}  {label}")


def odds(priced):
    if not priced:
        return [{"bookmaker": "Bet365", "fractional": "-", "decimal": "-"}]
    return [{"bookmaker": "Bet365", "fractional": "6/1", "decimal": "7.0"}]


def runner(name, number, priced=True, jockey="A Jockey"):
    return {"horse": name, "number": number, "jockey": jockey, "lbs": "130",
            "odds": odds(priced), "form": "1234"}


def race(runners, field_size):
    return {"race_name": "Test Handicap", "course": "Ayr", "type": "Flat",
            "off_dt": "2026-09-18T15:40:00+01:00", "race_class": "Class 2",
            "distance": "6f", "runners": runners,
            "field_size": "" if field_size is None else str(field_size)}


sc = S.Scraper()


def kept(data):
    return [r.name for r in sc._parse_race(data).runners]


# ── The two live cases from 18 Sep ───────────────────────────────────────────
AYR = [runner(f"Priced {i}", i + 1) for i in range(9)] + \
      [runner(f"Unpriced {i}", i + 10, priced=False) for i in range(15)] + \
      [runner("Rikki Tiki Tavi", "NR", priced=False, jockey="")]
NEWBURY = [runner(f"NoJockey {i}", i + 1, priced=False, jockey="") for i in range(16)] + \
          [runner(f"Declared {i}", i + 17, priced=False) for i in range(14)]

print("\n1. AYR 15:40 — 24 runners, field_size 24, only 9 priced")
out = kept(race(AYR, 24))
chk("all 24 real runners kept (was 9)", len(out) == 24)
chk("the NR-flagged horse is still dropped", "Rikki Tiki Tavi" not in out)
chk("an unpriced runner is kept", "Unpriced 0" in out)

print("\n2. NEWBURY 17:17 — 30 runners, field_size 30, none priced, 16 jockey-less")
out = kept(race(NEWBURY, 30))
chk("all 30 kept (was 14)", len(out) == 30)
chk("a runner with no jockey declared is kept", "NoJockey 0" in out)

print("\n3. GENUINE CATCH KEPT — card 9, field_size 7, exactly 2 unpriced (1 Jun)")
jun = [runner(f"Runs {i}", i + 1) for i in range(7)] + \
      [runner("Chasing Gold", 8, priced=False), runner("Tomarlo", 9, priced=False)]
out = kept(race(jun, 7))
chk("the 2 unpriced are dropped — the API says 7 run", len(out) == 7)
chk("Chasing Gold and Tomarlo gone",
    "Chasing Gold" not in out and "Tomarlo" not in out)

print("\n4. UNRECONCILABLE SURPLUS => KEEP ALL (the Irish self-inconsistency)")
irish = [runner(f"R{i}", i + 1) for i in range(14)]          # all priced
out = kept(race(irish, 13))
chk("surplus 1 but nothing unpriced => all 14 kept, warning fires", len(out) == 14)
mixed = [runner(f"R{i}", i + 1) for i in range(12)] + \
        [runner("U1", 13, priced=False), runner("U2", 14, priced=False)]
out = kept(race(mixed, 13))
chk("surplus 1 but 2 unpriced (can't tell which) => all 14 kept", len(out) == 14)

print("\n5. FAILS OPEN")
chk("no field_size => every non-NR runner kept", len(kept(race(AYR, None))) == 24)
chk("field_size matches and all priced => unchanged",
    len(kept(race([runner(f"R{i}", i + 1) for i in range(8)], 8))) == 8)

print("\n6. FLAG OFF => the pre-18-Sep behaviour, exactly")
old = S.FIELD_SIZE_RECONCILE_ENABLED
S.FIELD_SIZE_RECONCILE_ENABLED = False
try:
    chk("Ayr: price rule drops the 15 unpriced again (9 kept)",
        len(kept(race(AYR, 24))) == 9)
    chk("Newbury: jockey rule drops the 16 again (14 kept)",
        len(kept(race(NEWBURY, 30))) == 14)
    chk("1 Jun catch unchanged (7 kept)", len(kept(race(jun, 7))) == 7)
finally:
    S.FIELD_SIZE_RECONCILE_ENABLED = old

print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
