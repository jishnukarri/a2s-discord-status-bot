import discord
import a2s
import datetime
import asyncio
import os
import json
import logging
import sqlite3
from discord.ext import commands
from dotenv import load_dotenv
from collections import defaultdict
from tabulate import tabulate

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot_runtime.log'),
        logging.StreamHandler()
    ]
)

# Load all configurable variables from .env
load_dotenv()
CONFIG = {
    'REFRESH_INTERVAL': int(os.getenv('REFRESH_INTERVAL', 10)),
    'API_KEY': os.getenv('API_KEY'),
    'CHANNEL_ID': int(os.getenv('CHANNEL_ID')),
    'SERVERS': json.loads(os.getenv('SERVERS', '[]')),
    'QUERY_TIMEOUT': int(os.getenv('QUERY_TIMEOUT', 5)),
    'DATABASE_FILE': os.getenv('DATABASE_FILE', 'bot_data.db'),
    'MAX_RETRIES': int(os.getenv('MAX_RETRIES', 3)),
    'CUSTOM_TITLE': os.getenv('CUSTOM_TITLE', '🟢 Server Status'),
    'CUSTOM_TEXT': os.getenv('CUSTOM_TEXT', '**DM an admin to join our servers!**'),
    'LEADERBOARD_TITLE': os.getenv('LEADERBOARD_TITLE', '🏆 Player Leaderboard'),
    'LEADERBOARD_SIZE': int(os.getenv('LEADERBOARD_SIZE', 10)),
    'MONTHLY_RESET_DAY': int(os.getenv('MONTHLY_RESET_DAY', 1)),
    'STATUS_COLOR': int(os.getenv('STATUS_COLOR', '0x1A529A'), 16),
    'LEADERBOARD_COLOR': int(os.getenv('LEADERBOARD_COLOR', '0xFFD700'), 16),
    'FOOTER_ICON': os.getenv('FOOTER_ICON', 'https://example.com/icon.jpg'),
    'KILL_UPDATE_INTERVAL': int(os.getenv('KILL_UPDATE_INTERVAL', 300))
}

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

