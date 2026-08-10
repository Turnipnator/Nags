import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID", "0"))

# Racing API (primary data source - racecards, results, horse history)
RACING_API_USERNAME = os.getenv("RACING_API_USERNAME")
RACING_API_PASSWORD = os.getenv("RACING_API_PASSWORD")

# Claude API (judgement analysis only - data comes from Racing API)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
# Moved 4.6 → 4.8 on 1 Jun 2026. 4.6 was a deliberate roll-back from 4.7
# (5 May 2026) because 4.7 inflated judgement-layer scores (Precise 104,
# Star Prospect 88, Fairlawn Flyer 81 @ 22/1). 4.8 adopted with the now-
# stronger guardrails (NAP/NB price caps, C5/6 score-market gate, temp=0,
# NB-of-day score floor) as the safety net. Watch early cards for inflation.
JUDGEMENT_MODEL = os.getenv("JUDGEMENT_MODEL", "claude-opus-5")

# Judgement-layer guardrails (added 30 Jun 2026) — make the bot's score
# MODEL-AGNOSTIC so the Telegram output is reproducible and converges with the
# manual rubric instead of drifting with the model. Diagnosis 30 Jun 2026
# (Musselburgh): the LLM emits a FREE-FORM adjusted_score that overrides the
# deterministic rubric in either direction (The Gay Blade C4 90 from a far-lower
# anchor; High Degree figures-leader deflated to 68). A free-form number drifts
# between models AND between runs — reverting 4.8→4.6 does not cure it, it just
# changes which way it drifts. These two gates bound it structurally.
#
# ANCHOR CLAMP — bound the LLM's adjusted_score to the deterministic rubric
# anchor (scorer total) ± a band. UP tight: legitimate documented upgrades fit
# inside it (e.g. the Bellarchi excused-last-run +13), runaway inflation does
# not. DOWN loose: LLM Spotlight downgrades are legitimate and lose no money.
# Caveat: Bug 3 (reversed form weighting) still deflates the anchor for recent-
# momentum horses — that is the horse type we WANT clamped — once Bug 3 is fixed
# (its own paper-trade) the UP band can tighten toward ~8.
JUDGEMENT_CLAMP_ENABLED = os.getenv("JUDGEMENT_CLAMP_ENABLED", "true").lower() == "true"
JUDGEMENT_UP_BAND = float(os.getenv("JUDGEMENT_UP_BAND", "14"))
JUDGEMENT_DOWN_BAND = float(os.getenv("JUDGEMENT_DOWN_BAND", "25"))

# GENERAL SCORE-VS-MARKET GATE — demote NAP/NB when the score is high but the
# price is long (rubric-vs-market divergence) at ANY class, generalising the
# 8 May 2026 C5/6-only Option B. C5/6 keeps its stricter 80 floor; other classes
# use GENERAL_GATE_SCORE. The 9.0 (8/1) odds floor is the real safety valve:
# short-priced premium NAPs (e.g. Brighterdaysahead 9/4) never trip it, so
# legitimate championship-class short NAPs are untouched — only LONG-priced
# high scores get gated.
GENERAL_GATE_SCORE = float(os.getenv("GENERAL_GATE_SCORE", "82"))
GENERAL_GATE_ODDS = float(os.getenv("GENERAL_GATE_ODDS", "9.0"))

