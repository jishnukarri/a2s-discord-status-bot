"""Minimal bot entrypoint.

All functionality (queries, stats aggregation, commands, mod list generation)
resides in modular files. This script only initializes components and runs the
background update loop.
"""
from __future__ import annotations
import asyncio
import logging
import discord
from discord.ext import commands

from config import CONFIG
from database import init_db, DataManager
from server_monitor import ServerMonitor
from bot_commands import register_commands

init_db()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)
monitor = ServerMonitor()
register_commands(bot, monitor)

async def status_update_loop():
    while True:
        try:
            try:
                await monitor.update_all_servers()
            except Exception as e:
                logging.error('Error updating servers: %s', e)
            try:
                if monitor.leaderboard_message:
                    await monitor.leaderboard_message.edit(content='', embed=monitor.format_leaderboard())
            except Exception as e:
                logging.error('Error updating leaderboard message: %s', e)
            try:
                if monitor.status_message:
                    await monitor.status_message.edit(content='', embed=monitor.format_server_status())
            except Exception as e:
                logging.error('Error updating status message: %s', e)
        except Exception as e:
            logging.error('Unexpected loop error: %s', e)
        await asyncio.sleep(CONFIG['REFRESH_INTERVAL'])

@bot.event
async def on_ready():
    logging.info('Logged in as %s', bot.user)
    try:
        synced = await bot.tree.sync()
        logging.info('Synced %d command(s)', len(synced))
    except Exception as e:
        logging.error('Command sync failed: %s', e)
    channel = bot.get_channel(CONFIG['CHANNEL_ID'])
    if not channel:
        logging.error('Channel ID %s not found', CONFIG['CHANNEL_ID'])
        return
    async for message in channel.history(limit=100):
        if message.author == bot.user:
            await message.delete()
    monitor.leaderboard_message = await channel.send('Initializing leaderboard...')
    DataManager.save_message(monitor.leaderboard_message.id, CONFIG['CHANNEL_ID'], 'leaderboard')
    monitor.status_message = await channel.send('Initializing server status...')
    DataManager.save_message(monitor.status_message.id, CONFIG['CHANNEL_ID'], 'status')
    bot.loop.create_task(status_update_loop())

def main():
    bot.run(CONFIG['API_KEY'])

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logging.error('Critical error: %s', e)

mod_generator = ModListGenerator()

