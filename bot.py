import discord
from discord import app_commands
import a2s
import asyncio
import os
import json
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from tabulate import tabulate
from collections import defaultdict
import matplotlib.pyplot as plt
import hashlib
import sys
import platform
import subprocess
import aiohttp

# Hard-coded values (not user-configurable)
GITHUB_REPO = "jishnukarri/a2s-discord-status-bot"  # Your official repository
BOT_VERSION = os.getenv("BOT_VERSION", "dev")  # Auto-updated by build process

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('bot_runtime.log'), logging.StreamHandler()]
)

# Load user configuration (excluding hard-coded values)
load_dotenv()

CONFIG = {
    'REFRESH_INTERVAL': int(os.getenv('REFRESH_INTERVAL', 10)),
    'API_KEY': os.getenv('API_KEY'),
    'CHANNEL_ID': int(os.getenv('CHANNEL_ID')),
    'SERVERS': json.loads(os.getenv('SERVERS', '[]')),
    'QUERY_TIMEOUT': int(os.getenv('QUERY_TIMEOUT', 5)),
    'DATABASE_FILE': os.getenv('DATABASE_FILE', 'database/data.json'),
    'MAX_RETRIES': int(os.getenv('MAX_RETRIES', 3)),
    'CUSTOM_TITLE': os.getenv('CUSTOM_TITLE', '🟢 Server Status'),
    'CUSTOM_TEXT': os.getenv('CUSTOM_TEXT', '**DM an admin to join our servers!**'),
    'LEADERBOARD_TITLE': os.getenv('LEADERBOARD_TITLE', '🏆 Player Leaderboard'),
    'LEADERBOARD_SIZE': int(os.getenv('LEADERBOARD_SIZE', 10)),
    'MONTHLY_RESET_DAY': int(os.getenv('MONTHLY_RESET_DAY', 1)),
    'STATUS_COLOR': int(os.getenv('STATUS_COLOR', '0x1A529A'), 16),
    'LEADERBOARD_COLOR': int(os.getenv('LEADERBOARD_COLOR', '0xFFD700'), 16),
    'FOOTER_ICON': os.getenv('FOOTER_ICON', 'https://example.com/icon.jpg'),
    'KILL_UPDATE_INTERVAL': int(os.getenv('KILL_UPDATE_INTERVAL', 300)),
    'GRAPH_DAYS': int(os.getenv('GRAPH_DAYS', 7)),
    'SCHEMA_VERSION': 1  # Database schema version
}

# Ensure database directory exists
os.makedirs(os.path.dirname(CONFIG['DATABASE_FILE']), exist_ok=True)

class JSONDatabase:
    def __init__(self, filename):
        self.filename = filename
        self.lock = asyncio.Lock()
        self.data = self._load()
    
    def _load(self):
        if not os.path.exists(self.filename):
            return {
                "schema_version": CONFIG['SCHEMA_VERSION'],
                "messages": {},
                "leaderboard": {},
                "monthly_leaderboards": [],
                "weekly_activity": {}
            }
        
        try:
            with open(self.filename, 'r') as f:
                data = json.load(f)
                
                # Schema migration (if needed)
                if data.get("schema_version", 0) < CONFIG['SCHEMA_VERSION']:
                    logging.info(f"Migrating database from v{data.get('schema_version', 0)} to v{CONFIG['SCHEMA_VERSION']}")
                    # Add migration logic here if needed
                    data["schema_version"] = CONFIG['SCHEMA_VERSION']
                
                return data
        except Exception as e:
            logging.error(f"Database load error: {e}")
            return {
                "schema_version": CONFIG['SCHEMA_VERSION'],
                "messages": {},
                "leaderboard": {},
                "monthly_leaderboards": [],
                "weekly_activity": {}
            }
    
    async def save(self):
        async with self.lock:
            temp_file = self.filename + ".tmp"
            try:
                with open(temp_file, 'w') as f:
                    json.dump(self.data, f, indent=2)
                os.replace(temp_file, self.filename)  # Atomic write
            except Exception as e:
                logging.error(f"Database save error: {e}")
            finally:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
    
    async def update(self, key, value):
        async with self.lock:
            self.data[key] = value
            await self.save()
    
    async def get_message(self, key):
        return self.data['messages'].get(key)