# ── SELECTION FILTERS F1 / F2 — SHADOW MODE (added 14 Jul 2026) ──────────────
# Derived from 652 real logged picks, 73 race days, 26 Mar - 9 Jul 2026, joined
# to Racing API results. See TWO_FILTERS_PAPER_TRADE.md + CLAUDE.md header note.
#
# ⚠ STATUS 17 Jul 2026: F2 is now LIVE (enforces DROP); F1 stays SHADOW to the
# 11 Aug 2026 review. Shadow is per-filter now. FILTER_SHADOW_MODE is a MASTER
# kill-switch: set it true to force BOTH filters back to observe-only in one move
# (instant full revert). Per-filter: FILTER_LONGSHOT_SHADOW (F2), FILTER_HIGHSCORE_
# SHADOW (F1). A filter enforces only when neither the master nor its own shadow
# flag is set. F2 went live off 670 real logged picks re-validated at BOG (see
# project_market_divergence_finding): the market-divergence damage is F2's longshot
# cluster + the sub-70 tail; F2 owns the longshots, the 70+ floor owns the rest.
#
# F2 (LONGSHOT) — drop any selection at a morning price of 11/1 or bigger.
#   Evidence: 1 winner from 65 bets, ROI -76.9% at BOG. The existing price caps
#   only cover the NAP (10/1) and NB-of-day (14/1); race SELs and race NBs have
#   NO price cap at all, which is exactly where those 65 bets sit.
#   NOTE ON UNITS: _parse_odds_to_decimal returns the FRACTIONAL multiplier
#   (11/1 -> 11.0), NOT decimal odds. The threshold is 11.0, not 12.0.
#
# F1 (HIGH SCORE) — demote adjusted_score >= 85 to a flat race-SEL stake.
#   Evidence: n=55, win 16.4%, avg SP 5.56, ROI -31.3% at BOG. Persists across
#   every ruleset era (-57.6% in Jun-Jul alone) so it is NOT the Opus 4.7
#   inflation artefact. DEMOTE, never DROP: the band contains 9 winners incl.
#   Saddadd (91, 4/1) and Grey Dawning (86, 3/1) — the very horses CLAUDE.md
#   cites as proof premium short-priced NAPs work. F1 is the WEAKER of the two
#   and is expected to be the one that dies in paper-trade.
#
# The general score-vs-market gate above CANNOT see the F1 cluster: it needs
# score >= 82 AND odds >= 9.0, and the worst F1 losers are SHORT (avg SP 5.56).
# Master kill-switch. True => ALL filters revert to shadow (observe-only). Default
# False so the per-filter shadow flags below govern. Flip true for instant revert.
FILTER_SHADOW_MODE = os.getenv("FILTER_SHADOW_MODE", "false").lower() == "true"

# F2 LONGSHOT — LIVE (enforces DROP) as of 17 Jul 2026. To revert F2 alone without
# touching F1, set FILTER_LONGSHOT_SHADOW=true (or the master FILTER_SHADOW_MODE).
FILTER_LONGSHOT_ENABLED = os.getenv("FILTER_LONGSHOT_ENABLED", "true").lower() == "true"
FILTER_LONGSHOT_SHADOW = os.getenv("FILTER_LONGSHOT_SHADOW", "false").lower() == "true"
LONGSHOT_MAX_ODDS = float(os.getenv("LONGSHOT_MAX_ODDS", "11.0"))  # fractional

# F1 HIGHSCORE — STILL SHADOW (log only) to the 11 Aug 2026 review. The weaker
# filter, expected to die. Set FILTER_HIGHSCORE_SHADOW=false only after that review.
FILTER_HIGHSCORE_ENABLED = os.getenv("FILTER_HIGHSCORE_ENABLED", "true").lower() == "true"
FILTER_HIGHSCORE_SHADOW = os.getenv("FILTER_HIGHSCORE_SHADOW", "true").lower() == "true"
HIGHSCORE_DEMOTE_AT = float(os.getenv("HIGHSCORE_DEMOTE_AT", "85.0"))