@bot.tree.command(name="server", description="Get mod list and download links for configured servers")
@discord.app_commands.describe(server="Choose which server to get mods for")
async def server_command(interaction: discord.Interaction, server: str = None):
    """Generate mod lists for servers from GitHub configuration."""
    await interaction.response.defer(ephemeral=True)
    
    # Ensure preset servers are loaded
    await monitor.preset_manager.fetch_preset_servers()
    
    # Get all servers from GitHub servers.json
    preset_servers = monitor.preset_manager.get_all_preset_servers()
    
    if not preset_servers:
        await interaction.followup.send("No servers configured in GitHub config.", ephemeral=True)
        return
    
    # Convert to list for easier indexing
    available_servers = list(preset_servers.items())
    
    # If no server specified, show options
    if server is None:
        options_text = "**Available Servers:**\n\n"
        for i, (server_name, preset_info) in enumerate(available_servers, 1):
            address = preset_info.get('address', 'TBA')
            port = preset_info.get('port', '?')
            
            # Check if server is currently online by matching with monitored servers
            is_online = False
            if address != 'TBA':
                # Check primary address
                for monitored_address, server_data in monitor.server_data.items():
                    if not server_data or len(server_data) < 3:
                        continue
                    server_ip, server_port = monitored_address
                    
                    # Match IP and check if port matches (query port = preset port + 1)
                    if server_ip == address and server_port == port + 1:
                        is_online = True
                        break
                
                # Special case: also check 192.168.0.22 for theghost.ddns.net
                if not is_online and address == "theghost.ddns.net":
                    for monitored_address, server_data in monitor.server_data.items():
                        if not server_data or len(server_data) < 3:
                            continue
                        server_ip, server_port = monitored_address
                        
                        # Check fallback IP with same port logic
                        if server_ip == "192.168.0.22" and server_port == port + 1:
                            is_online = True
                            break
            
            status = "🟢 ONLINE" if is_online else "🔴 OFFLINE"
            password_text = " [Password Protected]" if preset_info.get('password') else ""
            mod_count = len(preset_info.get('mods', []))
            
            options_text += f"**{i}.** {server_name}{password_text}\n"
            options_text += f"   Status: {status}\n"
            options_text += f"   Mods: {mod_count} required\n\n"
        
        options_text += "Please use `/server <number>` to get mod list for a specific server.\n"
        options_text += "Example: `/server 1` for the first server."
        
        await interaction.followup.send(options_text, ephemeral=True)
        return
    
    # Parse server selection
    try:
        server_index = int(server) - 1
        if server_index < 0 or server_index >= len(available_servers):
            await interaction.followup.send(f"Invalid server number. Please use 1-{len(available_servers)}.", ephemeral=True)
            return
        
        selected_name, preset_info = available_servers[server_index]
        
    except ValueError:
        await interaction.followup.send("Please provide a valid server number.", ephemeral=True)
        return
    
    try:
        # Generate mod list from preset data
        mod_list = await mod_generator.generate_preset_server_mod_list(selected_name, preset_info)
        
        # Always send as DM
        try:
            dm_channel = await interaction.user.create_dm()
            
            # Split into chunks of 1900 characters to stay well under 2000 limit
            max_chunk_size = 1900
            chunks = []
            
            if len(mod_list) > max_chunk_size:
                # Split by lines first to avoid breaking formatting
                lines = mod_list.split('\n')
                current_chunk = ""
                
                for line in lines:
                    # Check if adding this line would exceed the limit
                    if len(current_chunk) + len(line + "\n") > max_chunk_size:
                        if current_chunk:
                            chunks.append(current_chunk)
                            current_chunk = line
                        else:
                            # Line itself is too long, split it
                            chunks.append(line[:max_chunk_size])
                            current_chunk = line[max_chunk_size:]
                    else:
                        if current_chunk:
                            current_chunk += "\n" + line
                        else:
                            current_chunk = line
                
                if current_chunk:
                    chunks.append(current_chunk)
            else:
                chunks = [mod_list]
            
            # Send each chunk
            for i, chunk in enumerate(chunks):
                if len(chunks) > 1:
                    header = f"**{selected_name} - Mod List (Part {i+1}/{len(chunks)})**\n\n"
                else:
                    header = f"**{selected_name} - Mod List**\n\n"
                
                # Make sure header + chunk doesn't exceed limit
                message_content = header + chunk
                if len(message_content) > 2000:
                    # If still too long, send without code blocks
                    await dm_channel.send(header + chunk[:2000-len(header)-10] + "...\n*(truncated)*")
                else:
                    await dm_channel.send(message_content)
                
                # Small delay between messages
                if i < len(chunks) - 1:
                    await asyncio.sleep(0.5)
            
            # Check if server is online for status message
            address = preset_info.get('address', 'TBA')
            port = preset_info.get('port', 0)
            is_online = False
            if address != 'TBA':
                # Check primary address
                for monitored_address, server_data in monitor.server_data.items():
                    if not server_data or len(server_data) < 3:
                        continue
                    server_ip, server_port = monitored_address
                    if server_ip == address and server_port == port + 1:
                        is_online = True
                        break
                
                # Special case: also check 192.168.0.22 for theghost.ddns.net
                if not is_online and address == "theghost.ddns.net":
                    for monitored_address, server_data in monitor.server_data.items():
                        if not server_data or len(server_data) < 3:
                            continue
                        server_ip, server_port = monitored_address
                        if server_ip == "192.168.0.22" and server_port == port + 1:
                            is_online = True
                            break
            
            status_text = "🟢 ONLINE" if is_online else "🔴 OFFLINE"
            await interaction.followup.send(f"Mod list for **{selected_name}** ({status_text}) sent to your DMs!", ephemeral=True)
            
        except discord.Forbidden:
            await interaction.followup.send("Cannot send DM. Please enable DMs from server members and try again.", ephemeral=True)
        except Exception as dm_error:
            logging.error(f"Error sending DM: {str(dm_error)}")
            await interaction.followup.send(f"Error sending DM: {str(dm_error)}", ephemeral=True)
            
    except Exception as e:
        logging.error(f"Error generating server mod list: {str(e)}")
        await interaction.followup.send(f"Error generating mod list: {str(e)}", ephemeral=True)

