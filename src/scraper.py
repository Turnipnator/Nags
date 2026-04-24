"""
Racing API client - replaces all web scraping.

Primary data source: The Racing API (theracingapi.com)
- Racecards with OR, RPR, Topspeed, wind surgery, headgear, spotlight
- Results with SP, finishing positions, beaten distances
- Horse search and full race history

UK and Irish racing only (filtered client-side).
"""

import logging
import re
import time as time_mod
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

import httpx

from config.settings import (
    RACING_API_USERNAME, RACING_API_PASSWORD, VALID_COURSES,
)

logger = logging.getLogger(__name__)


@dataclass
class Runner:
    name: str
    horse_id: Optional[str] = None
    age: Optional[int] = None
    weight_stones: Optional[int] = None
    weight_pounds: Optional[int] = None
    weight_lbs: Optional[int] = None
    official_rating: Optional[int] = None
    rpr: Optional[int] = None
    jockey: Optional[str] = None
    trainer: Optional[str] = None
    trainer_14d_pct: Optional[int] = None
    form: Optional[str] = None
    days_since_run: Optional[int] = None
    draw: Optional[int] = None
    headgear: Optional[str] = None
    first_time_headgear: bool = False
    wind_surgery: bool = False
    wind_surgery_run: Optional[str] = None
    speed_figure: Optional[int] = None  # Topspeed
    comment: Optional[str] = None  # Spotlight
    odds: Optional[str] = None
    sex: Optional[str] = None
    course_winner: bool = False
    distance_winner: bool = False
    cd_winner: bool = False
    sire: Optional[str] = None
    dam: Optional[str] = None
    damsire: Optional[str] = None
    saddle_cloth: Optional[int] = None
    silk_url: Optional[str] = None
    medical: Optional[list] = None
    stable_tour: Optional[str] = None
    # Last 3 runs: list of {date, class_level (int), position (str), race_name}
    # Populated by Scraper.enrich_with_recent_classes() after racecard fetch.
    # Used by scorer for authoritative class-drop kicker detection.
    recent_results: Optional[list] = None


@dataclass
class Race:
    time: str
    name: str
    course: str
    distance: str
    race_id: Optional[str] = None
    race_class: Optional[str] = None
    race_type: Optional[str] = None
    going: Optional[str] = None
    prize_money: Optional[str] = None
    num_runners: int = 0
    runners: list[Runner] = field(default_factory=list)
    surface: Optional[str] = None
    age_restriction: Optional[str] = None
    pattern: Optional[str] = None
    rail_movements: Optional[str] = None
    stalls: Optional[str] = None
    weather: Optional[str] = None


@dataclass
class Meeting:
    course: str
    date: date
    going: Optional[str] = None
    races: list[Race] = field(default_factory=list)


