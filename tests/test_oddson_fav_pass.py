"""Odds-on favourite pass (17 Sep 2026) + the write-up / F2-consensus / stake
wording changes shipped with it.

WHY: Southwell 17:25 on 17 Sep 2026 was a 4-runner Class 4 handicap whose
favourite, Level Look, was 4/9. The sub-evens block rightly kept him off the
card, so the bot backed the leftovers: Charging Thunder 10/1 (8yo, Flat form
502700, 14th of 15 beaten 57L last time) and New York Minute 10/1 as race NB.
No gate could stop it -- the betable-70 gate passed on Charging Thunder's 73,
and the dominant-favourite rule needs the favourite 8 RPR clear (Level Look had
the LOWEST RPR). Measured on 774 settled bot bets joined to the racecard cache:
races with an odds-on favourite and <= 6 runners = 51 bets / 30 races, 4 wins,
-40.8% ROI, negative in BOTH halves (-27.1% to 30 Jun, -82.9% since).

THE RULE: favourite STRICTLY odds-on (shorter than evens) AND field <= 6
=> the race never reaches judgement. Paul, 17 Sep: "evens is ok, just odds on".

Run:  python tests/test_oddson_fav_pass.py
"""
import copy
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("RACING_API_USERNAME", "x")
os.environ.setdefault("RACING_API_PASSWORD", "x")

import src.analyst as A  # noqa: E402
from src.scraper import Meeting, Race, Runner  # noqa: E402
from src.scorer import RunnerScore  # noqa: E402

results = []


def chk(label, cond):
    results.append(bool(cond))
    print(f"   {'PASS' if cond else 'FAIL'}  {label}")


def field(prices, totals=None, medians=None):
    """A race_scored list: one RunnerScore per (name, price)."""
    out = []
    for i, (name, odds) in enumerate(prices):
        r = Runner(name=name, odds=odds)
        if medians is not None:
            r.odds_median = medians[i]
        tot = totals[i] if totals else 60.0
        out.append(RunnerScore(runner=r, total=tot))
    return out


def fires(race_scored):
    return A._oddson_fav_small_field(race_scored)[0]


# The founding case, exactly as priced at the 10:05 run.
SOUTHWELL = [("Level Look", "4/9"), ("Dojin", "4/1"),
             ("Charging Thunder", "10/1"), ("New York Minute", "10/1")]

print("\n1. THE RULE")
fired, detail = A._oddson_fav_small_field(field(SOUTHWELL))
chk("Southwell 17:25 (4 runners, 4/9 fav) is passed", fired)
chk("detail names the favourite and its price", "Level Look" in detail and "4/9" in detail)
chk("detail states the field size", "4-runner" in detail)
six = [("Fav", "4/6")] + [(f"R{i}", "5/1") for i in range(5)]
chk("6 runners with a 4/6 favourite is passed (boundary)", fires(field(six)))
seven = six + [("R9", "8/1")]
chk("7 runners with a 4/6 favourite is NOT passed", not fires(field(seven)))
just_on = [("Fav", "20/21"), ("B", "3/1"), ("C", "6/1")]
chk("20/21 favourite (just odds-on) is passed", fires(field(just_on)))

print("\n2. ⚠ EVENS IS OK — only strictly odds-on fires (Paul, 17 Sep)")
for ev in ("Evens", "EvensF", "Evs", "1/1"):
    chk(f"favourite at {ev} does NOT fire",
        not fires(field([("Fav", ev), ("B", "3/1"), ("C", "6/1")])))
chk("favourite at 11/10 does NOT fire",
    not fires(field([("Fav", "11/10"), ("B", "2/1"), ("C", "6/1")])))

print("\n3. FAILS OPEN")
chk("no prices at all => does NOT fire",
    not fires(field([("A", None), ("B", None), ("C", None)])))
chk("unparseable prices => does NOT fire",
    not fires(field([("A", "CHECK PRICE"), ("B", "SP"), ("C", "")])))
chk("empty race => does NOT fire", not fires([]))
chk("an unpriced runner still COUNTS toward the field (7 runners => no fire)",
    not fires(field(six + [("Unpriced", None)])))

