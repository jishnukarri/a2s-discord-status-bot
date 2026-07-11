"""Configuration loading.

Reads environment variables (via `.env` if present, otherwise whatever the
process/container already has set) into a single validated CONFIG dict.
"""
from __future__ import annotations
import json
import os
import sys
from dotenv import load_dotenv

GITHUB_BASE = "https://raw.githubusercontent.com/Benkol003/CAC-Config/refs/heads/master"
CONTENT_URL = f"{GITHUB_BASE}/content.json"
STEAM_URL = f"{GITHUB_BASE}/steam.json"
SERVERS_URL = f"{GITHUB_BASE}/servers.json"

load_dotenv()


def _get_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _get_color(name: str, default: str) -> int:
    return int(os.getenv(name, default), 16)


LOCAL_IP = os.getenv("LOCAL_IP")  # optional LAN override for DDNS-based presets

CONFIG = {
    'API_KEY': os.getenv('API_KEY'),
    'CHANNEL_ID': _get_int('CHANNEL_ID', 0),
    'SERVERS': json.loads(os.getenv('SERVERS', '[]')),
    'REFRESH_INTERVAL': _get_int('REFRESH_INTERVAL', 10),
    'QUERY_TIMEOUT': _get_int('QUERY_TIMEOUT', 5),
    'MAX_RETRIES': _get_int('MAX_RETRIES', 3),
    'DATABASE_FILE': os.getenv('DATABASE_FILE', 'database/bot_data.db'),
    'CUSTOM_TITLE': os.getenv('CUSTOM_TITLE', 'Server Status'),
    'CUSTOM_TEXT': os.getenv('CUSTOM_TEXT', '**DM an admin to join our servers!**'),
    'LEADERBOARD_TITLE': os.getenv('LEADERBOARD_TITLE', 'Player Leaderboard'),
    'LEADERBOARD_SIZE': _get_int('LEADERBOARD_SIZE', 10),
    'STATUS_COLOR': _get_color('STATUS_COLOR', '0x1A529A'),
    'LEADERBOARD_COLOR': _get_color('LEADERBOARD_COLOR', '0xFFD700'),
    'FOOTER_ICON': os.getenv('FOOTER_ICON', 'https://example.com/icon.jpg'),
    'KILL_UPDATE_INTERVAL': _get_int('KILL_UPDATE_INTERVAL', 60),
    'MISSION_SYNC_DELAY': _get_int('MISSION_SYNC_DELAY', 300),
    'MONTHLY_RESET_DAY': _get_int('MONTHLY_RESET_DAY', 3),
    # Observability - Sentry only, no local log files.
    'SENTRY_DSN': os.getenv('SENTRY_DSN'),
    'ENVIRONMENT': os.getenv('ENVIRONMENT', 'production'),
    'LOG_LEVEL': os.getenv('LOG_LEVEL', 'INFO'),
}

REQUIRED_KEYS = ('API_KEY', 'CHANNEL_ID')


def validate_config() -> None:
    missing = [key for key in REQUIRED_KEYS if not CONFIG[key]]
    if missing:
        sys.exit(f"Missing required configuration: {', '.join(missing)}. Check your environment/.env.")


__all__ = [
    'CONFIG',
    'LOCAL_IP',
    'CONTENT_URL',
    'STEAM_URL',
    'SERVERS_URL',
    'validate_config',
]
