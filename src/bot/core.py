# src/bot/core.py

import discord
from discord.ext import tasks
from ..config import CONFIG
from .monitor import ServerMonitor
from .commands import setup_commands

class ServerMonitorBot(discord.Client):
    def __init__(self, *args, **kwargs):
        intents = discord.Intents.default()
        intents.messages = True
        super().__init__(intents=intents, *args, **kwargs)
        self.tree = discord.app_commands.CommandTree(self)
        self.monitor = ServerMonitor()

    async def on_ready(self):
        print(f"Logged in as {self.user}")
        await self.tree.sync()
        self.update_status.start()

    @tasks.loop(seconds=CONFIG.REFRESH_INTERVAL)
    async def update_status(self):
        channel = self.get_channel(CONFIG.CHANNEL_ID)
        if channel:
            status_embed = self.monitor.format_server_status()
            leaderboard_embed = self.monitor.format_leaderboard()
            
            if not hasattr(self, 'status_message'):
                self.status_message = await channel.send(embed=status_embed)
            else:
                await self.status_message.edit(embed=status_embed)
            
            if not hasattr(self, 'leaderboard_message'):
                self.leaderboard_message = await channel.send(embed=leaderboard_embed)
            else:
                await self.leaderboard_message.edit(embed=leaderboard_embed)

def main():
    bot = ServerMonitorBot()
    setup_commands(bot, bot.monitor)
    bot.run(CONFIG.API_KEY)