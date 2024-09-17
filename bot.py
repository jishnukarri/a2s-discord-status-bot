import discord
import a2s
import datetime
import socket
import asyncio
from tabulate import tabulate
from time import time
from dotenv import load_dotenv
import os
import json

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
        with open('.env', 'w') as f:
            f.write(DEFAULT_CONFIG)
        print("Created default .env file. Please update it with your API_KEY and other settings.")

# Ensure .env file is created if it does not exist
ensure_env_file_exists()

# Load environment variables from .env file
load_dotenv()

# Read configurations
REFRESH_INTERVAL = int(os.getenv('REFRESH_INTERVAL', 10))
API_KEY = os.getenv('API_KEY')
CHANNEL_ID = int(os.getenv('CHANNEL_ID'))
JOIN_URL = os.getenv('JOIN_URL')
REFRESH_EMOJI = os.getenv('REFRESH_EMOJI')
SERVERS = json.loads(os.getenv('SERVERS', '[]'))

COOLDOWN = 3  # in seconds

intents = discord.Intents.default()
client = discord.Client(intents=intents)
first_start = True

server_messages = {}

def fancy_time(input_seconds):
    timeformat = ""
    minutes, seconds = divmod(round(input_seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        timeformat += "{h}h "
    if minutes:
        timeformat += "{m}m "
    timeformat += "{s}s"
    return timeformat.format(h=hours, m=minutes, s=seconds)

def generate_embed(server_ip, server_port):
    a2sIP = (server_ip, server_port)
    
    try:
        server_info = a2s.info(a2sIP)
    except socket.timeout:
        return discord.Embed(title="Server down", color=0x00ff00, description="The server is currently down.", timestamp=datetime.datetime.now())
    except (ConnectionResetError, OSError, socket.gaierror):
        return discord.Embed(title="Unknown server", color=0x00ff00, description="Server is unreachable.", timestamp=datetime.datetime.now())

    try:
        server_players = a2s.players(a2sIP)
    except socket.timeout:
        return discord.Embed(title="Server down", color=0x00ff00, description="The server is currently down.", timestamp=datetime.datetime.now())
    except (ConnectionResetError, OSError, socket.gaierror):
        return discord.Embed(title="Unknown server", color=0x00ff00, description="Server is unreachable.", timestamp=datetime.datetime.now())

    header = ""
    plycount = "Player count: {current}/{max}\n".format(current=server_info.player_count, max=server_info.max_players)
    mapname = "Map: {0}\n".format(server_info.map_name)
    if server_info.password_protected:
        header = "**SERVER UNDER MAINTENANCE**\n\n"

    ply_table = []
    for ply in server_players:
        if ply.name == "":
            continue
        ply_table.append([ply.name, ply.score, fancy_time(ply.duration)])

    players_formatted = tabulate(ply_table, ["Player", "Score", "Time"], tablefmt="presto")
    description = header + plycount + mapname + "```" + players_formatted + "```\n" + "[Join server](" + JOIN_URL + ")"
    embed = discord.Embed(title=server_info.server_name, color=0x00ff00, description=description, timestamp=datetime.datetime.utcnow())
    
    return embed

async def set_status():
    for server in SERVERS:
        server_ip = server["ip"]
        server_port = server["port"]
        a2sIP = (server_ip, server_port)
        
        try:
            server_info = a2s.info(a2sIP)
            text = "Player count: {current}/{max}\n".format(current=server_info.player_count, max=server_info.max_players) if len(SERVERS) == 1 else "Monitoring servers"
            status = discord.Status.online
        except socket.timeout:
            text = "an offline server ☹️"
            status = discord.Status.dnd
        except (ConnectionResetError, OSError, socket.gaierror):
            text = "an unknown server ☹️"
            status = discord.Status.dnd
        
        game = discord.Activity(name=text, type=discord.ActivityType.watching)
        await client.change_presence(status=status, activity=game)

async def reset_message(server_index):
    message = server_messages.get(server_index)
    if message:
        await message.clear_reactions()
        await set_status()
        if time() > client.next_allowed_call:
            server = SERVERS[server_index]
            await message.edit(embed=generate_embed(server["ip"], server["port"]))

        client.next_allowed_call = time() + COOLDOWN
        await message.add_reaction(REFRESH_EMOJI)

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    if message.channel.id != CHANNEL_ID:
        return
    if message.content.startswith('!send'):
        await message.channel.send('Hello!')

@client.event
async def on_raw_reaction_add(payload):
    if payload.event_type != "REACTION_ADD": return
    if payload.channel_id != CHANNEL_ID: return
    if payload.member == client.user: return

    for index, msg in server_messages.items():
        if payload.message_id == msg.id:
            await reset_message(index)
            break

async def clear_channel_messages(channel):
    async for message in channel.history(limit=100):
        if message.author == client.user:
            await message.delete()

@client.event
async def on_ready():
    global first_start
    if not first_start:
        return
    client.next_allowed_call = time()
    client.status_channel = client.get_channel(CHANNEL_ID)

    await clear_channel_messages(client.status_channel)
    
    for index, server in enumerate(SERVERS):
        embed = generate_embed(server["ip"], server["port"])
        status_message = await client.status_channel.send(embed=embed)
        await status_message.add_reaction(REFRESH_EMOJI)
        server_messages[index] = status_message

    print(f'We have logged in as {client.user}')
    first_start = False

client.run(API_KEY)
