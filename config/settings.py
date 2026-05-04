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
JUDGEMENT_MODEL = os.getenv("JUDGEMENT_MODEL", "claude-opus-4-6")

# Scheduling (24h format, UK timezone)
TIMEZONE = os.getenv("TIMEZONE", "Europe/London")
SCRAPE_TIME = os.getenv("SCRAPE_TIME", "07:00")
ANALYSIS_TIME = os.getenv("ANALYSIS_TIME", "12:00")
RESULTS_TIME = os.getenv("RESULTS_TIME", "18:00")

# Auto-schedule: set to "true" to enable daily auto-runs at ANALYSIS_TIME/RESULTS_TIME.
# Default OFF — use /run via Telegram for on-demand analysis.
AUTO_SCHEDULE = os.getenv("AUTO_SCHEDULE", "false").lower() == "true"

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
