"""
Hybrid analysis engine - cherry-pick mode.

Backbone: Enhanced programmatic scorer (pure Python)
Edge layer: Claude API (Opus) with the FULL CLAUDE.md analysis framework
Compliance gate: Programmatic post-Claude checks that enforce rules
even when the LLM doesn't follow them.

Produces: 4 best selections + 4 NBs + best double = 9 bets
Quality over quantity — only pick races with genuine edge.
"""

import json
import logging
import re
from typing import Optional

import anthropic

from config.settings import ANTHROPIC_API_KEY, JUDGEMENT_MODEL, NAP_THRESHOLD
from src.scraper import Runner, Race, Meeting
from src.scorer import RunnerScore, Scorer

logger = logging.getLogger(__name__)

NUM_SELECTIONS = 4

# System-resistant race patterns — half stakes, E/W only, never NAP
SYSTEM_RESISTANT_PATTERNS = [
    "fred winter", "national hunt chase", "kim muir", "grand annual",
    "mares' novices' hurdle", "pertemps final", "veterans' chase final",
    "veterans chase final", "veterans' final", "series final",
    "foxhunters",
]

# The full CLAUDE.md analysis framework - distilled for the system prompt.
ANALYST_SYSTEM_PROMPT = """You are an expert UK horse racing analyst. You cherry-pick the best 4 selections across all UK/Irish meetings each day. Quality over quantity.

You will receive programmatically scored runners from today's races. The scorer handles quantifiable factors. YOUR job is the subjective judgement that gives us the edge.

## HARD RULES (NON-NEGOTIABLE)

1. ELIMINATED runners (score 0, "ELIMINATED" in edges): NEVER select these
2. READ EVERY SPOTLIGHT before selecting. When Spotlight says "all wins came under conditions that don't apply today" — DOWNGRADE regardless of RPR/TS
3. SUB-EVENS BLOCK: NEVER select a horse priced at evens or SHORTER (i.e. ≤ 1/1 fractional, ≤ 2.0 decimal).
   - BLOCKED examples: 1/1 (Evens / EvensF / Evs), 4/5, 4/6, 1/2, 1/3, 2/5, 1/4 — any price where the win-stake multiplier is ≤ 1.0
   - NOT BLOCKED: 5/4, 6/4, 11/8, 7/4, 2/1, 9/4, 5/2 — any price where the win-stake multiplier is > 1.0. Being market favourite alone does NOT trigger this rule. 5/4F and 6/4F are FINE.
   - Replace BLOCKED selections with the NB. Validated repeatedly: Wodhooh 8/11F 3rd 2 May, Independent Lady 4/6F beaten 39L, Lulamba 1/2F UR Aintree, Italian Fox 4/11F 2nd
4. NAP must score 75+ AND be priced ≤ 10/1 (decimal multiplier ≤ 10.0). NB-of-day must be priced ≤ 14/1. Added 5 May 2026 after Fairlawn Flyer NAP 22/1 (149-day absence) lost at Ffos Las — a high score in a competitive field does NOT translate to a high win probability; the market's price IS information. If your top scorer is priced longer than 10/1, set nap_index to -1 (flat stakes day) and treat the horse as a race SEL only. Same logic for NB-of-day at 14/1. The compliance gate enforces both caps.
5. NB SWAP RULE — only the market branch is enforced; value swap is YOUR judgment at scoring time:
   (a) MARKET SWAP (MANDATORY): scores within 5pts AND NB is shorter-priced / market favourite → swap. Trust the market. Validated 14 Apr: Mister Winston 9/4F won where Great Chieftain 100/30 NAP failed; Jakajaro 4/1F won where Regal Envoy 9/2 sel finished 3rd. Validated 29 Apr Pontefract: Walsingham 9/4F won (against On The River sel), Lightening Co 2/1JF won (against Bearwith sel). The compliance gate auto-fires this branch.
   (b) VALUE SWAP (DO NOT AUTO-PROMOTE): scores within 5pts AND NB is 2x+ the sel odds is NOT a deterministic swap trigger. Pick the SEL/NB ordering you genuinely believe before the gate runs — if you want the longer-priced horse as SEL, score it higher. Do NOT cite "value swap" in compliance_log as a swap action; the gate will not enforce it and an LLM-side promotion to a longer price needs an explicit positive case in the reasoning. CLAUDE.md frames this as "consider only" — judgment beats rule. Failure mode validated 5 May 2026: Lion Of The Desert 10/3 (sel) WON, Kylenoe Dancer 10/1 (NB, value-swapped to SEL) was a non-runner. Earlier failures 27 Apr Bath: Diamondsinthesand UP, Nakaaha 2nd. Negative-Spotlight phrases ("hard to fancy", "needs to improve", "may prove resurgent", "best watched", "needs further", "ideally needs", etc.) remain a reason to DOWNGRADE that horse on its own merits — not a reason to swap.
6. QUICK TURNAROUND: NH horse back within 7 days = already penalised -5 in scorer. Respect that penalty
7. SYSTEM-RESISTANT RACES: Big-field finals (12+ runners), Pertemps/Veterans/series finals, Foxhunters, bumpers with 15+ runners, early-season 3yo Flat handicaps (Mar/Apr/early May) with 12+ runners = half stakes, E/W only, NEVER NAP. (v4.1 dropped: 16+ Listed sprint rule, 3yo all-types extension)
8. ONE selection per race maximum
9. Score EVERY runner in target races before picking. No shortcuts
10. NEVER override our RPR/TS pick entirely for Timeform. When they disagree, keep BOTH as contenders
11. CLASS-DROP KICKER QUALITY FILTER (added 21 Apr after Pontefract 0-3): The scorer now skips the kicker when the higher-grade placed run was foreign, on AW with today on turf, or qualified in Spotlight as "weak form for the grade". If the kicker appears in Edges, trust it — if a Spotlight mentions a higher-grade placing but NO kicker shows, the quality filter fired, don't manually re-apply
12. AW CLASS 5/6 WEIGHT-RISE BLOCKER (added 7 May 2026 — Rule A): For AW Class 5 / Class 6 HANDICAPS only — if a horse has 3+ wins in last 5 starts AND is rising +7lb or more from its last winning mark, CAP AT NB ROLE (never NAP). +10lb or more = SKIP entirely. Class 5/6 AW horses are mature/exposed and recycle through the same pool; the handicapper's rise punishes the streak. Spotlight phrases like "this Xlb higher mark", "raised Xlb", "now Xlb higher", "Xlb higher than" indicate the rise — read the figure and apply the rule. Validated 7 May 2026: Roaring Ralph (-22111 form, +9lb in same Class 5) NAP'd 9/2 → 7th of 11. Rule does NOT apply at Group/Listed/big-handicap level — improvers there absorb rises.
13. AW CLASS 5/6 NO-NAP-ON-FAVOURITE (added 7 May 2026 — Rule B): For AW Class 5 / Class 6 HANDICAPS only — if your top scorer is also the betting market favourite (or co-favourite within ~5%) AND priced at sub-4/1 (decimal ≤ 4.0), set nap_index to -1 (no NAP that day, flat stakes). At sub-4/1 in compressed AW C5/6 form the framework's score adds nothing the market hasn't already priced — ROI is bookmaker-margin negative by construction. Validated 7 May 2026: Shades Of May 3/1F top scorer 78 → 8th of 10. NAP at 4/1+ is allowed only with explicit market-divergence note in reasoning. Rule does NOT apply at higher class — Brighterdaysahead 9/4 with TS+35, Madara, Saddadd 2/1 are legitimate short-priced NAPs that overwhelmed market consensus.
14. C5/C6 SPOTLIGHT RED-FLAG DOWNGRADE (added 8 May 2026): For ANY Class 5 / Class 6 race (AW or turf), if a selection's Spotlight contains any of the following phrases, REDUCE adjusted_score by 5: "doesn't have a great record when fresh", "has plenty to prove", "on dangerous mark", "may need this", "down the list", "well held", "needs to bounce back", "not easy to predict", "out of sorts", "bit to prove". These are analyst hedges in compressed-pool handicaps where the figures look better than the prospects. Validated 8 May 2026: Mark's Choice (Ripon 6:45 C5) Spotlight "doesn't have a great record when fresh" was missed; bot scored 79, finished 6th at 9/2.
15. C5/C6 SCORE-VS-MARKET GATE (added 8 May 2026 — Option B): In ANY Class 5 / Class 6 race, if a selection has adjusted_score ≥ 80 AND best decimal odds ≥ 9.0 (8/1 or longer), the score is structurally divergent from the market's view. Demote to race SEL stake (0.75pt) — never NAP, never NB-of-day. The framework score scale is not calibrated to win probability in compressed-pool handicaps; an 80+ score at 8/1+ means the rubric is over-counting recyclable-pool form, not finding edge. Pattern: Fairlawn Flyer 22/1 (score 81, Ffos Las 5 May), Star Prospect 88, Precise (3 May, score 104) — all score-market divergence in low-class form-compressed handicaps. Gate enforced by compliance backstop CHECK 6. Scope: Class 5/6 only — at C4 and above the score-market relationship is more reliable.

## v4.1 DROPPED RULES (do NOT apply, do NOT cite in compliance_log)
The following v3 rules were dropped on 1 May 2026. The scorer no longer emits these flags. Do NOT mention TS-VETO, TS-ELIMINATE, or DUAL-EDGE in your reasoning or compliance_log. The scoring already reflects the underlying signals (TS deficits zero the speed score; class-rise figures are interpreted normally):
- 🚫 TS-VETO (TS 10+ below OR → cap at NB) — DROPPED. Cost 8 winners/placers in 9 days
- ⛔ TS-ELIMINATE (TS deficit + surface change → skip) — DROPPED
- ⭐ DUAL-EDGE (biggest RPR + biggest TS → force-NB-min) — DROPPED. 0/7 winners from forcings

## ANALYSIS TASKS

### FORM READING
- "3F12" where horse fell when clear = BETTER than form shows
- "1111" in weak fields = may be flattered
- FALLS/UNSEATINGS: Single F/U does NOT erase class form. Only pattern (2+) matters
- Read Spotlight comments — they contain critical context the numbers miss

### GOING ANALYSIS (ground is king)
- More races lost to unsuitable going than any other factor
- Speed figures on different going do NOT transfer
- NEVER select an odds-on shot where going is questionable

### SPEED FIGURES (primary edge)
- RPR/TS 10+ above OR = significant edge
- RPR/TS 5-9 above OR = potentially well-handicapped
- TOPSPEED LEADER RULE: Highest TS by 3+ points at 5/1+ = serious contender. Clock doesn't lie

### EQUIPMENT (graded bonuses)
- 1st-time blinkers (2yo/3yo colt): +5 | older horse: +3
- 1st-time visor: +3 | cheekpieces: +2 | tongue-tie: +1
- BLINKERS REMOVED: -5 (strong negative)
- Older mares (5+) in 1st-time blinkers = AVOID

### WIND SURGERY
- +3 bonus ONLY when TS/RPR also above OR. If speed figs are AT/BELOW OR, wind op is papering over cracks

### SIGNAL COMPOUNDING (most important edge)
3+ intent signals on same horse = +5 additional. Signals: jockey upgrade, 1st-time HG, class drop, hot stable (20%+), wind op (with speed), return to preferred conditions
VALIDATED: Travis Wheatley (1st-time HG + hot stable 36%, WON 16/5)

### FIRST-STRING JOCKEY
When a top stable jockey picks one from a multi-entry, that IS the first string. Apply CONSISTENTLY.
Key combos: Townend/Mullins, Cobden/Nicholls, Skelton/Skelton, Kennedy/Elliott

### VALUE OVER CERTAINTY
4/1 with 25% chance > 1/2 with 55%. Our NBs consistently outperform selections because the market overprices the obvious choice. The NB swap rule exists for this reason.

## PRE-OUTPUT COMPLIANCE CHECKLIST (v4.1 — 6 CHECKS)

Before returning your JSON, verify EACH selection against these 6 checks. Do NOT add additional checks (the v3 9-check version with TS-VETO and DUAL-EDGE was dropped in v4.1). Hard rules 4 (NAP 75+), 6 (quick-turnaround), and 7 (system-resistant) are enforced by the scorer / hard-rule application above and don't need separate compliance entries:

1. MARKET SWAP (mandatory branch a): For each sel-vs-NB pair, scores within 5pts AND NB shorter-priced / market favourite? → SWAP. No discretion, no Spotlight gate on this branch.
2. NO EVENS-OR-SHORTER: Any selection priced ≤ 1/1 (e.g. EvensF, 4/5, 4/6, 1/2)? → Replace with NB. NOTE: 5/4, 6/4, 11/8, 7/4 are NOT sub-evens — do NOT block these. Being favourite alone is not a reason to demote.
3. SPOTLIGHT: Any negative language on selections? → Downgrade. Negative language on NB is NOT a swap trigger; it's a reason to leave the NB where it is.
4. ALL RUNNERS SCORED: Did you consider every horse in target races? → If not, go back.
5. AW CLASS 5/6 TARGETED RULES (added 7 May 2026): For each selection in an AW Class 5 or Class 6 HANDICAP, apply BOTH:
   (a) Weight-rise blocker (Rule A): if 3+ wins in last 5 starts AND Spotlight indicates a +7lb or larger rise from last winning mark, cap at NB role; +10lb or more, skip the selection. Phrases to scan: "this Xlb higher mark", "raised Xlb", "Xlb higher than", "now Xlb higher".
   (b) No-NAP-on-favourite (Rule B): if the NAP candidate is also the market favourite at sub-4/1 (decimal ≤ 4.0) — set nap_index to -1 (flat stakes day). Top scorer = market consensus at sub-4/1 in compressed C5/6 form has zero edge over market. NAP at 4/1+ allowed only with explicit market-divergence note.
   Compliance gate enforces both as backstop. Rules do NOT apply at Group/Listed/big-handicap level.
6. C5/C6 SCORE-VS-MARKET GATE (added 8 May 2026 — Option B): For each selection in ANY Class 5 / Class 6 race (AW or turf), if adjusted_score ≥ 80 AND best decimal odds ≥ 9.0 (8/1 or longer), demote to race SEL stake (no NAP, no NB-of-day). The score-vs-market divergence is too wide to trust — the framework over-counts recyclable-pool form in C5/C6. Compliance gate enforces as backstop.

## OUTPUT FORMAT

Return ONLY valid JSON:
{
  "selections": [
    {
      "rank": 1,
      "horse": "Name",
      "race_time": "HH:MM",
      "race_name": "Race Name",
      "course": "Course",
      "odds_guide": "X/Y",
      "confidence": "HIGH/MEDIUM-HIGH/MEDIUM",
      "reasoning": ["reason1", "reason2", "reason3"],
      "danger": "Horse name - brief why",
      "each_way": true,
      "adjusted_score": 80,
      "nb_score": 75,
      "next_best": {
        "horse": "Name",
        "odds_guide": "X/Y",
        "reasoning": "1-2 sentences",
        "each_way": false,
        "adjusted_score": 72
      }
    }
  ],
  "double": {
    "leg1": "Horse Name (HH:MM Course)",
    "leg2": "Horse Name (HH:MM Course)",
    "reasoning": "Why this double",
    "combined_odds_approx": "X/1"
  },
  "nap_index": 0,
  "compliance_log": [
    "CHECK 1 MARKET SWAP: Sel1 82pts 5/2 vs NB 78pts 9/4F — within 5pts, NB shorter-priced → SWAPPED",
    "CHECK 2 SUB-EVENS: Lowest selection priced 5/4 — above 1/1 threshold, no block — PASS",
    "CHECK 3 SPOTLIGHT: All spotlights reviewed, no negatives on selections — PASS",
    "CHECK 4 FULL FIELD: All runners scored in 4 target races — PASS",
    "CHECK 5 AW C5/6: No selection in AW Class 5/6 handicap, Rule A/B not applicable — PASS"
  ],
  "notes": "Meetings avoided and why, overall observations"
}

CRITICAL:
- Rank 1 = NAP (MUST score 75+), Rank 2 = Next Best overall
- If nothing scores 75+, set nap_index to -1
- Include nb_score and next_best.adjusted_score — the compliance gate needs these
- The compliance_log MUST show all 4 v4.1 checks with PASS/FAIL and action taken (do NOT add v3 checks like TS-VETO or DUAL-EDGE)
- Each-way: 8+ runners AND 3/1+ odds for non-handicaps. For HANDICAPS: ALWAYS E/W regardless of field size or odds
- Return exactly 4 selections (or fewer if not enough quality)
- ONE selection per race maximum — cherry-pick the 4 best RACES, not 4 horses from the same race
- ODDS: Each runner's block includes "ODDS: X/Y (Bet365, live from API)". USE THAT FIGURE EXACTLY in odds_guide. DO NOT invent odds, round them, or estimate from form/ratings. If a runner's ODDS line says "NO PRICE", use "CHECK PRICE" as the odds_guide. Your NB swap, sub-evens, each-way, and value calculations all depend on these being accurate — hallucinated prices will make the compliance gate lie. Added 24 Apr 2026 after bot was caught hallucinating prices wildly (Action 5/2 when real was 4/6F).
"""