# F3 SHORT-PREMIUM-NAP — SHADOW (log only) from 19 Jul 2026. Review 16 Aug 2026.
# Evidence: 639 logged picks settled at BOG (scripts/backfill_results.py machinery).
# A NAP priced UNDER 4/1 in a PREMIUM race (Group/Grade/Listed/Class 1-3) returns
# -40.2% ROI over n=29 -- the worst cell in the system. It is NOT outlier-driven
# (-52.4% with its best bet removed) and it is negative in BOTH halves of an
# out-of-sample date split (-47.4% / -33.7%). Sub-4/1 NAPs win 19.5% where the
# price needs 28.2%: a price problem, not a picking problem.
# CONTROL that makes this specific to the NAP slot: non-NAP bets under 4/1 are
# only -1.2% (n=189). Short prices are fine -- doubling the stake on them is not.
# NOTE this REFUTES the documented carve-out in CLAUDE.md's AW C5/6
# no-NAP-on-favourite rule, which deliberately exempts premium class on the
# grounds that short premium NAPs work (Brighterdaysahead/Madara/Saddadd).
# In the data that exemption is exactly backwards. Premium earns its keep at
# 4/1+ (+75%, n=17 -- suggestive only, NOT acted on).
# Action is DEMOTE to race-SEL stake, never DROP: these still win ~17%.
FILTER_SHORTNAP_ENABLED = os.getenv("FILTER_SHORTNAP_ENABLED", "true").lower() == "true"
FILTER_SHORTNAP_SHADOW = os.getenv("FILTER_SHORTNAP_SHADOW", "true").lower() == "true"
SHORTNAP_MIN_ODDS = float(os.getenv("SHORTNAP_MIN_ODDS", "4.0"))  # fractional

# ---------------------------------------------------------------------------
# F4 TOP-2 PRICE RED FLAG — SHADOW ONLY (added 10 Aug 2026)
# ---------------------------------------------------------------------------
# Flags a race where, among BETABLE runners (above evens), our top deterministic
# scorer is LONGER-priced at morning odds than our second. Log only: this filter
# never drops, demotes, restakes or reorders anything.
#
# Evidence (499 premium Group/Grade/Listed/Class 1-3 GB+IRE races 1 Apr - 9 Aug
# 2026 that pass every live gate, re-scored and joined to results, P&L at BOG;
# discovery 1 Apr-12 Jul / holdout 13 Jul-9 Aug declared before looking):
#   In the 189 flagged races our top scorer wins 6.4% (discovery) / 6.1%
#   (holdout) against a ~15% base rate -- ROI -63% / -73%. The win rate is
#   stable across independent windows, which is why it is worth watching.
#   Backing BOTH legs and simply skipping flagged races beat the status quo by
#   +172.5pt win-only / +221.2pt E/W (bootstrap 96.8% / 90.6%).
#
# ⚠ WHY IT IS SHADOW AND NOT LIVE: applied to our 288 REAL logged picks the
# effect INVERTS in the holdout -- status quo +3.5% vs drop-race -13.2%, and the
# picks it would have dropped returned +33.9%. n=33 there, so that is not a
# refutation either. Unresolved. Unresolved does not go near the card.
#
# ⚠ SEPARATE FINDING, already actionable knowledge: the mandatory MARKET SWAP is
# worth ZERO to anyone who backs both the SEL and the race NB -- it only relabels
# which horse is called SEL (measured P&L delta at level stakes: +0.0pt over all
# 499 races). Its entire value is stake allocation under the code's real
# 1.0pt/0.5pt weighting (+23.7pt). The swap is a STAKING rule, not a selection
# rule. See memory project_top2_premium_backtest.
#
# REVIEW 10 Sep 2026. Ship criteria: flagged races must underperform unflagged
# ones on OUR OWN picks in the forward window, in the same direction as
# discovery. If the holdout inversion repeats, drop the idea entirely.
FILTER_TOP2FLAG_ENABLED = os.getenv("FILTER_TOP2FLAG_ENABLED", "true").lower() == "true"
FILTER_TOP2FLAG_SHADOW = os.getenv("FILTER_TOP2FLAG_SHADOW", "true").lower() == "true"

