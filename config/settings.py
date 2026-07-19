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
JUDGEMENT_MODEL = os.getenv("JUDGEMENT_MODEL", "claude-opus-4-8")

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
