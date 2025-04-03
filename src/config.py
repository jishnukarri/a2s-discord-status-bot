# src/config.py

import os
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    REFRESH_INTERVAL = int(os.getenv('REFRESH_INTERVAL', 10))
    API_KEY = os.getenv('API_KEY')
    CHANNEL_ID = int(os.getenv('CHANNEL_ID'))
    SERVERS = json.loads(os.getenv('SERVERS', '[]'))
    QUERY_TIMEOUT = int(os.getenv('QUERY_TIMEOUT', 5))
    DATABASE_FILE = os.getenv('DATABASE_FILE', 'data.json')
    MAX_RETRIES = int(os.getenv('MAX_RETRIES', 3))
    CUSTOM_TITLE = os.getenv('CUSTOM_TITLE', '🟢 Server Status')
    CUSTOM_TEXT = os.getenv('CUSTOM_TEXT', '**DM an admin to join our servers!**')
    LEADERBOARD_TITLE = os.getenv('LEADERBOARD_TITLE', '🏆 Player Leaderboard')
    LEADERBOARD_SIZE = int(os.getenv('LEADERBOARD_SIZE', 10))
    MONTHLY_RESET_DAY = int(os.getenv('MONTHLY_RESET_DAY', 1))
    STATUS_COLOR = int(os.getenv('STATUS_COLOR', '0x1A529A'), 16)
    LEADERBOARD_COLOR = int(os.getenv('LEADERBOARD_COLOR', '0xFFD700'), 16)
    FOOTER_ICON = os.getenv('FOOTER_ICON', 'https://example.com/icon.jpg')
    KILL_UPDATE_INTERVAL = int(os.getenv('KILL_UPDATE_INTERVAL', 300))

# Export configuration globally
CONFIG = Config()