def sanitize_text(text):
    """Sanitize text to prevent markdown injection"""
    return str(text).replace("`", "'").replace("*", "•").replace("_", "-").replace("|", "¦")

class PlayerStats:
    def __init__(self, kills=0, time_played=0, last_seen=None, last_kill_update=None, current_session_kills=0):
        self.kills = kills
        self.time_played = time_played
        self.last_seen = last_seen or datetime.now().isoformat()
        self.last_kill_update = last_kill_update or datetime.now().isoformat()
        self.current_session_kills = current_session_kills
    
    def to_dict(self):
        return {
            'kills': self.kills,
            'time_played': self.time_played,
            'last_seen': self.last_seen,
            'last_kill_update': self.last_kill_update,
            'current_session_kills': self.current_session_kills
        }
    
    @classmethod
    def from_dict(cls, data):
        return cls(
            kills=data.get('kills', 0),
            time_played=data.get('time_played', 0),
            last_seen=data.get('last_seen'),
            last_kill_update=data.get('last_kill_update'),
            current_session_kills=data.get('current_session_kills', 0)
        )

class ServerMonitor:
    def __init__(self):
        self.db = JSONDatabase(CONFIG['DATABASE_FILE'])
        self.status_message = None
        self.leaderboard_message = None
        self.server_data = {}
        self.player_stats = {}
        self.monthly_leaderboard = {}
        self.weekly_activity = {}
        self.last_reset = datetime.now()
        self.keycap_emojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']
        
        # Initialize from database
        self._init_from_db()
    
    def _init_from_db(self):
        # Initialize player stats
        self.player_stats = {
            name: PlayerStats.from_dict(stats) 
            for name, stats in self.db.data.get('leaderboard', {}).items()
        }
        
        # Initialize monthly leaderboard
        self.monthly_leaderboard = {
            name: PlayerStats.from_dict(stats) 
            for name, stats in self.db.data.get('monthly_leaderboard', {}).items()
        }
        
        # Initialize weekly activity
        self.weekly_activity = self.db.data.get('weekly_activity', {})
    
    async def query_server(self, address):
        for attempt in range(CONFIG['MAX_RETRIES']):
            try:
                info = await asyncio.wait_for(a2s.ainfo(address), timeout=CONFIG['QUERY_TIMEOUT'])
                players = await asyncio.wait_for(a2s.aplayers(address), timeout=CONFIG['QUERY_TIMEOUT'])
                return info, players, round(info.ping * 1000)
            except Exception as e:
                logging.warning(f"Attempt {attempt + 1} failed for {address}: {e}")
                await asyncio.sleep(1)
        return None, [], None
    
    async def update_all_servers(self):
        tasks = [self.update_single_server(server['ip'], server['port']) for server in CONFIG['SERVERS']]
        await asyncio.gather(*tasks)
        self.check_monthly_reset()
        
        # Save to database
        await self.db.update('leaderboard', {name: stats.to_dict() for name, stats in self.player_stats.items()})
        await self.db.update('monthly_leaderboard', {name: stats.to_dict() for name, stats in self.monthly_leaderboard.items()})
        await self.db.update('weekly_activity', self.weekly_activity)
    
    async def update_single_server(self, ip, port):
        address = (ip, port)
        info, players, ping = await self.query_server(address)
        
        if info:
            self.server_data[address] = (info, players, ping)
            self.update_player_stats(players)
            self.update_weekly_activity(address, len(players))
        else:
            self.server_data.pop(address, None)
    
    def update_player_stats(self, players):
        now = datetime.now().isoformat()
        for player in players:
            if not player.name:
                continue
            
            # Update global stats
            if player.name not in self.player_stats:
                self.player_stats[player.name] = PlayerStats()
            
            stats = self.player_stats[player.name]
            
            # Update kills
            last_update = datetime.fromisoformat(stats.last_kill_update)
            now_time = datetime.fromisoformat(now)
            
            if (now_time - last_update).total_seconds() >= CONFIG['KILL_UPDATE_INTERVAL']:
                if player.score > stats.current_session_kills:
                    new_kills = player.score - stats.current_session_kills
                    stats.kills += new_kills
                    # Update monthly stats
                    if player.name not in self.monthly_leaderboard:
                        self.monthly_leaderboard[player.name] = PlayerStats()
                    self.monthly_leaderboard[player.name].kills += new_kills
                
                stats.current_session_kills = player.score
                stats.last_kill_update = now
            
            # Update time played
            stats.time_played += 1
            stats.last_seen = now
            
            # Update monthly time played
            if player.name in self.monthly_leaderboard:
                self.monthly_leaderboard[player.name].time_played += 1
    
    def update_weekly_activity(self, address, player_count):
        today = datetime.now().strftime('%Y-%m-%d')
        key = (address[0], str(address[1]))  # Make address hashable
        
        if key not in self.weekly_activity:
            self.weekly_activity[key] = {}
        
        self.weekly_activity[key][today] = player_count
    
    def format_server_status(self):
        embed = discord.Embed(title=sanitize_text(CONFIG['CUSTOM_TITLE']), color=CONFIG['STATUS_COLOR'])
        embed.add_field(name="Custom Text", value=sanitize_text(CONFIG['CUSTOM_TEXT']), inline=False)
        
        for idx, (address, (info, players, ping)) in enumerate(self.server_data.items()):
            if info:
                player_table = tabulate(
                    [[sanitize_text(p.name), p.score] for p in players if p.name],
                    headers=["Player", "Kills"],
                    tablefmt="presto"
                )
                embed.add_field(
                    name=f"{self.keycap_emojis[idx]} {sanitize_text(info.server_name)} ({info.player_count}/{info.max_players}) | Ping: {ping}ms",
                    value=f"**Map:** {sanitize_text(info.map_name)}\n{player_table}",
                    inline=False
                )
        
        embed.set_footer(text=f"Version {BOT_VERSION}", icon_url=CONFIG['FOOTER_ICON'])
        embed.timestamp = datetime.now()
        return embed
    
    def format_leaderboard(self):
        current_month = datetime.now().strftime('%Y-%m')
        monthly_stats = next((entry['stats'] for entry in reversed(self.db.data.get('monthly_leaderboards', [])) 
                             if entry['month'] == current_month), {})
        
        combined = {}
        # Global stats
        for name, stats in self.player_stats.items():
            combined[name] = (stats.kills, stats.time_played)
        
        # Monthly stats
        for name, stats in monthly_stats.items():
            combined[name] = (
                combined.get(name, (0, 0))[0] + stats.get('kills', 0),
                combined.get(name, (0, 0))[1] + stats.get('time_played', 0)
            )
        
        sorted_players = sorted(
            combined.items(),
            key=lambda x: (x[1][0], x[1][1]),
            reverse=True
        )[:CONFIG['LEADERBOARD_SIZE']]
        
        embed = discord.Embed(title=sanitize_text(CONFIG['LEADERBOARD_TITLE']), color=CONFIG['LEADERBOARD_COLOR'])
        
        for rank, (name, stats) in enumerate(sorted_players, 1):
            embed.add_field(
                name=f"{self.get_rank_emoji(rank)} {sanitize_text(name)}",
                value=f"**Kills:** {stats[0]} | **Time Played:** {stats[1]} mins",
                inline=False
            )
        
        embed.set_footer(text=f"Version {BOT_VERSION}", icon_url=CONFIG['FOOTER_ICON'])
        return embed
    
    def get_rank_emoji(self, rank):
        return {1: '🥇', 2: '🥈', 3: '🥉'}.get(rank, '🔹')
    
    def check_monthly_reset(self):
        now = datetime.now()
        if now.day == CONFIG['MONTHLY_RESET_DAY'] and now.month != self.last_reset.month:
            self.db.data['monthly_leaderboards'].append({
                "month": self.last_reset.strftime('%Y-%m'),
                "stats": {name: {"kills": stats.kills, "time_played": stats.time_played} 
                         for name, stats in self.monthly_leaderboard.items()}
            })
            self.monthly_leaderboard.clear()
            self.last_reset = now
            logging.info("Monthly leaderboard archived")
    
    async def generate_weekly_graph(self):
        plt.figure(figsize=(10, 6))
        for server in CONFIG['SERVERS']:
            address_key = (server['ip'], str(server['port']))
            if address_key in self.weekly_activity:
                activity = self.weekly_activity[address_key]
                dates = list(activity.keys())[-CONFIG['GRAPH_DAYS']:]
                players = [activity[date] for date in dates]
                
                if players:
                    avg = sum(players)/len(players)
                    plt.plot(dates, players, label=f"{server['name']} (Avg: {avg:.1f})")
        
        plt.title("Weekly Player Activity")
        plt.xlabel("Date")
        plt.ylabel("Players")
        plt.legend()
        plt.grid(True)
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        graph_path = "weekly_graph.png"
        plt.savefig(graph_path)
        plt.close()
        
        return graph_path

