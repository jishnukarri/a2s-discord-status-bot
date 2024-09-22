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
intents.message_content = True  # Ensure message content intent is enabled
bot = commands.Bot(command_prefix='!', intents=intents)

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
    description = []
    for index, server in enumerate(SERVERS):
        server_info, server_players = fetch_server_info((server['ip'], server['port']))

        if server_info is None:
            continue  # Skip offline servers

        player_count = f"{server_info.player_count}/{server_info.max_players}"
        ply_table = [[ply.name, ply.score, format_player_time(ply.duration)] for ply in server_players if ply.name]
        players_formatted = tabulate(ply_table, headers=["Player", "Score", "Time"], tablefmt="pipe")
        
        description.append(f"**Server {index + 1}:** {server_info.server_name} - Players: {player_count} | Players List: ```{players_formatted}```")

    return discord.Embed(title="Server Status", description="\n".join(description) if description else "All servers are offline.", color=0x1A529A)

class ServerStatusView(discord.ui.View):
    def __init__(self, status_message):
        super().__init__(timeout=None)
        self.status_message = status_message  # Store the status message

        # Create a button for each server to refresh
        for index in range(len(SERVERS)):
            self.add_item(discord.ui.Button(label=f"{REFRESH_EMOJI} Refresh Server {index + 1}", 
                                            style=discord.ButtonStyle.secondary, 
                                            custom_id=f"refresh_{index}"))

    async def interaction_check(self, interaction: discord.Interaction):
        button_index = int(interaction.data['custom_id'].split('_')[1])
        embed = generate_embed()  # Generate a new embed for all servers
        await self.status_message.edit(embed=embed)  # Update the status message with the new embed
        await interaction.response.defer()  # Acknowledge the interaction
        return True

@bot.event
async def on_ready():
    channel = bot.get_channel(CHANNEL_ID)

    # Delete previous messages from the bot at startup
    await channel.purge(limit=100, check=lambda m: m.author == bot.user)

    embed = generate_embed()  # Generate initial embed for all servers
    status_message = await channel.send(embed=embed)  # Send the initial message
    view = ServerStatusView(status_message)  # Pass the message to the view
    await status_message.edit(view=view)  # Attach the view to the message

    logging.info(f'We have logged in as {bot.user}')

    # Start periodic updates
    while True:
        await asyncio.sleep(REFRESH_INTERVAL)
        embed = generate_embed()  # Refresh the embed for all servers
        await status_message.edit(embed=embed)  # Update the embed in the message

bot.run(API_KEY)
