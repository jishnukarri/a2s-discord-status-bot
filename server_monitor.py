"""Server monitoring and player stats aggregation."""
from __future__ import annotations
import asyncio
import datetime
import logging
import re
from typing import Dict, Tuple, List
import a2s
from tabulate import tabulate
import discord

from old.config import CONFIG
from old.models import PlayerStats, format_time_readable
from old.database import DataManager
from old.preset_manager import PresetServerManager

# Optional arma3query support
try:
    import arma3query  # type: ignore
    ARMA3_QUERY_AVAILABLE = True
except Exception:
    ARMA3_QUERY_AVAILABLE = False

async def safe_arma3rules_async(address):  # noqa: D401
    """Wrapper for arma3query.arma3rules_async with fallback to sync and logging."""
    if not ARMA3_QUERY_AVAILABLE:
        raise ImportError("arma3query not available")
    try:
        return await arma3query.arma3rules_async(address)
    except Exception:
        return await asyncio.to_thread(arma3query.arma3rules, address)

class ServerMonitor:
    def __init__(self) -> None:
        self.status_message = None
        self.leaderboard_message = None
        self.server_data: Dict[Tuple[str, int], Tuple] = {}
        self.arma_server_data = {}
        self.last_arma_update: Dict[Tuple[str, int], datetime.datetime] = {}
        self.player_stats, self.monthly_leaderboard = DataManager.load_leaderboard()
        self.last_reset = datetime.datetime.now()
        self.preset_manager = PresetServerManager()

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

    async def update_all_servers(self):
        await self.preset_manager.fetch_preset_servers()
        tasks = [self.update_single_server(s['ip'], s['port']) for s in CONFIG['SERVERS']]
        if tasks:
            await asyncio.gather(*tasks)
        self.check_monthly_reset()
        DataManager.save_leaderboard(self.player_stats, self.monthly_leaderboard)

    async def update_single_server(self, ip: str, port: int):
        address = (ip, port)
        try:
            info, players, ping = await self.query_server(address)
            if info:
                players = players or []
                ping = ping or 0
                self.server_data[address] = (info, players, ping)
                self.update_player_stats(players)
                if self.is_arma3_server(info):
                    await self.update_arma3_server_data(address)
            else:
                self.server_data.pop(address, None)
        except Exception as e:
            logging.error("Error updating server %s:%s: %s", ip, port, e)
            self.server_data.pop(address, None)

    def is_arma3_server(self, info) -> bool:  # info object from a2s
        return (
            (hasattr(info, 'game') and 'arma' in info.game.lower()) or
            (hasattr(info, 'folder') and 'arma' in info.folder.lower()) or
            (hasattr(info, 'keywords') and info.keywords and any(k in info.keywords.lower() for k in ['arma', 'altis', 'malden', 'tanoa']))
        )

    async def update_arma3_server_data(self, address):
        now = datetime.datetime.now()
        last = self.last_arma_update.get(address, datetime.datetime.min)
        if (now - last).total_seconds() < 1200:  # 20 minutes
            return
        if not ARMA3_QUERY_AVAILABLE:
            return
        try:
            rules = await asyncio.wait_for(safe_arma3rules_async(address), timeout=CONFIG['QUERY_TIMEOUT'])
            self.arma_server_data[address] = rules
            self.last_arma_update[address] = now
            logging.info("Updated Arma 3 rules for %s: %d mods", address, len(rules.mods))
        except Exception as e:
            logging.error("Failed to query Arma 3 rules for %s: %s", address, e)

    # --- Player stats ---
    def update_player_stats(self, players):
        if not players or not hasattr(players, '__iter__'):
            return
        now = datetime.datetime.now()
        for player in players:
            if not player or not getattr(player, 'name', None):
                continue
            try:
                current_kills = getattr(player, 'score', 0) or 0
                current_time_seconds = int(getattr(player, 'duration', 0) or 0)
                stats = self.player_stats.get(player.name, PlayerStats())
                monthly = self.monthly_leaderboard.get(player.name, PlayerStats())

                server_reset = current_time_seconds == 0 and stats.last_session_time > 0
                rejoined = current_time_seconds < stats.last_session_time and (stats.last_session_time - current_time_seconds) > 2

                if server_reset or rejoined:
                    stats.current_session_kills = 0
                    stats.last_session_time = 0
                    stats.last_kill_update = None

                should_update = (
                    not stats.last_kill_update or
                    (now - stats.last_kill_update).total_seconds() >= CONFIG['KILL_UPDATE_INTERVAL'] or
                    server_reset or rejoined
                )
                if should_update:
                    if server_reset or rejoined:
                        kills_delta = 0
                        time_delta = 0
                    else:
                        kills_delta = max(0, current_kills - stats.current_session_kills)
                        time_delta = max(0, current_time_seconds - stats.last_session_time)
                        if kills_delta > 0 and current_time_seconds == 0:
                            kills_delta = 0  # wait for sync
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
                                logging.debug("Mission sync kill delta for %s: +%d", player.name, kills_delta)
                            else:
                                kills_delta = 0
                        else:
                            stats.kills += kills_delta
                            stats.time_played += time_delta
                            monthly.kills += kills_delta
                            monthly.time_played += time_delta
                    stats.current_session_kills = current_kills
                    stats.last_session_time = current_time_seconds
                    stats.last_kill_update = now
                stats.last_seen = now
                self.player_stats[player.name] = stats
                self.monthly_leaderboard[player.name] = monthly
            except Exception as e:
                logging.error("Player stat update error for %s: %s", getattr(player, 'name', 'Unknown'), e)

    # --- Leaderboard maintenance ---
    def check_monthly_reset(self):
        now = datetime.datetime.now()
        cutoff = datetime.datetime(now.year, now.month, CONFIG['MONTHLY_RESET_DAY'])
        for coll in (self.monthly_leaderboard, self.player_stats):
            to_delete = [name for name, stats in coll.items() if stats.last_seen < cutoff]
            for name in to_delete:
                del coll[name]
            if to_delete:
                logging.info("Pruned %d stale leaderboard entries prior to %s", len(to_delete), cutoff.date())

    # --- Embeds ---
    def format_leaderboard(self) -> discord.Embed:
        leaderboard = sorted(self.player_stats.items(), key=lambda x: (x[1].kills, x[1].time_played), reverse=True)[:CONFIG['LEADERBOARD_SIZE']]
        embed = discord.Embed(title=CONFIG['LEADERBOARD_TITLE'], color=CONFIG['LEADERBOARD_COLOR'])
        for rank, (name, stats) in enumerate(leaderboard, 1):
            embed.add_field(name=f"{rank}. {name}", value=f"**Kills:** {stats.kills} | **Time Played:** {format_time_readable(stats.time_played)}", inline=False)
        embed.set_footer(text='\u200b', icon_url=CONFIG['FOOTER_ICON'])
        embed.timestamp = datetime.datetime.now()
        return embed

    def format_server_status(self) -> discord.Embed:
        embed = discord.Embed(title="CAC Server Status", color=CONFIG['STATUS_COLOR'])
        embed.add_field(name=CONFIG['CUSTOM_TITLE'], value=CONFIG['CUSTOM_TEXT'], inline=False)
        servers_to_display: List[Tuple] = []
        for sc in CONFIG['SERVERS']:
            addr = (sc['ip'], sc['port'])
            data = self.server_data.get(addr)
            if data and len(data) >= 3:
                servers_to_display.append(data)
        if servers_to_display:
            for idx, (info, players, ping) in enumerate(servers_to_display):
                try:
                    server_number = f"{idx+1}."
                    if players and hasattr(players, '__iter__'):
                        table_rows = [[p.name, p.score] for p in players if getattr(p, 'name', None)]
                        if table_rows:
                            # Use tabulate for consistent header & separator line
                            player_table = tabulate(table_rows, headers=["Player", "Kills"], tablefmt="plain")
                        else:
                            player_table = "No players online"
                    else:
                        player_table = "No players online"
                    server_name = getattr(info, 'server_name', 'Unknown')
                    player_count = getattr(info, 'player_count', 0)
                    max_players = getattr(info, 'max_players', 0)
                    map_name = getattr(info, 'map_name', 'Unknown')
                    keywords = getattr(info, 'keywords', '') or ''
                    state_match = re.search(r's(\d+)', keywords)
                    state_names = {'0': 'NONE','1': 'SELECTING MISSION','2': 'EDITING MISSION','3': 'ASSIGNING ROLES','4': 'SENDING MISSION','5': 'LOADING GAME','6': 'BRIEFING','7': 'PLAYING','8': 'DEBRIEFING','9': 'MISSION ABORTED'}
                    state = state_names.get(state_match.group(1), 'UNKNOWN') if state_match else 'UNKNOWN'
                    embed.add_field(
                        name=f"{server_number} {server_name} ({player_count}/{max_players})",
                        value=f"**Map:** {map_name}\n**Status:** {state}\n```\n{player_table}\n```",
                        inline=False
                    )
                except Exception as e:
                    logging.error("Error formatting server field: %s", e)
        else:
            embed.add_field(name="No Servers Online", value="All servers are currently offline or unreachable.", inline=False)
        embed.add_field(name="Need Mods?", value="Use `/server` for mod links!\nUse `/cdlc` for Creator DLC downloads!", inline=False)
        embed.set_footer(text='\u200b', icon_url=CONFIG['FOOTER_ICON'])
        embed.timestamp = datetime.datetime.now()
        return embed

__all__ = ["ServerMonitor"]
