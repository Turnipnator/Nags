"""
SQLite database for selections, results, and P&L tracking.
"""

import json
import logging
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from config.settings import DB_PATH

logger = logging.getLogger(__name__)

_conn: Optional[sqlite3.Connection] = None


def init_db():
    """Initialise database and create tables."""
    global _conn
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    _conn.row_factory = sqlite3.Row
    _conn.execute("PRAGMA journal_mode=WAL")

    _conn.executescript("""
        CREATE TABLE IF NOT EXISTS meetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course TEXT NOT NULL,
            date TEXT NOT NULL,
            going TEXT,
            num_races INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(course, date)
        );

        CREATE TABLE IF NOT EXISTS selections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meeting_id INTEGER REFERENCES meetings(id),
            race_time TEXT NOT NULL,
            race_name TEXT,
            horse TEXT NOT NULL,
            selection_type TEXT NOT NULL,  -- 'nap', 'next_best', 'selection', 'race_nb'
            odds_guide TEXT,
            each_way BOOLEAN DEFAULT FALSE,
            stake_pts REAL,
            reasoning TEXT,
            confidence TEXT,
            danger TEXT,
            score REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            selection_id INTEGER REFERENCES selections(id),
            finish_position INTEGER,
            result TEXT,  -- 'won', 'placed', 'lost', 'nr', 'void'
            sp_odds TEXT,
            returns_pts REAL DEFAULT 0,
            pnl_pts REAL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS bot_state (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS daily_summary (
            date TEXT PRIMARY KEY,
            total_selections INTEGER DEFAULT 0,
            winners INTEGER DEFAULT 0,
            placed INTEGER DEFAULT 0,
            total_stake_pts REAL DEFAULT 0,
            total_returns_pts REAL DEFAULT 0,
            pnl_pts REAL DEFAULT 0,
            nap_result TEXT,
            nb_result TEXT,
            notes TEXT
        );
    """)
    _conn.commit()
    logger.info(f"Database initialised at {DB_PATH}")


def save_meeting(course: str, meeting_date: date, going: str = None,
                 num_races: int = 0) -> int:
    """Save a meeting, return meeting_id."""
    cursor = _conn.execute(
        "INSERT OR REPLACE INTO meetings (course, date, going, num_races) VALUES (?, ?, ?, ?)",
        (course, meeting_date.isoformat(), going, num_races),
    )
    _conn.commit()
    return cursor.lastrowid


def save_selections(meeting_id: int, selections: dict):
    """Save full selections dict from analyst."""
    nap = selections.get("nap", {})
    nb = selections.get("next_best", {})
    race_sels = selections.get("race_selections", [])

    # Save NAP
    if nap:
        _save_selection(meeting_id, nap, "nap", 2.0)

    # Save Next Best
    if nb:
        _save_selection(meeting_id, nb, "next_best", 1.5)

    # Save per-race selections
    for rs in race_sels:
        sel = rs.get("selection", {})
        rnb = rs.get("next_best", {})
        if sel:
            _save_selection(
                meeting_id,
                {**sel, "race_time": rs.get("race_time"), "race_name": rs.get("race_name")},
                "selection", 1.0,
            )
        if rnb:
            _save_selection(
                meeting_id,
                {**rnb, "race_time": rs.get("race_time"), "race_name": rs.get("race_name")},
                "race_nb", 0.5,
            )

    _conn.commit()


def _save_selection(meeting_id: int, sel: dict, sel_type: str, stake: float):
    """Save a single selection."""
    each_way = sel.get("each_way", False)
    _conn.execute(
        """INSERT INTO selections
           (meeting_id, race_time, race_name, horse, selection_type,
            odds_guide, each_way, stake_pts, reasoning, confidence, danger, score)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            meeting_id,
            sel.get("race_time", ""),
            sel.get("race_name", ""),
            sel.get("horse", ""),
            sel_type,
            sel.get("odds_guide", ""),
            each_way,
            stake * (2 if each_way else 1),  # E/W doubles outlay
            json.dumps(sel.get("reasoning", [])),
            sel.get("confidence", ""),
            sel.get("danger", ""),
            sel.get("adjusted_score") or sel.get("score", 0),
        ),
    )


def save_result(selection_id: int, finish_pos: int, result: str,
                sp_odds: str, returns_pts: float, pnl_pts: float):
    """Save a result for a selection."""
    _conn.execute(
        """INSERT INTO results (selection_id, finish_position, result, sp_odds, returns_pts, pnl_pts)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (selection_id, finish_pos, result, sp_odds, returns_pts, pnl_pts),
    )
    _conn.commit()


def get_todays_selections() -> Optional[str]:
    """Get formatted selections for today."""
    today = date.today().isoformat()
    rows = _conn.execute(
        """SELECT s.* FROM selections s
           JOIN meetings m ON s.meeting_id = m.id
           WHERE m.date = ?
           ORDER BY s.race_time, s.selection_type""",
        (today,),
    ).fetchall()

    if not rows:
        return None

    return _format_selections(rows)


def get_todays_nap() -> Optional[str]:
    """Get today's NAP."""
    today = date.today().isoformat()
    row = _conn.execute(
        """SELECT s.* FROM selections s
           JOIN meetings m ON s.meeting_id = m.id
           WHERE m.date = ? AND s.selection_type = 'nap'""",
        (today,),
    ).fetchone()

    if not row:
        return None

    reasoning = json.loads(row["reasoning"]) if row["reasoning"] else []
    text = f"🏆 *NAP: {row['horse']}*\n"
    text += f"📍 {row['race_time']} - {row['race_name']}\n"
    text += f"💰 {row['odds_guide']}\n"
    text += f"📊 Confidence: {row['confidence']}\n"
    for r in reasoning:
        text += f"• {r}\n"
    text += f"⚠️ Danger: {row['danger']}"
    return text