def _parse_odds_to_decimal(odds_str: str) -> float:
    """Convert fractional odds string to decimal multiplier. Returns 0 if unparseable.
    Handles Evens variants (Evens, Evs, EV, EvensF, E/Fav) as 1.0 — added 21 Apr 2026
    after Crystal Island EvensF slipped the sub-evens block at Ffos Las because
    "Evens" didn't match the N/M fractional regex."""
    if not odds_str or odds_str == "CHECK PRICE":
        return 0.0
    s = odds_str.strip().lower()
    if s.startswith("ev") or s == "e/fav":
        return 1.0
    match = re.match(r"(\d+)/(\d+)", odds_str)
    if match:
        return int(match.group(1)) / int(match.group(2))
    return 0.0


def _is_sub_evens(odds_str: str) -> bool:
    """Check if odds are evens or shorter (≤ 1/1). Tightened 14 Apr 2026
    after Dearkeithandkaty EvensF (2nd beaten 2.5L) sat exactly on the old
    block line."""
    dec = _parse_odds_to_decimal(odds_str)
    return 0 < dec <= 1.0


# Price caps (added 5 May 2026 after Fairlawn Flyer 22/1 NAP at Ffos Las
# scored 81 despite 149-day absence — the framework had no way to
# express "the market thinks this is a 4% shot, so 'NAP' is wrong even
# if our score is high". A high score in a competitive field doesn't
# translate to a high win probability; the market's pricing is
# information.
NAP_MAX_DECIMAL = 10.0   # 10/1 fractional → 11.0 decimal multiplier; cap at 10/1 (multiplier 10.0)
NB_MAX_DECIMAL = 14.0    # 14/1 fractional


