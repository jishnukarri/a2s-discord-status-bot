# src/bot/commands.py

from discord import app_commands
from .monitor import ServerMonitor

async def setup_commands(bot, monitor):
    @bot.tree.command(name="status", description="Show server status")
    async def status(interaction):
        await interaction.response.send_message(embed=monitor.format_server_status(), ephemeral=True)

    @bot.tree.command(name="leaderboard", description="Show player leaderboard")
    async def leaderboard(interaction):
        await interaction.response.send_message(embed=monitor.format_leaderboard(), ephemeral=True)