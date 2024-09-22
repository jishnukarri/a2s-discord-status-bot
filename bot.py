import discord
import a2s
import datetime
import socket
import asyncio
from discord.ext import commands
from tabulate import tabulate
from dotenv import load_dotenv
import os
import json
import sys
import logging

# Set up logging
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

log_file = os.path.join(log_dir, f"{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.FileHandler(log_file), logging.StreamHandler(sys.stdout)])

# Default configuration
DEFAULT_CONFIG = """
REFRESH_INTERVAL=10
API_KEY=YOUR_API_KEY_HERE
CHANNEL_ID=123456789012345678
REFRESH_EMOJI=🔄
SERVERS=[{"ip": "0.0.0.0", "port": 0000}]
"""

def ensure_env_file_exists():
    if not os.path.exists('.env'):
        with open('.env', 'w', encoding='utf-8') as f:
            f.write(DEFAULT_CONFIG.strip())
        logging.info("Created default .env file. Please update it with your API_KEY and other settings.")
        sys.exit()

ensure_env_file_exists()
load_dotenv()

# Read configurations
REFRESH_INTERVAL = int(os.getenv('REFRESH_INTERVAL', 10))
API_KEY = os.getenv('API_KEY')
CHANNEL_ID = int(os.getenv('CHANNEL_ID'))
REFRESH_EMOJI = os.getenv('REFRESH_EMOJI')
SERVERS = json.loads(os.getenv('SERVERS', '[]'))

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Store the number of failed attempts for each server
server_failure_counts = {i: 0 for i in range(len(SERVERS))}
max_failures = 5

def format_player_time(seconds):
    if seconds < 60:
        return f"{int(seconds)} seconds"
    elif seconds < 3600:
        return f"{int(seconds // 60)} minutes"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"

def fetch_server_info(a2sIP):
    try:
        return a2s.info(a2sIP), a2s.players(a2sIP)
    except socket.timeout:
        logging.warning(f"Timeout fetching server info for {a2sIP}")
        return None, None
    except (ConnectionResetError, OSError, socket.gaierror) as e:
        logging.error(f"Error fetching server info for {a2sIP}: {e}")
        return None, []

def generate_embed():
    online_servers = []
    
    for index, server in enumerate(SERVERS):
        server_info, server_players = fetch_server_info((server['ip'], server['port']))

        if server_info is None:
            server_failure_counts[index] += 1
            continue  # Skip offline servers

        # Reset failure count if the server is online
        server_failure_counts[index] = 0

        player_count = f"{server_info.player_count}/{server_info.max_players}"
        ply_table = [[ply.name, ply.score, format_player_time(ply.duration)] for ply in server_players if ply.name]
        players_formatted = tabulate(ply_table, headers=["Player", "Score", "Time"], tablefmt="pipe")

        online_servers.append(f"**Server {len(online_servers) + 1}:** {server_info.server_name} - Players: {player_count} | Players List: ```{players_formatted}```")

    description = "\n".join(online_servers) if online_servers else "All servers are offline."
    return discord.Embed(title="Server Status", description=description, color=0x1A529A)

class ServerStatusView(discord.ui.View):
    def __init__(self, status_message):
        super().__init__(timeout=None)
        self.status_message = status_message

    async def refresh_server_info(self):
        embed = generate_embed()  # Generate a new embed for all servers
        await self.status_message.edit(embed=embed)  # Update the status message with the new embed

@bot.event
async def on_ready():
    channel = bot.get_channel(CHANNEL_ID)

    # Delete previous messages from the bot at startup
    await channel.purge(limit=100, check=lambda m: m.author == bot.user)

    embed = generate_embed()  # Generate initial embed for all servers
    status_message = await channel.send(embed=embed)  # Send the initial message
    view = ServerStatusView(status_message)  # Pass the message to the view

    logging.info(f'We have logged in as {bot.user}')

    # Start periodic updates
    while True:
        await asyncio.sleep(REFRESH_INTERVAL)
        embed = generate_embed()  # Refresh the embed for all servers
        await status_message.edit(embed=embed)  # Update the embed in the message

        # Get current online servers for emoji assignment
        online_servers = [
            i for i in range(len(SERVERS)) 
            if server_failure_counts[i] < max_failures and fetch_server_info((SERVERS[i]['ip'], SERVERS[i]['port']))[0] is not None
        ]
        
        await status_message.clear_reactions()  # Clear previous reactions
        for index in online_servers:
            await status_message.add_reaction(f'{online_servers.index(index) + 1}️⃣')  # Use the new index for emoji
        await status_message.add_reaction(REFRESH_EMOJI)  # Add refresh emoji

@bot.event
async def on_reaction_add(reaction, user):
    if user != bot.user:  # Ignore bot's own reactions
        if reaction.emoji == REFRESH_EMOJI:
            view = ServerStatusView(reaction.message)
            await view.refresh_server_info()  # Refresh server info on reaction
        else:
            # Handle server-specific refresh based on the number emoji
            index = int(reaction.emoji[0]) - 1  # Extract index from emoji
            if 0 <= index < len(SERVERS):
                server_info, server_players = fetch_server_info((SERVERS[index]['ip'], SERVERS[index]['port']))
                if server_info:
                    embed = generate_embed()  # Refresh embed with server info
                    await reaction.message.edit(embed=embed)

bot.run(API_KEY)
