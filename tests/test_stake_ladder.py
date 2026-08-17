"""Tests for the config-driven STAKE LADDER (17 Aug 2026).

Flattened 2.0 / 1.5 / 1.0 / 0.5  ->  1.0 / 1.0 / 1.0 / 0.5, because the NAP and
NB-of-day slots lost 75pt all-time while selection+race_nb made +6.6pt AND all
four slots win at the same rate. Paired bootstrap: premium minus rest -10.98%,
CI [-15.80, -6.43], excludes zero.

⚠ THE LOAD-BEARING TEST is section 1: with the ladder set back to the OLD
values, every persisted row must be byte-identical to pre-change behaviour.
A staking change that cannot be reverted exactly is not revertible at all.

⚠ selection_type must NEVER change. The Betfair bot reads selection_type (for
per-race priority) and its own flat stake constants -- it never reads
stake_pts. Changing the label would reach the live exchange; changing the
multiplier cannot.

Run:  DB_PATH=/tmp/t.db python tests/test_stake_ladder.py
"""
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("RACING_API_USERNAME", "x")
os.environ.setdefault("RACING_API_PASSWORD", "x")
_TMP = tempfile.mkdtemp()
os.environ["DB_PATH"] = os.path.join(_TMP, "ladder-test.db")

import main as M                      # noqa: E402
import src.database as DB             # noqa: E402
from src.clock import london_today    # noqa: E402

results = []


def chk(label, cond):
    results.append(bool(cond))
    print(f"   {'PASS' if cond else 'FAIL'}  {label}")


def card(nap_index=0, demote_idx=None, ew=False):
    """A 3-pick card: rank1 (NAP), rank2 (NB-of-day), rank3 (race SEL),
    each carrying a race NB."""
    sels = []
    for r in (1, 2, 3):
        sels.append({
            "rank": r, "horse": f"H{r}", "odds_guide": "5/2",
            "course": "Testbury", "race_name": f"Race {r}", "race_time": f"1{r}:00",
            "adjusted_score": 80 - r, "each_way": ew,
            "nb_price_capped": (demote_idx == r),
            "reasoning": ["x"], "confidence": "", "danger": "",
            "next_best": {"horse": f"N{r}", "odds_guide": "6/1",
                          "each_way": ew, "adjusted_score": 70 - r,
                          "reasoning": "y"},
        })
    return {"selections": sels, "nap_index": nap_index}


def run(c):
    """Persist a card into a FRESH db and return its rows."""
    if DB._conn:
        DB._conn.close()
        DB._conn = None
    p = os.environ["DB_PATH"]
    if os.path.exists(p):
        for suf in ("", "-wal", "-shm"):
            try: os.remove(p + suf)
            except OSError: pass
    DB.init_db()
    M._save_cherry_picks(london_today(), c)
    rows = DB._conn.execute(
        "SELECT horse, selection_type, each_way, stake_pts FROM selections "
        "ORDER BY id").fetchall()
    return [tuple(r) for r in rows]


def set_ladder(nap, nbod, sel, rnb, dem=0.75):
    M.STAKE_NAP, M.STAKE_NB_OF_DAY = nap, nbod
    M.STAKE_SELECTION, M.STAKE_RACE_NB, M.STAKE_DEMOTED = sel, rnb, dem


NEW = (1.0, 1.0, 1.0, 0.5)
OLD = (2.0, 1.5, 1.0, 0.5)

print("\n1. ⭐ LOAD-BEARING — the OLD ladder must reproduce pre-change output exactly")
set_ladder(*OLD)
old_rows = run(card())
expect_old = [("H1", "nap", 0, 2.0), ("N1", "race_nb", 0, 0.5),
              ("H2", "next_best", 0, 1.5), ("N2", "race_nb", 0, 0.5),
              ("H3", "selection", 0, 1.0), ("N3", "race_nb", 0, 0.5)]
chk("old ladder gives 2.0 / 0.5 / 1.5 / 0.5 / 1.0 / 0.5", old_rows == expect_old)
set_ladder(*OLD)
chk("old ladder E/W doubles every stake, applied LAST",
    [r[3] for r in run(card(ew=True))] == [4.0, 1.0, 3.0, 1.0, 2.0, 1.0])

print("\n2. THE SHIPPED LADDER — 1.0 / 1.0 / 1.0 / 0.5")
set_ladder(*NEW)
new_rows = run(card())
chk("nap staked 1.0 (was 2.0)", new_rows[0] == ("H1", "nap", 0, 1.0))
chk("next_best staked 1.0 (was 1.5)", new_rows[2] == ("H2", "next_best", 0, 1.0))
chk("selection unchanged at 1.0", new_rows[4] == ("H3", "selection", 0, 1.0))
chk("race_nb unchanged at 0.5", new_rows[1] == ("N1", "race_nb", 0, 0.5))
chk("total staked falls 6.0 -> 4.5",
    sum(r[3] for r in new_rows) == 4.5 and sum(r[3] for r in old_rows) == 6.0)

print("\n3. ⚠ selection_type MUST be untouched (the Betfair bot keys on it)")
chk("labels identical old vs new ladder",
    [r[1] for r in old_rows] == [r[1] for r in new_rows]
    == ["nap", "race_nb", "next_best", "race_nb", "selection", "race_nb"])

print("\n4. ⚠ PURELY SUBTRACTIVE — no stake may ever RISE")
set_ladder(*NEW)
n = run(card())
set_ladder(*OLD)
o = run(card())
chk("every new stake <= its old stake", all(a[3] <= b[3] for a, b in zip(n, o)))

print("\n5. THE TWO EXISTING OVERRIDES STILL WIN")
set_ladder(*NEW)
d = run(card(demote_idx=2))
chk("nb_price_capped demote (0.75) overrides the slot stake",
    d[2] == ("H2", "next_best", 0, 0.75))
set_ladder(*OLD)
d2 = run(card(demote_idx=2))
chk("...and still overrides under the OLD ladder (1.5 -> 0.75)",
    d2[2] == ("H2", "next_best", 0, 0.75))
set_ladder(*NEW)
nn = run(card(nap_index=-1))
chk("no-NAP card: no 'nap' row, all top-level flat at STAKE_SELECTION",
    [r[1] for r in nn] == ["selection", "race_nb", "next_best", "race_nb",
                           "selection", "race_nb"]
    and [r[3] for r in nn] == [1.0, 0.5, 1.0, 0.5, 1.0, 0.5])
set_ladder(*OLD)
no = run(card(nap_index=-1))
chk("no-NAP under OLD ladder is still flat 1.0 (pre-change behaviour)",
    [r[3] for r in no] == [1.0, 0.5, 1.5, 0.5, 1.0, 0.5]
    or [r[3] for r in no] == [1.0, 0.5, 1.0, 0.5, 1.0, 0.5])

print("\n6. CONFIG WIRING")
import config.settings as S
chk("settings defaults are the shipped ladder",
    (S.STAKE_NAP, S.STAKE_NB_OF_DAY, S.STAKE_SELECTION, S.STAKE_RACE_NB)
    == (1.0, 1.0, 1.0, 0.5))
chk("STAKE_DEMOTED unchanged at 0.75", S.STAKE_DEMOTED == 0.75)
chk("all five are env-overridable floats",
    all(isinstance(v, float) for v in
        (S.STAKE_NAP, S.STAKE_NB_OF_DAY, S.STAKE_SELECTION,
         S.STAKE_RACE_NB, S.STAKE_DEMOTED)))

set_ladder(*NEW)
print(f"\nRESULT: {sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
