"""Server monitoring and player stats aggregation."""
from __future__ import annotations
import asyncio
import datetime
import logging
import re
from typing import Dict, List, Tuple

import a2s
import discord
from tabulate import tabulate

from .config import CONFIG
from .database import DataManager
from .models import PlayerStats, format_time_readable
from .preset_manager import PresetServerManager

try:
    import arma3query  # type: ignore
    ARMA3_QUERY_AVAILABLE = True
except Exception:
    ARMA3_QUERY_AVAILABLE = False

ARMA3_STATE_NAMES = {
    '0': 'NONE', '1': 'SELECTING MISSION', '2': 'EDITING MISSION', '3': 'ASSIGNING ROLES',
    '4': 'SENDING MISSION', '5': 'LOADING GAME', '6': 'BRIEFING', '7': 'PLAYING',
    '8': 'DEBRIEFING', '9': 'MISSION ABORTED',
}
ARMA3_RULES_REFRESH_SECONDS = 1200
ARMA3_RULES_TIMEOUT_SECONDS = 30  # generous: the underlying Steam Workshop lookups can be slow/rate-limited


async def _safe_arma3rules_async(address):
    """Always run in a worker thread, never on the event loop directly.

    arma3query's own "async" entrypoint isn't actually non-blocking - it does
    synchronous Steam Workshop HTTP lookups (which get rate-limited and can
    take seconds) straight on the calling coroutine. Calling that from the
    bot's event loop stalls *everything* - Discord interactions included -
    long enough to blow past Discord's 3s ack window. `asyncio.to_thread`
    keeps that blocking work off the event loop.
    """
    if not ARMA3_QUERY_AVAILABLE:
        raise ImportError("arma3query not available")
    return await asyncio.to_thread(arma3query.arma3rules, address)


