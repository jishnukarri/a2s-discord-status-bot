"""Discord command registration and handlers."""
from __future__ import annotations
import asyncio
import logging
import discord
from discord.ext import commands
from typing import List

from config import CONFIG
from mod_generator import ModListGenerator
from server_monitor import ServerMonitor
from database import DataManager
from models import format_time_readable

mod_generator = ModListGenerator()

def register_commands(bot: commands.Bot, monitor: ServerMonitor) -> None:
    @bot.tree.command(name="server", description="Get mod list and download links for configured servers")
    @discord.app_commands.describe(server="Choose which server to get mods for")
    async def server_command(interaction: discord.Interaction, server: str = None):
        await interaction.response.defer(ephemeral=True)
        await monitor.preset_manager.fetch_preset_servers()
        preset_servers = monitor.preset_manager.get_all_preset_servers()
        if not preset_servers:
            await interaction.followup.send("No servers configured in GitHub config.", ephemeral=True)
            return
        servers_list = list(preset_servers.items())
        if server is None:
            lines: List[str] = ["**Available Servers:**\n"]
            for idx, (name, info) in enumerate(servers_list, 1):
                mods = len(info.get('mods', []))
                lines.append(f"**{idx}.** {name} - Mods: {mods}")
            lines.append("\nUse `/server <number>` to get a specific mod list.")
            await interaction.followup.send("\n".join(lines), ephemeral=True)
            return
        try:
            index = int(server) - 1
            if index < 0 or index >= len(servers_list):
                await interaction.followup.send(f"Invalid server number. Use 1-{len(servers_list)}.", ephemeral=True)
                return
        except ValueError:
            await interaction.followup.send("Please provide a numeric server selection.", ephemeral=True)
            return
        name, preset = servers_list[index]
        try:
            text = await mod_generator.generate_preset_server_mod_list(name, preset)
            try:
                dm = await interaction.user.create_dm()
                MAX_MSG = 1900  # reserve some room for header
                lines = text.split('\n')
                chunks: List[str] = []
                current: List[str] = []
                current_len = 0
                for line in lines:
                    # +1 for newline when joined (except first)
                    add_len = len(line) + (1 if current else 0)
                    if current_len + add_len > MAX_MSG:
                        # flush current
                        if current:
                            chunks.append('\n'.join(current))
                        current = [line]
                        current_len = len(line)
                        # If a single line itself is huge, hard split (rare)
                        if current_len > MAX_MSG:
                            # hard break this long line into safe slices
                            long_line = current[0]
                            slice_size = MAX_MSG - 20
                            for i in range(0, len(long_line), slice_size):
                                segment = long_line[i:i+slice_size]
                                if i == 0:
                                    chunks.append(segment)
                                else:
                                    chunks.append(segment)
                            current = []
                            current_len = 0
                    else:
                        current.append(line)
                        current_len += add_len
                if current:
                    chunks.append('\n'.join(current))
                # Send chunks
                multi = len(chunks) > 1
                for idx, chunk in enumerate(chunks, 1):
                    header = f"**{name} - Mod List (Part {idx}/{len(chunks)})**\n\n" if multi else f"**{name} - Mod List**\n\n"
                    await dm.send(header + chunk)
                    await asyncio.sleep(0.15)
                await interaction.followup.send(f"Mod list for **{name}** sent to DM ({len(chunks)} message{'s' if len(chunks)>1 else ''}).", ephemeral=True)
            except discord.Forbidden:
                await interaction.followup.send("Enable DMs to receive the mod list.", ephemeral=True)
        except Exception as e:
            logging.error("Error generating mod list: %s", e)
            await interaction.followup.send(f"Error: {e}", ephemeral=True)

    @server_command.autocomplete('server')
    async def server_autocomplete(interaction: discord.Interaction, current: str):  # type: ignore
        await monitor.preset_manager.fetch_preset_servers()
        preset_servers = monitor.preset_manager.get_all_preset_servers()
        choices = []
        for i, (name, info) in enumerate(preset_servers.items()):
            if len(choices) >= 25:
                break
            choices.append(discord.app_commands.Choice(name=f"{i+1}. {name}", value=str(i+1)))
        return choices

    @bot.tree.command(name="cdlc", description="Get download links and info for Arma 3 Creator DLCs")
    @discord.app_commands.describe(dlc="Choose which CDLC to get info for (optional)")
    async def cdlc_command(interaction: discord.Interaction, dlc: str = None):
        await interaction.response.defer(ephemeral=True)
        await mod_generator.fetch_config_data()
        dlc_data = mod_generator.content_links.get('dlc', {})
        if not dlc_data:
            await interaction.followup.send("No CDLC data available.", ephemeral=True)
            return
        dlc_keys = list(dlc_data.keys())
        if dlc is None:
            lines = ["**Arma 3 Creator DLCs:**\n"]
            for i, k in enumerate(dlc_keys, 1):
                desc = dlc_data[k].get('description', k.upper())
                lines.append(f"**{i}.** {desc}")
            lines.append("\nUse `/cdlc <number>` for details.")
            await interaction.followup.send("\n".join(lines), ephemeral=True)
            return
        try:
            idx = int(dlc) - 1
            if idx < 0 or idx >= len(dlc_keys):
                await interaction.followup.send(f"Invalid DLC number. Use 1-{len(dlc_keys)}.", ephemeral=True)
                return
        except ValueError:
            await interaction.followup.send("Please provide a numeric DLC selection.", ephemeral=True)
            return
        key = dlc_keys[idx]
        info = dlc_data[key]
        desc = info.get('description', key.upper())
        password = info.get('pwd', 'N/A')
        
        # Handle both single link and array of links
        download_link = info.get('link', 'N/A')
        lines = [f"**Arma 3 Creator DLC: {desc}**\n"]
        
        if isinstance(download_link, list):
            # Multiple download links
            lines.append("**Download Links:**")
            for i, link in enumerate(download_link, 1):
                lines.append(f"  {i}. <{link}>")
            lines.append("")  # Empty line
        else:
            # Single download link
            lines.append(f"**Download:** <{download_link}>")
        
        if password != 'N/A':
            lines.append(f"**Password:** {password}\n")
        else:
            lines.append("")
        
        lines.extend([
            "**Installation:**",
            "1. Download the DLC file",
            "2. Go to Arma 3 installation folder",
            "3. Extract with 7zip (Extract here)",
            "4. Launch Arma 3",
            "",
            "**Notes:**",
            "• Ensure Arma 3 is closed during install",
            "• Some servers require specific DLCs",
        ])
        text = "\n".join(lines)
        try:
            dm = await interaction.user.create_dm()
            await dm.send(text)
            await interaction.followup.send(f"DLC info for **{desc}** sent to DM.", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send(text[:1900], ephemeral=True)

    @bot.command(name='reset_player')
    async def reset_player_stats(ctx, player_name: str, reset_type: str = "session"):
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("Admin permissions required.")
            return
        if player_name not in monitor.player_stats:
            await ctx.send(f"Player **{player_name}** not found.")
            return
        stats = monitor.player_stats[player_name]
        if reset_type.lower() == "session":
            stats.current_session_kills = 0
            stats.last_session_time = 0
            stats.last_kill_update = None
            await ctx.send(f"Session reset for **{player_name}**")
        elif reset_type.lower() == "total":
            stats.kills = stats.time_played = stats.current_session_kills = 0
            stats.last_session_time = 0
            stats.last_kill_update = None
            await ctx.send(f"Total stats reset for **{player_name}**")
        elif reset_type.lower() == "all":
            stats.kills = stats.time_played = stats.current_session_kills = 0
            stats.last_session_time = 0
            stats.last_kill_update = None
            monthly = monitor.monthly_leaderboard.get(player_name)
            if monthly:
                monthly.kills = monthly.time_played = 0
            await ctx.send(f"All stats reset for **{player_name}**")
        else:
            await ctx.send("Invalid reset type. Use: session | total | all")
            return
        DataManager.save_leaderboard(monitor.player_stats, monitor.monthly_leaderboard)

    @bot.command(name='leaderboard_info')
    async def leaderboard_info(ctx, player_name: str = None):
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("Admin permissions required.")
            return
        if player_name:
            stats = monitor.player_stats.get(player_name)
            if not stats:
                await ctx.send(f"Player **{player_name}** not found.")
                return
            embed = discord.Embed(title=f"Stats for {player_name}", color=0x00ff00)
            embed.add_field(name="Total Kills", value=stats.kills, inline=True)
            embed.add_field(name="Total Time", value=format_time_readable(stats.time_played), inline=True)
            embed.add_field(name="Current Session Kills", value=stats.current_session_kills, inline=True)
            embed.add_field(name="Last Session Time", value=format_time_readable(stats.last_session_time), inline=True)
            embed.add_field(name="Last Seen", value=stats.last_seen.strftime('%Y-%m-%d %H:%M:%S'), inline=True)
            if stats.last_kill_update:
                embed.add_field(name="Last Kill Update", value=stats.last_kill_update.strftime('%Y-%m-%d %H:%M:%S'), inline=True)
            await ctx.send(embed=embed)
        else:
            total_players = len(monitor.player_stats)
            total_kills = sum(s.kills for s in monitor.player_stats.values())
            total_time = sum(s.time_played for s in monitor.player_stats.values())
            embed = discord.Embed(title="Leaderboard Summary", color=0x00ff00)
            embed.add_field(name="Total Players", value=total_players, inline=True)
            embed.add_field(name="Total Kills", value=total_kills, inline=True)
            embed.add_field(name="Total Time", value=format_time_readable(total_time), inline=True)
            await ctx.send(embed=embed)

__all__ = ["register_commands", "mod_generator"]
