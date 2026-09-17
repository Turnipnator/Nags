"""NR saddle-cloth flag (17 Sep 2026).

WHY: the 9 Jul 2026 non-runner filter treats a runner as withdrawn only when
NO bookmaker quotes it. From 17 Aug 2026 the Racing API keeps stale prices on
withdrawn horses (0-4 a day still priced before; ~94% of them after), so the
filter stopped catching them. On the 17 Sep 10:05 run, 16 of 39 races were
scored with withdrawn horses still in the field (24 horses; Bet365 itself still
quoted 12). 20 of the 65 races the bot bet in since 17 Aug carried at least one.

What the API DOES do is replace the saddle-cloth number with "NR". Across
5,349 NR-flagged runners (Apr-Sep 2026 harvest) not one appears in a result.
Reserves keep an R-number ("R17") and DO run (68 of 68) -- they must be kept.

THE RULE: withdrawn = number is "NR"  OR  (unpriced while a rival is priced).

Run:  python tests/test_nr_flag.py
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


def odds(dec, books=29, quoting=None):
    """A bookmaker odds array: `quoting` books price it at `dec`, the rest '-'."""
    quoting = books if quoting is None else quoting
    out = []
    for i in range(books):
        if i == 0:
            name = "Bet365"
        else:
            name = f"Book{i}"
        if i < quoting and dec is not None:
            out.append({"bookmaker": name, "fractional": f"{int(dec - 1)}/1",
                        "decimal": str(dec)})
        else:
            out.append({"bookmaker": name, "fractional": "-", "decimal": "-"})
    return out


def runner(name, number, dec=6.0, quoting=None, jockey="A Jockey"):
    return {"horse": name, "number": number, "jockey": jockey, "lbs": "130",
            "odds": odds(dec, quoting=quoting), "form": "1234"}


def race(runners, field_size=None):
    return {"race_name": "Test Handicap", "course": "Southwell (AW)",
            "off_dt": "2026-09-17T19:30:00+01:00", "race_class": "Class 4",
            "type": "Flat", "distance": "1m", "runners": runners,
            "field_size": str(field_size if field_size is not None else "")}


sc = S.Scraper()


def names(data):
    return [r.name for r in sc._parse_race(data).runners]


print("\n1. NR-FLAGGED RUNNERS ARE DROPPED")
d = race([runner("Real One", "1"), runner("Real Two", "2"),
          runner("Startling", "NR", dec=8.0, quoting=19)], field_size=2)
chk("NR still priced at 19 of 29 books => dropped", names(d) == ["Real One", "Real Two"])
chk("num_runners matches field_size", sc._parse_race(d).num_runners == 2)
d = race([runner("Real One", "1"), runner("Moon Over Miami", "NR", dec=None)], field_size=1)
chk("NR with no price at all => dropped", names(d) == ["Real One"])
d = race([runner("Real One", "1"), runner("Captain Cess", "NR", dec=7.5, quoting=29)], field_size=1)
chk("NR priced at EVERY book (incl. Bet365) => still dropped", names(d) == ["Real One"])
for token in ("nr", " NR ", "Nr"):
    d = race([runner("Real One", "1"), runner("Ghost", token)], field_size=1)
    chk(f"number {token!r} => dropped", names(d) == ["Real One"])

print("\n2. RESERVES AND ORDINARY NUMBERS ARE KEPT")
d = race([runner("Real One", "1"), runner("Reserve In", "R17")], field_size=2)
chk("R17 reserve (priced) is KEPT", names(d) == ["Real One", "Reserve In"])
d = race([runner("Real One", "1"), runner("Numeric Int", 14)], field_size=2)
chk("integer saddle cloth 14 is KEPT", names(d) == ["Real One", "Numeric Int"])
d = race([runner("Real One", "1"), runner("No Number", None)], field_size=2)
chk("missing number (priced) is KEPT", names(d) == ["Real One", "No Number"])

print("\n3. EARLY CARD — market not open (nobody priced)")
d = race([runner("Early A", "1", dec=None), runner("Early B", "2", dec=None),
          runner("Early NR", "NR", dec=None)])
chk("unpriced card keeps every non-NR runner", names(d) == ["Early A", "Early B"])

print("\n4. PRICE RULE STILL APPLIES (backstop)")
d = race([runner("Real One", "1"), runner("Unpriced Old-Style NR", "3", dec=None)], field_size=1)
chk("unpriced runner with a normal number, rival priced => dropped",
    names(d) == ["Real One"])

print("\n5. THE 17 SEP SHAPE — Southwell 19:30 (field_size 12, 14 in payload)")
rs = [runner(f"Runner {i}", str(i)) for i in range(1, 13)]
rs.insert(10, runner("Royal County Glory", "NR", dec=3.75, quoting=22))
rs.append(runner("Captain Cess", "NR", dec=7.5, quoting=20))
d = race(rs, field_size=12)
parsed = sc._parse_race(d)
chk("both NRs dropped, 12 runners kept", parsed.num_runners == 12)
chk("Royal County Glory (stale 11/4 favourite) is gone",
    "Royal County Glory" not in [r.name for r in parsed.runners])

print("\n6. FLAG OFF => previous behaviour (price rule only)")
old = S.NR_NUMBER_FLAG_ENABLED
S.NR_NUMBER_FLAG_ENABLED = False
try:
    d = race([runner("Real One", "1"), runner("Startling", "NR", dec=8.0, quoting=19)], field_size=1)
    chk("flag off: priced NR is KEPT (as before 17 Sep)", names(d) == ["Real One", "Startling"])
    d = race([runner("Real One", "1"), runner("Moon Over Miami", "NR", dec=None)], field_size=1)
    chk("flag off: unpriced NR still dropped by the price rule", names(d) == ["Real One"])
finally:
    S.NR_NUMBER_FLAG_ENABLED = old

print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
