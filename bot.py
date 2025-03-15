import discord
import a2s
import datetime
import socket
import asyncio
import os
import json
import sys
import logging
import tkinter as tk
from tkinter import scrolledtext
from discord.ext import commands
from tabulate import tabulate
from dotenv import load_dotenv
import threading


# Create a 'logs' directory if it doesn't exist for saving logs
if not os.path.exists('logs'):
    os.makedirs('logs')

# Generate a timestamp for the log filename to avoid overwriting
current_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
log_filename = f'logs/bot_{current_time}.log'

# Set up detailed logging configuration with the timestamped filename
logging.basicConfig(
    filename=log_filename,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)

class TkinterLogHandler(logging.Handler):
    """Custom logging handler to write log messages to a Tkinter Text widget."""
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record):
        log_entry = self.format(record)
        self.text_widget.insert(tk.END, log_entry + '\n')
        self.text_widget.yview(tk.END)  # Auto-scroll to the bottom
# Default configuration
DEFAULT_CONFIG = """
REFRESH_INTERVAL=10
API_KEY=YOUR_API_KEY_HERE
CHANNEL_ID=123456789012345678
REFRESH_EMOJI=🔄
SERVERS=[{"ip": "0.0.0.0", "port": 0000}]
"""

def ensure_env_file_exists():
    """Ensure the .env file exists and contains default configurations."""
    if not os.path.exists('.env'):
        with open('.env', 'w', encoding='utf-8') as f:
            f.write(DEFAULT_CONFIG.strip())
        logging.info("Created default .env file. Please update it with your API_KEY and other settings.")
        sys.exit()

ensure_env_file_exists()
load_dotenv()

# Read configurations from .env file
REFRESH_INTERVAL = int(os.getenv('REFRESH_INTERVAL', 10))
API_KEY = os.getenv('API_KEY')
CHANNEL_ID = int(os.getenv('CHANNEL_ID'))
REFRESH_EMOJI = os.getenv('REFRESH_EMOJI')
SERVERS = json.loads(os.getenv('SERVERS', '[]'))

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)
run = False

# Store the number of failed attempts for each server
server_failure_counts = {i: 0 for i in range(len(SERVERS))}
max_failures = 5

def format_player_time(seconds):
    """Format the time a player has been online into a human-readable format."""
    if seconds < 60:
        return f"{int(seconds)} seconds"
    elif seconds < 3600:
        return f"{int(seconds // 60)} minutes"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"

def fetch_server_info(a2sIP):
    """Fetch server info using the a2s module."""
    logging.info(f"Attempting to fetch server info for IP: {a2sIP}")
    try:
        server_info = a2s.info(a2sIP)
        server_players = a2s.players(a2sIP)
        logging.info(f"Successfully fetched server info for {a2sIP}")
        return server_info, server_players
    except socket.timeout:
        logging.warning(f"Timeout while fetching server info for {a2sIP}")
        return None, None
    except (ConnectionResetError, OSError, socket.gaierror) as e:
        logging.error(f"Error fetching server info for {a2sIP}: {e}")
        return None, []

def generate_embed():
    """Generate a Discord embed with server status information."""
    logging.info("Generating embed with server information")
    online_servers = []
    
    for index, server in enumerate(SERVERS):
        logging.info(f"Fetching info for server {index + 1} with IP {server['ip']}:{server['port']}")
        server_info, server_players = fetch_server_info((server['ip'], server['port']))

        if server_info is None:
            server_failure_counts[index] += 1
            logging.warning(f"Server {index + 1} is offline or failed to respond. Failure count: {server_failure_counts[index]}")
            continue  # Skip offline servers

        # Reset failure count if the server is online
        server_failure_counts[index] = 0

        player_count = f"{server_info.player_count}/{server_info.max_players}"

        # Sort players by score in descending order
        sorted_players = sorted(server_players, key=lambda ply: ply.score, reverse=True)

        ply_table = [[ply.name, ply.score, format_player_time(ply.duration)] for ply in sorted_players if ply.name]
        players_formatted = tabulate(ply_table, headers=["Player", "Score", "Time"], tablefmt="pipe")

        online_servers.append(f"**Server {len(online_servers) + 1}:** {server_info.server_name} - Players: {player_count} | Players List: ```{players_formatted}```")
        logging.info(f"Server {index + 1} - {server_info.server_name} is online with {player_count} players.")

    description = "\n".join(online_servers) if online_servers else "All servers are offline."
    embed = discord.Embed(title="Server Status", description=description, color=0x1A529A)
    embed.timestamp = datetime.datetime.now()  # Add timestamp in users' local time
    embed.set_footer(text='\u200b', icon_url="https://i.imgur.com/AfHhftk.jpeg")
    logging.info("Embed generated successfully")

    return embed