print("\n4. FLAGS")
old_en, old_max = A.ODDSON_FAV_PASS_ENABLED, A.ODDSON_FAV_MAX_FIELD
try:
    A.ODDSON_FAV_PASS_ENABLED = False
    chk("flag off => Southwell does NOT fire", not fires(field(SOUTHWELL)))
    A.ODDSON_FAV_PASS_ENABLED = True
    A.ODDSON_FAV_MAX_FIELD = 3
    chk("ODDSON_FAV_MAX_FIELD=3 => 4-runner Southwell does NOT fire",
        not fires(field(SOUTHWELL)))
finally:
    A.ODDSON_FAV_PASS_ENABLED, A.ODDSON_FAV_MAX_FIELD = old_en, old_max


# ── 5. PIPELINE: both race-ranking branches drop the race before judgement ──
class FakeScorer:
    """Returns preset totals so a fixture can clear the betable-70 gate."""
    TOTALS = {}

    def score_race(self, race):
        rs = [RunnerScore(runner=r, total=self.TOTALS.get(r.name, 50.0))
              for r in race.runners]
        return sorted(rs, key=lambda x: -x.total)


def build_card():
    """Southwell 17:25 (odds-on fav, 4 runners) + a clean 8-runner race."""
    def race(time, name, prices):
        return Race(time=time, name=name, course="Southwell (AW)", distance="2m",
                    race_class="Class 4", race_type="Flat", num_runners=len(prices),
                    runners=[Runner(name=n, odds=o) for n, o in prices])
    sw = race("17:25", "Marketmovers Handicap", SOUTHWELL)
    clean = race("18:00", "Clean Handicap",
                 [("Clean Fav", "2/1"), ("Clean Pick", "7/2")] +
                 [(f"Clean {i}", "8/1") for i in range(6)])
    # A historical date so the past-post gate (today-only) never interferes.
    return [Meeting(course="Southwell (AW)", date=date(2026, 4, 1), races=[sw, clean])]


FakeScorer.TOTALS = {"Charging Thunder": 73.2, "Level Look": 44.5, "Dojin": 58.2,
                     "New York Minute": 56.9, "Clean Pick": 74.0, "Clean Fav": 66.0}


def run_pipeline(n_races, flag=True):
    captured = {}

    def fake_judgement(top_races_data, meetings, tips_text, going_reports, n_races=None):
        captured["races"] = [race.time for _, race, _ in top_races_data]
        return {}

    saved = (A.Scorer, A._run_claude_judgement, A.SPORTINGLIFE_ENABLED,
             A._programmatic_cherry_pick, A._enforce_compliance, A.ODDSON_FAV_PASS_ENABLED)
    A.Scorer = FakeScorer
    A._run_claude_judgement = fake_judgement
    A.SPORTINGLIFE_ENABLED = False
    A._programmatic_cherry_pick = lambda *a, **k: {"selections": [], "nap_index": -1}
    A._enforce_compliance = lambda sel, *a, **k: sel
    A.ODDSON_FAV_PASS_ENABLED = flag
    try:
        A.analyse_all_meetings(build_card(), n_races=n_races)
    finally:
        (A.Scorer, A._run_claude_judgement, A.SPORTINGLIFE_ENABLED,
         A._programmatic_cherry_pick, A._enforce_compliance,
         A.ODDSON_FAV_PASS_ENABLED) = saved
    return captured.get("races")


print("\n5. PIPELINE — the race never reaches judgement")
chk("default /run: Southwell 17:25 dropped, clean race kept",
    run_pipeline(None) == ["18:00"])
chk("/run 6: Southwell 17:25 dropped, clean race kept",
    run_pipeline(6) == ["18:00"])
chk("flag off, default /run: BOTH races reach judgement (no-regression)",
    sorted(run_pipeline(None, flag=False) or []) == ["17:25", "18:00"])
chk("flag off, /run 6: BOTH races reach judgement (no-regression)",
    sorted(run_pipeline(6, flag=False) or []) == ["17:25", "18:00"])


# ── 6. F2 CONSENSUS SHADOW — logs, never changes the card ────────────────────
def compliance_card(sel_odds, median):
    r = Runner(name="Charging Thunder", odds=sel_odds)
    r.odds_median = median
    r.sl_comment = ""
    lookup = {"charging thunder": RunnerScore(runner=r, total=73.0)}
    meta = {"marketmovers handicap": {
        "num_runners": 8, "race_type": "Flat", "pattern": "", "distance": "2m",
        "race_class": "Class 4", "course": "Southwell (AW)", "race_time": "17:25",
        "surface": "AW", "going": "Standard", "going_detailed": "", "api_tip": "",
        "runners": [("charging thunder", 10.0), ("filler a", 3.0), ("filler b", 4.0)],
        "top2_flag": False}}
    sel = {"horse": "Charging Thunder", "odds_guide": sel_odds, "adjusted_score": 73,
           "each_way": False, "reasoning": ["x"], "confidence": "", "danger": "",
           "next_best": {}, "course": "Southwell (AW)", "race_time": "17:25",
           "race_name": "Marketmovers Handicap"}
    return {"selections": [sel], "nap_index": -1, "compliance_log": []}, lookup, meta