# ---------------------------------------------------------------------------
# DAILY CARD REPLACEMENT (added 1 Aug 2026)
# ---------------------------------------------------------------------------
# The Operating Policy cap ("max 6 selections per day, 1 NAP") was enforced
# PER RUN, not per day: `_enforce_compliance` only ever sees one run's list and
# `_save_cherry_picks` did a bare INSERT with no knowledge of what today already
# held. So a second `/run` issued a whole fresh card at full stakes.
#   1 Aug 2026: Thirsk then Goodwood = 8 top-level selections, TWO NAPs,
#   £245 staked at £10/pt, -£116.38 (-47.5%).
# Paul's call: a second run REPLACES the day's card rather than adding to it.
# Implemented as SUPERSEDE, never DELETE -- rows stay for audit with
# `superseded_at` set, and every live read path filters them out.
DAILY_CARD_REPLACE_ENABLED = os.getenv(
    "DAILY_CARD_REPLACE_ENABLED", "true").lower() == "true"

# ---------------------------------------------------------------------------
# SIGNAL-ALIGNMENT FIXES (added 4 Aug 2026)
# ---------------------------------------------------------------------------
# Three places where the deterministic code read a different signal from the
# one CLAUDE.md specifies. All three found on the 4 Aug 2026 card.
#
# (1) GOING_DETAILED_REAL_FIELD -- Option Y's volatility phrase list ("in
#     places", "watered", "showers", ...) is specified against the API's
#     `going_detailed`. The Race model never captured that field, so
#     analyst.py SYNTHESISED one as `going + " " + weather`. On 4 Aug that
#     produced "Good Showers" for Ffos Las -- a WEATHER FORECAST -- which
#     matched "showers" and blocked the day's only 75+ NAP (Perfect Nation
#     76, 13/8) on a track whose real going_detailed read a perfectly stable
#     "GOOD (GoingStick: 6.0)". It fails the other way too: Catterick's real
#     going_detailed was "GOOD, Good to firm in places" -- a genuine listed
#     phrase -- and the gate could not see it. Wrong signal in BOTH
#     directions since 9 May 2026. Fix: capture and read the real field;
#     weather no longer feeds the volatility check at all. Empty
#     going_detailed FAILS OPEN (no demotion) -- never invent a demotion
#     from absent data.
#
# (2) NR_PRICE_ONLY -- the 9 Jul 2026 non-runner fix established that PRICE
#     is the authoritative withdrawal signal ("what the API strips from a
#     non-runner is every bookmaker price") and noted the old "no jockey =
#     non-runner" heuristic "never fired for a single one". That superseded
#     heuristic was left in `_parse_runner` and now does damage in the
#     opposite direction: it drops runners that ARE priced but have no
#     jockey declared yet -- common on Irish cards early in the day. On
#     4 Aug it removed THREE priced runners (Ataboymiley, John Gun,
#     Goeasyonme) from Roscommon 18:00, which the bot then scored as a
#     12-runner race against a true field_size of 15. Those runners were
#     invisible to every field-relative calculation (top-RPR-in-field,
#     speed ranks, the C4-and-below ability anchor) and to every field-size
#     gate. Fix: drop on missing jockey ONLY when the runner is also
#     unpriced, so a card whose market has not opened still keeps its field.
#     ⚠ THIS MOVES SCORES -- restoring runners changes field-relative maths.
#
# (3) EW_REQUIRE_PLACE_MARKET -- `each_way` was set with no field-size test,
#     so a 4-runner handicap got an E/W flag no bookmaker will accept
#     (Russian Rumour, Lingfield 19:18, 4 Aug -- the bot flagged the problem
#     in its own note but still set the flag). Bookmakers offer no place
#     market below 5 runners. Mirrors the guard already used by the 16 May
#     2026 NB-of-day demote path. Strictly subtractive: can only turn E/W
#     OFF, never on, so it can never increase outlay.
#
# (4) CLASS_FLOOR_BLOCKS_UNCLASSED -- `_meets_class_floor` matches substrings
#     of `race_class`, and Irish cards carry race_class="". Empty string
#     matched nothing, so every unclassed Irish race PASSED the floor by
#     default. On 4 Aug that let a 15-runner Roscommon maiden hurdle with
#     five 150/1 shots into the selections -- it did not clear the floor, it
#     bypassed it, and it is exactly the form-compressed field the floor
#     exists to exclude. Fix: missing class is treated as BELOW the floor
#     unless `pattern` names a Group/Grade/Listed race (Irish pattern racing
#     still passes). Paul's call, 4 Aug 2026. Cost: the bot stops betting
#     ordinary Irish racing (Roscommon, Ballinrobe, Sligo, Irish midweek).
GOING_DETAILED_REAL_FIELD = os.getenv(
    "GOING_DETAILED_REAL_FIELD", "true").lower() == "true"