def _exceeds_nap_cap(odds_str: str) -> bool:
    """Returns True when odds are LONGER than 10/1 (NAP cap)."""
    dec = _parse_odds_to_decimal(odds_str)
    return dec > NAP_MAX_DECIMAL


def _exceeds_nb_cap(odds_str: str) -> bool:
    """Returns True when odds are LONGER than 14/1 (NB-of-day cap)."""
    dec = _parse_odds_to_decimal(odds_str)
    return dec > NB_MAX_DECIMAL


# Spotlight gate phrases for value-swap rule (added 27 Apr 2026 after
# Diamondsinthesand "ideally needs further" UP and Nakaaha "may prove
# resurgent" 2nd-only on 27 Apr). When any of these appear in the NB's
# Spotlight, the value swap (a) is suppressed — chasing the longer
# price on a horse the analyst has already cautioned against is the
# worst kind of value-trap.
_NEG_SPOTLIGHT_PHRASES = (
    "hard to fancy",
    "hard to recommend",
    "needs to improve",
    "needs more",
    "may prove resurgent",
    "best watched",
    "not the percentage call",
    "needs further",
    "much to find",
    "ideally needs",
    "not totally convincing",
    "loads to find",
    "questionable",
    "plenty to prove",
    "lots to find",
    "lot to find",
    "needs a revival",
    "would need",
)


def _has_negative_spotlight(comment: str) -> bool:
    """Return True if the Spotlight contains a phrase that warrants
    suppressing the value-swap promotion. Case-insensitive substring
    match — keep the phrase list narrow and load-bearing, not every
    cautious word."""
    if not comment:
        return False
    c = comment.lower()
    return any(phrase in c for phrase in _NEG_SPOTLIGHT_PHRASES)


# AW Class 5/6 handicap targeted rules — added 7 May 2026 after Southwell
# evening card lost twice on market-confirmed sub-4/1 picks (Roaring Ralph
# 9/2 +9lb after C&D hat-trick → 7th of 11; Shades Of May 3/1F top scorer
# → 8th of 10). Two rules:
#  Rule A: 3+ wins in last 5 + rise ≥ +7lb → max NB; ≥ +10lb → skip
#  Rule B: NAP = market fav at sub-4/1 → no NAP, flat stakes day
# Class-specific to preserve framework flexibility at Group/Listed level.
_AW_ONLY_COURSES = {"southwell", "wolverhampton", "chelmsford"}
_DUAL_AW_COURSES = {"lingfield", "kempton", "newcastle"}

# Spotlight phrases that quote a weight rise. Group 1 captures lb count.
_RISE_PATTERNS = [
    re.compile(r"this\s+(\d+)\s*lb\s+higher\s+mark", re.I),
    re.compile(r"raised\s+(\d+)\s*lb", re.I),
    re.compile(r"now\s+(\d+)\s*lb\s+higher", re.I),
    re.compile(r"up\s+(\d+)\s*lb", re.I),
    re.compile(r"(\d+)\s*lb\s+higher\s+than", re.I),
    re.compile(r"(\d+)\s*lb\s+higher\s+mark", re.I),
    re.compile(r"(\d+)\s*lb\s+rise", re.I),
]


def _is_aw_course(course: str, surface: str = "") -> bool:
    """True if this course/surface is all-weather. Handles "(AW)" suffix on
    course name and surface field for dual-track courses."""
    c = (course or "").lower()
    s = (surface or "").lower()
    if "(aw)" in c:
        return True
    c_clean = c.replace("(aw)", "").strip()
    if c_clean in _AW_ONLY_COURSES:
        return True
    if c_clean in _DUAL_AW_COURSES:
        if any(x in s for x in ("all-weather", "all weather", "tapeta", "polytrack")):
            return True
    return False


def _is_aw_c5_or_c6_handicap(race_name: str, meta: dict) -> bool:
    """True if this race is an AW Class 5 or Class 6 handicap. Used by the
    targeted weight-rise and no-NAP-on-fav rules added 7 May 2026."""
    if not meta:
        return False
    rc = (meta.get("race_class") or "").lower()
    if "class 5" not in rc and "class 6" not in rc:
        return False
    rn = (race_name or "").lower()
    rt = (meta.get("race_type") or "").lower()
    if "handicap" not in rn and "handicap" not in rt:
        return False
    return _is_aw_course(meta.get("course", ""), meta.get("surface", ""))


def _is_c5_or_c6_any(meta: dict) -> bool:
    """True if this race is Class 5 or Class 6 on ANY surface (AW or turf).
    Used by the score-vs-market gate added 8 May 2026 (Option B). The gate
    is broader than the AW-specific weight-rise/no-NAP-on-fav rules — score
    inflation in compressed-pool C5/C6 form happens on turf evening cards
    too (Mark's Choice, Novamay at Ripon 8 May)."""
    if not meta:
        return False
    rc = (meta.get("race_class") or "").lower()
    return "class 5" in rc or "class 6" in rc


def _count_wins_in_last_5(form: str) -> int:
    """Count '1' (wins) among the most recent 5 completed runs of a form
    string. Letters like F/U/P/B/R are skipped (not completed runs); '0'
    means 10th or worse and is not a win."""
    if not form:
        return 0
    completed = [c for c in form if c in "0123456789"]
    if not completed:
        return 0
    last_5 = completed[-5:]
    return sum(1 for c in last_5 if c == "1")


