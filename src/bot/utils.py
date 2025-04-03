# Helper functions
# src/bot/utils.py

from datetime import datetime

class PlayerStats:
    def __init__(self, kills=0, time_played=0, last_seen=None, last_kill_update=None, current_session_kills=0):
        self.kills = kills
        self.time_played = time_played
        self.last_seen = last_seen or datetime.now()
        self.last_kill_update = last_kill_update
        self.current_session_kills = current_session_kills

def sanitize_input(input_str):
    """Sanitize user input to prevent injection attacks."""
    return ''.join(c for c in input_str if c.isalnum() or c in (' ', '-', '_'))

def get_rank_emoji(rank):
    emojis = {1: '🥇', 2: '🥈', 3: '🥉'}
    return emojis.get(rank, '🔹')