"""_save_cherry_picks must honour the compliance demote flag (28 Jul 2026).

Every demote check (NB field-size floor, price cap, NB score floor, F2/F3,
going gate) sets `nb_price_capped` meaning "0.75pt race SEL stake". Before this
fix the stake was derived from selection_type alone, so a demoted NB persisted
at its full 1.5pt E/W and lost double the intended stake (Pearl Eye, £30 vs £15).

Expectations read the CONFIGURED ladder (config.settings STAKE_*), not literal
points: the 17 Aug 2026 flattening (2.0/1.5 -> 1.0/1.0) silently broke the
hardcoded 4.0/3.0 expectations. What is under test is that the demote flag
selects STAKE_DEMOTED, whatever the ladder is.

Run: PYTHONPATH=. .venv/bin/python tests/test_demote_stake.py
"""
from datetime import date

import src.database as db
import main
from config.settings import STAKE_NAP, STAKE_NB_OF_DAY, STAKE_DEMOTED


def _fresh_db():
    # Build the schema with the REAL init_db() against an in-memory file.
    # The previous hand-mirrored CREATE TABLE went stale the moment the
    # `source` column was added (15 Aug 2026) and the test failed at HEAD on
    # "no such column: source" for a fortnight. Using init_db() means every
    # migration in database.py is applied here too, so this cannot drift again.
    db.DB_PATH = ":memory:"
    db.init_db()


def _mk(rank, horse, ew=True, capped=False):
    return {
        "rank": rank, "horse": horse, "race_time": "16:15", "course": "Ayr",
        "race_name": "Handicap", "odds_guide": "5/2", "each_way": ew,
        "adjusted_score": 82, "reasoning": [], "confidence": "", "danger": "",
        "next_best": {}, "nb_price_capped": capped,
    }


def stake_of(horse):
    return db._conn.execute(
        "SELECT stake_pts, each_way FROM selections WHERE horse = ?", (horse,)
    ).fetchone()


PASS = FAIL = 0
def check(label, got, want):
    global PASS, FAIL
    ok = abs(got - want) < 1e-9
    print(f"  {'PASS' if ok else 'FAIL'}  {label}: got {got} want {want}")
    PASS += ok; FAIL += not ok


# NAP present at rank 1; rank-2 pick is the NB-of-day. Demote the NB.
print(f"1. demoted NB (Pearl Eye case) -> {STAKE_DEMOTED}pt race SEL, E/W => {2*STAKE_DEMOTED} outlay")
_fresh_db()
main._save_cherry_picks(date(2026, 7, 28), {
    "selections": [_mk(1, "TheNap", ew=True, capped=False),
                   _mk(2, "PearlEye", ew=True, capped=True)],
    "nap_index": 0,
})
check(f"PearlEye stake_pts ({STAKE_DEMOTED} E/W)", stake_of("PearlEye")["stake_pts"], 2 * STAKE_DEMOTED)
check(f"TheNap stake_pts ({STAKE_NAP} E/W)", stake_of("TheNap")["stake_pts"], 2 * STAKE_NAP)

print(f"2. no-regression: undemoted NB keeps full {STAKE_NB_OF_DAY}pt E/W => {2*STAKE_NB_OF_DAY} outlay")
_fresh_db()
main._save_cherry_picks(date(2026, 7, 28), {
    "selections": [_mk(1, "TheNap2", ew=True, capped=False),
                   _mk(2, "RealNB", ew=True, capped=False)],
    "nap_index": 0,
})
check(f"RealNB stake_pts ({STAKE_NB_OF_DAY} E/W)", stake_of("RealNB")["stake_pts"], 2 * STAKE_NB_OF_DAY)

print(f"3. demoted win-only pick -> {STAKE_DEMOTED} win => {STAKE_DEMOTED} outlay")
_fresh_db()
main._save_cherry_picks(date(2026, 7, 28), {
    "selections": [_mk(1, "TheNap3", ew=True, capped=False),
                   _mk(2, "WinOnlyCap", ew=False, capped=True)],
    "nap_index": 0,
})
check(f"WinOnlyCap stake_pts ({STAKE_DEMOTED} win)", stake_of("WinOnlyCap")["stake_pts"], STAKE_DEMOTED)

print(f"\nRESULT: {PASS}/{PASS + FAIL} passed")
raise SystemExit(1 if FAIL else 0)