class Scraper:
    """Racing API client with UK/Irish filtering."""

    def __init__(self):
        self.client = httpx.Client(
            auth=(RACING_API_USERNAME, RACING_API_PASSWORD),
            timeout=30.0,
        )
        self.base_url = "https://api.theracingapi.com/v1"

    def close(self):
        self.client.close()

    # --- Public API ---

    def get_todays_meetings(self, target_date: date = None) -> list[dict]:
        """Get today's UK/Irish meetings from the Racing API."""
        if target_date is None:
            target_date = date.today()

        day_param = self._get_day_param(target_date)
        qs = f"?{day_param}" if day_param else ""
        data = self._api_get(f"/racecards/pro{qs}")
        if not data:
            return []

        races = data.get("racecards", [])

        # Group by course, filter to UK/Irish
        courses = {}
        for race in races:
            course = race["course"]
            region = race.get("region", "")
            if region in ("GB", "IRE") and self._is_valid_course(course):
                if course not in courses:
                    courses[course] = {
                        "course": course,
                        "country": "IRE" if region == "IRE" else "UK",
                        "source": "racing_api",
                        "num_races": 0,
                        "going": race.get("going", ""),
                    }
                courses[course]["num_races"] += 1

        meetings = list(courses.values())
        logger.info(f"Found {len(meetings)} UK/Irish meetings from Racing API")
        return meetings

    def fetch_meeting(self, course: str, target_date: date) -> Optional[Meeting]:
        """Fetch full meeting data from the Racing API."""
        day_param = self._get_day_param(target_date)
        qs = f"?{day_param}" if day_param else ""
        data = self._api_get(f"/racecards/pro{qs}")
        if not data:
            return None

        meeting = Meeting(course=course, date=target_date)

        for race_data in data.get("racecards", []):
            if race_data["course"].lower() == course.lower():
                race = self._parse_race(race_data)
                if race and race.runners:
                    meeting.races.append(race)
                    if race.going and not meeting.going:
                        meeting.going = race.going

        if meeting.races:
            total = sum(len(r.runners) for r in meeting.races)
            logger.info(
                f"Parsed {course} from API: {len(meeting.races)} races, {total} runners"
            )
            return meeting

        logger.warning(f"No races found for {course}")
        return None

    def fetch_all_uk_irish_races(self, target_date: date = None, focus_courses: list[str] = None) -> list[Meeting]:
        """Fetch UK/Irish meetings in one API call. Optionally filter to specific courses."""
        if target_date is None:
            target_date = date.today()

        day_param = self._get_day_param(target_date)
        qs = f"?{day_param}" if day_param else ""
        data = self._api_get(f"/racecards/pro{qs}")
        if not data:
            return []

        # Normalise focus list for matching
        if focus_courses:
            focus_lower = {c.strip().lower() for c in focus_courses if c.strip()}
        else:
            focus_lower = None

        # Group races by course — EXCLUDE AW flat cards
        # Our system is proven on NH turf. AW evening cards consistently underperform.
        course_races = {}
        for race_data in data.get("racecards", []):
            region = race_data.get("region", "")
            course = race_data["course"]
            surface = race_data.get("surface", "")
            race_type = race_data.get("type", "")

            # Skip abandoned meetings
            if race_data.get("is_abandoned") or race_data.get("race_status") == "abandoned":
                continue

            # Apply focus filter if set (check BEFORE AW block — explicit focus overrides)
            # Use substring matching so "wolverhampton" matches "Wolverhampton (AW)"
            if focus_lower:
                course_lower = course.lower()
                if not any(f in course_lower or course_lower in f for f in focus_lower):
                    continue

            # Skip AW flat cards — UNLESS user explicitly focused on this course
            if not focus_lower:
                if surface and surface.lower() in ("artificial", "polytrack", "tapeta", "fibresand"):
                    continue
                if "(AW)" in course:
                    continue

            if region in ("GB", "IRE") and self._is_valid_course(course):
                if course not in course_races:
                    course_races[course] = []
                course_races[course].append(race_data)

        # Build Meeting objects
        meetings = []
        for course, race_list in course_races.items():
            meeting = Meeting(course=course, date=target_date)
            for race_data in race_list:
                race = self._parse_race(race_data)
                if race and race.runners:
                    meeting.races.append(race)
                    if race.going and not meeting.going:
                        meeting.going = race.going
            if meeting.races:
                meetings.append(meeting)

        total_races = sum(len(m.races) for m in meetings)
        total_runners = sum(sum(len(r.runners) for r in m.races) for m in meetings)
        logger.info(
            f"Fetched {len(meetings)} meetings, {total_races} races, "
            f"{total_runners} runners from Racing API"
        )
        return meetings

    def fetch_timeform_verdicts(self, meetings: list[Meeting]) -> dict:
        """
        Fetch Timeform analyst verdicts for each meeting.
        Source: timeform.com/horse-racing/tips/{course}-best-bets-today/{id}
        Returns dict of {course: verdict_text}
        """
        import httpx as _httpx
        import re as _re

        TIMEFORM_IDS = {
            "newcastle": 35, "lingfield": 30, "curragh": 204,
            "chepstow": 12, "wincanton": 56, "kelso": 18,
            "sedgefield": 18, "southwell": 27, "doncaster": 14,
            "ascot": 2, "haydock": 21, "warwick": 85,
            "bangor-on-dee": 4, "bangor": 4, "uttoxeter": 46,
            "cheltenham": 11, "kempton": 23, "york": 47,
            "wetherby": 46, "newbury": 31, "fontwell": 19,
            "exeter": 17, "taunton": 44, "stratford": 43,
            "ludlow": 27, "huntingdon": 23, "carlisle": 8,
            "perth": 35, "musselburgh": 28, "ayr": 3,
            "navan": 204, "leopardstown": 204, "fairyhouse": 204,
            "punchestown": 204, "galway": 204, "cork": 204,
            "limerick": 204, "downpatrick": 204, "clonmel": 204,
        }

        verdicts = {}
        tf_client = _httpx.Client(
            headers={"User-Agent": "Mozilla/5.0"},
            follow_redirects=True,
            timeout=15.0,
        )

        for meeting in meetings:
            course_lower = meeting.course.lower().replace(" (aw)", "").replace(" ", "-")
            tf_id = TIMEFORM_IDS.get(course_lower)
            if not tf_id:
                logger.debug(f"No Timeform ID for {course_lower}")
                continue

            url = f"https://www.timeform.com/horse-racing/tips/{course_lower}-best-bets-today/{tf_id}"
            try:
                resp = tf_client.get(url)
                if resp.status_code == 200:
                    # Extract text content
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(resp.text, "lxml")
                    text = soup.get_text(separator="\n", strip=True)
                    # Look for verdict sections
                    if "Verdict" in text or "verdict" in text or "1." in text:
                        verdicts[meeting.course] = text[:5000]
                        logger.info(f"Timeform verdicts fetched for {meeting.course}")
                    else:
                        logger.debug(f"No verdicts found in Timeform page for {meeting.course}")
                else:
                    logger.debug(f"Timeform {resp.status_code} for {meeting.course}")
            except Exception as e:
                logger.debug(f"Timeform fetch failed for {meeting.course}: {e}")

            time_mod.sleep(1)  # Be polite

        tf_client.close()
        return verdicts

    def fetch_results(self, target_date: date, region: str = "gb") -> list[dict]:
        """Fetch results for a specific date."""
        date_str = target_date.strftime("%Y-%m-%d")
        data = self._api_get(
            f"/results?start_date={date_str}&end_date={date_str}"
            f"&region={region}&limit=100"
        )
        if not data:
            return []
        return data.get("results", [])

    def fetch_result_by_race_id(self, race_id: str) -> Optional[dict]:
        """Fetch result for a specific race."""
        data = self._api_get(f"/results/{race_id}")
        return data

    def search_horse(self, name: str) -> Optional[dict]:
        """Search for a horse by name."""
        data = self._api_get(f"/horses/search?name={name}")
        if data and data.get("search_results"):
            return data["search_results"][0]
        return None

    def fetch_horse_results(self, horse_id: str) -> list[dict]:
        """Fetch full race history for a horse."""
        data = self._api_get(f"/horses/{horse_id}/results")
        if not data:
            return []
        return data.get("results", [])

    def fetch_recent_race_classes(self, horse_id: str, limit: int = 3) -> list[dict]:
        """
        Fetch the most recent `limit` race results for a horse and return
        a compact list of {date, class_str, class_level, position, race_name}.

        class_level is a numeric level from CLASS_LEVELS_NH/FLAT in scorer
        (higher = better). Returns [] on any failure.

        Used for authoritative class-drop detection in scoring, replacing
        fragile Spotlight text matching.
        """
        from src.scorer import CLASS_LEVELS_NH, CLASS_LEVELS_FLAT
        data = self._api_get(f"/horses/{horse_id}/results?limit={limit}")
        if not data:
            return []
        out = []
        for r in data.get("results", [])[:limit]:
            class_str = (r.get("class") or "").strip().lower()
            pattern = (r.get("pattern") or "").strip().lower()
            race_type = (r.get("type") or "").lower()
            # NH races: chase / hurdle / nh flat. Otherwise treat as Flat.
            is_nh = any(t in race_type for t in ("chase", "hurdle", "nh flat"))
            class_map = CLASS_LEVELS_NH if is_nh else CLASS_LEVELS_FLAT
            # Resolve level: pattern (grade/listed) beats class_str if present
            level = None
            for label, lvl in class_map.items():
                if label in pattern:
                    level = lvl
                    break
            if level is None:
                for label, lvl in class_map.items():
                    if label in class_str:
                        level = lvl
                        break
            # Find this horse's position in the runners list
            position = None
            for rn in r.get("runners", []):
                if rn.get("horse_id") == horse_id:
                    position = rn.get("position")
                    break
            course_raw = r.get("course") or ""
            # Quality-filter markers for the class-drop kicker:
            # - is_foreign: races outside UK/IRE don't translate cleanly
            # - is_aw: surface mismatch to turf today (or vice versa) erodes signal
            foreign_markers = ("(FR)", "(SWI)", "(GER)", "(US)", "(CAN)",
                               "(JPN)", "(HK)", "(UAE)", "(AUS)", "(ITA)",
                               "(ARG)", "(SAF)", "(BAH)")
            is_foreign = any(m in course_raw for m in foreign_markers)
            is_aw = "(AW)" in course_raw
            out.append({
                "date": r.get("date"),
                "class_str": class_str or pattern,
                "class_level": level,
                "position": position,
                "race_name": r.get("race_name"),
                "course": course_raw,
                "is_foreign": is_foreign,
                "is_aw": is_aw,
            })
        return out

    def enrich_with_recent_classes(self, meetings: list, limit: int = 3,
                                   max_workers: int = 4) -> None:
        """
        Populate runner.recent_results for every runner across all meetings
        using a thread pool (one API call per runner). Modifies meetings
        in place. Skips runners with no horse_id or that already have
        recent_results populated.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        runners = []
        for m in meetings:
            for race in m.races:
                for runner in race.runners:
                    if runner.horse_id and runner.recent_results is None:
                        runners.append(runner)

        if not runners:
            return

        logger.info(f"Enriching {len(runners)} runners with recent race classes...")
        start = time_mod.time()

        def _fetch(runner):
            try:
                return runner, self.fetch_recent_race_classes(runner.horse_id, limit)
            except Exception as exc:
                logger.debug(f"recent_classes fetch failed for {runner.name}: {exc}")
                return runner, []

        completed = 0
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [pool.submit(_fetch, r) for r in runners]
            for fut in as_completed(futures):
                runner, results = fut.result()
                runner.recent_results = results
                completed += 1

        elapsed = time_mod.time() - start
        logger.info(
            f"Enriched {completed}/{len(runners)} runners in {elapsed:.1f}s"
        )

    def fetch_tips_and_previews(self, course: str, target_date: date) -> list[str]:
        """Spotlight comments from the API serve as our tips/previews."""
        # The API spotlight comments replace external tip scraping
        return []

    def fetch_going_report(self, course: str) -> Optional[str]:
        """Going is embedded in the racecard data from the API."""
        return None

    # --- API helpers ---

    def _api_get(self, endpoint: str) -> Optional[dict]:
        """Make an authenticated GET request to the Racing API."""
        url = f"{self.base_url}{endpoint}"
        try:
            resp = self.client.get(url)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 429:
                logger.warning("Racing API rate limited, waiting 5s...")
                time_mod.sleep(5)
                resp = self.client.get(url)
                if resp.status_code == 200:
                    return resp.json()
            logger.warning(f"Racing API {endpoint}: {resp.status_code}")
            return None
        except Exception as e:
            logger.error(f"Racing API error: {e}")
            return None

    def _get_day_param(self, target_date: date) -> str:
        """Return the /racecards/pro query string for a target date.
        The /pro endpoint accepts ?date=YYYY-MM-DD (NOT ?day=today/tomorrow,
        which is the basic endpoint's format). Returns an empty string for
        today (endpoint defaults to today when no param is provided).
        Updated 24 Apr 2026 when scraper switched to /pro for odds data."""
        today = date.today()
        if target_date == today:
            return ""
        return f"date={target_date.isoformat()}"

    # --- Data parsing ---

    def _parse_race(self, data: dict) -> Race:
        """Parse a race from API response into our Race dataclass."""
        race = Race(
            time=data.get("off_time", ""),
            name=data.get("race_name", ""),
            course=data.get("course", ""),
            distance=data.get("distance", ""),
            race_id=data.get("race_id"),
            race_class=data.get("race_class", ""),
            race_type=data.get("type", ""),
            going=data.get("going", ""),
            prize_money=data.get("prize", ""),
            surface=data.get("surface", ""),
            age_restriction=data.get("age_band", ""),
            pattern=data.get("pattern", ""),
            rail_movements=data.get("rail_movements", ""),
            stalls=data.get("stalls", ""),
            weather=data.get("weather", ""),
        )

        for runner_data in data.get("runners", []):
            runner = self._parse_runner(runner_data)
            if runner:
                race.runners.append(runner)

        race.num_runners = len(race.runners)
        return race

    def _parse_runner(self, data: dict) -> Optional[Runner]:
        """Parse a runner from API response into our Runner dataclass."""
        name = data.get("horse", "")
        if not name:
            return None

        # Skip non-runners (no jockey assigned)
        jockey = data.get("jockey", "")
        if not jockey:
            return None

        # Parse weight from lbs
        weight_lbs = None
        weight_stones = None
        weight_pounds = None
        try:
            lbs = int(data.get("lbs", 0))
            if lbs > 0:
                weight_lbs = lbs
                weight_stones = lbs // 14
                weight_pounds = lbs % 14
        except (ValueError, TypeError):
            pass

        # Parse OR, RPR, TS
        ofr = self._safe_int(data.get("ofr"))
        rpr = self._safe_int(data.get("rpr"))
        ts = self._safe_int(data.get("ts"))

        # Parse headgear
        headgear = data.get("headgear", "") or ""
        headgear_run = data.get("headgear_run", "") or ""
        first_time_hg = bool(headgear and headgear_run == "1")

        # Parse wind surgery
        wind_surgery = data.get("wind_surgery") == "yes"
        wind_surgery_run = data.get("wind_surgery_run", "")

        # Parse trainer 14-day form
        t14 = data.get("trainer_14_days", {})
        trainer_14d_pct = self._safe_int(t14.get("percent"))

        # Parse days since run
        days_since = self._safe_int(data.get("last_run"))

        # Parse draw
        draw = self._safe_int(data.get("draw"))

        # Parse saddle cloth number
        number = self._safe_int(data.get("number"))

        # Parse past results flags for C/D/CD
        flags = data.get("past_results_flags", "") or ""
        cd_winner = "CD" in flags or "C&D" in flags
        course_winner = cd_winner or "C" in flags
        distance_winner = cd_winner or "D" in flags

        # Parse sex
        sex = data.get("sex", "")

        # Parse breeding
        sire = data.get("sire", "")
        dam = data.get("dam", "")
        damsire = data.get("damsire", "")

        # Spotlight comment
        spotlight = data.get("spotlight", "") or ""

        # Medical history
        medical = data.get("medical", [])

        # Stable tour quotes
        stable_tour_data = data.get("stable_tour", [])
        stable_tour = ""
        if stable_tour_data:
            quotes = [q.get("quote", "") for q in stable_tour_data if q.get("quote")]
            stable_tour = " | ".join(quotes)

        # Parse odds from API response. Prefer Bet365 as reference bookmaker;
        # fall back to first available. Added 24 Apr 2026 after discovering the
        # bot's LLM was hallucinating prices because this field was never populated.
        odds_value = None
        odds_list = data.get("odds", []) or []
        if odds_list:
            bet365 = next((o for o in odds_list if o.get("bookmaker") == "Bet365"), None)
            ref = bet365 or odds_list[0]
            odds_value = ref.get("fractional") or None

        runner = Runner(
            name=name,
            horse_id=data.get("horse_id"),
            age=self._safe_int(data.get("age")),
            weight_stones=weight_stones,
            weight_pounds=weight_pounds,
            weight_lbs=weight_lbs,
            official_rating=ofr,
            rpr=rpr,
            jockey=jockey,
            trainer=data.get("trainer", ""),
            trainer_14d_pct=trainer_14d_pct,
            form=data.get("form", ""),
            days_since_run=days_since,
            draw=draw,
            headgear=headgear,
            first_time_headgear=first_time_hg,
            wind_surgery=wind_surgery,
            wind_surgery_run=wind_surgery_run,
            speed_figure=ts,
            comment=spotlight,
            sex=sex,
            course_winner=course_winner,
            distance_winner=distance_winner,
            cd_winner=cd_winner,
            sire=sire,
            dam=dam,
            damsire=damsire,
            saddle_cloth=number,
            silk_url=data.get("silk_url"),
            medical=medical,
            stable_tour=stable_tour,
            odds=odds_value,
        )

        return runner

    # --- Utility ---

    def _safe_int(self, val) -> Optional[int]:
        """Safely convert a value to int, returning None on failure."""
        if val is None or val == "" or val == "-":
            return None
        try:
            return int(val)
        except (ValueError, TypeError):
            return None

    def _is_valid_course(self, name: str) -> bool:
        name_lower = name.lower().strip()
        if name_lower in VALID_COURSES:
            return True
        for valid in VALID_COURSES:
            if valid in name_lower or name_lower in valid:
                return True
        return False

    def _extract_text(self, html: str) -> str:
        """Kept for compatibility but shouldn't be needed with API."""
        return html
