# src/bot/monitor.py

import asyncio
import a2s
import datetime
from discord import Embed
from tabulate import tabulate
from ..config import CONFIG
from .utils import PlayerStats

class ServerMonitor:
    def __init__(self):
        self.server_data = {}
        self.player_stats, self.monthly_leaderboard = {}, {}
        self.keycap_emojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']

    async def query_server(self, address):
        for attempt in range(CONFIG.MAX_RETRIES):
            try:
                info = await asyncio.wait_for(a2s.ainfo(address), timeout=CONFIG.QUERY_TIMEOUT)
                players = await asyncio.wait_for(a2s.aplayers(address), timeout=CONFIG.QUERY_TIMEOUT)
                return info, players, round(info.ping * 1000)
            except Exception as e:
                logging.warning(f"Attempt {attempt + 1} failed for {address}: {str(e)}")
                await asyncio.sleep(1)
        return None, [], None

    def format_server_status(self):
        embed = Embed(title=CONFIG.CUSTOM_TITLE, color=CONFIG.STATUS_COLOR)
        embed.add_field(name="Custom Text", value=CONFIG.CUSTOM_TEXT, inline=False)
        for idx, (address, (info, players, ping)) in enumerate(self.server_data.items()):
            if info:
                player_table = tabulate(
                    [[p.name, p.score] for p in players if p.name],
                    headers=["Player", "Kills"],
                    tablefmt="presto"
                )
                embed.add_field(
                    name=f"{self.keycap_emojis[idx]} {info.server_name} ({info.player_count}/{info.max_players}) | Ping: {ping}ms",
                    value=f"**Map:** {info.map_name}\n{player_table}",
                    inline=False
                )
        return embed

    def format_leaderboard(self):
        leaderboard = sorted(
            self.player_stats.items(),
            key=lambda x: (x[1].kills, x[1].time_played),
            reverse=True
        )[:CONFIG.LEADERBOARD_SIZE]
        embed = Embed(title=CONFIG.LEADERBOARD_TITLE, color=CONFIG.LEADERBOARD_COLOR)
        for rank, (name, stats) in enumerate(leaderboard, 1):
            embed.add_field(
                name=f"{self.get_rank_emoji(rank)} {name}",
                value=f"**Kills:** {stats.kills} | **Time Played:** {stats.time_played} mins",
                inline=False
            )
        return embed

    def get_rank_emoji(self, rank):
        emojis = {1: '🥇', 2: '🥈', 3: '🥉'}
        return emojis.get(rank, '🔹')

    def check_monthly_reset(self):
        now = datetime.now()
        if now.day == CONFIG.MONTHLY_RESET_DAY:
            self.monthly_leaderboard.clear()