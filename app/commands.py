"""Discord command registration: /server, /cdlc, and admin prefix commands."""
from __future__ import annotations
import asyncio
import logging
from typing import List

import discord
from discord.ext import commands

from .database import DataManager
from .mod_generator import ModListGenerator
from .models import format_time_readable
from .server_monitor import ServerMonitor

DISCORD_MESSAGE_LIMIT = 1900  # leaves headroom under Discord's 2000-char hard limit


def _chunk_message(text: str, limit: int = DISCORD_MESSAGE_LIMIT) -> List[str]:
    """Split text into <= `limit` char chunks without breaking lines where possible."""
    chunks: List[str] = []
    current: List[str] = []
    current_len = 0
    for line in text.split('\n'):
        add_len = len(line) + (1 if current else 0)
        if current_len + add_len > limit:
            if current:
                chunks.append('\n'.join(current))
            if len(line) > limit:
                for i in range(0, len(line), limit):
                    chunks.append(line[i:i + limit])
                current, current_len = [], 0
            else:
                current, current_len = [line], len(line)
        else:
            current.append(line)
            current_len += add_len
    if current:
        chunks.append('\n'.join(current))
    return chunks


def _refresh_in_background(coro, description: str) -> None:
    """Fire off a cache-refreshing coroutine without awaiting it.

    Autocomplete handlers get ~3s from Discord to respond - far less than a
    cold GitHub config fetch (up to 15s) can take. Awaiting the fetch inline
    means the interaction is already dead by the time we'd reply. The fetch
    functions already no-op internally if their cache is still fresh, so it's
    always cheap to kick this off; autocomplete responds immediately with
    whatever's cached (possibly empty on the very first call) instead.
    """
    async def runner():
        try:
            await coro
        except Exception:
            logging.exception("Background refresh failed: %s", description)

    asyncio.ensure_future(runner())


async def _safe_defer(interaction: discord.Interaction, *, ephemeral: bool = True) -> bool:
    """Defer the interaction, swallowing the case where it already expired.

    Discord discards interactions that aren't acknowledged within ~3s. If the
    bot was briefly stalled (e.g. a slow network call on the event loop) the
    token can already be dead by the time we get here - that's not a bug in
    the command itself, so log it quietly and let the caller bail out instead
    of raising an unhandled CommandInvokeError.
    """
    try:
        await interaction.response.defer(ephemeral=ephemeral)
        return True
    except (discord.NotFound, discord.HTTPException) as e:
        logging.warning("Interaction %s expired before it could be deferred: %s", interaction.id, e)
        return False


async def _send_as_dm(interaction: discord.Interaction, title: str, text: str) -> None:
    try:
        dm = await interaction.user.create_dm()
    except discord.Forbidden:
        await interaction.followup.send("Enable DMs to receive this from the bot.", ephemeral=True)
        return

    chunks = _chunk_message(text)
    multi = len(chunks) > 1
    for idx, chunk in enumerate(chunks, 1):
        header = f"**{title} (Part {idx}/{len(chunks)})**\n\n" if multi else f"**{title}**\n\n"
        await dm.send(header + chunk)
        await asyncio.sleep(0.15)

    await interaction.followup.send(
        f"**{title}** sent to your DMs ({len(chunks)} message{'s' if multi else ''}).",
        ephemeral=True,
    )