def get_todays_next_best() -> Optional[str]:
    """Get today's Next Best."""
    today = date.today().isoformat()
    row = _conn.execute(
        """SELECT s.* FROM selections s
           JOIN meetings m ON s.meeting_id = m.id
           WHERE m.date = ? AND s.selection_type = 'next_best'""",
        (today,),
    ).fetchone()

    if not row:
        return None

    reasoning = json.loads(row["reasoning"]) if row["reasoning"] else []
    text = f"⭐ *NEXT BEST: {row['horse']}*\n"
    text += f"📍 {row['race_time']} - {row['race_name']}\n"
    text += f"💰 {row['odds_guide']}\n"
    for r in reasoning:
        text += f"• {r}\n"
    return text


def get_latest_results() -> Optional[str]:
    """Get latest results with P&L."""
    rows = _conn.execute(
        """SELECT s.horse, s.race_time, s.selection_type, s.odds_guide, s.stake_pts,
                  r.result, r.sp_odds, r.returns_pts, r.pnl_pts
           FROM results r
           JOIN selections s ON r.selection_id = s.id
           ORDER BY r.created_at DESC LIMIT 20""",
    ).fetchall()

    if not rows:
        return None

    text = "📊 *Latest Results*\n\n"
    total_pnl = 0
    for row in rows:
        emoji = "✅" if row["result"] == "won" else "🔸" if row["result"] == "placed" else "❌"
        text += (
            f"{emoji} {row['horse']} ({row['race_time']}) - "
            f"{row['result'].upper()} | "
            f"P&L: {row['pnl_pts']:+.1f}pts\n"
        )
        total_pnl += row["pnl_pts"]

    text += f"\n*Running P&L: {total_pnl:+.1f}pts*"
    return text


def get_stats() -> str:
    """Get overall stats."""
    row = _conn.execute(
        """SELECT
              COUNT(*) as total_sels,
              SUM(CASE WHEN r.result = 'won' THEN 1 ELSE 0 END) as winners,
              SUM(CASE WHEN r.result = 'placed' THEN 1 ELSE 0 END) as placed,
              SUM(r.pnl_pts) as total_pnl,
              SUM(s.stake_pts) as total_staked
           FROM results r
           JOIN selections s ON r.selection_id = s.id""",
    ).fetchone()

    total = row["total_sels"] or 0
    winners = row["winners"] or 0
    placed = row["placed"] or 0
    pnl = row["total_pnl"] or 0
    staked = row["total_staked"] or 0

    sr = (winners / total * 100) if total > 0 else 0
    roi = (pnl / staked * 100) if staked > 0 else 0

    # NAP record
    nap_row = _conn.execute(
        """SELECT
              COUNT(*) as total,
              SUM(CASE WHEN r.result = 'won' THEN 1 ELSE 0 END) as winners
           FROM results r
           JOIN selections s ON r.selection_id = s.id
           WHERE s.selection_type = 'nap'""",
    ).fetchone()

    nap_total = nap_row["total"] or 0
    nap_wins = nap_row["winners"] or 0
    nap_sr = (nap_wins / nap_total * 100) if nap_total > 0 else 0

    text = "📊 *Overall Stats*\n\n"
    text += f"Total selections: {total}\n"
    text += f"Winners: {winners} ({sr:.0f}% SR)\n"
    text += f"Placed: {placed}\n"
    text += f"Total P&L: {pnl:+.1f}pts\n"
    text += f"ROI: {roi:+.1f}%\n"
    text += f"\n🏆 NAP Record: {nap_wins}/{nap_total} ({nap_sr:.0f}%)\n"
    return text


def get_bot_status() -> str:
    """Get bot operational status."""
    paused = _get_state("paused") == "true"
    last_analysis = _get_state("last_analysis_time") or "Never"
    last_results = _get_state("last_results_time") or "Never"

    status = "PAUSED ⏸" if paused else "RUNNING ▶️"
    text = f"Status: {status}\n"
    text += f"Last analysis: {last_analysis}\n"
    text += f"Last results check: {last_results}\n"
    return text


def set_bot_paused(paused: bool):
    """Set bot paused state."""
    _set_state("paused", "true" if paused else "false")


def is_bot_paused() -> bool:
    """Check if bot is paused."""
    return _get_state("paused") == "true"


def _get_state(key: str) -> Optional[str]:
    """Get a bot state value."""
    row = _conn.execute("SELECT value FROM bot_state WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def _set_state(key: str, value: str):
    """Set a bot state value."""
    _conn.execute(
        "INSERT OR REPLACE INTO bot_state (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
        (key, value),
    )
    _conn.commit()


def _format_selections(rows) -> str:
    """Format selection rows into readable text."""
    text = "📋 *Today's Selections*\n\n"
    current_time = ""
    for row in rows:
        if row["race_time"] != current_time:
            current_time = row["race_time"]
            text += f"\n*{current_time}* {row['race_name'] or ''}\n"

        type_emoji = {
            "nap": "🏆 NAP",
            "next_best": "⭐ NB",
            "selection": "📌 SEL",
            "race_nb": "📎 RNB",
        }
        label = type_emoji.get(row["selection_type"], row["selection_type"])
        ew = " (E/W)" if row["each_way"] else ""
        text += f"  {label}: {row['horse']} {row['odds_guide']}{ew}\n"

    return text