# Autocomplete for server selection
@server_command.autocomplete('server')
async def server_autocomplete(interaction: discord.Interaction, current: str) -> list[discord.app_commands.Choice[str]]:
    """Provide autocomplete options for server selection."""
    # Ensure preset servers are loaded
    await monitor.preset_manager.fetch_preset_servers()
    
    preset_servers = monitor.preset_manager.get_all_preset_servers()
    available_servers = list(preset_servers.items())
    
    choices = []
    for i, (server_name, preset_info) in enumerate(available_servers):
        if len(choices) >= 25:  # Discord limit
            break
            
        # Check if server is online
        address = preset_info.get('address', 'TBA')
        port = preset_info.get('port', 0)
        is_online = False
        
        if address != 'TBA':
            # Check primary address
            for monitored_address, server_data in monitor.server_data.items():
                if not server_data or len(server_data) < 3:
                    continue
                server_ip, server_port = monitored_address
                if server_ip == address and server_port == port + 1:
                    is_online = True
                    break
            
            # Special case: also check 192.168.0.22 for theghost.ddns.net
            if not is_online and address == "theghost.ddns.net":
                for monitored_address, server_data in monitor.server_data.items():
                    if not server_data or len(server_data) < 3:
                        continue
                    server_ip, server_port = monitored_address
                    if server_ip == "192.168.0.22" and server_port == port + 1:
                        is_online = True
                        break
        
        status = "🟢" if is_online else "🔴"
        password_text = " [PW]" if preset_info.get('password') else ""
        display_name = f"{status} {server_name}{password_text}"
        
        if len(display_name) > 80:  # Discord choice name limit
            display_name = display_name[:77] + "..."
        choices.append(discord.app_commands.Choice(name=f"{i+1}. {display_name}", value=str(i+1)))
    
    return choices

@bot.tree.command(name="cdlc", description="Get download links and info for Arma 3 Creator DLCs")
@discord.app_commands.describe(dlc="Choose which CDLC to get info for (optional)")
async def cdlc_command(interaction: discord.Interaction, dlc: str = None):
    """Show information about Arma 3 Creator DLCs with download links."""
    await interaction.response.defer(ephemeral=True)
    
    # Ensure mod config is loaded
    await mod_generator.fetch_config_data()
    
    dlc_data = mod_generator.content_links.get('dlc', {})
    
    if not dlc_data:
        await interaction.followup.send("No CDLC data available. Please try again later.", ephemeral=True)
        return
    
    # If no specific DLC requested, show all available
    if dlc is None:
        message_parts = []
        message_parts.append("**Arma 3 Creator DLCs Available:**\n")
        
        for dlc_key, dlc_info in dlc_data.items():
            description = dlc_info.get('description', dlc_key.upper())
            message_parts.append(f"• {description}")
        
        message_parts.append("\nUse `/cdlc <dlc_name>` to get download info for a specific CDLC.")
        message_parts.append("Example: `/cdlc Western Sahara` or use autocomplete to select.")
        
        await interaction.followup.send("\n".join(message_parts), ephemeral=True)
        return
    
    # Find DLC by description (case-insensitive)
    selected_key = None
    selected_dlc = None
    
    for dlc_key, dlc_info in dlc_data.items():
        description = dlc_info.get('description', dlc_key.upper())
        if description.lower() == dlc.lower() or dlc_key.lower() == dlc.lower():
            selected_key = dlc_key
            selected_dlc = dlc_info
            break
    
    if not selected_dlc:
        await interaction.followup.send(f"CDLC '{dlc}' not found. Use `/cdlc` without arguments to see available DLCs.", ephemeral=True)
        return
    
    # Generate DLC info message
    try:
        message_parts = []
        
        # Header
        description = selected_dlc.get('description', selected_key.upper())
        message_parts.append(f"**Arma 3 Creator DLC: {description}**\n")
        
        # Download info - handle both single link and array of links
        download_link = selected_dlc.get('link', 'N/A')
        password = selected_dlc.get('pwd', 'N/A')
        
        if isinstance(download_link, list):
            # Multiple download links
            message_parts.append("**Download Links:**")
            for idx, link in enumerate(download_link, 1):
                message_parts.append(f"  {idx}. <{link}>")
            message_parts.append("")  # Empty line after links
        else:
            # Single download link
            message_parts.append(f"**Download:** <{download_link}>")
        
        if password != 'N/A':
            message_parts.append(f"**Password:** {password}\n")
        else:
            message_parts.append("")
        
        # Installation instructions
        message_parts.append("**Installation:**")
        message_parts.append("1. Download the DLC file")
        message_parts.append("2. Navigate to your Arma 3 installation folder")
        message_parts.append("3. Select and extract the downloaded file using 7zip")
        message_parts.append("4. Use 'Extract here' option in 7zip")
        message_parts.append("5. Launch Arma 3 and the DLC should be available\n")
        
        # Additional notes
        message_parts.append("**Notes:**")
        message_parts.append("• Make sure Arma 3 is closed during installation")
        message_parts.append("• Creator DLCs add new maps, vehicles, and equipment")
        message_parts.append("• Some servers may require specific DLCs to join")
        message_parts.append("• Check server mod lists to see which DLCs are needed")
        
        full_message = "\n".join(message_parts)
        
        # Send as DM to avoid clutter
        try:
            dm_channel = await interaction.user.create_dm()
            
            # Split message if too long
            if len(full_message) > 1900:
                # Split into chunks
                chunks = []
                lines = full_message.split('\n')
                current_chunk = ""
                
                for line in lines:
                    if len(current_chunk) + len(line) + 1 > 1900:
                        if current_chunk:
                            chunks.append(current_chunk)
                            current_chunk = line
                        else:
                            chunks.append(line[:1900])
                            current_chunk = line[1900:]
                    else:
                        if current_chunk:
                            current_chunk += "\n" + line
                        else:
                            current_chunk = line
                
                if current_chunk:
                    chunks.append(current_chunk)
                
                # Send each chunk
                for i, chunk in enumerate(chunks):
                    if len(chunks) > 1:
                        header = f"📦 **{description} - Info (Part {i+1}/{len(chunks)})**\n\n"
                    else:
                        header = f"📦 **{description} - DLC Info**\n\n"
                    
                    await dm_channel.send(header + chunk)
                    
                    if i < len(chunks) - 1:
                        await asyncio.sleep(0.5)
            else:
                await dm_channel.send(f"📦 **{description} - DLC Info**\n\n{full_message}")
            
            await interaction.followup.send(f"📨 DLC info for **{description}** sent to your DMs!", ephemeral=True)
            
        except discord.Forbidden:
            # If DM fails, send in channel but truncate if needed
            if len(full_message) > 1900:
                truncated = full_message[:1850] + "...\n*(Message truncated - enable DMs for full info)*"
                await interaction.followup.send(f"📦 **{description} - DLC Info**\n\n{truncated}", ephemeral=True)
            else:
                await interaction.followup.send(f"**{description} - DLC Info**\n\n{full_message}", ephemeral=True)
        except Exception as dm_error:
            logging.error(f"Error sending DLC info DM: {str(dm_error)}")
            await interaction.followup.send(f"Error sending DM: {str(dm_error)}", ephemeral=True)
            
    except Exception as e:
        logging.error(f"Error generating DLC info: {str(e)}")
        await interaction.followup.send(f"Error generating DLC info: {str(e)}", ephemeral=True)

