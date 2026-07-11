"""Database utilities: schema initialization and persistence layer.

Plain sqlite3, no ORM. The `messages` table lets the bot find its own
status/leaderboard embeds again after a restart; `leaderboard` and
`monthly_leaderboard` hold accumulated player stats.
"""
from __future__ import annotations
import datetime
import logging
import os
import sqlite3
from typing import Dict, Optional, Tuple

from .config import CONFIG
from .models import PlayerStats

CREATE_MESSAGES = """CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,
    message_id TEXT,
    channel_id TEXT,
    type TEXT
)"""

CREATE_LEADERBOARD = """CREATE TABLE IF NOT EXISTS leaderboard (
    player_name TEXT PRIMARY KEY,
    kills INTEGER,
    time_played INTEGER,
    last_seen TEXT,
    last_kill_update TEXT,
    current_session_kills INTEGER,
    last_session_time INTEGER
)"""

CREATE_MONTHLY = """CREATE TABLE IF NOT EXISTS monthly_leaderboard (
    player_name TEXT PRIMARY KEY,
    kills INTEGER,
    time_played INTEGER,
    month TEXT
)"""


def _connect() -> sqlite3.Connection:
    return sqlite3.connect(CONFIG['DATABASE_FILE'])


def init_db() -> None:
    db_dir = os.path.dirname(CONFIG['DATABASE_FILE'])
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    with _connect() as conn:
        conn.execute(CREATE_MESSAGES)
        conn.execute(CREATE_LEADERBOARD)
        conn.execute(CREATE_MONTHLY)
    logging.info("Database initialized / verified at %s", CONFIG['DATABASE_FILE'])


def _current_period(now: datetime.datetime) -> str:
    if now.day >= CONFIG['MONTHLY_RESET_DAY']:
        return f"{now.year}-{now.month:02d}"
    prev_month = now.replace(day=1) - datetime.timedelta(days=1)
    return f"{prev_month.year}-{prev_month.month:02d}"


class DataManager:
    @staticmethod
    def save_message(message_id: int, channel_id: int, message_type: str) -> None:
        with _connect() as conn:
            conn.execute(
                'INSERT OR REPLACE INTO messages (message_id, channel_id, type) VALUES (?, ?, ?)',
                (str(message_id), str(channel_id), message_type),
            )

    @staticmethod
    def get_message(message_type: str) -> Optional[Tuple[str, str]]:
        with _connect() as conn:
            cur = conn.execute('SELECT message_id, channel_id FROM messages WHERE type = ?', (message_type,))
            return cur.fetchone()

    @staticmethod
    def save_leaderboard(player_stats: Dict[str, PlayerStats], monthly_stats: Dict[str, PlayerStats]) -> None:
        with _connect() as conn:
            conn.executemany(
                '''INSERT OR REPLACE INTO leaderboard
                (player_name, kills, time_played, last_seen, last_kill_update, current_session_kills, last_session_time)
                VALUES (?, ?, ?, ?, ?, ?, ?)''',
                [
                    (
                        name,
                        stats.kills,
                        stats.time_played,
                        stats.last_seen.isoformat(),
                        stats.last_kill_update.isoformat() if stats.last_kill_update else None,
                        stats.current_session_kills,
                        stats.last_session_time,
                    )
                    for name, stats in player_stats.items()
                ],
            )

            current_period = _current_period(datetime.datetime.now())
            conn.executemany(
                '''INSERT OR REPLACE INTO monthly_leaderboard (player_name, kills, time_played, month)
                VALUES (?, ?, ?, ?)''',
                [(name, stats.kills, stats.time_played, current_period) for name, stats in monthly_stats.items()],
            )

    @staticmethod
    def load_leaderboard() -> Tuple[Dict[str, PlayerStats], Dict[str, PlayerStats]]:
        with _connect() as conn:
            now = datetime.datetime.now()
            month_reset_cutoff = datetime.datetime(now.year, now.month, CONFIG['MONTHLY_RESET_DAY'])

            cur = conn.execute(
                '''SELECT player_name, kills, time_played, last_seen, last_kill_update,
                current_session_kills, last_session_time FROM leaderboard WHERE last_seen >= ?''',
                (month_reset_cutoff.isoformat(),),
            )
            player_stats = {
                row[0]: PlayerStats(
                    kills=row[1],
                    time_played=row[2],
                    last_seen=datetime.datetime.fromisoformat(row[3]),
                    last_kill_update=datetime.datetime.fromisoformat(row[4]) if row[4] else None,
                    current_session_kills=row[5],
                    last_session_time=row[6],
                )
                for row in cur.fetchall()
            }

            current_period = _current_period(now)
            cur = conn.execute(
                'SELECT player_name, kills, time_played FROM monthly_leaderboard WHERE month = ?',
                (current_period,),
            )
            monthly_stats = {row[0]: PlayerStats(kills=row[1], time_played=row[2]) for row in cur.fetchall()}

            return player_stats, monthly_stats


__all__ = ['init_db', 'DataManager']
