"""
100-point scoring system codified from CLAUDE.md analysis framework.

Programmatically scores runners on the ~70% of factors that can be
quantified. The remaining ~30% (judgement calls) are handled by the
analyst module via Claude API.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from src.scraper import Runner, Race

logger = logging.getLogger(__name__)


@dataclass
class RunnerScore:
    """Scored runner with breakdown."""
    runner: Runner
    form_score: float = 0.0
    course_score: float = 0.0
    going_score: float = 0.0
    distance_score: float = 0.0
    class_score: float = 0.0
    speed_score: float = 0.0
    weight_score: float = 0.0
    jockey_score: float = 0.0
    trainer_score: float = 0.0
    edge_bonus: float = 0.0
    edge_details: list[str] = None
    total: float = 0.0
    judgement_adjustment: float = 0.0  # Added by analyst module
    judgement_notes: str = ""
    final_score: float = 0.0

    def __post_init__(self):
        if self.edge_details is None:
            self.edge_details = []


# --- Top jockeys/trainers for scoring ---

TOP_NH_JOCKEYS = {
    "paul townend", "harry cobden", "harry skelton", "nico de boinville",
    "brian hughes", "rachael blackmore", "danny mullins", "jack kennedy",
    "sean bowen", "jordan gainford", "mark walsh",
}

TOP_FLAT_JOCKEYS = {
    "william buick", "oisin murphy", "tom marquand", "ryan moore",
    "james doyle", "silvestre de sousa", "rossa ryan", "ben curtis",
    "jim crowley", "daniel tudhope",
}

TOP_NH_TRAINERS = {
    "willie mullins", "w p mullins", "gordon elliott", "dan skelton",
    "paul nicholls", "nicky henderson", "henry de bromhead",
    "gary moore", "nigel twiston-davies", "lucinda russell",
    "jonjo o'neill", "alan king", "kim bailey", "ben pauling",
    "olly murphy",
}

TOP_FLAT_TRAINERS = {
    "aidan o'brien", "charlie appleby", "john gosden",
    "william haggas", "karl burke", "andrew balding",
    "ralph beckett", "roger varian", "sir michael stoute",
    "richard hannon", "clive cox",
}

# Class hierarchy for comparison
CLASS_LEVELS_NH = {
    "grade 1": 10, "g1": 10,
    "grade 2": 9, "g2": 9,
    "grade 3": 8, "g3": 8,
    "listed": 7,
    "class 1": 6,
    "class 2": 5,
    "class 3": 4,
    "class 4": 3,
    "class 5": 2,
}

CLASS_LEVELS_FLAT = {
    "group 1": 11, "g1": 11,
    "group 2": 10, "g2": 10,
    "group 3": 9, "g3": 9,
    "listed": 8,
    "class 1": 7,
    "class 2": 6,
    "class 3": 5,
    "class 4": 4,
    "class 5": 3,
    "class 6": 2,
    "class 7": 1,
}


def _is_c5_or_c6(race) -> bool:
    """Class 5 or Class 6 detection. Used for targeted calibration patches
    (8 May 2026) — course-bonus decay, class-score cap, Flat DSLR penalty,
    and the score-vs-market gate. The framework over-rates compressed-pool
    handicaps; these patches deflate those scores by 5-9 points without
    touching premium-class scoring where the framework retains edge."""
    rc = (race.race_class or "").lower()
    return "class 5" in rc or "class 6" in rc


# Feature flag for Rule 18b (added 27 May 2026). Set False to disable.
# Behaviour returns to current state in <1 minute when toggled off.
RULE_18B_ENABLED = True

# Rule 18b margin guard (10 Jul 2026). Rule 18b excuses a poor finish in
# tougher company on the premise that the horse was COMPETITIVE at a level
# above today's. Position + class tier alone cannot tell "respectable 7th"
# from "tailed off last", so a rout was being excused identically to a
# near-miss. A candidate run is only excusable when the horse finished
# within this many lengths-per-furlong of the winner.
#
# Calibrated on 208 real result lines (10 Jul 2026 card):
#   Flat n=106: median 0.57, p90 1.84, p95 2.20
#   NH   n=102: median 0.83, p90 2.53, p95 3.04
#   Of 47 PLACED (1-2-3) NH runs, ZERO exceeded 2.00 L/f.
# Anchors:
#   PASS Classic Encounter, Spring Mile C2, 7th/22, 9.75L over 8f = 1.22 L/f
#        (the founding case for Rule 18b; he then WON at 11/8)
#   FAIL Flora Of Bermuda, Jubilee Gp1, 18th/18, 38.75L over 6f = 6.46 L/f
# Missing margin or trip => do NOT excuse (fail closed; matches the
# no-guessing convention in _blocked_favourite_dominates).
RULE_18B_MAX_BTN_PER_FURLONG = 2.0

# NH quick-turnaround penalty: require a WIN last time (14 Jul 2026).
# CLAUDE.md factor 11 has always said the -3 applies "8-14 days AFTER A HARD
# WIN for 8yo+"; the code checked only age and days, never the win. Set False
# to restore the pre-14-Jul (age+days only) behaviour.
QUICK_TURNAROUND_REQUIRE_WIN = True


def _race_class_tier(race) -> Optional[int]:
    """Return the numeric class tier of `race` using CLASS_LEVELS tables.
    Higher number = higher class quality. Returns None when the race has
    no resolvable class (e.g., Irish midweek unclassed cards)."""
    pattern = (getattr(race, "pattern", "") or "").lower()
    rt = (race.race_type or "").lower()
    is_nh = any(t in rt for t in ("chase", "hurdle", "nh flat"))
    class_map = CLASS_LEVELS_NH if is_nh else CLASS_LEVELS_FLAT
    if pattern:
        for label, lvl in class_map.items():
            if label in pattern:
                return lvl
    rc = (race.race_class or "").lower()
    if rc:
        for label, lvl in class_map.items():
            if label in rc:
                return lvl
    return None


def _rule18b_scope(race) -> bool:
    """Rule 18b scope guard. Mirrors base Rule 18 exactly.

    Fires only in Flat C4+ / NH C3+ / Group / Listed / Grade.
    NEVER fires in Flat C5/C6/C7 — preserves C5/6 calibration patches
    (8 May 2026) that exist BECAUSE the bot over-scores compressed-pool
    form. NEVER fires in NH C4/C5 — preserves NH class-floor logic.

    Pattern check first (G/L/Grade), then class string."""
    pattern = (getattr(race, "pattern", "") or "").lower()
    if any(p in pattern for p in ("group", "listed", "grade")):
        return True
    rc = (race.race_class or "").lower()
    rt = (race.race_type or "").lower()
    is_nh = any(t in rt for t in ("chase", "hurdle", "nh flat"))
    if is_nh:
        return any(x in rc for x in ("class 1", "class 2", "class 3"))
    return any(x in rc for x in ("class 1", "class 2", "class 3", "class 4"))


# Scorer recalibration (added 30 Jun 2026). Two coupled fixes diagnosed on
# Musselburgh 30 Jun, where the deterministic scorer INVERTED the field: The
# Gay Blade (C4 hcap, OR 71 / RPR 81 / TS 65 — the LOWEST TS in its race)
# scored 90, while genuine class horses (Son RPR 93/TS 92; cross-card High
# Degree RPR 105/TS 118) sat at 63-65. Root cause: the positional block
# (Form 22 + Course 15 + Going 15 + Distance 12 = 64) can be fully banked by a
# low-rated course specialist, while ability (Class 12 + Speed 8) is only a
# fifth of the score — so course/form accumulation buries the clock.
# (1) Bug 3: _score_form weighted the OLDEST run heaviest; corrected to weight
#     the MOST RECENT heaviest (all classes — pure correctness).
# (2) ABILITY ANCHOR: in non-premium handicaps (Flat C4 & below / NH C3 &
#     below, tier <= 4) scale the positional block by how the runner's best
#     figure ranks within today's field. Premium classes (tier >= 5) untouched.
# Feature-flagged for instant revert; needs a paper-trade (moves every score).
SCORER_RECAL_ENABLED = True


def _ability_factor(runner, race) -> float:
    """Ability anchor for the positional block (added 30 Jun 2026).

    Returns a multiplier in [0.7, 1.0] applied to Form+Course+Going+Distance
    in non-premium handicaps only. 1.0 = no change (premium class, the
    field-best horse, or insufficient data). Scales linearly with the
    runner's best figure (RPR/TS/OR) between the field min (0.7) and field
    max (1.0). A C&D specialist far below the field on the clock can no
    longer out-score the field on course/form alone. Never raises."""
    if not SCORER_RECAL_ENABLED:
        return 1.0
    tier = _race_class_tier(race)
    if tier is None or tier >= 5:  # premium: Flat C3+/NH C2+/Listed/Group/Grade
        return 1.0

    def best_fig(r):
        vals = [v for v in (getattr(r, "rpr", None), getattr(r, "speed_figure", None),
                            getattr(r, "official_rating", None)) if v]
        return max(vals) if vals else None

    mine = best_fig(runner)
    figs = [f for f in (best_fig(r) for r in race.runners) if f is not None]
    if mine is None or len(figs) < 3:
        return 1.0
    fmax, fmin = max(figs), min(figs)
    if fmax == fmin:
        return 1.0
    frac = (mine - fmin) / (fmax - fmin)
    return round(0.7 + 0.3 * max(0.0, min(1.0, frac)), 3)


def _form_chars(form_str: str) -> str:
    """Strip season-break separators from a form string. Returns the
    chronological digit/letter sequence (LEFT = OLDEST, RIGHT = MOST
    RECENT) per Racing API convention.

    Note: a pre-existing bug in `_score_form` weights form[0] heaviest
    treating it as most recent. That weighting is wrong but out of scope
    for Rule 18b — see CLAUDE.md "Bug 3 — Form Weighting" footnote.
    Rule 18b's index mapping uses the CORRECT convention so the right
    character is excused even if the score-weight applied to it is the
    bot's existing (wrong) weight for that position."""
    return (form_str or "").replace("-", "").replace("/", "")


