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
    # Selection-role constraints set by scoring rules:
    # ts_veto: TS 10+ below OR — cap at NB role, never SEL/NAP. If surface
    #   also changing, eliminate entirely (ts_eliminate=True).
    # ts_eliminate: TS deficit + surface change = exclude from all roles.
    # force_nb_minimum: set by dual-edge rule (biggest RPR AND biggest TS
    #   gap above OR in the field) — horse must be at least NB of the race.
    ts_veto: bool = False
    ts_eliminate: bool = False
    force_nb_minimum: bool = False

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

        score.form_score = self._score_form(runner)
        score.course_score = self._score_course(runner, race)
        score.going_score = self._score_going(runner, race)
        score.distance_score = self._score_distance(runner, race)
        score.class_score = self._score_class(runner, race)
        score.speed_score = self._score_speed(runner, race)
        score.weight_score = self._score_weight(runner, race)
        score.jockey_score = self._score_jockey(runner, race)
        score.trainer_score = self._score_trainer(runner, race)

        # TS-below-OR veto flag — feeds the analyst compliance gate
        or_val = runner.official_rating or 0
        ts = runner.speed_figure or 0
        if or_val and ts and (or_val - ts) >= 10:
            score.ts_veto = True
            # Surface change on top of deficit = eliminate entirely.
            # We only have today's surface; the "change" test uses past
            # runs via recent_results if present.
            today_surface_lc = (race.surface or "").lower()
            today_is_aw = ("aw" in today_surface_lc
                           or "polytrack" in today_surface_lc
                           or "tapeta" in today_surface_lc
                           or "all-weather" in today_surface_lc)
            recent = runner.recent_results or []
            if recent:
                # If most recent run's surface differs from today → eliminate
                last = recent[0]
                last_is_aw = bool(last.get("is_aw"))
                if last_is_aw != today_is_aw:
                    score.ts_eliminate = True

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

    def _score_form(self, runner: Runner) -> float:
        """Score recent form (max 22 points)."""
        if not runner.form:
            return 5.0  # Unknown/no form = neutral

        form = runner.form.replace("-", "").replace("/", "")
        if not form:
            return 5.0

        points = 0.0
        total_weight = 0.0

        # Weight recent runs more heavily (most recent first)
        weights = [3.0, 2.5, 2.0, 1.5, 1.0, 0.5]

        for i, char in enumerate(form[:6]):
            if i >= len(weights):
                break
            w = weights[i]
            total_weight += w

            if char == "1":
                points += w * 1.0  # Win
            elif char == "2":
                points += w * 0.75  # Second
            elif char == "3":
                points += w * 0.6  # Third
            elif char in ("4", "5"):
                points += w * 0.35  # Thereabouts
            elif char == "6":
                points += w * 0.2
            elif char in ("F", "U"):
                # Falls/unseatings - don't heavily penalise class horses
                points += w * 0.15
            elif char == "P":
                points += w * 0.05  # Pulled up is worse
            elif char in ("0", "7", "8", "9"):
                points += w * 0.1  # Well beaten

        if total_weight > 0:
            normalised = points / total_weight
        else:
            normalised = 0.3

        # Check for improving pattern (last 3 runs getting better)
        improving = self._check_improving(form)
        if improving:
            normalised = min(1.0, normalised + 0.1)

        return round(normalised * 22.0, 1)

    def _check_improving(self, form: str) -> bool:
        """Check if last 3 runs show improving trend."""
        positions = []
        for char in form[:3]:
            if char.isdigit():
                positions.append(int(char))
        if len(positions) >= 3:
            # Improving if each run is same or better than previous
            return positions[0] <= positions[1] <= positions[2]
        return False

    def _score_course(self, runner: Runner, race: Race) -> float:
        """Score course form (max 15 points)."""
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
        """Score class (max 12 points). Uses OR and RPR vs field."""
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

        # Higher rating relative to field = better class
        if my_rating >= max_rating:
            return 12.0
        elif my_rating >= avg_rating + 5:
            return 10.0
        elif my_rating >= avg_rating:
            return 8.0
        elif my_rating >= avg_rating - 5:
            return 6.0
        else:
            return 4.0

    def _score_speed(self, runner: Runner, race: Race = None) -> float:
        """
        Score speed figures (max 8 points). Uses better of RPR or TS gap vs OR.

        TS-BELOW-OR VETO (added 21 Apr 2026 after Yorkshire Glory 8/8 LAST
        at 3/1F). When TS is 10+ below OR, zero the speed score regardless
        of RPR. The ts_veto flag is set on the RunnerScore later in
        _score_runner so the analyst can cap role at NB (never SEL/NAP).
        """
        or_val = runner.official_rating or 0
        ts = runner.speed_figure or 0
        rpr = runner.rpr or 0

        if not or_val or (not ts and not rpr):
            return 3.0  # Neutral

        # TS 10+ below OR is an authoritative red flag — zero speed score.
        # The ts_veto flag (set in _score_runner) prevents SEL/NAP role.
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

        today_class_lc = (race.race_class or "").lower()
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
            age = runner.age or 0
            if age >= 8:
                bonus -= 3.0
                details.append(f"⚠️ Quick turnaround {runner.days_since_run}d (8yo+ NH) -3")
        elif runner.days_since_run and 14 <= runner.days_since_run <= 42:
            bonus += 1.0
            details.append("Optimal return window +1")
        elif runner.days_since_run and runner.days_since_run > 60:
            details.append(f"Long absence ({runner.days_since_run} days) - needs analyst review")

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

        # DUAL-EDGE BONUS (added 21 Apr 2026 after Have Secret 4/1 winner).
        # When the SAME runner has the biggest RPR gap above OR AND the
        # biggest TS gap above OR in the field, that's a compound speed-
        # figure edge we cannot keep scoring down for "class rising" or
        # similar soft reasons. Force into NB minimum role via the flag.
        my_or = runner.official_rating or 0
        my_rpr = runner.rpr or 0
        my_ts = runner.speed_figure or 0
        if my_or and my_rpr and my_ts:
            my_rpr_gap = my_rpr - my_or
            my_ts_gap = my_ts - my_or
            if my_rpr_gap > 0 and my_ts_gap > 0:
                # Check if this runner leads the field on BOTH metrics
                leads_rpr = True
                leads_ts = True
                for r in race.runners:
                    if r.name == runner.name:
                        continue
                    r_or = r.official_rating or 0
                    if not r_or:
                        continue
                    if r.rpr:
                        if (r.rpr - r_or) >= my_rpr_gap:
                            leads_rpr = False
                    if r.speed_figure:
                        if (r.speed_figure - r_or) >= my_ts_gap:
                            leads_ts = False
                    if not (leads_rpr or leads_ts):
                        break
                if leads_rpr and leads_ts:
                    bonus += 5.0
                    details.append(
                        f"DUAL-EDGE: biggest RPR gap (+{my_rpr_gap}) AND biggest "
                        f"TS gap (+{my_ts_gap}) above OR — +5 (force NB minimum)"
                    )
                    score.force_nb_minimum = True

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