def _extract_weight_rise_lb(comment: str) -> int:
    """Parse a Spotlight string for a numeric lb rise. Returns the largest
    plausible value found (0 if none). Bounded at <30lb to filter false
    matches like 'won by 14 lengths'."""
    if not comment:
        return 0
    best = 0
    for pat in _RISE_PATTERNS:
        for m in pat.finditer(comment):
            try:
                v = int(m.group(1))
                if v > best and v < 30:
                    best = v
            except (ValueError, IndexError):
                continue
    return best


def _parse_distance_to_furlongs(distance: str) -> float:
    """Convert distance string like '5f', '1m4f', '1m', '7.5f' to furlongs.
    Returns 0 if unparseable."""
    if not distance:
        return 0.0
    s = distance.lower().replace(" ", "")
    miles = 0.0
    furlongs = 0.0
    if "m" in s:
        before_m, _, after_m = s.partition("m")
        try:
            miles = float(before_m)
        except ValueError:
            miles = 0.0
        s = after_m
    if "f" in s:
        before_f, _, _ = s.partition("f")
        try:
            furlongs = float(before_f)
        except ValueError:
            furlongs = 0.0
    return miles * 8 + furlongs


def _is_system_resistant_race(race_name: str, num_runners: int,
                              race_type: str = "",
                              pattern: str = "",
                              distance: str = "",
                              race_class: str = "") -> bool:
    """Check if a race is system-resistant (big-field finals, big bumpers,
    early-season 3yo Flat handicaps, big-field Listed sprints etc).
    Half stakes, E/W only, never NAP."""
    import datetime
    name_lower = (race_name or "").lower()
    type_lower = (race_type or "").lower()
    pattern_lower = (pattern or "").lower()
    class_lower = (race_class or "").lower()

    for sr_pattern in SYSTEM_RESISTANT_PATTERNS:
        if sr_pattern in name_lower:
            return True
    # Big-field finals (12+ runners)
    if num_runners >= 12 and "final" in name_lower:
        return True
    # Grade 2+ bumpers with 15+ runners — form book unreliable
    is_bumper = "bumper" in name_lower or "nh flat" in name_lower or "nhf" in type_lower or "bumper" in type_lower
    if is_bumper and num_runners >= 15:
        return True
    # Early-season 3yo Flat handicaps 12+ runners (March/April/early May).
    # Added 14 Apr 2026 after Newmarket 16:10 (Darn Hot Gallop 22/1) and
    # Newmarket 15:00 (Startled 15/2) — two shock winners same day in
    # exactly this race type. Form compressed, sighting runs, handicapper
    # is guessing too.
    today_month = datetime.date.today().month
    is_early_season = today_month in (3, 4, 5)
    is_3yo_only = "3yo" in name_lower or "3-y-o" in name_lower or "3-y-o" in type_lower or "3yo" in type_lower
    is_handicap = "handicap" in name_lower or "handicap" in type_lower
    is_flat = "flat" in type_lower or ("hurdle" not in name_lower and "chase" not in name_lower and "bumper" not in name_lower)
    if is_early_season and is_3yo_only and is_handicap and is_flat and num_runners >= 12:
        return True
    # v4.1 (1 May 2026): big-field Listed/Group sprints rule removed —
    # added too late (27 Apr) and didn't earn its keep in v4.1 paper-trade
    return False