def register_commands(bot: commands.Bot, monitor: ServerMonitor, mod_generator: ModListGenerator) -> None:

    @bot.tree.command(name="server", description="Get mod list and download links for configured servers")
    @discord.app_commands.describe(server="Choose which server to get mods for")
    async def server_command(interaction: discord.Interaction, server: str = None):
        if not await _safe_defer(interaction):
            return
        await monitor.preset_manager.fetch_preset_servers()
        preset_servers = monitor.preset_manager.get_all_preset_servers()
        if not preset_servers:
            await interaction.followup.send("No servers configured in GitHub config.", ephemeral=True)
            return

        servers_list = list(preset_servers.items())
        if server is None:
            lines = ["**Available Servers:**\n"]
            for idx, (name, info) in enumerate(servers_list, 1):
                lines.append(f"**{idx}.** {name} - Mods: {len(info.get('mods', []))}")
            lines.append("\nUse `/server <number>` to get a specific mod list.")
            await interaction.followup.send("\n".join(lines), ephemeral=True)
            return

        try:
            index = int(server) - 1
            if not (0 <= index < len(servers_list)):
                await interaction.followup.send(f"Invalid server number. Use 1-{len(servers_list)}.", ephemeral=True)
                return
        except ValueError:
            await interaction.followup.send("Please provide a numeric server selection.", ephemeral=True)
            return

        name, preset = servers_list[index]
        try:
            text = await mod_generator.generate_preset_server_mod_list(name, preset)
            await _send_as_dm(interaction, f"{name} - Mod List", text)
        except Exception as e:
            logging.exception("Error generating mod list")
            await interaction.followup.send(f"Error: {e}", ephemeral=True)

    @server_command.autocomplete('server')
    async def server_autocomplete(interaction: discord.Interaction, current: str):  # noqa: ARG001
        _refresh_in_background(monitor.preset_manager.fetch_preset_servers(), "preset servers")
        preset_servers = monitor.preset_manager.get_all_preset_servers()
        return [
            discord.app_commands.Choice(name=f"{i}. {name}", value=str(i))
            for i, name in enumerate(preset_servers.keys(), 1)
        ][:25]

    @bot.tree.command(name="cdlc", description="Get download links and info for Arma 3 Creator DLCs")
    @discord.app_commands.describe(dlc="Choose which CDLC to get info for (optional)")
    async def cdlc_command(interaction: discord.Interaction, dlc: str = None):
        if not await _safe_defer(interaction):
            return
        await mod_generator.fetch_config_data()
        dlc_data = mod_generator.content_links.get('dlc', {})
        if not dlc_data:
            await interaction.followup.send("No CDLC data available.", ephemeral=True)
            return

        dlc_keys = list(dlc_data.keys())
        if dlc is None:
            lines = ["**Arma 3 Creator DLCs:**\n"]
            for i, key in enumerate(dlc_keys, 1):
                lines.append(f"**{i}.** {dlc_data[key].get('description', key.upper())}")
            lines.append("\nUse `/cdlc <number>` for details.")
            await interaction.followup.send("\n".join(lines), ephemeral=True)
            return

        try:
            idx = int(dlc) - 1
            if not (0 <= idx < len(dlc_keys)):
                await interaction.followup.send(f"Invalid DLC number. Use 1-{len(dlc_keys)}.", ephemeral=True)
                return
        except ValueError:
            await interaction.followup.send("Please provide a numeric DLC selection.", ephemeral=True)
            return

        key = dlc_keys[idx]
        info = dlc_data[key]
        desc = info.get('description', key.upper())
        text = _format_cdlc_info(desc, info)
        await _send_as_dm(interaction, desc, text)

    @cdlc_command.autocomplete('dlc')
    async def cdlc_autocomplete(interaction: discord.Interaction, current: str):
        _refresh_in_background(mod_generator.fetch_config_data(), "mod/DLC config")
        dlc_data = mod_generator.content_links.get('dlc', {})
        choices = []
        for i, (key, info) in enumerate(dlc_data.items(), 1):
            desc = info.get('description', key.upper())
            if current.lower() in desc.lower():
                choices.append(discord.app_commands.Choice(name=f"{i}. {desc}", value=str(i)))
            if len(choices) >= 25:
                break
        return choices

    @bot.command(name='reset_player')
    @commands.has_guild_permissions(administrator=True)
    async def reset_player_stats(ctx: commands.Context, player_name: str, reset_type: str = "session"):
        """!reset_player <name> [session|total|all] - admin only."""
        stats = monitor.player_stats.get(player_name)
        if not stats:
            await ctx.send(f"Player **{player_name}** not found.")
            return

        reset_type = reset_type.lower()
        if reset_type not in ("session", "total", "all"):
            await ctx.send("Invalid reset type. Use: session | total | all")
            return

        stats.current_session_kills = 0
        stats.last_session_time = 0
        stats.last_kill_update = None
        if reset_type in ("total", "all"):
            stats.kills = 0
            stats.time_played = 0
        if reset_type == "all":
            monthly = monitor.monthly_leaderboard.get(player_name)
            if monthly:
                monthly.kills = 0
                monthly.time_played = 0

        DataManager.save_leaderboard(monitor.player_stats, monitor.monthly_leaderboard)
        await ctx.send(f"{reset_type.capitalize()} stats reset for **{player_name}**")

    @bot.command(name='leaderboard_info')
    @commands.has_guild_permissions(administrator=True)
    async def leaderboard_info(ctx: commands.Context, player_name: str = None):
        """!leaderboard_info [name] - admin only."""
        if player_name:
            stats = monitor.player_stats.get(player_name)
            if not stats:
                await ctx.send(f"Player **{player_name}** not found.")
                return
            embed = discord.Embed(title=f"Stats for {player_name}", color=0x00FF00)
            embed.add_field(name="Total Kills", value=stats.kills, inline=True)
            embed.add_field(name="Total Time", value=format_time_readable(stats.time_played), inline=True)
            embed.add_field(name="Current Session Kills", value=stats.current_session_kills, inline=True)
            embed.add_field(name="Last Session Time", value=format_time_readable(stats.last_session_time), inline=True)
            embed.add_field(name="Last Seen", value=stats.last_seen.strftime('%Y-%m-%d %H:%M:%S'), inline=True)
            if stats.last_kill_update:
                embed.add_field(name="Last Kill Update", value=stats.last_kill_update.strftime('%Y-%m-%d %H:%M:%S'), inline=True)
        else:
            embed = discord.Embed(title="Leaderboard Summary", color=0x00FF00)
            embed.add_field(name="Total Players", value=len(monitor.player_stats), inline=True)
            embed.add_field(name="Total Kills", value=sum(s.kills for s in monitor.player_stats.values()), inline=True)
            embed.add_field(name="Total Time", value=format_time_readable(sum(s.time_played for s in monitor.player_stats.values())), inline=True)
        await ctx.send(embed=embed)

    @reset_player_stats.error
    @leaderboard_info.error
    async def admin_command_error(ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("Admin permissions required.")
        else:
            logging.exception("Admin command error", exc_info=error)
            await ctx.send(f"Error: {error}")


def _format_cdlc_info(desc: str, info: dict) -> str:
    lines = [f"**Arma 3 Creator DLC: {desc}**\n"]
    download_link = info.get('link', 'N/A')
    if isinstance(download_link, list):
        lines.append("**Download Links:**")
        lines.extend(f"{i}. {link}" for i, link in enumerate(download_link, 1))
        lines.append("")
    else:
        lines.append(f"**Download:** {download_link}")

    password = info.get('pwd', 'N/A')
    lines.append(f"**Password:** {password}\n" if password != 'N/A' else "")

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
    return "\n".join(lines)


__all__ = ["register_commands"]
