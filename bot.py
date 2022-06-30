import discord
import a2s
import datetime
import socket
import asyncio
from tabulate import tabulate
from time import time

TOKEN = 'TOKEN' # Bot token
CHANNEL = 123456 # Channel ID
COOLDOWN = 3 #in seconds
SERVER_IP = "127.0.0.1" # server ip
SERVER_PORT = 27015
JOIN_URL = "https://website.com/join/"
REFRESH_EMOJI = "🔄"

a2sIP = (SERVER_IP,SERVER_PORT) # server IP
intents = discord.Intents.default()
client = discord.Client(intents=intents)
first_start = True

def fancy_time( input_seconds ):
    timeformat = ""
    minutes, seconds = divmod(round(input_seconds), 60)

    hours, minutes = divmod(minutes,60)
    if hours:
        timeformat += "{h}h "
    if minutes:
        timeformat += "{m}m "
    timeformat += "{s}s"

    return timeformat.format(h=hours,m=minutes,s=seconds)

def generate_embed():
    try:
        server_info = a2s.info(a2sIP)
    except socket.timeout:
        return discord.Embed(title="Server down",color=0x00ff00,description="The server is currently down.",timestamp=datetime.datetime.now())
    except (ConnectionResetError, OSError, socket.gaierror):
        return discord.Embed(title="Unknown server",color=0x00ff00,description="Server is unreachable.",timestamp=datetime.datetime.now())

    server_players = a2s.players(a2sIP)

    header = ""
    plycount = "Player count: {current}/{max}\n".format(current=server_info.player_count,max=server_info.max_players)
    mapname = "Map: {0}\n".format(server_info.map_name)
    if server_info.password_protected:
        header = "**SERVER UNDER MAINTENACE**\n\n"

    ply_table = []
    for ply in server_players:
        if ply.name == "":
            continue
        ply_table.append([ply.name,ply.score,fancy_time(ply.duration)])

    players_formatted = tabulate(ply_table,["Player","Score","Time"],tablefmt="presto")
    description = header+plycount+mapname+"```"+players_formatted+"```\n"+"[Join server]("+JOIN_URL+")"
    embed = discord.Embed(title=server_info.server_name,color=0x00ff00,description=description,timestamp=datetime.datetime.utcnow())#timestamp=datetime.datetime.now())
    return embed

async def set_status():
    try:
        server_info = a2s.info(a2sIP)
    except socket.timeout:
        text = "an offline server ☹️"
        status = discord.Status.dnd
    except (ConnectionResetError, OSError, socket.gaierror):
        text = "an unknown server ☹️"
        status = discord.Status.dnd
    else:
        text = "Player count: {current}/{max}\n".format(current=server_info.player_count, max=server_info.max_players)
        status = discord.Status.online
    
    game = discord.Activity(name=text, type=discord.ActivityType.watching)
    await client.change_presence(status=status, activity=game)

async def set_status_loop():
    while True:
        await set_status()
        await asyncio.sleep(5)

async def reset_message():
    await client.status_message.clear_reactions()
    
    if time() > client.next_allowed_call:
        await client.status_message.edit(embed=generate_embed())

    client.next_allowed_call = time() + COOLDOWN

    await client.status_message.add_reaction(REFRESH_EMOJI)

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    if message.channel.id != CHANNEL:
        return
    if message.content.startswith('!send'):
        await message.channel.send('Hello!')

@client.event
async def on_raw_reaction_add( payload ):
    if payload.event_type != "REACTION_ADD": return
    if payload.channel_id != CHANNEL: return
    if payload.message_id != client.status_message.id: return
    if payload.member == client.user: return

    await reset_message()

@client.event
async def on_ready():
    if not first_start:
        return
    client.next_allowed_call = time()
    client.status_channel = client.get_channel(CHANNEL)
    client.status_message = await client.status_channel.send(embed=generate_embed())
    await client.status_message.add_reaction(REFRESH_EMOJI)

    asyncio.create_task(set_status_loop())

    print(f'We have logged in as {client.user}')

client.run( TOKEN )