NR_PRICE_ONLY = os.getenv("NR_PRICE_ONLY", "true").lower() == "true"
EW_REQUIRE_PLACE_MARKET = os.getenv(
    "EW_REQUIRE_PLACE_MARKET", "true").lower() == "true"
EW_MIN_RUNNERS_FOR_PLACE = int(os.getenv("EW_MIN_RUNNERS_FOR_PLACE", "5"))
CLASS_FLOOR_BLOCKS_UNCLASSED = os.getenv(
    "CLASS_FLOOR_BLOCKS_UNCLASSED", "true").lower() == "true"

# GOING_VOLATILITY_SPATIAL_PHRASES (5 Aug 2026) -- Option Y's phrase list mixed
# two different things. The rule exists because of Hexham 9 May 2026, where the
# card read Good in the morning and the race ran on Soft: it is about going
# CHANGING between taking the price and the off. Seven of the nine phrases
# forecast change ("watered", "rain forecast", "becoming softer", ...). Two --
# "in places" and "in the back straight" -- describe how going varies ACROSS
# the track right now, on a surface that is otherwise stable, and are ordinary
# clerk-of-the-course phrasing. Pontefract 5 Aug read "GOOD TO FIRM, Good in
# places (GoingStick: 8.4)" -- a firm, settled surface described precisely --
# and the gate blocked the day's only 75+ NAP (The Good Biscuit 77.2, 3/1) with
# measured drift of ZERO. It fired on 2 of 4 GB courses that day and on
# Catterick the day before. Default false = spatial phrases are IGNORED.
# WARNING: unlike the 4 Aug fixes this is NOT subtractive -- it re-enables NAPs
# (1pt -> 2pt) and removes forced E/W, so it ADDS money at risk. Paper-trade to
# 12 Aug 2026; set true to restore the old behaviour in one move. The drift
# half of Option Y (>= 2 ordinal steps vs the persisted snapshot) is untouched
# and still catches the Hexham case.
GOING_VOLATILITY_SPATIAL_PHRASES = os.getenv(
    "GOING_VOLATILITY_SPATIAL_PHRASES", "false").lower() == "true"

