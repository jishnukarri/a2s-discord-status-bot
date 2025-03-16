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
from tabulate import tabulate  # For creating tables

# Configure logging (separate system)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot_runtime.log'),
        logging.StreamHandler()
    ]
)

# Load configuration
load_dotenv()
CONFIG = {
    'REFRESH_INTERVAL': int(os.getenv('REFRESH_INTERVAL', 10)),
    'API_KEY': os.getenv('API_KEY'),
    'CHANNEL_ID': int(os.getenv('CHANNEL_ID')),
    'SERVERS': json.loads(os.getenv('SERVERS', '[]')),
    'QUERY_TIMEOUT': 5,
    'DATABASE_FILE': 'bot_data.db',
    'MAX_RETRIES': 3,
    'CUSTOM_TITLE': os.getenv('CUSTOM_TITLE', '🟢 Server Status'),
    'CUSTOM_TEXT': os.getenv('CUSTOM_TEXT', '**DM Brenner650 or any Helpers to join our servers!  🎮**')
}

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Database setup
def init_db():
    """Initialize SQLite database"""
    conn = sqlite3.connect(CONFIG['DATABASE_FILE'])
    cursor = conn.cursor()
    
    # Create tables if they don't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY,
            message_id TEXT,
            channel_id TEXT,
            type TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leaderboard (
            player_name TEXT PRIMARY KEY,
            kills INTEGER,
            time_played INTEGER,
            last_seen TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS monthly_leaderboard (
            player_name TEXT PRIMARY KEY,
            kills INTEGER,
            time_played INTEGER
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

class DataManager:
    """Handles all database operations"""
    @staticmethod
    def save_message(message_id, channel_id, message_type):
        """Save message info to database"""
        with sqlite3.connect(CONFIG['DATABASE_FILE']) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO messages (message_id, channel_id, type)
                VALUES (?, ?, ?)
            ''', (message_id, channel_id, message_type))
    
    @staticmethod
    def get_message(message_type):
        """Retrieve message info from database"""
        with sqlite3.connect(CONFIG['DATABASE_FILE']) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT message_id, channel_id FROM messages WHERE type = ?', (message_type,))
            return cursor.fetchone()
    
    @staticmethod
    def save_leaderboard(player_stats, monthly_stats):
        """Save leaderboard data"""
        with sqlite3.connect(CONFIG['DATABASE_FILE']) as conn:
            # Save main leaderboard
            conn.executemany('''
                INSERT OR REPLACE INTO leaderboard (player_name, kills, time_played, last_seen)
                VALUES (?, ?, ?, ?)
            ''', [(name, stats.kills, stats.time_played, stats.last_seen.isoformat()) 
                  for name, stats in player_stats.items()])
            
            # Save monthly leaderboard
            conn.executemany('''
                INSERT OR REPLACE INTO monthly_leaderboard (player_name, kills, time_played)
                VALUES (?, ?, ?)
            ''', [(name, stats.kills, stats.time_played) 
                  for name, stats in monthly_stats.items()])
    
    @staticmethod
    def load_leaderboard():
        """Load leaderboard data"""
        with sqlite3.connect(CONFIG['DATABASE_FILE']) as conn:
            cursor = conn.cursor()
            
            # Load main leaderboard
            cursor.execute('SELECT player_name, kills, time_played, last_seen FROM leaderboard')
            player_stats = {
                row[0]: PlayerStats(row[1], row[2], datetime.datetime.fromisoformat(row[3]))
                for row in cursor.fetchall()
            }
            
            # Load monthly leaderboard
            cursor.execute('SELECT player_name, kills, time_played FROM monthly_leaderboard')
            monthly_stats = {
                row[0]: PlayerStats(row[1], row[2]) 
                for row in cursor.fetchall()
            }
            
            return player_stats, monthly_stats

class PlayerStats:
    """Tracks player statistics"""
    def __init__(self, kills=0, time_played=0, last_seen=None):
        self.kills = kills
        self.time_played = time_played
        self.last_seen = last_seen or datetime.datetime.now()

class ServerMonitor:
    def __init__(self):
        self.status_message = None
        self.leaderboard_message = None
        self.server_data = {}
        self.player_stats, self.monthly_leaderboard = DataManager.load_leaderboard()
        self.last_reset = datetime.datetime.now()
        self.keycap_emojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']

    async def query_server(self, address):
        """Query game server with retries"""
        for attempt in range(CONFIG['MAX_RETRIES']):
            try:
                info = await asyncio.wait_for(a2s.ainfo(address), timeout=CONFIG['QUERY_TIMEOUT'])
                players = await asyncio.wait_for(a2s.aplayers(address), timeout=CONFIG['QUERY_TIMEOUT'])
                return info, players, round(info.ping * 1000)  # Return ping in milliseconds
            except Exception as e:
                logging.warning(f"Attempt {attempt + 1} failed for {address}: {str(e)}")
                await asyncio.sleep(1)
        return None, [], None

    async def update_all_servers(self):
        """Update all servers concurrently"""
        tasks = []
        for server in CONFIG['SERVERS']:
            address = (server['ip'], server['port'])
            tasks.append(self.update_single_server(address))
        
        await asyncio.gather(*tasks)
        self.check_monthly_reset()
        DataManager.save_leaderboard(self.player_stats, self.monthly_leaderboard)

    async def update_single_server(self, address):
        """Update single server status and player stats"""
        info, players, ping = await self.query_server(address)
        if info:
            self.server_data[address] = (info, players, ping)
            self.update_player_stats(players)

    def update_player_stats(self, players):
        """Update player statistics"""
        for player in players:
            if player.name:
                stats = self.player_stats.get(player.name, PlayerStats())
                stats.kills = max(stats.kills, player.score)
                stats.time_played += 1
                stats.last_seen = datetime.datetime.now()
                self.player_stats[player.name] = stats

                # Update monthly stats
                monthly_stats = self.monthly_leaderboard.get(player.name, PlayerStats())
                monthly_stats.kills = max(monthly_stats.kills, player.score)
                monthly_stats.time_played += 1
                self.monthly_leaderboard[player.name] = monthly_stats

    def format_server_status(self):
        """Create status embed with online servers and custom text"""
        embed = discord.Embed(title="🟢 Online Servers", color=0x1A529A)
        
        # Add custom markdown text
        embed.add_field(
            name=CONFIG['CUSTOM_TITLE'],
            value=CONFIG['CUSTOM_TEXT'],
            inline=False
        )
        
        # Add server status
        for idx, (address, (info, players, ping)) in enumerate(self.server_data.items()):
            if info:
                # Create a small table for players
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

        embed.set_footer(text='\u200b', icon_url="https://i.imgur.com/AfHhftk.jpeg")
        embed.timestamp = datetime.datetime.now()
        return embed

    def format_leaderboard(self):
        """Create leaderboard embed"""
        leaderboard = sorted(
            self.player_stats.items(),
            key=lambda x: (x[1].kills, x[1].time_played),
            reverse=True
        )[:10]

        embed = discord.Embed(title="🏆 Player Leaderboard", color=0xFFD700)
        for rank, (name, stats) in enumerate(leaderboard, 1):
            embed.add_field(
                name=f"{self.get_rank_emoji(rank)} {name}",
                value=f"**Kills:** {stats.kills} | **Time Played:** {stats.time_played} mins",
                inline=False
            )

        embed.set_footer(text='\u200b', icon_url="https://i.imgur.com/AfHhftk.jpeg")
        embed.timestamp = datetime.datetime.now()
        return embed

    def get_rank_emoji(self, rank):
        """Get rank emoji for leaderboard"""
        emojis = {1: '🥇', 2: '🥈', 3: '🥉'}
        return emojis.get(rank, '🔹')

    def check_monthly_reset(self):
        """Reset monthly leaderboard at month end"""
        now = datetime.datetime.now()
        if now.month != self.last_reset.month:
            self.monthly_leaderboard.clear()
            self.last_reset = now
            logging.info("Monthly leaderboard reset")

monitor = ServerMonitor()

@bot.event
async def on_ready():
    """Initialize bot when connected"""
    logging.info(f'Logged in as {bot.user}')
    try:
        channel = bot.get_channel(CONFIG['CHANNEL_ID'])
        
        # Clean up previous bot messages
        async for message in channel.history(limit=100):
            if message.author == bot.user:
                try:
                    await message.delete()
                    logging.info(f"Deleted old bot message: {message.id}")
                except discord.NotFound:
                    logging.warning(f"Message {message.id} already deleted")
                except discord.Forbidden:
                    logging.error(f"Missing permissions to delete message {message.id}")
                except Exception as e:
                    logging.error(f"Error deleting message {message.id}: {str(e)}")
        
        # Create new leaderboard message
        monitor.leaderboard_message = await channel.send("Updating leaderboard...")
        DataManager.save_message(monitor.leaderboard_message.id, CONFIG['CHANNEL_ID'], 'leaderboard')
        
        # Create new status message
        monitor.status_message = await channel.send("Updating server status...")
        DataManager.save_message(monitor.status_message.id, CONFIG['CHANNEL_ID'], 'status')
        
        # Start update loop
        bot.loop.create_task(status_update_loop())
    except Exception as e:
        logging.error(f"Initialization failed: {str(e)}")

async def status_update_loop():
    """Main update loop with error handling"""
    while True:
        try:
            await monitor.update_all_servers()
            
            # Update leaderboard first
            try:
                await monitor.leaderboard_message.edit(
                    content="",
                    embed=monitor.format_leaderboard()
                )
            except discord.NotFound:
                logging.warning("Leaderboard message deleted, creating a new one")
                channel = bot.get_channel(CONFIG['CHANNEL_ID'])
                monitor.leaderboard_message = await channel.send(embed=monitor.format_leaderboard())
                DataManager.save_message(monitor.leaderboard_message.id, CONFIG['CHANNEL_ID'], 'leaderboard')
            
            # Update server status
            try:
                await monitor.status_message.edit(
                    content="",
                    embed=monitor.format_server_status()
                )
            except discord.NotFound:
                logging.warning("Status message deleted, creating a new one")
                channel = bot.get_channel(CONFIG['CHANNEL_ID'])
                monitor.status_message = await channel.send(embed=monitor.format_server_status())
                DataManager.save_message(monitor.status_message.id, CONFIG['CHANNEL_ID'], 'status')
            
            await asyncio.sleep(CONFIG['REFRESH_INTERVAL'])
        except Exception as e:
            logging.error(f"Update error: {str(e)}")
            await asyncio.sleep(CONFIG['REFRESH_INTERVAL'])

if __name__ == "__main__":
    try:
        bot.run(CONFIG['API_KEY'])
    except KeyboardInterrupt:
        logging.info("Bot shutdown requested")
    except Exception as e:
        logging.error(f"Critical error: {str(e)}")
    finally:
        logging.info("Bot process terminated")