# Autocomplete for CDLC selection
@cdlc_command.autocomplete('dlc')
async def cdlc_autocomplete(interaction: discord.Interaction, current: str) -> list[discord.app_commands.Choice[str]]:
    """Provide autocomplete options for CDLC selection."""
    # Ensure mod config is loaded
    await mod_generator.fetch_config_data()
    
    dlc_data = mod_generator.content_links.get('dlc', {})
    
    choices = []
    for dlc_key, dlc_info in dlc_data.items():
        if len(choices) >= 25:  # Discord limit
            break
        description = dlc_info.get('description', dlc_key.upper())
        
        # Filter based on current input
        if current.lower() in description.lower():
            if len(description) > 100:  # Discord choice name limit
                display_name = description[:97] + "..."
            else:
                display_name = description
            
            # Use description as both name and value
            choices.append(discord.app_commands.Choice(name=display_name, value=description))
    
    return choices

@bot.command(name='reset_player')
async def reset_player_stats(ctx, player_name: str, reset_type: str = "session"):
    """Reset a specific player's stats (admin only).
    
    Usage: 
    !reset_player <name> session - Reset only session tracking
    !reset_player <name> total - Reset all accumulated stats
    !reset_player <name> all - Reset everything including monthly
    """
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("Admin permissions required.")
        return
    
    if player_name not in monitor.player_stats:
        await ctx.send(f"Player **{player_name}** not found in leaderboard.")
        return
    
    stats = monitor.player_stats[player_name]
    
    if reset_type.lower() == "session":
        # Reset only session tracking
        stats.current_session_kills = 0
        stats.last_session_time = 0
        stats.last_kill_update = None
        await ctx.send(f"Reset session tracking for **{player_name}**")
        logging.info(f"Manual session reset for {player_name} by {ctx.author}")
        
    elif reset_type.lower() == "total":
        # Reset accumulated stats but keep monthly
        old_kills = stats.kills
        old_time = stats.time_played
        stats.kills = 0
        stats.time_played = 0
        stats.current_session_kills = 0
        stats.last_session_time = 0
        stats.last_kill_update = None
        await ctx.send(f"Reset total stats for **{player_name}** (was {old_kills} kills, {format_time_readable(old_time)})")
        logging.info(f"Manual total reset for {player_name} by {ctx.author} - was {old_kills} kills, {format_time_readable(old_time)}")
        
    elif reset_type.lower() == "all":
        # Reset everything including monthly
        old_kills = stats.kills
        old_time = stats.time_played
        stats.kills = 0
        stats.time_played = 0
        stats.current_session_kills = 0
        stats.last_session_time = 0
        stats.last_kill_update = None
        
        # Also reset monthly if exists
        if player_name in monitor.monthly_leaderboard:
            monthly_stats = monitor.monthly_leaderboard[player_name]
            monthly_stats.kills = 0
            monthly_stats.time_played = 0
        
        await ctx.send(f"Reset ALL stats for **{player_name}** (was {old_kills} kills, {format_time_readable(old_time)})")
        logging.info(f"Manual complete reset for {player_name} by {ctx.author} - was {old_kills} kills, {format_time_readable(old_time)}")
        
    else:
        await ctx.send("Invalid reset type. Use: `session`, `total`, or `all`")
        return
    
    # Save changes to database
    DataManager.save_leaderboard(monitor.player_stats, monitor.monthly_leaderboard)