def consensus_lines(out):
    return [l for l in out.get("filter_shadow_log", []) if "F2 CONSENSUS" in l]


print("\n6. F2 CONSENSUS SHADOW — log only")
card, lookup, meta = compliance_card("10/1", 11.0)
out = A._enforce_compliance(copy.deepcopy(card), lookup, meta)
chk("Bet365 10/1 but median 11/1 => a CONSENSUS shadow line is logged",
    len(consensus_lines(out)) == 1 and "would DROP" in consensus_lines(out)[0])
chk("...and the selection is still on the card (shadow, not live)",
    [s["horse"] for s in out["selections"]] == ["Charging Thunder"])
card, lookup, meta = compliance_card("12/1", 9.0)
out = A._enforce_compliance(copy.deepcopy(card), lookup, meta)
chk("Bet365 12/1 but median 9/1 => shadow line says median would KEEP",
    len(consensus_lines(out)) == 1 and "would KEEP" in consensus_lines(out)[0])
chk("...while live F2 still drops it on the Bet365 price", out["selections"] == [])
card, lookup, meta = compliance_card("10/1", 9.0)
out = A._enforce_compliance(copy.deepcopy(card), lookup, meta)
chk("Bet365 and median agree => no CONSENSUS line", consensus_lines(out) == [])
card, lookup, meta = compliance_card("10/1", None)
out = A._enforce_compliance(copy.deepcopy(card), lookup, meta)
chk("no median price => no CONSENSUS line (fails quiet, never guesses)",
    consensus_lines(out) == [])
old = A.F2_CONSENSUS_SHADOW_ENABLED
A.F2_CONSENSUS_SHADOW_ENABLED = False
try:
    card, lookup, meta = compliance_card("10/1", 11.0)
    out = A._enforce_compliance(copy.deepcopy(card), lookup, meta)
    chk("flag off => no CONSENSUS line", consensus_lines(out) == [])
finally:
    A.F2_CONSENSUS_SHADOW_ENABLED = old


print("\n7. WRITE-UP RULES reach the judgement prompt")
P = A.ANALYST_SYSTEM_PROMPT
chk("prompt has a WRITE-UP RULES section", "WRITE-UP RULES" in P)
chk("...requiring the market favourite to be named", "market favourite" in P.split("WRITE-UP RULES")[-1])
chk("...requiring the Sporting Life read to be used", "Sporting Life" in P.split("WRITE-UP RULES")[-1])
chk("...banning raw field dumps", "C&D: True" in P.split("WRITE-UP RULES")[-1])


print("\n8. STAKE WORDING matches the live ladder")
def render(sels, nap_idx):
    return A.format_selections_telegram(
        {"selections": sels, "nap_index": nap_idx, "double": {}, "notes": "",
         "compliance_log": []})

base = {"rank": 1, "horse": "Pick One", "race_time": "15:00", "course": "Ayr",
        "race_name": "R", "odds_guide": "5/1", "adjusted_score": 72,
        "reasoning": ["for and against"], "danger": "Rival 4/9 - odds-on",
        "each_way": False, "next_best": {}}
demoted = dict(base, rank=2, horse="Pick Two", nb_price_capped=True)
msg = render([base, demoted], -1)
chk("no-NAP staking line quotes the demoted stake when a pick is demoted",
    f"{A.STAKE_DEMOTED:g}pt" in msg.split("STAKING")[-1])
chk("no-NAP header no longer hard-codes '1pt' when the ladder says otherwise",
    f"Flat {A.STAKE_SELECTION:g}pt stakes" in msg)
chk("danger line shown under each selection on a no-NAP card",
    "Danger: Rival 4/9" in msg.split("TODAY'S SELECTIONS")[-1])
src = open(A.__file__).read()
chk("CHECK 12 note no longer quotes the retired 1.5pt stake",
    "1.5pt E/W needs 8+ runners" not in src)


print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