class ServerStatusView(discord.ui.View):
    """Handles interactions with the server status message."""
    def __init__(self, status_message):
        super().__init__(timeout=None)
        self.status_message = status_message

    async def refresh_server_info(self):
        """Refresh server information when triggered by emoji reaction."""
        logging.info("Refreshing server information on emoji reaction")
        embed = generate_embed()
        await self.status_message.edit(embed=embed)
        logging.info("Server information refreshed successfully")

async def setup_initial_reactions(status_message):
    """Adds number emojis and refresh emoji to the status message initially."""
    # Get list of active servers (those that are online and haven't exceeded the max failures)
    online_servers = [
        i for i in range(len(SERVERS)) 
        if server_failure_counts[i] < max_failures and fetch_server_info((SERVERS[i]['ip'], SERVERS[i]['port']))[0] is not None
    ]
    
    # Reassign emojis to active servers, renumbering them starting from 1
    for index in range(len(online_servers)):
        emoji = f'{index + 1}️⃣'  # Emoji is dynamically numbered
        await status_message.add_reaction(emoji)
        logging.info(f"Added emoji {emoji} for Server {index + 1}")
    
    await status_message.add_reaction(REFRESH_EMOJI)
    logging.info("Added refresh emoji")

async def sync_reactions(status_message):
    """Synchronizes reactions based on current online server status."""
    # Get list of active servers (those that are online and haven't exceeded the max failures)
    online_servers = [
        i for i in range(len(SERVERS)) 
        if server_failure_counts[i] < max_failures and fetch_server_info((SERVERS[i]['ip'], SERVERS[i]['port']))[0] is not None
    ]

    # Define the reactions we expect based on online servers
    expected_reactions = [f'{i + 1}️⃣' for i in range(len(online_servers))] + [REFRESH_EMOJI]
    existing_reactions = [str(reaction.emoji) for reaction in status_message.reactions]

    # Clear all reactions if there's any server state change
    if set(existing_reactions) != set(expected_reactions):
        await status_message.clear_reactions()  # Clear all reactions
        logging.info("Cleared reactions due to server state change")

        # Re-add the correct emojis based on active servers
        for index in range(len(online_servers)):
            emoji = f'{index + 1}️⃣'
            await status_message.add_reaction(emoji)  # Add the emojis in the correct order
            logging.info(f"Re-added emoji {emoji} for Server {index + 1}")

        # Always ensure the refresh emoji is added
        if REFRESH_EMOJI not in existing_reactions:
            await status_message.add_reaction(REFRESH_EMOJI)
            logging.info("Re-added refresh emoji")

        # Ensure that all expected emojis are added in the right order
        logging.info("Reactions synchronized successfully")

@bot.event
async def on_ready():
    """Event triggered when the bot successfully connects to Discord."""
    logging.info(f"Bot connected as {bot.user}")
    
    channel = bot.get_channel(CHANNEL_ID)
    await channel.purge(limit=100, check=lambda m: m.author == bot.user)
    logging.info("Purged previous bot messages on startup")

    # Send the initial embed and setup emojis
    embed = generate_embed()
    status_message = await channel.send(embed=embed)
    logging.info("Sent initial server status message")
    
    await setup_initial_reactions(status_message)
    logging.info("Initial emoji reactions added")

    # Start a persistent loop for periodic updates
    global run
    run = True
    while True:  # Keeps running unless manually stopped
        try:
            await asyncio.sleep(REFRESH_INTERVAL)
            embed = generate_embed()
            await status_message.edit(embed=embed)
            logging.info("Updated server status embed")

            await sync_reactions(status_message)
        except Exception as e:
            logging.error(f"Exception in main loop: {e}")
            continue  # Keep the loop alive even after exceptions

@bot.event
async def on_disconnect():
    """Event triggered when the bot disconnects from Discord."""
    global run
    run = False
    logging.warning("Bot disconnected from Discord")

def start_bot():
    """Start the bot in a separate thread."""
    asyncio.run(bot.start(API_KEY))

def stop_bot():
    """Stop the bot gracefully."""
    asyncio.run(bot.logout())

def restart_bot():
    """Restart the bot."""
    stop_bot()
    start_bot()

# GUI implementation
class BotGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Discord Bot GUI")
        self.geometry("600x400")

        # Create log area
        self.log_area = scrolledtext.ScrolledText(self, wrap=tk.WORD)
        self.log_area.pack(expand=True, fill=tk.BOTH)

        # Set up logging to the GUI
        log_handler = TkinterLogHandler(self.log_area)
        log_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logging.getLogger().addHandler(log_handler)
        logging.getLogger().setLevel(logging.INFO)

        # Start the bot automatically without buttons
        self.start_bot()

    def start_bot(self):
        """Starts the bot on the GUI thread."""
        logging.info("Starting bot...")
        self.thread = threading.Thread(target=start_bot)
        self.thread.start()

    def on_closing(self):
        """Ensure bot stops when the window is closed."""
        logging.info("Exiting application...")
        stop_bot()
        self.destroy()

if __name__ == "__main__":
    app = BotGUI()
    app.mainloop()