@bot.command(name='leaderboard_info')
async def leaderboard_info(ctx, player_name: str = None):
    """Show detailed leaderboard info for a player (admin only)."""
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("Admin permissions required.")
        return
    
    if player_name:
        if player_name in monitor.player_stats:
            stats = monitor.player_stats[player_name]
            embed = discord.Embed(title=f"Stats for {player_name}", color=0x00ff00)
            embed.add_field(name="Total Kills", value=stats.kills, inline=True)
            embed.add_field(name="Total Time", value=format_time_readable(stats.time_played), inline=True)
            embed.add_field(name="Current Session Kills", value=stats.current_session_kills, inline=True)
            embed.add_field(name="Last Session Time", value=format_time_readable(stats.last_session_time), inline=True)
            embed.add_field(name="Last Seen", value=stats.last_seen.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
            if stats.last_kill_update:
                embed.add_field(name="Last Kill Update", value=stats.last_kill_update.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"Player **{player_name}** not found.")
    else:
        total_players = len(monitor.player_stats)
        total_kills = sum(stats.kills for stats in monitor.player_stats.values())
        total_time = sum(stats.time_played for stats in monitor.player_stats.values())
        
        embed = discord.Embed(title="Leaderboard Summary", color=0x00ff00)
        embed.add_field(name="Total Players", value=total_players, inline=True)
        embed.add_field(name="Total Kills", value=total_kills, inline=True)
        embed.add_field(name="Total Time", value=format_time_readable(total_time), inline=True)
        await ctx.send(embed=embed)

@bot.event
async def on_ready():
    """Initialize bot by clearing old messages and starting update loop."""
    logging.info(f'Logged in as {bot.user}')
    
    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        logging.info(f"Synced {len(synced)} command(s)")
    except Exception as e:
        logging.error(f"Failed to sync commands: {e}")
    
    channel = bot.get_channel(CONFIG['CHANNEL_ID'])
    
    async for message in channel.history(limit=100):
        if message.author == bot.user:
            await message.delete()
            logging.info(f"Deleted old bot message: {message.id}")
    
    # IMPORTANT: Leaderboard message first, then server status
    monitor.leaderboard_message = await channel.send("Updating leaderboard...")
    DataManager.save_message(monitor.leaderboard_message.id, CONFIG['CHANNEL_ID'], 'leaderboard')
    
    monitor.status_message = await channel.send("Updating server status...")
    DataManager.save_message(monitor.status_message.id, CONFIG['CHANNEL_ID'], 'status')
    
    bot.loop.create_task(status_update_loop())

async def status_update_loop():
    """Continuously update server data and Discord messages."""
    while True:
        try:
            # Update server data
            try:
                await monitor.update_all_servers()
            except Exception as e:
                logging.error(f"Error updating server data: {str(e)}")
            
            # Update leaderboard message
            try:
                if monitor.leaderboard_message:
                    await monitor.leaderboard_message.edit(content="", embed=monitor.format_leaderboard())
            except Exception as e:
                logging.error(f"Error updating leaderboard message: {str(e)}")
            
            # Update status message
            try:
                if monitor.status_message:
                    await monitor.status_message.edit(content="", embed=monitor.format_server_status())
            except Exception as e:
                logging.error(f"Error updating status message: {str(e)}")
                
        except Exception as e:
            logging.error(f"Unexpected error in update loop: {str(e)}")
        
        await asyncio.sleep(CONFIG['REFRESH_INTERVAL'])

if __name__ == "__main__":
    try:
        bot.run(CONFIG['API_KEY'])
    except Exception as e:
        logging.error(f"Critical error: {str(e)}")
