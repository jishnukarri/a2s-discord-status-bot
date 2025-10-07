"""Domain models and utility formatting helpers."""
from __future__ import annotations
import datetime
from dataclasses import dataclass, field

__all__ = ["PlayerStats", "format_time_readable"]

@dataclass
class PlayerStats:
    kills: int = 0
    time_played: int = 0  # seconds
    last_seen: datetime.datetime = field(default_factory=lambda: datetime.datetime.now())
    last_kill_update: datetime.datetime | None = None
    current_session_kills: int = 0
    last_session_time: int = 0  # seconds from server for current session


def format_time_readable(seconds: int) -> str:
    """Convert seconds to a human-readable short format.

    Examples:
        43 -> '43s'
        125 -> '2m 5s'
        3600 -> '1hr'
        3670 -> '1hr 1mins'
        90061 -> '1 days 1.0hrs'
    """
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        minutes = seconds // 60
        remaining_seconds = seconds % 60
        return f"{minutes}m {remaining_seconds}s" if remaining_seconds else f"{minutes}m"
    if seconds < 86400:
        hours = seconds // 3600
        remaining_minutes = (seconds % 3600) // 60
        return f"{hours}hr {remaining_minutes}mins" if remaining_minutes else f"{hours}hr"
    days = seconds // 86400
    remaining_hours = (seconds % 86400) / 3600
    return f"{days} days {remaining_hours:.1f}hrs" if remaining_hours >= 1 else f"{days} days"