def _enforce_compliance(selections: dict, scored_lookup: dict,
                        race_meta_lookup: dict = None) -> dict:
    """
    PROGRAMMATIC COMPLIANCE GATE.
    Runs AFTER Claude returns selections, BEFORE sending to Telegram.
    Enforces rules that Claude may have missed.
    Returns corrected selections dict.

    race_meta_lookup is keyed by lowered race name and provides
    num_runners / pattern / distance / race_class for richer system-
    resistant detection (added 27 Apr 2026 for big-field Listed sprints).
    """
    if race_meta_lookup is None:
        race_meta_lookup = {}
    sels = selections.get("selections", [])
    if not sels:
        return selections

    compliance_fixes = []

    for i, sel in enumerate(sels):
        horse = sel.get("horse", "")
        odds = sel.get("odds_guide", "")
        score = sel.get("adjusted_score", 0)
        nb = sel.get("next_best", {})
        nb_odds = nb.get("odds_guide", "") if nb else ""
        nb_score = nb.get("adjusted_score", 0) if nb else 0

        # Also check nb_score field at selection level (backup)
        if not nb_score and sel.get("nb_score"):
            nb_score = sel["nb_score"]

        # v4.1: TS-veto and TS-eliminate gates removed (1 May 2026).
        # 8 vetoed winners/placers in 9 days made this rule a clear drag.
        # Speed figures already factored into score directly; no extra gate.
        sel_sr = scored_lookup.get(horse.lower()) if horse else None
        nb_horse = nb.get("horse", "") if nb else ""
        nb_sr = scored_lookup.get(nb_horse.lower()) if nb_horse else None

        # CHECK 1: MARKET SWAP RULE (mandatory only — Branch a)
        # Scores within 5pts AND NB is shorter-priced / market favourite → swap.
        # Trust the market; it is integrating information the analyst missed.
        # Validated 14 Apr 2026: Mister Winston 9/4F won (Great Chieftain NAP
        # 100/30 9th); Jakajaro 4/1F won (Regal Envoy 9/2 3rd). Validated
        # 29 Apr Pontefract: Walsingham 9/4F won, Lightening Co 2/1JF won.
        #
        # Value swap (Branch b — longer-priced NB) is INTENTIONALLY NOT
        # enforced here. CLAUDE.md v4.1 makes value swap "consider only"
        # for the analyst at scoring time — it is NOT a deterministic
        # compliance action. Validated 5 May 2026: bot promoted Kylenoe
        # Dancer 10/1 over Lion Of The Desert 10/3 (clean Spotlight, gate
        # passed) — LotD WON, KD was a non-runner. Removing the auto-fire
        # restores the asymmetric design from CLAUDE.md.
        if nb and nb_score > 0 and score > 0:
            score_gap = abs(score - nb_score)
            sel_dec = _parse_odds_to_decimal(odds)
            nb_dec = _parse_odds_to_decimal(nb_odds)

            swap_reason = None
            if score_gap <= 5 and sel_dec > 0 and nb_dec > 0:
                if nb_dec < sel_dec:
                    swap_reason = "NB shorter-priced / market favourite (market swap)"

            if swap_reason:
                # SWAP selection and NB
                old_sel_horse = horse
                old_nb_horse = nb.get("horse", "")

                # Swap horses, odds, scores, reasoning
                sel["horse"], nb["horse"] = nb["horse"], sel["horse"]
                sel["odds_guide"], nb["odds_guide"] = nb["odds_guide"], sel["odds_guide"]
                sel["adjusted_score"], nb["adjusted_score"] = nb.get("adjusted_score", nb_score), score
                sel["each_way"] = _should_be_each_way_from_odds(nb_odds, sel.get("race_name", ""), 0)
                nb["each_way"] = _should_be_each_way_from_odds(odds, sel.get("race_name", ""), 0)

                # Swap reasoning
                old_sel_reasoning = sel.get("reasoning", [])
                old_nb_reasoning = nb.get("reasoning", "")
                sel["reasoning"] = [old_nb_reasoning] if isinstance(old_nb_reasoning, str) else old_nb_reasoning
                nb["reasoning"] = "; ".join(old_sel_reasoning) if isinstance(old_sel_reasoning, list) else old_sel_reasoning

                sel["danger"] = f"{nb['horse']} — original selection, swapped by compliance gate"

                compliance_fixes.append(
                    f"NB SWAP ENFORCED: {old_sel_horse} ({odds}, {score}pts) ↔ "
                    f"{old_nb_horse} ({nb_odds}, {nb_score}pts) — "
                    f"within 5pts, {swap_reason}"
                )
                logger.info(f"Compliance: NB swap {old_sel_horse} → {old_nb_horse} [{swap_reason}]")

        # CHECK 2: NO SUB-EVENS
        current_odds = sel.get("odds_guide", "")
        if _is_sub_evens(current_odds):
            if nb and nb.get("horse"):
                old_horse = sel["horse"]
                # Replace selection with NB
                sel["horse"] = nb["horse"]
                sel["odds_guide"] = nb.get("odds_guide", "CHECK PRICE")
                sel["adjusted_score"] = nb.get("adjusted_score", 0)
                sel["reasoning"] = [nb.get("reasoning", "")] if isinstance(nb.get("reasoning"), str) else nb.get("reasoning", [])
                nb["horse"] = old_horse
                nb["odds_guide"] = current_odds
                compliance_fixes.append(
                    f"SUB-EVENS BLOCKED: {old_horse} ({current_odds}) replaced with {sel['horse']}"
                )
                logger.info(f"Compliance: Sub-evens {old_horse} blocked, replaced with {sel['horse']}")
            else:
                compliance_fixes.append(
                    f"SUB-EVENS WARNING: {sel['horse']} ({current_odds}) — no NB to swap in"
                )
                logger.warning(f"Compliance: Sub-evens {sel['horse']} but no NB to replace")

    # CHECK 5: NAP THRESHOLD (v4.1: 75+, was 78+ in v3)
    nap_idx = selections.get("nap_index", 0)
    if nap_idx >= 0 and nap_idx < len(sels):
        nap_score = sels[nap_idx].get("adjusted_score", 0)
        nap_horse = sels[nap_idx].get("horse", "")
        if nap_score < NAP_THRESHOLD:
            selections["nap_index"] = -1
            compliance_fixes.append(
                f"NAP BLOCKED: Score {nap_score} < {NAP_THRESHOLD} threshold. Flat stakes today"
            )
            logger.info(f"Compliance: NAP blocked, score {nap_score} < {NAP_THRESHOLD}")

    # CHECK 6: PRICE CAPS (added 5 May 2026 after Fairlawn Flyer 22/1 NAP
    # at Ffos Las scored 81 despite 149-day absence — score 81 in a
    # competitive 10-runner Class 4 chase ≠ 25%+ win probability. Market at
    # 22/1 implies ~4%. The market's pricing is information; a high score
    # alone is not enough to override it for the NAP/NB-of-day slot.)
    nap_idx = selections.get("nap_index", -1)
    if nap_idx >= 0 and nap_idx < len(sels):
        nap_odds = sels[nap_idx].get("odds_guide", "")
        if _exceeds_nap_cap(nap_odds):
            old_horse = sels[nap_idx].get("horse", "")
            selections["nap_index"] = -1
            compliance_fixes.append(
                f"NAP PRICE CAP: {old_horse} ({nap_odds}) exceeds 10/1 NAP cap. "
                f"Demoted to race SEL — flat stakes day, no NAP"
            )
            logger.info(f"Compliance: NAP cap blocked {old_horse} at {nap_odds}")

    # NB-of-day price cap (selection at index 1 by convention)
    if len(sels) > 1:
        nb_of_day = sels[1]
        nb_odds = nb_of_day.get("odds_guide", "")
        if _exceeds_nb_cap(nb_odds):
            old_horse = nb_of_day.get("horse", "")
            # Demote NB-of-day to a regular race SEL stake — leave the
            # selection in place but flag in compliance log so the staking
            # block treats it like a 0.75pt race SEL rather than a 1.5pt
            # NB-of-day. The display formatter inspects this fix line.
            nb_of_day["nb_price_capped"] = True
            compliance_fixes.append(
                f"NB-OF-DAY PRICE CAP: {old_horse} ({nb_odds}) exceeds 14/1 NB cap. "
                f"Demoted to race SEL stake (0.75pt) — flagged for staking block"
            )
            logger.info(f"Compliance: NB-of-day cap blocked {old_horse} at {nb_odds}")

    # CHECK 8: AW CLASS 5/6 WEIGHT-RISE BLOCKER (Rule A — added 7 May 2026)
    # 3+ wins in last 5 starts AND Spotlight indicates a +7lb rise → max NB
    # role (NAP demoted). +10lb → flag in compliance log as "should skip".
    # Triggered by Roaring Ralph (-22111, +9lb after C&D hat-trick) NAP'd
    # 9/2 → 7th of 11 at Southwell 7 May. Class 5/6 AW horses are
    # mature/exposed; the handicapper's rise is reliably punitive in this
    # echo chamber. Rule does NOT apply at Group/Listed/big-handicap level.
    for i, sel in enumerate(sels):
        horse = sel.get("horse", "")
        sr = scored_lookup.get(horse.lower()) if horse else None
        if not sr:
            continue
        race_name = sel.get("race_name", "")
        meta = race_meta_lookup.get((race_name or "").lower(), {})
        if not _is_aw_c5_or_c6_handicap(race_name, meta):
            continue
        runner = sr.runner
        wins_in_5 = _count_wins_in_last_5(runner.form or "")
        if wins_in_5 < 3:
            continue
        rise = _extract_weight_rise_lb(runner.comment or "")
        if rise >= 7:
            if selections.get("nap_index") == i:
                selections["nap_index"] = -1
                compliance_fixes.append(
                    f"AW C5/6 WEIGHT-RISE: {horse} (+{rise}lb after {wins_in_5} wins "
                    f"in last 5) — NAP blocked, kept as race SEL only"
                )
                logger.info(
                    f"Compliance: AW C5/6 +{rise}lb NAP demote for {horse}"
                )
            if rise >= 10:
                # Flag strong skip recommendation in log; don't auto-remove
                # the selection (let user/analyst decide), since removing
                # mid-list invalidates indexes that other checks depend on.
                compliance_fixes.append(
                    f"AW C5/6 WEIGHT-RISE STRONG: {horse} (+{rise}lb) — rule says SKIP "
                    f"entirely; kept in list but flat stakes only, consider dropping"
                )

    # CHECK 9: AW CLASS 5/6 NO-NAP-ON-FAVOURITE (Rule B — added 7 May 2026)
    # If the NAP candidate is also the betting market favourite (or co-fav
    # within ~5%) at sub-4/1 in an AW Class 5/6 handicap → no NAP that day
    # (flat stakes). At sub-4/1 in compressed C5/6 form the framework's
    # score adds nothing the market hasn't already priced — ROI is
    # bookmaker-margin negative by construction. Triggered by Shades Of
    # May 3/1F top scorer 78 → 8th of 10 at Southwell 7 May.
    nap_idx = selections.get("nap_index", -1)
    if nap_idx >= 0 and nap_idx < len(sels):
        nap = sels[nap_idx]
        nap_horse = nap.get("horse", "")
        nap_odds = nap.get("odds_guide", "")
        nap_dec = _parse_odds_to_decimal(nap_odds)
        nap_race_name = nap.get("race_name", "")
        nap_meta = race_meta_lookup.get((nap_race_name or "").lower(), {})
        if (
            _is_aw_c5_or_c6_handicap(nap_race_name, nap_meta)
            and nap_dec > 0
            and nap_dec <= 4.0
        ):
            runners_odds = nap_meta.get("runners", [])
            valid = [(n, d) for (n, d) in runners_odds if d > 0]
            if valid:
                fav_dec = min(d for (_, d) in valid)
                # Co-favourite tolerance ~5% of decimal price
                is_market_fav = abs(nap_dec - fav_dec) <= max(0.25, 0.05 * fav_dec)
                if is_market_fav:
                    selections["nap_index"] = -1
                    compliance_fixes.append(
                        f"AW C5/6 NO-NAP-FAV: {nap_horse} ({nap_odds}, dec {nap_dec:.2f}) "
                        f"is market favourite (fav dec {fav_dec:.2f}) at sub-4/1 in "
                        f"AW Class 5/6 handicap — NAP blocked, flat stakes day"
                    )
                    logger.info(
                        f"Compliance: AW C5/6 no-NAP-fav blocked {nap_horse} at {nap_odds}"
                    )

    # CHECK 10: C5/C6 SCORE-VS-MARKET GATE (Option B — added 8 May 2026)
    # In ANY Class 5 / Class 6 race (AW or turf), if a selection scores 80+
    # AND the best decimal odds are 9.0+ (i.e. 8/1 or longer), the score
    # has materially diverged from the market's view. The framework over-
    # counts recyclable-pool form in compressed C5/C6 fields — an 80+ score
    # at 8/1+ means rubric inflation, not edge. Demote NAP / NB-of-day /
    # promoted-NB to race SEL stake. Pattern: Fairlawn Flyer 22/1 score 81
    # (Ffos Las 5 May), Star Prospect 88, Precise score 104, Novamay 86
    # at 16/1 (Ripon 8 May, C4 — note this gate is C5/C6-scoped per user
    # decision; the validation comes from the broader pattern). Premium-
    # class scoring (Class 1-4, Listed, Group, Grade) keeps full ceiling.
    for i, sel in enumerate(sels):
        horse = sel.get("horse", "")
        score = sel.get("adjusted_score", 0)
        odds = sel.get("odds_guide", "")
        dec = _parse_odds_to_decimal(odds)
        race_name = sel.get("race_name", "")
        meta = race_meta_lookup.get((race_name or "").lower(), {})
        if not _is_c5_or_c6_any(meta):
            continue
        if score < 80:
            continue
        if dec < 9.0:
            continue
        # Score-market divergence — demote to race SEL stake
        was_nap = selections.get("nap_index") == i
        if was_nap:
            selections["nap_index"] = -1
            compliance_fixes.append(
                f"C5/C6 SCORE-MARKET GATE: {horse} ({odds}, score {score}) — "
                f"score 80+ AND price 8/1+ in C5/C6 race; NAP blocked "
                f"(score-market divergence too wide)"
            )
            logger.info(
                f"Compliance: C5/C6 score-market gate blocked NAP for {horse} "
                f"at {odds} (score {score})"
            )
        # Flag NB-of-day (rank 2 in selections is bot's NB-of-day convention)
        if i == 1:
            sel["nb_price_capped"] = True
            compliance_fixes.append(
                f"C5/C6 SCORE-MARKET GATE: {horse} ({odds}, score {score}) — "
                f"NB-of-day demoted to race SEL stake (0.75pt) — "
                f"score-market divergence too wide for 1.5pt slot"
            )
            logger.info(
                f"Compliance: C5/C6 score-market gate demoted NB-of-day "
                f"{horse} to race SEL stake"
            )

    # CHECK 7: SYSTEM-RESISTANT RACES — demote to E/W, prevent NAP
    for i, sel in enumerate(sels):
        race_name = sel.get("race_name", "")
        meta = race_meta_lookup.get((race_name or "").lower(), {})
        num_runners = meta.get("num_runners", 12)
        if _is_system_resistant_race(
            race_name,
            num_runners,
            race_type=meta.get("race_type", ""),
            pattern=meta.get("pattern", ""),
            distance=meta.get("distance", ""),
            race_class=meta.get("race_class", ""),
        ):
            sel["each_way"] = True
            if selections.get("nap_index") == i:
                selections["nap_index"] = -1
                compliance_fixes.append(
                    f"SYSTEM-RESISTANT: {sel['horse']} in {race_name} — NAP removed, E/W only"
                )
                logger.info(f"Compliance: System-resistant race, NAP removed for {sel['horse']}")

    # Log all fixes
    if compliance_fixes:
        existing_log = selections.get("compliance_log", [])
        selections["compliance_log"] = existing_log + [f"[GATE FIX] {fix}" for fix in compliance_fixes]
        logger.info(f"Compliance gate applied {len(compliance_fixes)} fix(es)")
    else:
        logger.info("Compliance gate: all checks passed, no fixes needed")

    return selections