class Scorer:
    """Programmatic scorer for the quantifiable 70% of the analysis."""

    def score_race(self, race: Race) -> list[RunnerScore]:
        """Score all runners in a race. Returns sorted list (highest first)."""
        scores = []
        for runner in race.runners:
            score = self._score_runner(runner, race)
            scores.append(score)

        # Sort by total score descending
        scores.sort(key=lambda s: s.total, reverse=True)
        return scores

    def _score_runner(self, runner: Runner, race: Race) -> RunnerScore:
        """Score a single runner across all quantifiable factors."""
        score = RunnerScore(runner=runner)

        # ELIMINATION GATE: Competitiveness floor
        if self._fails_competitiveness_gate(runner):
            # Return a zeroed score — this runner is eliminated
            score.edge_details = ["ELIMINATED: No wins + no recent places"]
            score.total = 0.0
            score.final_score = 0.0
            return score

        score.form_score = self._score_form(runner, race)
        score.course_score = self._score_course(runner, race)
        score.going_score = self._score_going(runner, race)
        score.distance_score = self._score_distance(runner, race)
        # Ability anchor (30 Jun 2026): in non-premium handicaps, scale the
        # positional block (Form+Course+Going+Distance) by the runner's
        # figure-rank within today's field so a low-rated course specialist
        # cannot out-score the field on course/form alone. No-op (1.0) at
        # premium class, for the field-best horse, or with insufficient data.
        af = _ability_factor(runner, race)
        if af != 1.0:
            score.form_score = round(score.form_score * af, 1)
            score.course_score = round(score.course_score * af, 1)
            score.going_score = round(score.going_score * af, 1)
            score.distance_score = round(score.distance_score * af, 1)
            logger.debug(
                f"Ability anchor {runner.name}: x{af} on positional block"
            )
        score.class_score = self._score_class(runner, race)
        score.speed_score = self._score_speed(runner, race)
        score.weight_score = self._score_weight(runner, race)
        score.jockey_score = self._score_jockey(runner, race)
        score.trainer_score = self._score_trainer(runner, race)

        score.edge_bonus = self._score_edges(runner, race, score)

        score.total = (
            score.form_score + score.course_score + score.going_score +
            score.distance_score + score.class_score + score.speed_score +
            score.weight_score + score.jockey_score + score.trainer_score +
            score.edge_bonus
        )
        score.final_score = score.total  # Before judgement adjustment

        return score

    def _fails_competitiveness_gate(self, runner: Runner) -> bool:
        """
        ELIMINATION GATE: Competitiveness floor.
        Zero wins AND no placed form (1st-3rd) in last 3 completed runs = eliminated.
        Exception: Lightly-raced (≤4 career starts).
        Exception: When Spotlight is available, Spotlight takes priority — the gate
        only acts as safety net when no narrative data exists.
        """
        form = runner.form or ""
        if not form:
            return False  # No form = could be debut, don't eliminate

        # Exception: lightly-raced (4 or fewer runs)
        completed_runs = [c for c in form if c in "0123456789"]
        if len(completed_runs) <= 4:
            return False  # Genuinely unexposed

        # Exception: Spotlight available — let Claude judge with the narrative
        if runner.comment and len(runner.comment) > 20:
            return False  # Spotlight exists, Claude will assess

        # Check for ANY win in entire form string
        has_any_win = "1" in form

        # Check last 3 completed runs for places (1st, 2nd, 3rd)
        last_3_completed = [c for c in form if c in "0123456789"][-3:]
        has_recent_place = any(c in "123" for c in last_3_completed)

        # Fail gate if: no wins ever AND no recent places
        if not has_any_win and not has_recent_place:
            return True

        return False

    def _score_form(self, runner: Runner, race: Race = None) -> float:
        """Score recent form (max 22 points).

        Optional `race` parameter (added 27 May 2026) enables Rule 18b —
        Excused Higher-Class Last Runs. When race is provided AND
        RULE_18B_ENABLED, the helper `_excused_form_indices` returns a
        set of form-string positions to SKIP. Skipped positions contribute
        nothing to either points or total_weight (treated as missing data,
        not a positive)."""
        if not runner.form:
            return 5.0  # Unknown/no form = neutral

        form = _form_chars(runner.form)
        if not form:
            return 5.0

        # Rule 18b: identify positions to excuse from form scoring.
        # Returns empty set when out of scope, no candidates, or race is None.
        excused = set()
        if race is not None and RULE_18B_ENABLED:
            excused = self._excused_form_indices(runner, race, form)

        points = 0.0
        total_weight = 0.0

        # Recency weighting. Bug 3 (pre-30 Jun 2026): weights[0] was applied to
        # form[0] = the OLDEST run, so a horse's most recent runs counted LEAST.
        # Corrected under SCORER_RECAL so the MOST RECENT run carries the
        # heaviest weight. `excused` (Rule 18b) indexes the FULL form string
        # (0 = oldest), so both branches test the full-form index against it.
        weights = [3.0, 2.5, 2.0, 1.5, 1.0, 0.5]
        form_len = len(form)

        def _pos_value(ch, w):
            if ch == "1":
                return w * 1.0  # Win
            if ch == "2":
                return w * 0.75  # Second
            if ch == "3":
                return w * 0.6  # Third
            if ch in ("4", "5"):
                return w * 0.35  # Thereabouts
            if ch == "6":
                return w * 0.2
            if ch in ("F", "U"):
                return w * 0.15  # Falls/unseatings — don't bury class horses
            if ch == "P":
                return w * 0.05  # Pulled up is worse
            if ch in ("0", "7", "8", "9"):
                return w * 0.1  # Well beaten
            return 0.0

        if SCORER_RECAL_ENABLED:
            # Correct: most recent run (rightmost) weighted heaviest.
            for k in range(min(6, form_len)):
                idx = form_len - 1 - k
                if idx in excused:
                    continue  # Rule 18b: skip — treat as missing data
                w = weights[k]
                total_weight += w
                points += _pos_value(form[idx], w)
        else:
            # Legacy (Bug 3) weighting — oldest run heaviest.
            for i, char in enumerate(form[:6]):
                if i >= len(weights):
                    break
                if i in excused:
                    continue
                w = weights[i]
                total_weight += w
                points += _pos_value(char, w)

        if total_weight > 0:
            normalised = points / total_weight
        else:
            normalised = 0.3

        # Check for improving pattern (last 3 runs getting better)
        improving = self._check_improving(form)
        if improving:
            normalised = min(1.0, normalised + 0.1)

        return round(normalised * 22.0, 1)

    def _excused_form_indices(self, runner: Runner, race: Race,
                              form: str) -> set:
        """Rule 18b core (added 27 May 2026). Return a set of form-string
        indices to EXCLUDE from form penalty calculation.

        Triggers when:
          - Today's race is in Rule 18b scope (Flat C4+/NH C3+/G-L-Grade)
          - The runner has `recent_results` populated (API enrichment ran)
          - At least one historical run was at HIGHER class than today
            AND the runner finished position 4+ in that run
          - The runner does NOT have 2+ same-class poor finishes (in which
            case the form at this level is honest and should not be excused)

        Cap: at most 1 excused position (best candidate by tier diff, then
        worst position). Mirrors base Rule 18's single-run-excuse design.

        Form-string mapping: Racing API form is chronological LEFT-TO-RIGHT
        (form[0] = oldest visible, form[len-1] = most recent). API
        recent_results is reverse-chronological (idx 0 = most recent). So
        form_idx = len(form) - 1 - past_api_idx (where past_api_idx counts
        only API entries dated STRICTLY BEFORE today — same-day races would
        shift the mapping by one because the form string doesn't include
        them yet).

        Returns empty set on any failure (out of scope, no data, no
        candidates) — safe-by-default. Never raises."""
        if not _rule18b_scope(race):
            return set()
        hist = getattr(runner, "recent_results", None) or []
        if not hist:
            return set()
        today_tier = _race_class_tier(race)
        if today_tier is None:
            return set()

        # Filter out same-day-or-later API results. They're in the API
        # because some races on the card have already run, but the form
        # string was generated before today and doesn't reflect them.
        # Without this filter the index mapping is off-by-one.
        from datetime import date as _date_cls
        today_iso = _date_cls.today().isoformat()
        past_hist = [h for h in hist if (h.get("date") or "") < today_iso]
        if not past_hist:
            return set()

        form_len = len(form)
        candidates = []  # (form_idx, position, hist_tier)
        same_class_poor_count = 0

        for past_idx, h in enumerate(past_hist[:3]):
            pos_raw = h.get("position")
            if pos_raw is None:
                continue
            try:
                pos = int(pos_raw)
            except (ValueError, TypeError):
                continue
            if pos < 4:
                continue
            hist_tier = h.get("class_level")
            if hist_tier is None:
                continue
            if hist_tier == today_tier:
                same_class_poor_count += 1
            elif hist_tier > today_tier:
                # Higher class than today — Rule 18b candidate, but only if
                # the horse was COMPETITIVE there. A rout carries no
                # information about a level the horse never reached.
                btn_per_f = h.get("btn_per_f")
                if btn_per_f is None:
                    logger.debug(
                        f"Rule 18b: {runner.name} — no beaten margin for "
                        f"{h.get('race_name')}, not excusing"
                    )
                    continue
                if btn_per_f > RULE_18B_MAX_BTN_PER_FURLONG:
                    logger.info(
                        f"Rule 18b MARGIN GUARD: {runner.name} — NOT excusing "
                        f"pos {pos} in {h.get('race_name')} "
                        f"(beaten {h.get('ovr_btn')}L over {h.get('dist_f')}f "
                        f"= {btn_per_f:.2f} L/f > {RULE_18B_MAX_BTN_PER_FURLONG})"
                    )
                    continue
                form_idx = form_len - 1 - past_idx
                if 0 <= form_idx < form_len:
                    candidates.append((form_idx, pos, hist_tier))

        # Guard: form at this level is honest if 2+ same-class poor finishes
        if same_class_poor_count >= 2:
            return set()
        if not candidates:
            return set()

        # Pick best candidate: largest tier diff, then worst position
        candidates.sort(key=lambda x: (-(x[2] - today_tier), -x[1]))
        chosen = candidates[0]
        # Log the firing for paper-trade tracking
        logger.info(
            f"Rule 18b: {runner.name} — excused form[{chosen[0]}] "
            f"(API pos {chosen[1]} at tier {chosen[2]} vs today {today_tier})"
        )
        return {chosen[0]}

    def _check_improving(self, form: str) -> bool:
        """Check if the last 3 runs show an improving trend.

        Bug 3 sibling (fixed 30 Jun 2026): this read form[:3] (the 3 OLDEST
        runs) and tested ascending finish numbers — which actually flags a
        DECLINING horse as improving. Corrected to read the 3 MOST RECENT
        runs (form[-3:], oldest→newest) and flag improvement when finishing
        positions get smaller (better) toward the present."""
        if SCORER_RECAL_ENABLED:
            positions = [int(c) for c in form[-3:] if c.isdigit()]
            if len(positions) >= 3:
                return positions[0] >= positions[1] >= positions[2]
            return False
        positions = []
        for char in form[:3]:
            if char.isdigit():
                positions.append(int(char))
        if len(positions) >= 3:
            return positions[0] <= positions[1] <= positions[2]
        return False

    def _score_course(self, runner: Runner, race: Race) -> float:
        """Score course form (max 15 points).

        C5/C6 patch (8 May 2026): cap at 12/9/6/5 instead of 15/12/8/5.
        In Class 5/6 the same recyclable pool of horses cycles through the
        same tracks, so course bonus banks repeatedly off historical wins
        that don't predict today (Mark's Choice 10x course winner at 11yo,
        Novamay C&D winner last July before +25lb rise + 239 days off).
        Premium-class scoring (Class 1-4, Listed, Group, Grade) keeps the
        full 15-point ceiling — Lambourn's Chester Vase form is genuine
        course edge in a Group 2."""
        if _is_c5_or_c6(race):
            if runner.cd_winner:
                return 12.0
            if runner.course_winner:
                return 9.0
            if runner.distance_winner:
                return 6.0
            return 5.0
        if runner.cd_winner:
            return 15.0
        if runner.course_winner:
            return 12.0
        if runner.distance_winner:
            return 8.0
        # Default: neutral (never run here)
        return 5.0

    def _score_going(self, runner: Runner, race: Race) -> float:
        """
        Score going suitability (max 15 points).
        Assesses going preference INDEPENDENTLY of course/distance flags.
        C&D/course wins are already rewarded in _score_course — using them
        here too triple-counts and inflates C&D winners by ~24 points.
        """
        comment = (runner.comment or "").lower()

        # Parse Spotlight for going clues FIRST — narrative overrides
        negative_going_phrases = [
            "needs softer", "needs faster", "wrong ground",
            "ground against", "unsuited by", "doesn't handle",
            "may not handle", "ground a concern", "questionable going",
            "all wins on heavy", "all wins on soft", "all wins on firm",
        ]
        positive_going_phrases = [
            "acts on", "proven on", "handles", "won on good to soft",
            "suited by", "relishes", "loves", "ground suits",
            "goes on any", "effective on",
        ]

        # Negative going signals = strong downgrade
        for phrase in negative_going_phrases:
            if phrase in comment:
                return 3.0

        # Positive going signals = strong upgrade
        for phrase in positive_going_phrases:
            if phrase in comment:
                return 13.0

        # No Spotlight going clues — use course winner as a MILD hint
        # (they've at least run at this track before, which may have
        # similar going patterns, but it's not proof for TODAY's going)
        if runner.cd_winner or runner.course_winner:
            return 10.0

        # Distance winner = has run competitively on some surface
        if runner.distance_winner:
            return 8.0

        return 7.5  # Neutral — Claude analyst may enhance further

    def _score_distance(self, runner: Runner, race: Race) -> float:
        """Score distance suitability (max 12 points)."""
        if runner.distance_winner:
            return 12.0
        if runner.cd_winner:
            return 12.0
        # Default neutral - enhanced by analyst
        return 6.0

    def _score_class(self, runner: Runner, race: Race) -> float:
        """Score class (max 12 points). Uses OR and RPR vs field.

        C5/C6 patch (8 May 2026): cap at 8/12 instead of 12/12 in Class 5/6.
        The field-relative score has no absolute anchor — top RPR in a
        Class 5 field of 70-90 RPRs gets the same bonus as top RPR in a
        Class 1 field of 120-140. The class score is supposed to capture
        'this horse stands out by class' but in compressed pools it just
        rewards relative ranking with nothing absolute to back it up.
        Validated 8 May 2026: Novamay top RPR 97 in Class 4 6f field got
        +12 same as Lambourn would get in a Group 1 — but won at 16/1 vs
        Lambourn's 11/8F. The signal is materially weaker."""
        # Use RPR as the primary class indicator (more current than OR in graded races)
        # Fall back to OR if no RPR available
        my_rating = runner.rpr or runner.official_rating
        if not my_rating:
            return 6.0

        # Build field ratings using RPR where available, OR as fallback
        field_ratings = []
        for r in race.runners:
            rating = r.rpr or r.official_rating
            if rating:
                field_ratings.append(rating)
        if not field_ratings:
            return 6.0

        avg_rating = sum(field_ratings) / len(field_ratings)
        max_rating = max(field_ratings)

        is_low_class = _is_c5_or_c6(race)

        # Higher rating relative to field = better class
        if my_rating >= max_rating:
            return 8.0 if is_low_class else 12.0
        elif my_rating >= avg_rating + 5:
            return 7.0 if is_low_class else 10.0
        elif my_rating >= avg_rating:
            return 6.0 if is_low_class else 8.0
        elif my_rating >= avg_rating - 5:
            return 5.0 if is_low_class else 6.0
        else:
            return 3.0 if is_low_class else 4.0

    def _score_speed(self, runner: Runner, race: Race = None) -> float:
        """
        Score speed figures (max 8 points). Uses better of RPR or TS gap vs OR.

        TS-BELOW-OR penalty: when TS is 10+ below OR, zero the speed score.
        v4.1 (1 May 2026) dropped the role-veto that this fed (capping SEL→NB);
        the score penalty stays as a scoring nuance, but no longer blocks
        the horse from being SEL/NAP if other factors compensate.
        """
        or_val = runner.official_rating or 0
        ts = runner.speed_figure or 0
        rpr = runner.rpr or 0

        if not or_val or (not ts and not rpr):
            return 3.0  # Neutral

        # TS 10+ below OR zeros speed factor (but no longer role-vetoes)
        if ts and (or_val - ts) >= 10:
            return 0.0

        # Use the BETTER of RPR-OR or TS-OR gaps
        ts_gap = (ts - or_val) if ts else -999
        rpr_gap = (rpr - or_val) if rpr else -999
        best_gap = max(ts_gap, rpr_gap)

        if best_gap >= 10:
            score = 8.0
        elif best_gap >= 5:
            score = 6.0
        elif best_gap >= 0:
            score = 4.0
        elif best_gap >= -5:
            score = 2.0
        else:
            score = 0.0

        return score

    def _score_weight(self, runner: Runner, race: Race = None) -> float:
        """Score weight carried (max 8 points). Detects mares' allowance advantage."""
        if not race or not runner.weight_lbs:
            return 4.0

        # Find field average and max weight
        weights = [r.weight_lbs for r in race.runners if r.weight_lbs]
        if not weights:
            return 4.0

        max_weight = max(weights)
        avg_weight = sum(weights) / len(weights)
        my_weight = runner.weight_lbs

        # Mares receiving allowance in graded races carry significantly less
        # This is a real, quantifiable advantage
        race_class = (race.race_class or "").lower()
        is_graded = any(g in race_class for g in ("grade 1", "grade 2", "g1", "g2"))
        is_mare = runner.sex in ("mare", "filly", "f", "m")

        if is_graded and is_mare and my_weight < max_weight:
            lb_advantage = max_weight - my_weight
            if lb_advantage >= 7:
                return 8.0  # 7lb+ advantage = maximum score
            elif lb_advantage >= 5:
                return 7.0
            elif lb_advantage >= 3:
                return 6.0

        # For handicaps: lighter weight = generally better
        if my_weight <= avg_weight - 7:
            return 7.0  # Bottom weight area
        elif my_weight <= avg_weight:
            return 5.0
        elif my_weight <= avg_weight + 7:
            return 4.0
        else:
            return 3.0  # Top weight

    def _score_jockey(self, runner: Runner, race: Race) -> float:
        """Score jockey (max 5 points)."""
        if not runner.jockey:
            return 2.0

        jockey_lower = runner.jockey.lower()

        # Determine if flat or NH based on race type
        is_nh = race.race_type and any(
            kw in race.race_type.lower()
            for kw in ["hurdle", "chase", "bumper", "nhf", "national hunt"]
        )

        top_jockeys = TOP_NH_JOCKEYS if is_nh else TOP_FLAT_JOCKEYS

        if jockey_lower in top_jockeys:
            return 5.0
        # Partial credit for known competent jockeys
        return 2.5

    def _score_trainer(self, runner: Runner, race: Race) -> float:
        """Score trainer (max 5 points). Uses 14-day form data from API."""
        if not runner.trainer:
            return 2.0

        trainer_lower = runner.trainer.lower()

        is_nh = race.race_type and any(
            kw in race.race_type.lower()
            for kw in ["hurdle", "chase", "bumper", "nhf", "national hunt"]
        )

        top_trainers = TOP_NH_TRAINERS if is_nh else TOP_FLAT_TRAINERS

        # Use 14-day form if available (more current than static lists)
        if runner.trainer_14d_pct is not None:
            pct = runner.trainer_14d_pct
            if pct >= 25:
                return 5.0
            elif pct >= 15:
                return 4.0
            elif pct >= 10:
                return 3.0
            elif pct >= 5:
                return 2.5
            else:
                return 1.5

        if trainer_lower in top_trainers:
            return 5.0
        return 2.5

    def _score_edges(self, runner: Runner, race: Race, score: RunnerScore) -> float:
        """Calculate edge bonuses — graded per CLAUDE.md framework."""
        bonus = 0.0
        details = []
        intent_signals = 0  # Count for compound signal detection

        base_score = (
            score.form_score + score.course_score + score.going_score +
            score.distance_score + score.class_score + score.speed_score +
            score.weight_score + score.jockey_score + score.trainer_score
        )

        # Wind surgery (+3 if base 60+ AND speed figures support)
        # RULE: When TS is available and significantly below OR (5+ pts),
        # the clock says the horse can't run fast enough — withhold bonus
        # regardless of RPR. Validated: Koapey TS 106 vs OR 117, unplaced.
        # Indeevar Bleu TS 125 vs OR 138 = -13, bot scored 88 (wrong).
        if runner.wind_surgery and base_score >= 60:
            or_val = runner.official_rating or 999
            ts = runner.speed_figure or 0
            rpr = runner.rpr or 0

            # TS red flag: if TS exists and is 5+ below OR, the horse
            # isn't fast enough — wind op can't fix that
            ts_red_flag = ts > 0 and (ts < or_val - 5)

            if ts_red_flag:
                details.append(
                    f"Wind surgery noted but TS {ts} well below OR {or_val} "
                    f"— bonus withheld (clock doesn't lie)"
                )
            elif (rpr > or_val) or (ts > or_val):
                bonus += 3.0
                details.append("Wind surgery +3 (base 60+, speed figs support)")
                intent_signals += 1
            else:
                details.append("Wind surgery noted but TS/RPR not above OR — bonus withheld")
        elif runner.wind_surgery:
            details.append(f"Wind surgery noted but base {base_score:.0f} < 60 gate")

        # First-time headgear — GRADED by type
        if runner.first_time_headgear:
            hg = (runner.headgear or "").lower()
            age = runner.age or 99
            sex = (runner.sex or "").lower()

            if "b" in hg and hg not in ("p", "v", "t", "h"):  # Blinkers
                if age <= 3 and sex in ("colt", "gelding", "horse"):
                    bonus += 5.0
                    details.append("1st-time blinkers (young colt) +5")
                elif age >= 5 and sex in ("mare", "filly"):
                    bonus -= 2.0  # Older mare penalty (not full -5 but a warning)
                    details.append("1st-time blinkers (older mare) -2 WARNING")
                else:
                    bonus += 3.0
                    details.append("1st-time blinkers +3")
            elif "v" in hg:  # Visor
                bonus += 3.0
                details.append("1st-time visor +3")
            elif "p" in hg or "c" in hg:  # Cheekpieces
                bonus += 2.0
                details.append("1st-time cheekpieces +2")
            elif "t" in hg:  # Tongue-tie
                bonus += 1.0
                details.append("1st-time tongue-tie +1")
            else:
                bonus += 2.0  # Unknown headgear type
                details.append(f"1st-time headgear ({hg}) +2")
            intent_signals += 1

        # Blinkers REMOVED detection (would need previous headgear data)
        # For now Claude handles this via Spotlight comments

        # Mares' allowance in graded races (+4)
        if runner.sex in ("mare", "filly"):
            race_class_lower = (race.race_class or "").lower()
            if "grade 1" in race_class_lower or "grade 2" in race_class_lower:
                bonus += 4.0
                details.append("Mares' allowance (Grade 1/2) +4")

        # CLASS-DROP KICKER — validated 20 Apr 2026 by Kilmore Rock 6/1
        #   • 1-class drop with placed run at higher level = +3
        #   • 2+ class drop with placed run at higher level = +5
        # The single strongest handicap edge.
        #
        # PRIMARY source: runner.recent_results (authoritative API data
        # from /horses/{id}/results, populated by Scraper.enrich_with_
        # recent_classes). Scans last 3 runs for highest-class placing.
        #
        # FALLBACK: Spotlight text matching (for runners where API data
        # is missing — e.g. first-time runners or API failures).
        #
        # QUALITY FILTER (added 21 Apr 2026 after Pontefract 0-3 on kicker):
        # Skip the kicker when the higher-class placed run was:
        #   - Foreign (France, Ireland weak, Germany, etc.) — translation risk
        #   - AW when today is turf (or turf when today is AW) — surface mismatch
        #   - Qualified in Spotlight as "weak form for the grade" etc.

        # Resolve today's class level from PATTERN first, then race_class.
        # A Listed/Group race carries race_class="Class 1" with the true level
        # held in `pattern` ("Listed"/"Group N"). Reading race_class alone
        # under-reads EVERY pattern race to level 7, so a prior Listed/Group
        # placing wrongly registers as a class DROP and misfires the kicker.
        # Confirmed 5 Jun 2026 (Epsom Oaks day): Stellar Sunrise got +3 for a
        # Listed→Listed move he finished 3rd in (King Charles II Stks), and
        # Legacy Link got +5 for a Group 3 win into the Group 1 Oaks — a class
        # RISE that should carry zero drop bonus. Both inflated into the bot's
        # top two picks. Mirrors the enrichment side (scraper.fetch_recent_race
        # _classes), which already resolves pattern before class_str. Empty
        # pattern (plain handicaps) → string is just race_class → unchanged.
        today_class_lc = f"{race.pattern or ''} {race.race_class or ''}".lower()
        is_nh_race = (race.race_type or "").lower() in ("chase", "hurdle", "nh flat")
        class_map = CLASS_LEVELS_NH if is_nh_race else CLASS_LEVELS_FLAT
        today_level = None
        for label, lvl in class_map.items():
            if label in today_class_lc:
                today_level = lvl
                break

        # Today's surface for AW/turf mismatch check
        today_surface_lc = (race.surface or "").lower()
        today_is_aw = "aw" in today_surface_lc or "polytrack" in today_surface_lc \
            or "tapeta" in today_surface_lc or "all-weather" in today_surface_lc

        # Spotlight qualifier phrases that erode the class-drop signal
        comment_lc_full = (runner.comment or "").lower()
        quality_qualifier_phrases = [
            "weak form for the grade",
            "modest form for the grade",
            "fair form for the grade",
            "albeit weak",
            "not a hot renewal",
            "not the strongest",
            "ordinary form",
            "moderate form",
        ]
        spotlight_qualified = any(
            p in comment_lc_full for p in quality_qualifier_phrases
        )

        kicker_applied = False

        # --- PRIMARY: data-driven using recent_results ---
        recent = runner.recent_results or []
        if today_level is not None and recent:
            best_drop = 0
            best_source = None
            for r in recent:
                level = r.get("class_level")
                pos = str(r.get("position") or "").strip()
                if level is None or not pos:
                    continue
                if level > today_level and pos in ("1", "2", "3"):
                    drop = level - today_level
                    if drop > best_drop:
                        best_drop = drop
                        best_source = r
            if best_drop > 0 and best_source:
                # Apply quality filter
                src_foreign = bool(best_source.get("is_foreign"))
                src_aw = bool(best_source.get("is_aw"))
                surface_mismatch = src_aw != today_is_aw
                skip_reasons = []
                if src_foreign:
                    skip_reasons.append("foreign")
                if surface_mismatch:
                    skip_reasons.append(
                        "AW→turf" if src_aw else "turf→AW"
                    )
                if spotlight_qualified:
                    skip_reasons.append("Spotlight qualified")

                if skip_reasons:
                    details.append(
                        f"Class-drop candidate (pos {best_source.get('position')} "
                        f"in '{best_source.get('class_str','?')}' at "
                        f"{best_source.get('course','?')}) SKIPPED — "
                        f"quality filter: {', '.join(skip_reasons)}"
                    )
                else:
                    kicker = 5.0 if best_drop >= 2 else 3.0
                    bonus += kicker
                    details.append(
                        f"Class-drop kicker +{kicker:.0f} (pos {best_source.get('position')} "
                        f"in '{best_source.get('class_str','?')}' at "
                        f"{best_source.get('course','?')} — {best_drop}-class drop)"
                    )
                    intent_signals += 1
                kicker_applied = True

        # --- FALLBACK: Spotlight text matching ---
        if not kicker_applied and today_level is not None:
            comment_lc = comment_lc_full
            high_grade_phrases = {
                "grade 1": 10, "grade 2": 9, "grade 3": 8,
                "listed race": 7, "listed handicap": 7, "listed contest": 7,
                "valuable series final": 5, "valuable final": 5,
                "eider": 5, "coral cup": 5, "silver trophy": 5,
                "greatwood": 5, "ladbrokes trophy": 5, "imperial cup": 5,
                "county hurdle": 5, "pertemps": 5, "martin pipe": 5,
                "fred winter": 5, "lanzarote": 5, "betfair hurdle": 5,
            }
            placed_phrases = [
                "won ", "winner of", "landed", "fine second", "close second",
                "fine third", "close third", "creditable second",
                "creditable third", "good second", "good third",
                "second ", "third ", "runner-up", "runner up",
            ]
            flagged_level = None
            matched_phrase = None
            for phrase, lvl in high_grade_phrases.items():
                if phrase in comment_lc:
                    if flagged_level is None or lvl > flagged_level:
                        flagged_level = lvl
                        matched_phrase = phrase
            if flagged_level is not None and flagged_level > today_level:
                if any(p in comment_lc for p in placed_phrases):
                    drop = flagged_level - today_level
                    # Quality filter for Spotlight fallback — only qualifier
                    # check available here (no course data for the prior race)
                    if spotlight_qualified:
                        details.append(
                            f"Class-drop candidate (Spotlight fallback: "
                            f"'{matched_phrase}') SKIPPED — "
                            f"quality filter: Spotlight qualified"
                        )
                    else:
                        kicker = 5.0 if drop >= 2 else 3.0
                        bonus += kicker
                        details.append(
                            f"Class-drop kicker +{kicker:.0f} (Spotlight fallback: "
                            f"'{matched_phrase}' — {drop}-class drop)"
                        )
                        intent_signals += 1

        # Hot stable bonus (graduated)
        if runner.trainer_14d_pct is not None:
            # Need to check runs count too — but we only have percent in Runner
            # The API provides runs in trainer_14_days dict but we store only pct
            pct = runner.trainer_14d_pct
            if pct >= 30:
                bonus += 3.0
                details.append(f"Hot stable ({pct}% 14d) +3")
                intent_signals += 1
            elif pct >= 20:
                bonus += 2.0
                details.append(f"Hot stable ({pct}% 14d) +2")
                intent_signals += 1
            elif pct < 5 and pct >= 0:
                bonus -= 1.0
                details.append(f"Cold stable ({pct}% 14d) -1")

        # Days since run - fresh from break bonus AND quick turnaround penalty
        race_type = (race.race_type or "").lower()
        is_nh = any(t in race_type for t in ("hurdle", "chase", "nh flat", "bumper"))
        if runner.days_since_run is not None and runner.days_since_run <= 7 and is_nh:
            bonus -= 5.0
            details.append(f"⚠️ QUICK TURNAROUND {runner.days_since_run}d (NH ≤7d) -5")
        elif runner.days_since_run is not None and runner.days_since_run <= 14 and is_nh:
            # CLAUDE.md factor 11: "8-14 days AFTER A HARD WIN for 8yo+ = -3".
            # The win condition was missing until 14 Jul 2026, so this fired on
            # ANY 8yo+ returning inside 14 days regardless of what it did last
            # time — the opposite of the rule's rationale ("hard-won races take
            # MORE out of a horse than easy wins"). Caught at Perth 3:51 on
            # 12 Jul 2026: Grand Clermont (10yo, back in 14 days off a beaten
            # 4th in a Class 2) was docked -3 and then WON at 3/1; Wasdell
            # Dundalk took the same -3 off a 2nd. Neither had won last time.
            age = runner.age or 0
            won_last = _form_chars(runner.form)[-1:] == "1"
            if age >= 8 and (won_last or not QUICK_TURNAROUND_REQUIRE_WIN):
                bonus -= 3.0
                details.append(
                    f"⚠️ Quick turnaround {runner.days_since_run}d after win (8yo+ NH) -3"
                )
        elif runner.days_since_run and 14 <= runner.days_since_run <= 42:
            bonus += 1.0
            details.append("Optimal return window +1")
        elif runner.days_since_run and runner.days_since_run > 60:
            details.append(f"Long absence ({runner.days_since_run} days) - needs analyst review")

        # FLAT LONG-ABSENCE PENALTY (C5/C6 only) — added 8 May 2026
        # Validated by Novamay 16/1 86 unplaced at Ripon 7:15 8 May 2026:
        # 239 days off, three-wins-then-fade form, no DSLR penalty applied
        # under the prior rules. In compressed-pool C5/C6 Flat handicaps the
        # form signal is fragile and a long absence makes it untestable.
        # NH already has the 7-day quick-turnaround rule; this adds the
        # opposite-end penalty for Flat C5/C6.
        if (
            not is_nh
            and runner.days_since_run is not None
            and _is_c5_or_c6(race)
        ):
            if runner.days_since_run > 180:
                bonus -= 5.0
                details.append(
                    f"⚠️ Flat C5/C6 long absence {runner.days_since_run}d (>180) -5"
                )
            elif runner.days_since_run > 90:
                bonus -= 3.0
                details.append(
                    f"⚠️ Flat C5/C6 absence {runner.days_since_run}d (>90) -3"
                )

        # Class drop detection (intent signal)
        if runner.official_rating:
            ratings = [r.official_rating for r in race.runners if r.official_rating]
            if ratings:
                avg_or = sum(ratings) / len(ratings)
                if runner.official_rating >= avg_or + 8:
                    intent_signals += 1  # Effectively dropping in class

        # FIELD-RELATIVE SPEED DOMINANCE
        # When this runner's best figure (RPR or TS) leads the field by 10+, bonus
        my_best = max(runner.rpr or 0, runner.speed_figure or 0)
        if my_best > 0:
            field_figs = []
            for r in race.runners:
                if r.name != runner.name:
                    fig = max(r.rpr or 0, r.speed_figure or 0)
                    if fig > 0:
                        field_figs.append(fig)
            if field_figs:
                next_best = max(field_figs)
                lead = my_best - next_best
                if lead >= 20:
                    bonus += 5.0
                    details.append(f"SPEED DOMINANCE: best fig {my_best} leads field by {lead}pts +5")
                elif lead >= 10:
                    bonus += 3.0
                    details.append(f"Speed leader: best fig {my_best} leads by {lead}pts +3")
                elif lead >= 5:
                    bonus += 1.0
                    details.append(f"Speed edge: best fig {my_best} leads by {lead}pts +1")

        # SIGNAL COMPOUNDING: 3+ intent signals = +5 additional
        if intent_signals >= 3:
            bonus += 5.0
            details.append(f"⚡ COMPOUND SIGNAL ({intent_signals} signals) +5")
        elif intent_signals == 2:
            details.append(f"2 intent signals (close to compound threshold)")

        score.edge_details = details
        return round(bonus, 1)


def format_score_summary(scored: RunnerScore) -> str:
    """Format a runner score for display."""
    r = scored.runner
    lines = [
        f"  {r.name} ({r.jockey or '?'} / {r.trainer or '?'})",
        f"    Form: {r.form or '?'} | OR: {r.official_rating or '?'} | "
        f"Speed Fig: {r.speed_figure or '?'}",
        f"    Score: {scored.total:.0f}/100 "
        f"[F:{scored.form_score:.0f} C:{scored.course_score:.0f} "
        f"G:{scored.going_score:.0f} D:{scored.distance_score:.0f} "
        f"Cl:{scored.class_score:.0f} Sp:{scored.speed_score:.0f} "
        f"W:{scored.weight_score:.0f} J:{scored.jockey_score:.0f} "
        f"T:{scored.trainer_score:.0f}]",
    ]
    if scored.edge_details:
        lines.append(f"    Edges: {', '.join(scored.edge_details)}")
    if scored.judgement_notes:
        lines.append(f"    Analyst: {scored.judgement_notes}")
    return "\n".join(lines)
