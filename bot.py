import discord
import a2s
import datetime
import socket
import asyncio
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
JOIN_URL=https://discord.com/channels/603659242334847016/673625469975003138
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
JOIN_URL = os.getenv('JOIN_URL')
REFRESH_EMOJI = os.getenv('REFRESH_EMOJI')
SERVERS = json.loads(os.getenv('SERVERS', '[]'))

intents = discord.Intents.default()
client = discord.Client(intents=intents)
server_messages = {}

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

def generate_embed(server_ip, server_port):
    a2sIP = (server_ip, server_port)
    server_info, server_players = fetch_server_info(a2sIP)

    if server_info is None:
        return discord.Embed(title="Server down", color=0xFF0000, description="The server is currently down.", timestamp=datetime.datetime.now())

    ply_table = [[ply.name, ply.score, format_player_time(ply.duration)] for ply in server_players if ply.name]
    players_formatted = tabulate(ply_table, headers=["Player", "Score", "Time"], tablefmt="presto")
    
    description = (f"Player count: {server_info.player_count}/{server_info.max_players}\n"
                   f"Map: {server_info.map_name}\n"
                   f"```{players_formatted}```\n"
                   f"[Join server]({JOIN_URL})")
    return discord.Embed(title=server_info.server_name, color=0x00FF00, description=description, timestamp=datetime.datetime.now())

async def reset_message(server_index):
    message = server_messages.get(server_index)
    if message:
        await message.clear_reactions()
        server = SERVERS[server_index]
        await message.edit(embed=generate_embed(server["ip"], server["port"]))
        await message.add_reaction(REFRESH_EMOJI)

@client.event
async def on_raw_reaction_add(payload):
    if payload.event_type == "REACTION_ADD" and payload.channel_id == CHANNEL_ID and payload.member != client.user:
        for index, msg in server_messages.items():
            if payload.message_id == msg.id:
                await reset_message(index)
                break

@client.event
async def on_ready():
    channel = client.get_channel(CHANNEL_ID)

    # Delete previous messages from the bot at startup
    await channel.purge(limit=100, check=lambda m: m.author == client.user)

    for index, server in enumerate(SERVERS):
        embed = generate_embed(server["ip"], server["port"])
        status_message = await channel.send(embed=embed)
        await status_message.add_reaction(REFRESH_EMOJI)
        server_messages[index] = status_message

    logging.info(f'We have logged in as {client.user}')

    # Start periodic updates
    while True:
        await asyncio.sleep(REFRESH_INTERVAL)
        for index in range(len(SERVERS)):
            await reset_message(index)  # Edit the existing messages

client.run(API_KEY)