# T14_MIN_RUNS (6 Aug 2026) -- CLAUDE.md factor 21 has ALWAYS said "Small
# samples distort (1 from 2 = 50% but meaningless). Minimum 5 runs in 14 days
# for the bonus." The code never implemented it: scraper.py read the API's
# trainer_14_days dict and kept ONLY `percent`, discarding `runs` and `wins`,
# and scorer.py had a comment openly admitting the gap. TWO scoring sites were
# affected, not one:
#   (a) _score_trainer  -- worth 5 of 100 (5.0 at pct >= 25 ... 1.5 at pct < 5)
#   (b) _score_edges    -- hot-stable +3 / +2 and cold-stable -1
# Caught auditing the bot's own NAP on 6 Aug 2026: Leopardstown 6:00 Desmond
# Stakes (Group 3), Sparan Nua 11/8 scored 75.6 and was NAP'd at 2pts, where
# the "Hot stable (67% 14d)" was J S Bolger 2 WINS FROM 3 RUNS. With the
# mandated guard she scores 70.1 (-5.5: 5.0 -> 2.5 at site (a), +3 removed at
# site (b)) -- below the 75 NAP line AND no longer top scorer in her race, so
# the correct output was a no-NAP flat-stakes day.
#
# Below the threshold each site falls back to the behaviour it would use with
# no 14-day data at all -- site (a) to the static TOP_*_TRAINERS list (the
# code's own comment calls the 14-day block "more current than static lists",
# so when it is not trustworthy the static list is the right fallback), site
# (b) to no bonus. Missing/unparseable `runs` FAILS OPEN (current behaviour
# preserved): absence of a count is not evidence of a small sample, and on the
# 6 Aug card all 400 runners carried both keys, so that branch is theoretical.
#
# T14_MIN_RUNS_APPLY_COLD gates the -1 cold-stable penalty separately and is
# OFF by default. Suppressing phantom HOT bonuses is subtractive (scores only
# fall, bets can only be removed) -- the kind of change that has actually
# worked here. Suppressing phantom COLD penalties is additive. Measured blast
# radius on the pinned 6 Aug card (373 runners / 46 races): hot half moves 12
# runners, ALL down, and changes the top scorer in 2 races (the Desmond, plus
# one the class floor already blocks); cold half moves 66 runners UP and its
# three top-scorer changes are ALL in unclassed Irish races the class floor
# already blocks. Zero horses lose a compound-signal +5 either way.
#
# Paper-trade 7 days to 13 Aug 2026: log every "T14 SMALL SAMPLE" suppression
# and whether the suppressed horse won. Failure trigger -- 3+ suppressed
# horses win where they would otherwise have been selections => lower
# T14_MIN_RUNS to 3 before reverting. Revert: T14_MIN_RUNS_ENABLED=false.
T14_MIN_RUNS_ENABLED = os.getenv("T14_MIN_RUNS_ENABLED", "true").lower() == "true"
T14_MIN_RUNS = int(os.getenv("T14_MIN_RUNS", "5"))
T14_MIN_RUNS_APPLY_COLD = os.getenv(
    "T14_MIN_RUNS_APPLY_COLD", "false").lower() == "true"

# EDGE-BLOCK RUBRIC ALIGNMENT (6 Aug 2026) -- three bonuses that _score_edges
# awarded and CLAUDE.md's edge-factor list does not contain. Found by a
# line-by-line audit of the block against the rubric, prompted by the T14
# min-runs bug: every gate in CLAUDE.md checks scores, prices and class, and
# NONE of them can see how a score was built. Measured on 1896 runners across
# all GB/IRE cards 1-6 Aug 2026. Defaults are OFF because off is the corrected
# state; set any to "true" to restore the old behaviour independently.
#
# (1) SPEED_DOMINANCE_BONUS_ENABLED -- a field-relative lead on max(RPR, TS)
#     paid +5 (>=20 clear), +3 (>=10) or +1 (>=5). No such edge factor exists
#     in CLAUDE.md; the only speed guidance beyond the 8-point Speed Figures
#     factor is factor 6's TOPSPEED LEADER RULE, which is narrative ("deserves
#     serious selection consideration") and assigns no points. It also
#     DOUBLE-COUNTS _score_class, which already scores rating-vs-field, and it
#     inflates exactly the best-figure favourites that sit in the measured F3
#     short-premium-NAP losing cell. 47 firings / 1896 (2.5%), 9 of them +3 or
#     +5. The lead is still computed and reported at ZERO points so the LLM
#     judgement layer can still act on it where the rubric intends.
#
# (2) UNKNOWN_HEADGEAR_BONUS_ENABLED -- the first-time-headgear ladder's else
#     branch paid +2 for any code it did not recognise. CLAUDE.md factor 15
#     grades four types only (blinkers, visor, cheekpieces, tongue-tie); hood
#     and eyeshield are not in it. 11 firings in 6 days, every one a hood.
#     Note kept at zero points, which also logs which codes actually appear.
#
# (3) OR_ABOVE_FIELD_INTENT_SIGNAL -- labelled "class drop detection", it
#     awarded a silent intent signal for being rated 8lb+ ABOVE the field
#     average, i.e. for being the best-handicapped horse: the OPPOSITE of a
#     class drop, and in a handicap just a description of the top weight. The
#     genuine rubric item (factor 20 signal 3) is already counted by the
#     class-drop kicker. Numerically a no-op today -- compound has NEVER
#     reached 3 signals (0 firings in 1896 runners) -- so this exists to stop
#     a future spurious +5. NO replacement signals added: inventing intent
#     signals is the additive-edge trap, refuted five times.
#
# Blast radius (1-6 Aug, 1896 runners / 209 races): 58 runners moved (3.1%),
# ALL DOWN (-1.0 x38, -2.0 x11, -3.0 x7, -5.0 x2); top scorer changed in 3 of
# 209 races, two unclassed Irish (class-floor blocked) and one a Class 4 topping
# out at 53.6 (far below the 70+ betable gate) -- so NO race that would reach
# LLM judgement changed. Of 28 real logged picks in the window, ONE moved, by
# -1.0. This is hygiene, not edge: it is not expected to move ROI.
#
# Paper-trade 7 days to 13 Aug 2026 (same window as the T14 guard). Failure
# trigger -- 3+ races where the horse that lost SPEED DOMINANCE points wins and
# our replacement top scorer loses => SPEED_DOMINANCE_BONUS_ENABLED=true and
# reopen the question of writing it into the rubric properly.
SPEED_DOMINANCE_BONUS_ENABLED = os.getenv(
    "SPEED_DOMINANCE_BONUS_ENABLED", "false").lower() == "true"
