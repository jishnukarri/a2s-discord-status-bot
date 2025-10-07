"""Database utilities: initialization and persistence layer.

Responsible for creating tables and migrating legacy structures.
"""
from __future__ import annotations
import sqlite3
import datetime
import logging
from typing import Dict, Tuple, Optional
from config import CONFIG
from models import PlayerStats

SCHEMA_VERSION = 1  # Future-proofing for migrations

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
    last_session_time INTEGER,
    migrated_to_seconds INTEGER DEFAULT 1
)"""

CREATE_MONTHLY = """CREATE TABLE IF NOT EXISTS monthly_leaderboard (
    player_name TEXT PRIMARY KEY,
    kills INTEGER,
    time_played INTEGER,
    month TEXT,
    migrated_to_seconds INTEGER DEFAULT 1
)"""

def init_db() -> None:
    conn = sqlite3.connect(CONFIG['DATABASE_FILE'])
    cur = conn.cursor()
    cur.execute(CREATE_MESSAGES)
    cur.execute(CREATE_LEADERBOARD)
    cur.execute(CREATE_MONTHLY)

    # Ensure columns exist (idempotent migrations)
    cur.execute("PRAGMA table_info(leaderboard)")
    cols = {row[1] for row in cur.fetchall()}
    if 'last_session_time' not in cols:
        cur.execute("ALTER TABLE leaderboard ADD COLUMN last_session_time INTEGER DEFAULT 0")
    if 'migrated_to_seconds' not in cols:
        cur.execute("ALTER TABLE leaderboard ADD COLUMN migrated_to_seconds INTEGER DEFAULT 1")

    cur.execute("PRAGMA table_info(monthly_leaderboard)")
    mcols = {row[1] for row in cur.fetchall()}
    if 'migrated_to_seconds' not in mcols:
        cur.execute("ALTER TABLE monthly_leaderboard ADD COLUMN migrated_to_seconds INTEGER DEFAULT 1")

    conn.commit()
    conn.close()
    logging.info("Database initialized / verified.")

class DataManager:
    @staticmethod
    def save_message(message_id: int, channel_id: int, message_type: str) -> None:
        with sqlite3.connect(CONFIG['DATABASE_FILE']) as conn:
            conn.execute(
                'INSERT OR REPLACE INTO messages (message_id, channel_id, type) VALUES (?, ?, ?)',
                (str(message_id), str(channel_id), message_type)
            )

    @staticmethod
    def get_message(message_type: str) -> Optional[Tuple[str, str]]:
        with sqlite3.connect(CONFIG['DATABASE_FILE']) as conn:
            cur = conn.cursor()
            cur.execute('SELECT message_id, channel_id FROM messages WHERE type = ?', (message_type,))
            return cur.fetchone()

    @staticmethod
    def save_leaderboard(player_stats: Dict[str, PlayerStats], monthly_stats: Dict[str, PlayerStats]) -> None:
        with sqlite3.connect(CONFIG['DATABASE_FILE']) as conn:
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
                        stats.last_session_time
                    )
                    for name, stats in player_stats.items()
                ]
            )

            now = datetime.datetime.now()
            if now.day >= CONFIG['MONTHLY_RESET_DAY']:
                current_period = f"{now.year}-{now.month:02d}"
            else:
                prev_month = now.replace(day=1) - datetime.timedelta(days=1)
                current_period = f"{prev_month.year}-{prev_month.month:02d}"

            conn.executemany(
                '''INSERT OR REPLACE INTO monthly_leaderboard (player_name, kills, time_played, month)
                VALUES (?, ?, ?, ?)''',
                [
                    (name, stats.kills, stats.time_played, current_period)
                    for name, stats in monthly_stats.items()
                ]
            )

    @staticmethod
    def load_leaderboard() -> Tuple[Dict[str, PlayerStats], Dict[str, PlayerStats]]:
        with sqlite3.connect(CONFIG['DATABASE_FILE']) as conn:
            cur = conn.cursor()
            now = datetime.datetime.now()
            current_month_reset_day = datetime.datetime(now.year, now.month, CONFIG['MONTHLY_RESET_DAY'])

            cur.execute('''SELECT player_name, kills, time_played, last_seen, last_kill_update, current_session_kills, last_session_time FROM leaderboard WHERE last_seen >= ?''', (current_month_reset_day.isoformat(),))
            player_stats = {}
            for row in cur.fetchall():
                player_stats[row[0]] = PlayerStats(
                    kills=row[1],
                    time_played=row[2],
                    last_seen=datetime.datetime.fromisoformat(row[3]),
                    last_kill_update=datetime.datetime.fromisoformat(row[4]) if row[4] else None,
                    current_session_kills=row[5],
                    last_session_time=row[6]
                )

            if now.day >= CONFIG['MONTHLY_RESET_DAY']:
                current_period = f"{now.year}-{now.month:02d}"
            else:
                prev_month = now.replace(day=1) - datetime.timedelta(days=1)
                current_period = f"{prev_month.year}-{prev_month.month:02d}"

            cur.execute('SELECT player_name, kills, time_played FROM monthly_leaderboard WHERE month = ?', (current_period,))
            monthly_stats = {}
            for row in cur.fetchall():
                monthly_stats[row[0]] = PlayerStats(kills=row[1], time_played=row[2])

            return player_stats, monthly_stats

__all__ = ['init_db', 'DataManager']