class Updater:
    def __init__(self):
        self.session = aiohttp.ClientSession()
    
    async def check_for_updates(self):
        try:
            async with self.session.get(f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest") as resp:
                release = await resp.json()
                latest_version = release['tag_name'].lstrip('v')
                
                if latest_version == BOT_VERSION:
                    return False
                
                # Find matching asset for current platform
                asset = next(
                    (a for a in release['assets'] 
                     if platform.system().lower() in a['name'].lower()),
                    None
                )
                
                if not asset:
                    return False
                
                # Find checksum asset
                checksum_asset = next(
                    (a for a in release['assets'] 
                     if a['name'].endswith('.sha256')),
                    None
                )
                
                if not checksum_asset:
                    return False
                
                # Get checksum
                async with self.session.get(checksum_asset['browser_download_url']) as cs_resp:
                    checksum = await cs_resp.text()
                    expected_hash = checksum.split()[0]
                
                return {
                    'version': latest_version,
                    'download_url': asset['browser_download_url'],
                    'checksum': expected_hash
                }
        except Exception as e:
            logging.error(f"Update check error: {e}")
            return False
    
    async def perform_update(self, update_info):
        try:
            async with self.session.get(update_info['download_url']) as resp:
                with open('update.tmp', 'wb') as f:
                    while True:
                        chunk = await resp.content.read(1024)
                        if not chunk:
                            break
                        f.write(chunk)
            
            # Verify checksum
            sha256_hash = hashlib.sha256()
            with open('update.tmp', 'rb') as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            
            if sha256_hash.hexdigest() != update_info['checksum']:
                os.remove('update.tmp')
                return False
            
            # Replace executable
            os.replace('update.tmp', sys.executable)
            self._restart_bot()
            return True
        except Exception as e:
            logging.error(f"Update error: {e}")
            return False
    
    def _restart_bot(self):
        args = sys.argv.copy()
        args.insert(0, sys.executable)
        
        if platform.system() == 'Windows':
            subprocess.Popen(['start', sys.executable] + args, shell=True)
        else:
            subprocess.Popen(['nohup', sys.executable] + args + ['&'], shell=True)
        
        sys.exit()

# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)
monitor = ServerMonitor()
updater = Updater()

@bot.event
async def on_ready():
    logging.info(f'Logged in as {bot.user} (Version: {BOT_VERSION})')
    await tree.sync()
    
    channel = bot.get_channel(CONFIG['CHANNEL_ID'])
    
    # Clean up old messages
    async for message in channel.history(limit=100):
        if message.author == bot.user:
            await message.delete()
    
    # Initialize messages from JSON database
    status_msg = await monitor.db.get_message("status")
    if status_msg:
        try:
            monitor.status_message = await channel.fetch_message(int(status_msg[0]))
        except discord.NotFound:
            monitor.status_message = await channel.send("Initializing status...")
            await monitor.db.update('messages', {"status": str(monitor.status_message.id)})
    else:
        monitor.status_message = await channel.send("Initializing status...")
        await monitor.db.update('messages', {"status": str(monitor.status_message.id)})
    
    leaderboard_msg = await monitor.db.get_message("leaderboard")
    if leaderboard_msg:
        try:
            monitor.leaderboard_message = await channel.fetch_message(int(leaderboard_msg[0]))
        except discord.NotFound:
            monitor.leaderboard_message = await channel.send("Initializing leaderboard...")
            await monitor.db.update('messages', {
                "status": str(monitor.status_message.id),
                "leaderboard": str(monitor.leaderboard_message.id)
            })
    else:
        monitor.leaderboard_message = await channel.send("Initializing leaderboard...")
        await monitor.db.update('messages', {
            "status": str(monitor.status_message.id),
            "leaderboard": str(monitor.leaderboard_message.id)
        })
    
    bot.loop.create_task(status_update_loop())

async def status_update_loop():
    while True:
        try:
            await monitor.update_all_servers()
            
            # Update status message
            if monitor.status_message:
                await monitor.status_message.edit(embed=monitor.format_server_status())
            
            # Update leaderboard message
            if monitor.leaderboard_message:
                await monitor.leaderboard_message.edit(embed=monitor.format_leaderboard())
            
            await asyncio.sleep(CONFIG['REFRESH_INTERVAL'])
        except Exception as e:
            logging.error(f"Update error: {e}")
            await asyncio.sleep(CONFIG['REFRESH_INTERVAL'])

# Slash commands
@tree.command(name="status", description="Show server status")
@app_commands.checks.cooldown(1, 5, key=lambda i: i.user.id)
async def status(interaction: discord.Interaction):
    await interaction.response.send_message(embed=monitor.format_server_status(), ephemeral=True)

@tree.command(name="leaderboard", description="Show player rankings")
@app_commands.checks.cooldown(1, 5, key=lambda i: i.user.id)
async def leaderboard(interaction: discord.Interaction):
    await interaction.response.send_message(embed=monitor.format_leaderboard(), ephemeral=True)

@tree.command(name="weeklygraph", description="Generate weekly activity graph")
@app_commands.checks.cooldown(1, 30, key=lambda i: i.user.id)
async def weeklygraph(interaction: discord.Interaction):
    try:
        graph_path = await monitor.generate_weekly_graph()
        await interaction.response.send_message(file=discord.File(graph_path), ephemeral=True)
        os.remove(graph_path)
    except Exception as e:
        logging.error(f"Graph generation error: {e}")
        await interaction.response.send_message("Failed to generate graph.", ephemeral=True)

@tree.command(name="help", description="Show bot usage guide")
async def help(interaction: discord.Interaction):
    embed = discord.Embed(title="Bot Commands", description="Available slash commands:")
    embed.add_field(name="/status", value="Show server status (5s cooldown)", inline=False)
    embed.add_field(name="/leaderboard", value="Show player rankings (5s cooldown)", inline=False)
    embed.add_field(name="/weeklygraph", value="Generate weekly player graph (30s cooldown)", inline=False)
    embed.add_field(name="/help", value="Show this help message", inline=False)
    embed.set_footer(text=f"Version {BOT_VERSION}")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Register the command tree
tree = app_commands.CommandTree(bot)

if __name__ == "__main__":
    try:
        bot.run(CONFIG['API_KEY'])
    except Exception as e:
        logging.critical(f"Bot failed to start: {e}")