def init_db():
    """Initialize SQLite database with improved schema"""
    conn = sqlite3.connect(CONFIG['DATABASE_FILE'])
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY,
        message_id TEXT,
        channel_id TEXT,
        type TEXT
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS leaderboard (
        player_name TEXT PRIMARY KEY,
        kills INTEGER,
        time_played INTEGER,
        last_seen TEXT,
        last_kill_update TEXT,
        current_session_kills INTEGER
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS monthly_leaderboard (
        player_name TEXT PRIMARY KEY,
        kills INTEGER,
        time_played INTEGER,
        month TEXT
    )''')
    
    conn.commit()
    conn.close()

init_db()

class DataManager:
    @staticmethod
    def save_message(message_id, channel_id, message_type):
        with sqlite3.connect(CONFIG['DATABASE_FILE']) as conn:
            conn.execute('INSERT OR REPLACE INTO messages (message_id, channel_id, type) VALUES (?, ?, ?)',
                        (message_id, channel_id, message_type))
    
    @staticmethod
    def get_message(message_type):
        with sqlite3.connect(CONFIG['DATABASE_FILE']) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT message_id, channel_id FROM messages WHERE type = ?', (message_type,))
            return cursor.fetchone()
    
    @staticmethod
    def save_leaderboard(player_stats, monthly_stats):
        with sqlite3.connect(CONFIG['DATABASE_FILE']) as conn:
            conn.executemany('''INSERT OR REPLACE INTO leaderboard 
                (player_name, kills, time_played, last_seen, last_kill_update, current_session_kills)
                VALUES (?, ?, ?, ?, ?, ?)''',
                [(name, stats.kills, stats.time_played, stats.last_seen.isoformat(),
                  stats.last_kill_update.isoformat() if stats.last_kill_update else None,
                  stats.current_session_kills) 
                 for name, stats in player_stats.items()])
            
            current_month = datetime.datetime.now().strftime('%Y-%m')
            conn.executemany('''INSERT OR REPLACE INTO monthly_leaderboard 
                (player_name, kills, time_played, month)
                VALUES (?, ?, ?, ?)''',
                [(name, stats.kills, stats.time_played, current_month) 
                 for name, stats in monthly_stats.items()])
    
    @staticmethod
    def load_leaderboard():
        with sqlite3.connect(CONFIG['DATABASE_FILE']) as conn:
            cursor = conn.cursor()
            cursor.execute('''SELECT player_name, kills, time_played, last_seen, 
                            last_kill_update, current_session_kills FROM leaderboard''')
            player_stats = {
                row[0]: PlayerStats(row[1], row[2], 
                                  datetime.datetime.fromisoformat(row[3]),
                                  datetime.datetime.fromisoformat(row[4]) if row[4] else None,
                                  row[5])
                for row in cursor.fetchall()
            }
            
            current_month = datetime.datetime.now().strftime('%Y-%m')
            cursor.execute('SELECT player_name, kills, time_played FROM monthly_leaderboard WHERE month = ?', 
                         (current_month,))
            monthly_stats = {
                row[0]: PlayerStats(row[1], row[2]) 
                for row in cursor.fetchall()
            }
            
            return player_stats, monthly_stats

class PlayerStats:
    def __init__(self, kills=0, time_played=0, last_seen=None, last_kill_update=None, current_session_kills=0):
        self.kills = kills
        self.time_played = time_played
        self.last_seen = last_seen or datetime.datetime.now()
        self.last_kill_update = last_kill_update
        self.current_session_kills = current_session_kills

class ServerMonitor:
    def __init__(self):
        self.status_message = None
        self.leaderboard_message = None
        self.server_data = {}
        self.player_stats, self.monthly_leaderboard = DataManager.load_leaderboard()
        self.last_reset = datetime.datetime.now()
        self.keycap_emojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']

    async def query_server(self, address):
        for attempt in range(CONFIG['MAX_RETRIES']):
            try:
                info = await asyncio.wait_for(a2s.ainfo(address), timeout=CONFIG['QUERY_TIMEOUT'])
                players = await asyncio.wait_for(a2s.aplayers(address), timeout=CONFIG['QUERY_TIMEOUT'])
                return info, players, round(info.ping * 1000)
            except Exception as e:
                logging.warning(f"Attempt {attempt + 1} failed for {address}: {str(e)}")
                await asyncio.sleep(1)
        return None, [], None

    async def update_all_servers(self):
        tasks = [self.update_single_server(server['ip'], server['port']) for server in CONFIG['SERVERS']]
        await asyncio.gather(*tasks)
        self.check_monthly_reset()
        DataManager.save_leaderboard(self.player_stats, self.monthly_leaderboard)

    async def update_single_server(self, ip, port):
        address = (ip, port)
        info, players, ping = await self.query_server(address)
        if info:
            self.server_data[address] = (info, players, ping)
            self.update_player_stats(players)

    def update_player_stats(self, players):
        now = datetime.datetime.now()
        for player in players:
            if not player.name:
                continue
                
            stats = self.player_stats.get(player.name, PlayerStats())
            monthly_stats = self.monthly_leaderboard.get(player.name, PlayerStats())
            
            if not stats.last_kill_update or (now - stats.last_kill_update).total_seconds() >= CONFIG['KILL_UPDATE_INTERVAL']:
                if player.score > stats.current_session_kills:
                    new_kills = player.score - stats.current_session_kills
                    stats.kills += new_kills
                    monthly_stats.kills += new_kills
                stats.current_session_kills = player.score
                stats.last_kill_update = now
            
            stats.time_played += 1
            stats.last_seen = now
            monthly_stats.time_played += 1
            
            self.player_stats[player.name] = stats
            self.monthly_leaderboard[player.name] = monthly_stats

    def format_server_status(self):
        embed = discord.Embed(title="🟢 Online Servers", color=CONFIG['STATUS_COLOR'])
        embed.add_field(name=CONFIG['CUSTOM_TITLE'], value=CONFIG['CUSTOM_TEXT'], inline=False)
        
        for idx, (address, (info, players, ping)) in enumerate(self.server_data.items()):
            if info:
                player_table = tabulate(
                    [[p.name, p.score] for p in players if p.name],
                    headers=["Player", "Kills"],
                    tablefmt="presto"
                )
                embed.add_field(
                    name=f"{self.keycap_emojis[idx]} {info.server_name} ({info.player_count}/{info.max_players}) | Ping: {ping}ms",
                    value=f"**Map:** {info.map_name}\n```\n{player_table}\n```",
                    inline=False
                )

        embed.set_footer(text='\u200b', icon_url=CONFIG['FOOTER_ICON'])
        embed.timestamp = datetime.datetime.now()
        return embed

    def format_leaderboard(self):
        leaderboard = sorted(
            self.player_stats.items(),
            key=lambda x: (x[1].kills, x[1].time_played),
            reverse=True
        )[:CONFIG['LEADERBOARD_SIZE']]

        embed = discord.Embed(title=CONFIG['LEADERBOARD_TITLE'], color=CONFIG['LEADERBOARD_COLOR'])
        for rank, (name, stats) in enumerate(leaderboard, 1):
            embed.add_field(
                name=f"{self.get_rank_emoji(rank)} {name}",
                value=f"**Kills:** {stats.kills} | **Time Played:** {stats.time_played} mins",
                inline=False
            )

        embed.set_footer(text='\u200b', icon_url=CONFIG['FOOTER_ICON'])
        embed.timestamp = datetime.datetime.now()
        return embed

    def get_rank_emoji(self, rank):
        emojis = {1: '🥇', 2: '🥈', 3: '🥉'}
        return emojis.get(rank, '🔹')

    def check_monthly_reset(self):
        now = datetime.datetime.now()
        if now.day == CONFIG['MONTHLY_RESET_DAY'] and now.month != self.last_reset.month:
            self.monthly_leaderboard.clear()
            self.last_reset = now
            logging.info("Monthly leaderboard reset")

monitor = ServerMonitor()

@bot.event
async def on_ready():
    logging.info(f'Logged in as {bot.user}')
    channel = bot.get_channel(CONFIG['CHANNEL_ID'])
    
    async for message in channel.history(limit=100):
        if message.author == bot.user:
            await message.delete()
            logging.info(f"Deleted old bot message: {message.id}")
    
    monitor.leaderboard_message = await channel.send("Updating leaderboard...")
    DataManager.save_message(monitor.leaderboard_message.id, CONFIG['CHANNEL_ID'], 'leaderboard')
    
    monitor.status_message = await channel.send("Updating server status...")
    DataManager.save_message(monitor.status_message.id, CONFIG['CHANNEL_ID'], 'status')
    
    bot.loop.create_task(status_update_loop())

async def status_update_loop():
    while True:
        try:
            await monitor.update_all_servers()
            
            await monitor.leaderboard_message.edit(content="", embed=monitor.format_leaderboard())
            await monitor.status_message.edit(content="", embed=monitor.format_server_status())
            
            await asyncio.sleep(CONFIG['REFRESH_INTERVAL'])
        except Exception as e:
            logging.error(f"Update error: {str(e)}")
            await asyncio.sleep(CONFIG['REFRESH_INTERVAL'])

if __name__ == "__main__":
    try:
        bot.run(CONFIG['API_KEY'])
    except Exception as e:
        logging.error(f"Critical error: {str(e)}")