def _should_be_each_way_from_odds(odds_str: str, race_name: str, num_runners: int) -> bool:
    """Determine each-way from odds string."""
    dec = _parse_odds_to_decimal(odds_str)
    return dec >= 3.0


def analyse_all_meetings(meetings: list[Meeting], tips_text: str = "",
                         going_reports: dict = None,
                         n_races: int = None) -> dict:
    """
    Cherry-pick mode: score ALL meetings, send top races to Claude,
    apply compliance gate, return the best 3 selections.

    If n_races is set, deterministically pick the top N races by
    top-runner score (gap-to-2nd as tiebreak), with Operating Policy
    floor (top scorer must be 70+).
    """
    if not meetings:
        return {}

    if going_reports is None:
        going_reports = {}

    # Step 1: Score everything programmatically
    scorer = Scorer()
    all_scored = []

    for meeting in meetings:
        for race in meeting.races:
            if not race.runners:
                continue
            scored = scorer.score_race(race)
            for sr in scored:
                all_scored.append((sr, race, meeting))

    if not all_scored:
        return {}

    # Step 2: Build per-race scored lists, then choose target races
    races_by_key = {}
    for sr, race, meeting in all_scored:
        key = f"{meeting.course}_{race.time}"
        if key not in races_by_key:
            races_by_key[key] = (scorer.score_race(race), race, meeting)

    if n_races:
        # /run N mode: rank races by top-runner score, gap-to-2nd tiebreak
        ranked = []
        for race_scored, race, meeting in races_by_key.values():
            if not race_scored:
                continue
            top1 = race_scored[0].total
            top2 = race_scored[1].total if len(race_scored) > 1 else 0
            gap = top1 - top2
            ranked.append((top1, gap, race_scored, race, meeting))
        ranked.sort(key=lambda x: (-x[0], -x[1]))

        # Operating Policy floor — drop races whose top scorer is <70
        qualifying = [r for r in ranked if r[0] >= 70]
        dropped = len(ranked) - len(qualifying)
        if dropped:
            logger.info(
                f"/run {n_races}: {dropped} races dropped — top scorer < 70 (Operating Policy)"
            )

        chosen = qualifying[:n_races]
        top_races_data = [(rs, race, meeting) for _, _, rs, race, meeting in chosen]

        if not top_races_data:
            logger.warning(
                f"/run {n_races}: no races qualify (no top scorer ≥70). Returning empty."
            )
            return {
                "selections": [],
                "double": {},
                "nap_index": -1,
                "notes": (
                    f"You asked for top {n_races} races but no card has a runner "
                    f"scoring 70+. Operating Policy says skip — try later or use "
                    f"/run without a number."
                ),
            }

        if len(top_races_data) < n_races:
            logger.info(
                f"/run {n_races}: only {len(top_races_data)} races qualify at 70+. "
                f"Returning those."
            )

        logger.info(
            f"Scored {len(all_scored)} runners across {len(meetings)} meetings. "
            f"Cherry-picked top {len(top_races_data)} of {n_races} requested races."
        )
    else:
        # Default mode: top runners across all meetings → distinct races
        all_scored.sort(key=lambda x: x[0].total, reverse=True)
        top_runners = all_scored[:60]

        top_race_keys = set()
        top_races_data = []
        for sr, race, meeting in top_runners:
            key = f"{meeting.course}_{race.time}"
            if key not in top_race_keys:
                top_race_keys.add(key)
                top_races_data.append(races_by_key[key])

        logger.info(
            f"Scored {len(all_scored)} runners across {len(meetings)} meetings. "
            f"Top {len(top_races_data)} races ({len(top_runners)} runners) sent for judgement."
        )

    # Build scored lookup for compliance gate
    scored_lookup = {}
    race_meta_lookup = {}
    for scored_runners, race, meeting in top_races_data:
        for sr in scored_runners:
            scored_lookup[sr.runner.name.lower()] = sr
        # race meta keyed by lowercased name — compliance gate looks up
        # selection by race_name to enforce system-resistant + sub-evens.
        # course / surface / runners-with-odds added 7 May 2026 for AW
        # Class 5/6 targeted rules (weight-rise blocker + no-NAP-on-fav).
        race_meta_lookup[(race.name or "").lower()] = {
            "num_runners": race.num_runners,
            "race_type": race.race_type or "",
            "pattern": getattr(race, "pattern", "") or "",
            "distance": race.distance or "",
            "race_class": race.race_class or "",
            "course": meeting.course or "",
            "surface": race.surface or "",
            "runners": [
                (sr.runner.name.lower(), _parse_odds_to_decimal(sr.runner.odds or ""))
                for sr in scored_runners
            ],
        }

    # Step 3: Claude judgement
    try:
        selections = _run_claude_judgement(
            top_races_data, meetings, tips_text, going_reports,
            n_races=n_races,
        )
        if selections and selections.get("selections"):
            logger.info(f"Claude picked {len(selections['selections'])} selections")

            # Step 3.5: COMPLIANCE GATE — enforce rules programmatically
            selections = _enforce_compliance(selections, scored_lookup, race_meta_lookup)

            return selections
        logger.warning("Claude returned empty, falling back to programmatic")
    except Exception as e:
        logger.error(f"Claude judgement failed: {e}", exc_info=True)

    # Step 4: Fallback (also gets compliance gate)
    fallback = _programmatic_cherry_pick(top_races_data, n_races=n_races)
    fallback = _enforce_compliance(fallback, scored_lookup, race_meta_lookup)
    return fallback


