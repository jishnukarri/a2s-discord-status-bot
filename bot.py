import discord
import a2s
import datetime
import socket
import asyncio
from tabulate import tabulate
from time import time

# Configuration
TOKEN = 'YOUR_BOT_TOKEN'  # Replace with your bot token
CHANNEL = YOUR_CHANNEL_ID  # Replace with your channel ID
COOLDOWN = 3  # Cooldown period in seconds
REFRESH_INTERVAL = 30  # Refresh every 30 seconds
JOIN_URL = "https://example.com/join/"  # Replace with your join URL
REFRESH_EMOJI = "🔄"

# List of servers with their IPs and ports
SERVERS = [
    {"ip": "server_ip_1", "port": 1234},
    {"ip": "server_ip_2", "port": 5678},
    # Add more servers as needed
]

intents = discord.Intents.default()
client = discord.Client(intents=intents)
first_start = True

# Store server messages for reaction handling
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
    except (socket.timeout, ConnectionResetError, OSError, socket.gaierror):
        return discord.Embed(title="Server down", color=0x00ff00, description="The server is currently down.", timestamp=datetime.datetime.now())

    try:
        server_players = a2s.players(a2sIP)
    except (socket.timeout, ConnectionResetError, OSError, socket.gaierror):
        return discord.Embed(title="Server down", color=0x00ff00, description="The server is currently down.", timestamp=datetime.datetime.now())

    header = ""
    plycount = f"Player count: {server_info.player_count}/{server_info.max_players}\n"
    mapname = f"Map: {server_info.map_name}\n"
    if server_info.password_protected:
        header = "**SERVER UNDER MAINTENANCE**\n\n"

    ply_table = [[ply.name, ply.score, fancy_time(ply.duration)] for ply in server_players if ply.name]
    players_formatted = tabulate(ply_table, ["Player", "Score", "Time"], tablefmt="presto")
    description = header + plycount + mapname + f"```{players_formatted}```\n[Join server]({JOIN_URL})"
    return discord.Embed(title=server_info.server_name, color=0x00ff00, description=description, timestamp=datetime.datetime.utcnow())

async def set_status():
    for server in SERVERS:
        server_ip = server["ip"]
        server_port = server["port"]
        a2sIP = (server_ip, server_port)
        
        try:
            server_info = a2s.info(a2sIP)
            text = f"Player count: {server_info.player_count}/{server_info.max_players}"
            status = discord.Status.online
        except (socket.timeout, ConnectionResetError, OSError, socket.gaierror):
            text = "an offline server ☹️"
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

async def clear_channel_messages(channel):
    async for message in channel.history(limit=100):
        if message.author == client.user:
            await message.delete()

async def refresh_server_status():
    while True:
        for index in range(len(SERVERS)):
            await reset_message(index)
        await asyncio.sleep(REFRESH_INTERVAL)

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    if message.channel.id != CHANNEL:
        return
    if message.content.startswith('!send'):
        await message.channel.send('Hello!')

@client.event
async def on_raw_reaction_add(payload):
    if payload.event_type != "REACTION_ADD": return
    if payload.channel_id != CHANNEL: return
    if payload.member == client.user: return

    for index, message in server_messages.items():
        if payload.message_id == message.id:
            await reset_message(index)
            break

@client.event
async def on_ready():
    global first_start
    if not first_start:
        return
    client.next_allowed_call = time()
    client.status_channel = client.get_channel(CHANNEL)
    await clear_channel_messages(client.status_channel)
    
    for index, server in enumerate(SERVERS):
        embed = generate_embed(server["ip"], server["port"])
        status_message = await client.status_channel.send(embed=embed)
        await status_message.add_reaction(REFRESH_EMOJI)
        server_messages[index] = status_message

    client.loop.create_task(refresh_server_status())
    print(f'We have logged in as {client.user}')
    first_start = False

client.run(TOKEN)