UNKNOWN_HEADGEAR_BONUS_ENABLED = os.getenv(
    "UNKNOWN_HEADGEAR_BONUS_ENABLED", "false").lower() == "true"
OR_ABOVE_FIELD_INTENT_SIGNAL = os.getenv(
    "OR_ABOVE_FIELD_INTENT_SIGNAL", "false").lower() == "true"

# Scheduling (24h format, UK timezone)
TIMEZONE = os.getenv("TIMEZONE", "Europe/London")
SCRAPE_TIME = os.getenv("SCRAPE_TIME", "07:00")
ANALYSIS_TIME = os.getenv("ANALYSIS_TIME", "12:00")
RESULTS_TIME = os.getenv("RESULTS_TIME", "21:15")

# Auto-schedule: set to "true" to enable daily auto-runs at ANALYSIS_TIME/RESULTS_TIME.
# Default OFF — use /run via Telegram for on-demand analysis.
AUTO_SCHEDULE = os.getenv("AUTO_SCHEDULE", "false").lower() == "true"

# Auto-results: fetch race results daily at RESULTS_TIME, independent
# of AUTO_SCHEDULE. Free (Racing API only) and keeps the results table
# populated for backtesting / live P&L. Default ON.
AUTO_RESULTS = os.getenv("AUTO_RESULTS", "true").lower() == "true"

# Course focus filter (comma-separated, e.g. "aintree" or "aintree,haydock")
# When set, only these courses are analysed. Empty = all courses.
FOCUS_COURSES = os.getenv("FOCUS_COURSES", "")

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Database
DB_PATH = os.getenv("DB_PATH", "/app/data/racing.db")

# Scraping - source priority order (HorseRacing.net has the richest free data)
RACECARD_SOURCES = [
    "horseracingnet",
    "attheraces",
    "sportinglife",
]

# UK courses (for filtering - only UK and Irish racing)
UK_COURSES = {
    "aintree", "ascot", "ayr", "bangor", "bath", "beverley", "brighton",
    "carlisle", "cartmel", "catterick", "chelmsford", "cheltenham",
    "chepstow", "chester", "doncaster", "epsom", "exeter", "fakenham",
    "ffos las", "fontwell", "goodwood", "hamilton", "haydock", "hereford",
    "hexham", "huntingdon", "kelso", "kempton", "leicester", "lingfield",
    "ludlow", "market rasen", "musselburgh", "newbury", "newcastle",
    "newmarket", "newton abbot", "nottingham", "perth", "plumpton",
    "pontefract", "redcar", "ripon", "salisbury", "sandown", "sedgefield",
    "southwell", "stratford", "taunton", "thirsk", "uttoxeter", "warwick",
    "wetherby", "wincanton", "windsor", "wolverhampton", "worcester",
    "yarmouth", "york",
    # AW tracks
    "chelmsford city", "kempton park", "lingfield park", "newcastle",
    "southwell", "wolverhampton", "dundalk",
}