def _run_claude_judgement(top_races_data: list, meetings: list[Meeting],
                          tips_text: str, going_reports: dict,
                          n_races: int = None) -> dict:
    """Send scored data to Claude for final selection."""
    if not ANTHROPIC_API_KEY:
        logger.warning("No API key, skipping Claude judgement")
        return {}

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    parts = []
    if n_races:
        parts.append(
            f"CHERRY-PICK MODE: User requested top {n_races} races. "
            f"You are given exactly {len(top_races_data)} pre-selected races below "
            f"(ranked by top-runner score). Return ONE selection per race — "
            f"so exactly {len(top_races_data)} entries in the selections array. "
            f"This OVERRIDES the system prompt's '4 selections' default. "
            f"NAP/NB-of-day discipline still applies (NAP must score 75+ or set "
            f"nap_index to -1). Each entry needs its own next_best."
        )
        parts.append("")
    parts.append("TODAY'S UK/IRISH RACING - TOP SCORING RACES FOR ANALYSIS")
    parts.append(f"\nMeetings scanned: {', '.join(m.course + ' (' + (m.going or '?') + ')' for m in meetings)}")

    for course, report in going_reports.items():
        if report:
            parts.append(f"\nGOING ({course}): {report[:500]}")

    if tips_text:
        parts.append(f"\n{tips_text[:3000]}")

    parts.append("\n" + "=" * 60)
    parts.append("RACES AND RUNNERS (sorted by top runner score):")
    parts.append("=" * 60)

    for scored_runners, race, meeting in top_races_data:
        race = next((r for r in meeting.races if r.time == race.time), race)

        # Flag system-resistant races
        resistant_flag = ""
        if _is_system_resistant_race(
            race.name, race.num_runners, race.race_type,
            pattern=getattr(race, "pattern", "") or "",
            distance=race.distance or "",
            race_class=race.race_class or "",
        ):
            resistant_flag = " ⚠️ SYSTEM-RESISTANT (half stakes, E/W only, never NAP)"

        parts.append(f"\n{'─' * 55}")
        parts.append(f"{race.time} {meeting.course} - {race.name}{resistant_flag}")
        parts.append(
            f"{race.distance} | {race.race_class or ''} {race.race_type or ''} | "
            f"Going: {race.going or meeting.going or '?'} | Runners: {race.num_runners} | "
            f"Prize: {race.prize_money or '?'}"
        )
        parts.append(f"{'─' * 55}")

        for sr in scored_runners:
            r = sr.runner
            or_val = r.official_rating or 0
            rpr_val = r.rpr or 0
            ts_val = r.speed_figure or 0

            rpr_gap = f"(+{rpr_val - or_val})" if or_val and rpr_val and rpr_val > or_val else ""
            ts_gap = f"(+{ts_val - or_val})" if or_val and ts_val and ts_val > or_val else ""

            # Build intent signal flags
            signals = []
            if r.first_time_headgear:
                signals.append(f"1st-time-{r.headgear or 'HG'}")
            if r.wind_surgery:
                signals.append("WIND-OP")
            if r.trainer_14d_pct and r.trainer_14d_pct >= 20:
                signals.append(f"HotStable{r.trainer_14d_pct}%")

            sig_str = f" SIGNALS: [{', '.join(signals)}]" if signals else ""
            compound = " ⚡COMPOUND" if len(signals) >= 3 else ""

            # v4.1 (1 May 2026): role flags removed — TS-veto and dual-edge
            # rules were dropped after 8 vetoed winners and 0W from dual-edge

            parts.append(
                f"\n  {r.name} | Score: {sr.total:.0f}/100"
                f"\n    ODDS: {r.odds or 'NO PRICE'} (Bet365, live from API)"
                f"\n    Form: {r.form or '?'} | Age: {r.age or '?'} | "
                f"Wt: {r.weight_stones or '?'}-{r.weight_pounds or '?'} | "
                f"OR: {or_val or '?'} | RPR: {rpr_val or '?'} {rpr_gap} | "
                f"TS: {ts_val or '?'} {ts_gap}"
                f"\n    Jockey: {r.jockey or '?'} | Trainer: {r.trainer or '?'} "
                f"(14d: {r.trainer_14d_pct or '?'}%)"
                f"\n    Days off: {r.days_since_run or '?'} | Draw: {r.draw or 'N/A'} | "
                f"Sex: {r.sex or '?'}"
                f"\n    C&D: {r.cd_winner} | Course: {r.course_winner} | "
                f"Dist: {r.distance_winner}"
                f"\n    Headgear: {r.headgear or 'none'} | "
                f"1st-time HG: {r.first_time_headgear} | "
                f"Wind op: {r.wind_surgery}"
                f"\n    Sire: {r.sire or '?'} | Dam: {r.dam or '?'}"
                f"\n    Score breakdown: [F:{sr.form_score:.0f} C:{sr.course_score:.0f} "
                f"G:{sr.going_score:.0f} D:{sr.distance_score:.0f} "
                f"Cl:{sr.class_score:.0f} Sp:{sr.speed_score:.0f} "
                f"Wt:{sr.weight_score:.0f} J:{sr.jockey_score:.0f} "
                f"T:{sr.trainer_score:.0f} Edge:{sr.edge_bonus:.0f}]"
                f"{sig_str}{compound}"
            )
            if sr.edge_details:
                parts.append(f"    Edges: {', '.join(sr.edge_details)}")
            if r.comment:
                parts.append(f"    Spotlight: {r.comment[:300]}")
            if r.stable_tour:
                parts.append(f"    Stable tour: {r.stable_tour[:150]}")

    prompt = "\n".join(parts)

    response = client.messages.create(
        model=JUDGEMENT_MODEL,
        max_tokens=6000,
        system=ANALYST_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()

    usage = response.usage
    logger.info(f"Claude API ({JUDGEMENT_MODEL}): {usage.input_tokens} in / {usage.output_tokens} out tokens")

    # Robust JSON extraction
    if "```json" in text:
        text = text.split("```json", 1)[1]
        if "```" in text:
            text = text.split("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1]
        if "```" in text:
            text = text.split("```", 1)[0]

    text = text.strip()

    # Find the first { and last } to extract JSON object
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        text = text[first_brace:last_brace + 1]

    logger.debug(f"Parsing JSON ({len(text)} chars): {text[:200]}...")
    return json.loads(text)


def _programmatic_cherry_pick(top_races_data: list, n_races: int = None) -> dict:
    """Fallback: pick top SEL+NB per race from programmatic scores alone."""
    all_picks = []
    for scored_runners, race, meeting in top_races_data:
        if len(scored_runners) < 2:
            continue
        sel = scored_runners[0]
        nb = scored_runners[1]
        all_picks.append({"sel": sel, "nb": nb, "race": race, "meeting": meeting})

    all_picks.sort(key=lambda x: x["sel"].total, reverse=True)

    cap = n_races if n_races else NUM_SELECTIONS
    selections = []
    for i, pick in enumerate(all_picks[:cap]):
        sel = pick["sel"]
        nb = pick["nb"]
        race = pick["race"]
        meeting = pick["meeting"]

        conf = "HIGH" if sel.total >= 75 else "MEDIUM-HIGH" if sel.total >= 68 else "MEDIUM"
        selections.append({
            "rank": i + 1,
            "horse": sel.runner.name,
            "race_time": race.time,
            "race_name": race.name,
            "course": meeting.course,
            "odds_guide": sel.runner.odds or "CHECK PRICE",
            "confidence": conf,
            "reasoning": _quick_reasons(sel),
            "danger": f"{nb.runner.name}",
            "each_way": _is_each_way(sel.runner, race),
            "adjusted_score": round(sel.total, 1),
            "nb_score": round(nb.total, 1),
            "next_best": {
                "horse": nb.runner.name,
                "odds_guide": nb.runner.odds or "CHECK PRICE",
                "reasoning": _quick_reason_str(nb),
                "each_way": _is_each_way(nb.runner, race),
                "adjusted_score": round(nb.total, 1),
            },
        })

    double_legs = [s for s in selections if not _is_odds_on_str(s.get("odds_guide", ""))][:2]
    double = {}
    if len(double_legs) >= 2:
        double = {
            "leg1": f"{double_legs[0]['horse']} ({double_legs[0]['race_time']} {double_legs[0]['course']})",
            "leg2": f"{double_legs[1]['horse']} ({double_legs[1]['race_time']} {double_legs[1]['course']})",
            "reasoning": "NAP + NB",
            "combined_odds_approx": "?",
        }

    # NAP threshold check in fallback too
    nap_idx = 0
    if selections and selections[0].get("adjusted_score", 0) < NAP_THRESHOLD:
        nap_idx = -1

    return {
        "selections": selections,
        "double": double,
        "nap_index": nap_idx,
        "notes": "Programmatic fallback (Claude API unavailable)",
    }


def _sanitise_markdown(text: str) -> str:
    """Remove or escape characters that break Telegram Markdown parsing."""
    if not text:
        return ""
    # Replace problematic characters that break Telegram's Markdown V1 parser
    for char in ["*", "_", "`", "["]:
        text = text.replace(char, "")
    return text


def format_selections_telegram(selections: dict) -> str:
    """Format cherry-picked selections for Telegram — matches manual format exactly."""
    if not selections or not selections.get("selections"):
        return "⚠️ No selections today."

    sels = selections["selections"]
    nap_idx = selections.get("nap_index", 0)
    double = selections.get("double", {})
    notes = selections.get("notes", "")
    compliance_log = selections.get("compliance_log", [])

    msg = ""

    # NAP (only if something scored 75+, v4.1 threshold)
    if sels and nap_idx >= 0:
        nap = sels[nap_idx] if nap_idx < len(sels) else sels[0]
        msg += "═══════════════════════════\n"
        msg += "🏆 *NAP OF THE DAY*\n"
        msg += "═══════════════════════════\n"
        msg += f"*{nap['horse']}*\n"
        msg += f"📍 {nap['race_time']} {nap['course']}\n"
        msg += f"   {nap.get('race_name', '')}\n"
        ew = " (E/W)" if nap.get("each_way") else ""
        msg += f"💰 {nap['odds_guide']}{ew}\n"
        msg += f"📊 Score: {nap.get('adjusted_score', '?')}/100 | Confidence: {nap.get('confidence', '?')}\n\n"
        for r in nap.get("reasoning", []):
            msg += f"• {_sanitise_markdown(r)}\n"
        msg += f"\n⚠️ Danger: {_sanitise_markdown(nap.get('danger', '?'))}\n"
    elif sels and nap_idx < 0:
        msg += "═══════════════════════════\n"
        msg += "⚠️ *NO NAP TODAY*\n"
        msg += "═══════════════════════════\n"
        msg += "Nothing scored 75+. Flat 1pt stakes across all selections.\n"

    # Next Best (rank 2)
    if len(sels) >= 2 and nap_idx >= 0:
        nb_idx = 1 if nap_idx == 0 else 0
        nb = sels[nb_idx]
        msg += "\n═══════════════════════════\n"
        msg += "⭐ *NEXT BEST*\n"
        msg += "═══════════════════════════\n"
        msg += f"*{nb['horse']}*\n"
        msg += f"📍 {nb['race_time']} {nb['course']}\n"
        ew = " (E/W)" if nb.get("each_way") else ""
        msg += f"💰 {nb['odds_guide']}{ew}\n"
        msg += f"📊 Score: {nb.get('adjusted_score', '?')}/100\n\n"
        for r in nb.get("reasoning", []):
            msg += f"• {_sanitise_markdown(r)}\n"
        msg += f"\n⚠️ Danger: {_sanitise_markdown(nb.get('danger', '?'))}\n"

    # All selections
    msg += "\n═══════════════════════════\n"
    msg += "📋 *TODAY'S SELECTIONS*\n"
    msg += "═══════════════════════════\n"

    for sel in sels:
        rank_emoji = "🏆" if sel["rank"] == nap_idx + 1 and nap_idx >= 0 else "⭐" if sel["rank"] == 2 else "📌"
        ew = " (E/W)" if sel.get("each_way") else ""
        msg += f"\n{rank_emoji} *{sel['rank']}. {sel['horse']}* {sel['odds_guide']}{ew}\n"
        msg += f"   {sel['race_time']} {sel['course']} ({sel.get('adjusted_score', '?')}pts)\n"

        reasons = sel.get("reasoning", [])
        if isinstance(reasons, list) and reasons:
            msg += f"   _{_sanitise_markdown(reasons[0])}_\n"
        elif isinstance(reasons, str):
            msg += f"   _{_sanitise_markdown(reasons)}_\n"

        rnb = sel.get("next_best", {})
        if rnb and rnb.get("horse"):
            nb_ew = " (E/W)" if rnb.get("each_way") else ""
            msg += f"   NB: {rnb['horse']} {rnb.get('odds_guide', '?')}{nb_ew}\n"

    # Double
    if double and nap_idx >= 0:
        msg += "\n═══════════════════════════\n"
        msg += "🔗 *DOUBLE*\n"
        msg += "═══════════════════════════\n"
        msg += f"{double.get('leg1', '?')}\n"
        msg += f"{double.get('leg2', '?')}\n"
        if double.get("combined_odds_approx"):
            msg += f"Approx: {double['combined_odds_approx']}\n"

    # Staking
    msg += "\n═══════════════════════════\n"
    msg += "💷 *STAKING*\n"
    msg += "═══════════════════════════\n"
    nb_capped = (
        len(sels) > 1
        and sels[1].get("nb_price_capped", False)
    )
    if nap_idx >= 0:
        if nb_capped:
            msg += "NAP: 2pts | NB-of-day capped at 14/1: 0.75pt (race SEL stake)\n"
        else:
            msg += "NAP: 2pts | NB: 1.5pts\n"
        msg += "Selections 3-4: 0.75pt each\n"
    else:
        msg += "All selections: 1pt flat (no NAP today)\n"
    msg += "Race NBs: 0.75pt each\n"
    if nap_idx >= 0 and not nb_capped:
        msg += "Double: 1pt\n"
    msg += "\n⏰ *TAKE EARLY PRICES - NEVER SP*"

    # Compliance gate fixes (if any)
    gate_fixes = [c for c in compliance_log if c.startswith("[GATE FIX]")]
    if gate_fixes:
        msg += "\n\n🔒 *Compliance Gate*\n"
        for fix in gate_fixes:
            msg += f"• {fix.replace('[GATE FIX] ', '')}\n"

    if notes:
        msg += f"\n\n📝 _{_sanitise_markdown(notes)}_"

    return msg


def _is_each_way(runner: Runner, race: Race) -> bool:
    if not race or race.num_runners < 8:
        return False
    odds = runner.odds
    if not odds:
        return True
    match = re.match(r"(\d+)/(\d+)", odds)
    if match:
        return int(match.group(1)) / int(match.group(2)) >= 3.0
    return False


def _is_odds_on_str(odds: str) -> bool:
    if not odds or odds == "CHECK PRICE":
        return False
    match = re.match(r"(\d+)/(\d+)", odds)
    if match:
        return int(match.group(1)) < int(match.group(2))
    return False


def _quick_reasons(sr: RunnerScore) -> list[str]:
    reasons = []
    if sr.form_score >= 16:
        reasons.append(f"Strong form ({sr.form_score:.0f}/22)")
    if sr.runner.cd_winner:
        reasons.append("C&D winner")
    elif sr.runner.course_winner:
        reasons.append("Course winner")
    if sr.speed_score >= 6:
        reasons.append("Speed figures ahead of OR")
    if sr.runner.wind_surgery:
        reasons.append("First run post wind surgery")
    if sr.runner.first_time_headgear:
        reasons.append("First-time headgear")
    if not reasons:
        reasons.append(f"Top score: {sr.total:.0f}/100")
    return reasons


def _quick_reason_str(sr: RunnerScore) -> str:
    return "; ".join(_quick_reasons(sr))
