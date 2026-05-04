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
4. NAP must score 75+ (v4.1, dropped from v3's 78+). If nothing qualifies, set nap_index to -1
5. NB SWAP RULE — split into mandatory market swap and gated value swap:
   (a) MARKET SWAP (MANDATORY): scores within 5pts AND NB is shorter-priced / market favourite → swap. Trust the market. Validated 14 Apr: Mister Winston 9/4F won where Great Chieftain 100/30 NAP failed; Jakajaro 4/1F won where Regal Envoy 9/2 sel finished 3rd. Validated 29 Apr Pontefract: Walsingham 9/4F won (against On The River sel), Lightening Co 2/1JF won (against Bearwith sel)
   (b) VALUE SWAP (CONSIDER WITH SPOTLIGHT GATE): scores within 5pts AND NB is 2x+ the sel odds → consider, but DO NOT promote if NB Spotlight contains negative phrases ("hard to fancy", "needs to improve", "may prove resurgent", "best watched", "needs further", "not the percentage call", "much to find", "ideally needs", "not totally convincing", "loads to find"). The compliance gate blocks suppressed swaps automatically — log shows "VALUE SWAP BLOCKED". Validated 27 Apr: Diamondsinthesand 33/1 (Spotlight "ideally needs further") and Nakaaha 9/1 (Spotlight "may prove resurgent") both bot value-swap promotions; Diamonds UP, Nakaaha 2nd only
6. QUICK TURNAROUND: NH horse back within 7 days = already penalised -5 in scorer. Respect that penalty
7. SYSTEM-RESISTANT RACES: Big-field finals (12+ runners), Pertemps/Veterans/series finals, Foxhunters, bumpers with 15+ runners, early-season 3yo Flat handicaps (Mar/Apr/early May) with 12+ runners = half stakes, E/W only, NEVER NAP. (v4.1 dropped: 16+ Listed sprint rule, 3yo all-types extension)
8. ONE selection per race maximum
9. Score EVERY runner in target races before picking. No shortcuts
10. NEVER override our RPR/TS pick entirely for Timeform. When they disagree, keep BOTH as contenders
11. CLASS-DROP KICKER QUALITY FILTER (added 21 Apr after Pontefract 0-3): The scorer now skips the kicker when the higher-grade placed run was foreign, on AW with today on turf, or qualified in Spotlight as "weak form for the grade". If the kicker appears in Edges, trust it — if a Spotlight mentions a higher-grade placing but NO kicker shows, the quality filter fired, don't manually re-apply

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

## PRE-OUTPUT COMPLIANCE CHECKLIST (v4.1 — 4 CHECKS)

Before returning your JSON, verify EACH selection against these 4 checks. Do NOT add additional checks (the v3 9-check version with TS-VETO and DUAL-EDGE was dropped in v4.1). Hard rules 4 (NAP 75+), 6 (quick-turnaround), and 7 (system-resistant) are enforced by the scorer / hard-rule application above and don't need separate compliance entries:

1. MARKET SWAP (mandatory branch a): For each sel-vs-NB pair, scores within 5pts AND NB shorter-priced / market favourite? → SWAP. No discretion, no Spotlight gate on this branch.
2. NO EVENS-OR-SHORTER: Any selection priced ≤ 1/1 (e.g. EvensF, 4/5, 4/6, 1/2)? → Replace with NB. NOTE: 5/4, 6/4, 11/8, 7/4 are NOT sub-evens — do NOT block these. Being favourite alone is not a reason to demote.
3. SPOTLIGHT: Any negative language on selections? Any negative language on NB before a value-swap promotion? → Downgrade or block swap (per Rule 5b).
4. ALL RUNNERS SCORED: Did you consider every horse in target races? → If not, go back.

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
    "CHECK 4 FULL FIELD: All runners scored in 4 target races — PASS"
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

        # CHECK 1: NB SWAP RULE (BIDIRECTIONAL)
        # (a) VALUE SWAP: scores close AND NB is 2x+ the odds → chase value
        #     GATED 27 Apr 2026: suppress when NB Spotlight contains negative
        #     phrases (Diamondsinthesand "ideally needs further" UP and
        #     Nakaaha "may prove resurgent" 2nd-only validated the gate)
        # (b) MARKET SWAP: scores close AND NB is shorter-priced / favourite → trust market
        # Both validated 14 Apr 2026: Great Chieftain NAP (100/30) vs Mister
        # Winston NB (9/4F) — NB won; Regal Envoy (9/2) vs Jakajaro (4/1F) — NB won
        if nb and nb_score > 0 and score > 0:
            score_gap = abs(score - nb_score)
            sel_dec = _parse_odds_to_decimal(odds)
            nb_dec = _parse_odds_to_decimal(nb_odds)

            swap_reason = None
            if score_gap <= 5 and sel_dec > 0 and nb_dec > 0:
                if nb_dec >= (sel_dec * 2):
                    # Apply Spotlight gate to value swap only
                    nb_comment = ""
                    if nb_sr is not None and getattr(nb_sr, "runner", None) is not None:
                        nb_comment = getattr(nb_sr.runner, "comment", "") or ""
                    if _has_negative_spotlight(nb_comment):
                        compliance_fixes.append(
                            f"VALUE SWAP BLOCKED: {nb_horse} ({nb_odds}) has "
                            f"negative Spotlight — keeping {horse} ({odds}) as SEL. "
                            f"Spotlight gate added 27 Apr"
                        )
                        logger.info(
                            f"Compliance: value swap blocked, {nb_horse} has "
                            f"negative Spotlight"
                        )
                    else:
                        swap_reason = "NB 2x+ odds (value swap)"
                elif nb_dec < sel_dec:
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
        # selection by race_name to enforce system-resistant + sub-evens
        race_meta_lookup[(race.name or "").lower()] = {
            "num_runners": race.num_runners,
            "race_type": race.race_type or "",
            "pattern": getattr(race, "pattern", "") or "",
            "distance": race.distance or "",
            "race_class": race.race_class or "",
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
    if nap_idx >= 0:
        msg += "NAP: 2pts | NB: 1.5pts\n"
        msg += "Selections 3-4: 1pt each\n"
    else:
        msg += "All selections: 1pt flat (no NAP today)\n"
    msg += "Race NBs: 0.5pt each\n"
    if nap_idx >= 0:
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
