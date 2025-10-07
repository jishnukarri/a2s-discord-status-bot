"""Configuration and logging setup.

Loads environment variables, provides CONFIG dict, and exposes helper to refresh config if needed.
"""
from __future__ import annotations
import os
import json
import logging
from dotenv import load_dotenv

# Centralize external resource URLs so they are easy to change / test
GITHUB_BASE = "https://raw.githubusercontent.com/Benkol003/CAC-Config/refs/heads/master"
CONTENT_URL = f"{GITHUB_BASE}/content.json"
STEAM_URL = f"{GITHUB_BASE}/steam.json"
SERVERS_URL = f"{GITHUB_BASE}/servers.json"

# Logging (file + console). File name kept as original for continuity.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('bot_runtime.log'), logging.StreamHandler()]
)

load_dotenv()

def _get_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default

# Local IP override (used when preset DNS should map to LAN IP)
LOCAL_IP = os.getenv("LOCAL_IP")  # If provided, used in server matching logic

CONFIG = {
    'REFRESH_INTERVAL': _get_int('REFRESH_INTERVAL', 10),
    'API_KEY': os.getenv('API_KEY'),
    'CHANNEL_ID': _get_int('CHANNEL_ID', 0),
    'SERVERS': json.loads(os.getenv('SERVERS', '[]')),
    'QUERY_TIMEOUT': _get_int('QUERY_TIMEOUT', 5),
    'DATABASE_FILE': os.getenv('DATABASE_FILE', 'bot_data.db'),
    'MAX_RETRIES': _get_int('MAX_RETRIES', 3),
    'CUSTOM_TITLE': os.getenv('CUSTOM_TITLE', 'Server Status'),
    'CUSTOM_TEXT': os.getenv('CUSTOM_TEXT', '**DM an admin to join our servers!**'),
    'LEADERBOARD_TITLE': os.getenv('LEADERBOARD_TITLE', 'Player Leaderboard'),
    'LEADERBOARD_SIZE': _get_int('LEADERBOARD_SIZE', 10),
    'STATUS_COLOR': int(os.getenv('STATUS_COLOR', '0x1A529A'), 16),
    'LEADERBOARD_COLOR': int(os.getenv('LEADERBOARD_COLOR', '0xFFD700'), 16),
    'FOOTER_ICON': os.getenv('FOOTER_ICON', 'https://example.com/icon.jpg'),
    'KILL_UPDATE_INTERVAL': _get_int('KILL_UPDATE_INTERVAL', 60),
    'MISSION_SYNC_DELAY': _get_int('MISSION_SYNC_DELAY', 300),
    'MONTHLY_RESET_DAY': _get_int('MONTHLY_RESET_DAY', 3)
}

__all__ = [
    'CONFIG',
    'LOCAL_IP',
    'CONTENT_URL',
    'STEAM_URL',
    'SERVERS_URL'
]
