"""Daily card replacement — a later /run supersedes the day's earlier card.

Added 1 Aug 2026. The Operating Policy cap ("max 6 selections per day, 1 NAP")
was enforced PER RUN: `_enforce_compliance` only sees one run's list, and the
save path did a bare INSERT with no knowledge of what today already held. So a
second `/run` wrote a whole fresh card at full stakes — Thirsk then Goodwood on
1 Aug 2026 gave 8 top-level selections, TWO NAPs and £245 staked at £10/pt.

Paul's call (1 Aug 2026): a later run REPLACES the day's card. Implemented as
SUPERSEDE, never DELETE — rows stay for audit, live reads filter them.

The load-bearing test here is `test_single_run_unchanged`: on a normal one-run
day the behaviour must be byte-identical to before.
"""
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _fresh_db(tmp_path):
    """Mini schema mirroring init_db() for the columns under test."""
    db = tmp_path / "racing.db"
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE selections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meeting_id INTEGER,
            race_time TEXT NOT NULL,
            race_name TEXT,
            horse TEXT NOT NULL,
            selection_type TEXT NOT NULL,
            odds_guide TEXT,
            each_way BOOLEAN DEFAULT FALSE,
            stake_pts REAL,
            reasoning TEXT,
            confidence TEXT,
            danger TEXT,
            score REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            superseded_at TEXT          -- migration under test
        );
        CREATE TABLE results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            selection_id INTEGER REFERENCES selections(id),
            finish_position INTEGER,
            result TEXT,
            sp_odds TEXT,
            returns_pts REAL DEFAULT 0,
            pnl_pts REAL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE UNIQUE INDEX idx_results_selection ON results(selection_id);
        """
    )
    conn.commit()
    return conn


def _add(conn, horse, sel_type, when="now", stake=2.0):
    """Insert a selection. when='now' = today, 'old' = yesterday."""
    created = ("datetime('now')" if when == "now"
               else "datetime('now', '-1 day')")
    conn.execute(
        f"""INSERT INTO selections
            (meeting_id, race_time, race_name, horse, selection_type,
             odds_guide, each_way, stake_pts, score, created_at)
            VALUES (NULL,'14:08','Thirsk - X',?,?,'7/1',1,?,80,{created})""",
        (horse, sel_type, stake),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _supersede(conn):
    """Mirror of database.supersede_todays_selections()."""
    now = datetime.now().isoformat(timespec="seconds")
    cur = conn.execute(
        """UPDATE selections
              SET superseded_at = ?
            WHERE date(created_at) = date('now')
              AND superseded_at IS NULL
              AND id NOT IN (SELECT selection_id FROM results)""",
        (now,),
    )
    conn.commit()
    return cur.rowcount


def _live_today(conn):
    return conn.execute(
        """SELECT horse, selection_type FROM selections
           WHERE date(created_at) = date('now') AND superseded_at IS NULL
           ORDER BY id"""
    ).fetchall()


def test_single_run_unchanged(tmp_path):
    """NO-REGRESSION: one run/day must behave exactly as before."""
    conn = _fresh_db(tmp_path)
    _add(conn, "Northern Express", "nap")
    _add(conn, "It Just Takes Time", "next_best")
    before = [tuple(r) for r in _live_today(conn)]
    # No second run => supersede is never called. Nothing changes.
    assert before == [("Northern Express", "nap"),
                      ("It Just Takes Time", "next_best")]
    assert conn.execute(
        "SELECT count(*) FROM selections WHERE superseded_at IS NOT NULL"
    ).fetchone()[0] == 0


def test_second_run_replaces_card(tmp_path):
    """The 1 Aug case: run 2 supersedes run 1, leaving ONE NAP live."""
    conn = _fresh_db(tmp_path)
    _add(conn, "Northern Express", "nap")          # run 1 — Thirsk
    _add(conn, "It Just Takes Time", "next_best")
    assert _supersede(conn) == 2                    # run 2 — Goodwood
    _add(conn, "Al Aasy", "nap")
    _add(conn, "Ironwill", "next_best")

    live = [tuple(r) for r in _live_today(conn)]
    assert live == [("Al Aasy", "nap"), ("Ironwill", "next_best")]
    naps = [r for r in live if r[1] == "nap"]
    assert len(naps) == 1, "two NAPs in one day is the bug being fixed"


def test_superseded_rows_are_kept_not_deleted(tmp_path):
    """Audit trail: superseding must never remove a row."""
    conn = _fresh_db(tmp_path)
    _add(conn, "Northern Express", "nap")
    _supersede(conn)
    total = conn.execute("SELECT count(*) FROM selections").fetchone()[0]
    assert total == 1
    row = conn.execute("SELECT superseded_at FROM selections").fetchone()
    assert row["superseded_at"] is not None


def test_settled_rows_are_never_superseded(tmp_path):
    """A pick with a result was a real resolved bet — it stays live."""
    conn = _fresh_db(tmp_path)
    sid = _add(conn, "Northern Express", "nap")
    conn.execute(
        "INSERT INTO results (selection_id, finish_position, result, pnl_pts)"
        " VALUES (?,3,'placed',0.8)", (sid,))
    conn.commit()
    other = _add(conn, "Mirsky", "race_nb")
    assert _supersede(conn) == 1                    # only the unsettled one
    live = {r["horse"] for r in _live_today(conn)}
    assert "Northern Express" in live
    assert "Mirsky" not in live
    assert other  # silence lint


def test_yesterdays_card_untouched(tmp_path):
    """Supersede is scoped to today — history must not move."""
    conn = _fresh_db(tmp_path)
    _add(conn, "Old Pick", "nap", when="old")
    _add(conn, "Today Pick", "nap")
    assert _supersede(conn) == 1
    old = conn.execute(
        "SELECT superseded_at FROM selections WHERE horse='Old Pick'"
    ).fetchone()
    assert old["superseded_at"] is None


def test_settler_ignores_superseded(tmp_path):
    """The nightly settler must not settle a replaced card."""
    conn = _fresh_db(tmp_path)
    _add(conn, "Northern Express", "nap")
    _supersede(conn)
    _add(conn, "Al Aasy", "nap")
    pending = conn.execute(
        """SELECT horse FROM selections
           WHERE race_time != '' AND date(created_at) = date('now')
             AND superseded_at IS NULL
             AND id NOT IN (SELECT selection_id FROM results)"""
    ).fetchall()
    assert [r["horse"] for r in pending] == ["Al Aasy"]


def test_migration_is_idempotent(tmp_path):
    """Re-running the ADD COLUMN probe must not throw on an existing DB."""
    conn = _fresh_db(tmp_path)
    for _ in range(3):
        cols = {r[1] for r in conn.execute("PRAGMA table_info(selections)")}
        if "superseded_at" not in cols:
            conn.execute("ALTER TABLE selections ADD COLUMN superseded_at TEXT")
    cols = {r[1] for r in conn.execute("PRAGMA table_info(selections)")}
    assert "superseded_at" in cols


# --- source tagging (2 Aug 2026) -------------------------------------------

def _fresh_db_v2(tmp_path):
    conn = _fresh_db(tmp_path)
    conn.execute("ALTER TABLE selections ADD COLUMN source TEXT NOT NULL DEFAULT 'bot'")
    conn.commit()
    return conn


def _add_src(conn, horse, sel_type, source):
    conn.execute(
        """INSERT INTO selections
           (meeting_id,race_time,race_name,horse,selection_type,odds_guide,
            each_way,stake_pts,score,source,created_at)
           VALUES (NULL,'14:08','Chester - X',?,?,'3/1',1,3.0,80,?,datetime('now'))""",
        (horse, sel_type, source))
    conn.commit()


def _supersede_v2(conn):
    """Mirror of the patched supersede: bot rows only."""
    cur = conn.execute(
        """UPDATE selections SET superseded_at = '2026-08-02T20:00:00'
            WHERE date(created_at) = date('now') AND superseded_at IS NULL
              AND source = 'bot'
              AND id NOT IN (SELECT selection_id FROM results)""")
    conn.commit()
    return cur.rowcount


def test_existing_rows_backfill_to_bot(tmp_path):
    """ADD COLUMN ... DEFAULT 'bot' must backfill history, not leave NULLs."""
    conn = _fresh_db(tmp_path)
    _add(conn, "Old Bot Pick", "nap")
    conn.execute("ALTER TABLE selections ADD COLUMN source TEXT NOT NULL DEFAULT 'bot'")
    conn.commit()
    assert conn.execute("SELECT source FROM selections").fetchone()[0] == "bot"


def test_manual_card_survives_a_bot_run(tmp_path):
    """A later bot /run replaces the BOT card and leaves manual picks alone."""
    conn = _fresh_db_v2(tmp_path)
    _add_src(conn, "Tiger", "selection", "manual")
    _add_src(conn, "Bot Pick A", "nap", "bot")
    assert _supersede_v2(conn) == 1              # only the bot row
    live = conn.execute(
        """SELECT horse, source FROM selections
           WHERE superseded_at IS NULL ORDER BY id""").fetchall()
    assert [tuple(r) for r in live] == [("Tiger", "manual")]


def test_betfair_query_never_sees_manual(tmp_path):
    """THE MONEY TEST: the exchange must not stake a manually-logged pick."""
    conn = _fresh_db_v2(tmp_path)
    _add_src(conn, "Tiger", "selection", "manual")
    _add_src(conn, "Bot Pick A", "nap", "bot")
    rows = conn.execute(
        """SELECT horse FROM selections
           WHERE date(created_at) = date('now')
             AND superseded_at IS NULL
             AND (source IS NULL OR source = 'bot')""").fetchall()
    assert [r["horse"] for r in rows] == ["Bot Pick A"]


def test_bot_roi_can_exclude_manual(tmp_path):
    """Bot performance queries must be able to filter manual picks out."""
    conn = _fresh_db_v2(tmp_path)
    _add_src(conn, "Tiger", "selection", "manual")
    _add_src(conn, "Bot Pick A", "nap", "bot")
    n = conn.execute(
        "SELECT count(*) FROM selections WHERE source='bot'").fetchone()[0]
    assert n == 1