# Irish courses
IRISH_COURSES = {
    "ballinrobe", "bellewstown", "clonmel", "cork", "curragh",
    "downpatrick", "down royal", "dundalk", "fairyhouse", "galway",
    "gowran park", "kilbeggan", "killarney", "laytown", "leopardstown",
    "limerick", "listowel", "naas", "navan", "punchestown",
    "roscommon", "sligo", "thurles", "tipperary", "tramore",
    "wexford",
}

# All valid courses (UK + Ireland)
VALID_COURSES = UK_COURSES | IRISH_COURSES

# Racing Post course IDs (kept for reference / future use)
COURSE_IDS = {
    "aintree": 1, "ascot": 2, "ayr": 3, "bangor": 4, "bath": 5,
    "beverley": 6, "brighton": 7, "carlisle": 8, "cartmel": 9,
    "catterick": 10, "chelmsford": 74, "cheltenham": 11, "chepstow": 12,
    "chester": 10, "doncaster": 14, "epsom": 16, "exeter": 17,
    "fakenham": 18, "fontwell": 19, "goodwood": 19, "hamilton": 20,
    "haydock": 21, "hereford": 22, "hexham": 83, "huntingdon": 23,
    "kempton": 23, "leicester": 24, "lingfield": 26, "ludlow": 27,
    "market rasen": 28, "musselburgh": 28, "newbury": 31, "newcastle": 29,
    "newmarket": 30, "newton abbot": 32, "nottingham": 33, "perth": 35,
    "plumpton": 36, "pontefract": 37, "redcar": 38, "ripon": 39,
    "salisbury": 40, "sandown": 54, "sedgefield": 41, "southwell": 42,
    "stratford": 43, "taunton": 44, "thirsk": 45, "uttoxeter": 46,
    "warwick": 47, "wetherby": 46, "wincanton": 48, "windsor": 49,
    "wolverhampton": 49, "worcester": 50, "york": 47,
}

# Scoring weights (from CLAUDE.md analysis framework)
SCORING_WEIGHTS = {
    "form": 22,
    "course_form": 15,
    "going": 15,
    "distance": 12,
    "class": 12,
    "speed_figures": 8,
    "weight": 8,
    "jockey": 5,
    "trainer": 5,
}

# Edge bonuses
EDGE_BONUSES = {
    "mares_allowance_g1_g2": 4,
    "wind_surgery_first_run": 3,
    "first_time_headgear": 3,
    "olbg_trend_market_mover": 5,
    "stable_confidence": 3,
    "superior_sectionals": 3,
    "strong_gallop_reports": 3,
    "flat_jockey_nh_bumper": 3,
    "fresh_from_break": 2,
    "pace_scenario_suits": 2,
}

# Selection thresholds (v4.1: 75+ for NAP, back from v3's 78+)
NAP_THRESHOLD = 75
NEXT_BEST_THRESHOLD = 65
EACH_WAY_THRESHOLD = 55
PASS_THRESHOLD = 55

# Staking (in points)
# Updated 4 May 2026: race SEL 1.0 → 0.75 and race_nb 0.5 → 0.75. Per-race
# total stays at 1.5pt — risk redistributed from SEL slot (where picks
# have systematically lost) to race NB slot (where 5/1+ winners have been
# rescuing both cards: Lyrical Song 10/1, Must Believe 17/2, Diamont Katie
# 100/30, Place De La Nation 10/1, Layla Liz 12/1 etc).
STAKING = {
    "nap": 2.0,
    "next_best": 1.5,
    "selection": 0.75,
    "race_nb": 0.75,
    "double_nap_nb": 1.0,
    "treble_top3": 0.5,
}

# User agent for scraping
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