class ServerMonitor:
    def __init__(self) -> None:
        self.status_message: discord.Message | None = None
        self.leaderboard_message: discord.Message | None = None
        self.server_data: Dict[Tuple[str, int], Tuple] = {}
        self.arma_server_data: Dict[Tuple[str, int], object] = {}
        self.last_arma_update: Dict[Tuple[str, int], datetime.datetime] = {}
        self.player_stats, self.monthly_leaderboard = DataManager.load_leaderboard()
        self.preset_manager = PresetServerManager()

    # ---------- Querying ----------
    async def query_server(self, address: Tuple[str, int]):
        for attempt in range(CONFIG['MAX_RETRIES']):
            try:
                info = await asyncio.wait_for(a2s.ainfo(address), timeout=CONFIG['QUERY_TIMEOUT'])
                players = await asyncio.wait_for(a2s.aplayers(address), timeout=CONFIG['QUERY_TIMEOUT'])
                return info, players, round(info.ping * 1000)
            except Exception as e:
                logging.warning("Attempt %d failed for %s: %s", attempt + 1, address, e)
                await asyncio.sleep(1)
        return None, [], None

    async def update_all_servers(self) -> None:
        await self.preset_manager.fetch_preset_servers()
        tasks = [self.update_single_server(s['ip'], s['port']) for s in CONFIG['SERVERS']]
        if tasks:
            await asyncio.gather(*tasks)
        self.check_monthly_reset()
        DataManager.save_leaderboard(self.player_stats, self.monthly_leaderboard)

    async def update_single_server(self, ip: str, port: int) -> None:
        address = (ip, port)
        try:
            info, players, ping = await self.query_server(address)
            if not info:
                self.server_data.pop(address, None)
                return
            players = players or []
            self.server_data[address] = (info, players, ping or 0)
            self.update_player_stats(players)
            if self._is_arma3_server(info):
                await self._update_arma3_server_data(address)
        except Exception:
            logging.exception("Error updating server %s:%s", ip, port)
            self.server_data.pop(address, None)

    @staticmethod
    def _is_arma3_server(info) -> bool:
        return (
            (hasattr(info, 'game') and 'arma' in info.game.lower())
            or (hasattr(info, 'folder') and 'arma' in info.folder.lower())
            or (hasattr(info, 'keywords') and info.keywords and any(
                k in info.keywords.lower() for k in ('arma', 'altis', 'malden', 'tanoa')
            ))
        )

    async def _update_arma3_server_data(self, address: Tuple[str, int]) -> None:
        now = datetime.datetime.now()
        last = self.last_arma_update.get(address, datetime.datetime.min)
        if (now - last).total_seconds() < ARMA3_RULES_REFRESH_SECONDS or not ARMA3_QUERY_AVAILABLE:
            return
        # Stamp the attempt time up front so a slow/flaky lookup can't cause
        # this to be retried again a few seconds later for the same server.
        self.last_arma_update[address] = now
        try:
            rules = await asyncio.wait_for(_safe_arma3rules_async(address), timeout=ARMA3_RULES_TIMEOUT_SECONDS)
            self.arma_server_data[address] = rules
            logging.info("Updated Arma 3 rules for %s: %d mods", address, len(rules.mods))
        except Exception as e:
            # Best-effort/unused-for-display data pulled from a third-party
            # library that scrapes Steam Workshop and is known to be flaky
            # (rate limits, occasional malformed responses) - log it quietly
            # rather than as an error so it doesn't page out via Sentry.
            logging.warning("Failed to query Arma 3 rules for %s: %s", address, e)

    # ---------- Player stats ----------
    def update_player_stats(self, players) -> None:
        """Delta-track kills/playtime against each player's last known in-session
        counters. Server-reported counters reset unpredictably on mission change,
        so `server_reset`/`rejoined` guard against double-counting across those
        resets, and MISSION_SYNC_DELAY bridges a short window where a kill lands
        just before the server's duration counter catches up.
        """
        if not players or not hasattr(players, '__iter__'):
            return
        now = datetime.datetime.now()
        for player in players:
            name = getattr(player, 'name', None)
            if not name:
                continue
            try:
                self._apply_player_update(name, player, now)
            except Exception:
                logging.exception("Player stat update error for %s", name)

    def _apply_player_update(self, name: str, player, now: datetime.datetime) -> None:
        current_kills = getattr(player, 'score', 0) or 0
        current_time_seconds = int(getattr(player, 'duration', 0) or 0)
        stats = self.player_stats.get(name, PlayerStats())
        monthly = self.monthly_leaderboard.get(name, PlayerStats())

        server_reset = current_time_seconds == 0 and stats.last_session_time > 0
        rejoined = current_time_seconds < stats.last_session_time and (stats.last_session_time - current_time_seconds) > 2

        if server_reset or rejoined:
            stats.current_session_kills = 0
            stats.last_session_time = 0
            stats.last_kill_update = None

        should_update = (
            not stats.last_kill_update
            or (now - stats.last_kill_update).total_seconds() >= CONFIG['KILL_UPDATE_INTERVAL']
            or server_reset or rejoined
        )
        if should_update:
            if server_reset or rejoined:
                kills_delta = time_delta = 0
            else:
                kills_delta = max(0, current_kills - stats.current_session_kills)
                time_delta = max(0, current_time_seconds - stats.last_session_time)
                if kills_delta > 0 and current_time_seconds == 0:
                    kills_delta = 0  # wait for the duration counter to sync
                elif kills_delta > 0 and current_kills == stats.current_session_kills:
                    kills_delta = 0

            if (time_delta > 0 or kills_delta > 0) and not (server_reset or rejoined):
                if time_delta > 300 and current_time_seconds < 60:
                    time_delta = 0
                if kills_delta > 0 and time_delta == 0:
                    window = (now - stats.last_kill_update).total_seconds() if stats.last_kill_update else 0
                    if window <= CONFIG['MISSION_SYNC_DELAY']:
                        stats.kills += kills_delta
                        monthly.kills += kills_delta
                        logging.debug("Mission sync kill delta for %s: +%d", name, kills_delta)
                else:
                    stats.kills += kills_delta
                    stats.time_played += time_delta
                    monthly.kills += kills_delta
                    monthly.time_played += time_delta

            stats.current_session_kills = current_kills
            stats.last_session_time = current_time_seconds
            stats.last_kill_update = now

        stats.last_seen = now
        self.player_stats[name] = stats
        self.monthly_leaderboard[name] = monthly

    def check_monthly_reset(self) -> None:
        now = datetime.datetime.now()
        cutoff = datetime.datetime(now.year, now.month, CONFIG['MONTHLY_RESET_DAY'])
        for collection in (self.monthly_leaderboard, self.player_stats):
            stale = [name for name, stats in collection.items() if stats.last_seen < cutoff]
            for name in stale:
                del collection[name]
            if stale:
                logging.info("Pruned %d stale leaderboard entries prior to %s", len(stale), cutoff.date())

    # ---------- Embeds ----------
    def format_leaderboard(self) -> discord.Embed:
        leaderboard = sorted(
            self.player_stats.items(), key=lambda x: (x[1].kills, x[1].time_played), reverse=True
        )[:CONFIG['LEADERBOARD_SIZE']]
        embed = discord.Embed(title=CONFIG['LEADERBOARD_TITLE'], color=CONFIG['LEADERBOARD_COLOR'])
        for rank, (name, stats) in enumerate(leaderboard, 1):
            embed.add_field(
                name=f"{rank}. {name}",
                value=f"**Kills:** {stats.kills} | **Time Played:** {format_time_readable(stats.time_played)}",
                inline=False,
            )
        embed.set_footer(text='​', icon_url=CONFIG['FOOTER_ICON'])
        embed.timestamp = datetime.datetime.now()
        return embed

    def format_server_status(self) -> discord.Embed:
        embed = discord.Embed(title="CAC Server Status", color=CONFIG['STATUS_COLOR'])
        embed.add_field(name=CONFIG['CUSTOM_TITLE'], value=CONFIG['CUSTOM_TEXT'], inline=False)

        servers_to_display: List[Tuple] = []
        for server_cfg in CONFIG['SERVERS']:
            data = self.server_data.get((server_cfg['ip'], server_cfg['port']))
            if data and len(data) >= 3:
                servers_to_display.append(data)

        if not servers_to_display:
            embed.add_field(name="No Servers Online", value="All servers are currently offline or unreachable.", inline=False)
        else:
            for idx, (info, players, _ping) in enumerate(servers_to_display, 1):
                try:
                    embed.add_field(**self._format_server_field(idx, info, players))
                except Exception:
                    logging.exception("Error formatting server field")

        embed.add_field(
            name="Need Mods?",
            value="Use `/server` for mod links!\nUse `/cdlc` for Creator DLC downloads!",
            inline=False,
        )
        embed.set_footer(text='​', icon_url=CONFIG['FOOTER_ICON'])
        embed.timestamp = datetime.datetime.now()
        return embed

    @staticmethod
    def _format_server_field(index: int, info, players) -> dict:
        if players and hasattr(players, '__iter__'):
            rows = [[p.name, p.score] for p in players if getattr(p, 'name', None)]
            player_table = tabulate(rows, headers=["Player", "Kills"], tablefmt="plain") if rows else "No players online"
        else:
            player_table = "No players online"

        server_name = getattr(info, 'server_name', 'Unknown')
        player_count = getattr(info, 'player_count', 0)
        max_players = getattr(info, 'max_players', 0)
        map_name = getattr(info, 'map_name', 'Unknown')
        keywords = getattr(info, 'keywords', '') or ''
        state_match = re.search(r's(\d+)', keywords)
        state = ARMA3_STATE_NAMES.get(state_match.group(1), 'UNKNOWN') if state_match else 'UNKNOWN'

        return {
            'name': f"{index}. {server_name} ({player_count}/{max_players})",
            'value': f"**Map:** {map_name}\n**Status:** {state}\n```\n{player_table}\n```",
            'inline': False,
        }


__all__ = ["ServerMonitor"]
