```
# Discord Server Status Bot

A versatile Discord bot designed to monitor and display the status of game servers, including player counts, server details, and more. Suitable for various types of servers with adjustable configurations.

---

## Features:
- **Real-Time Monitoring**: Tracks multiple servers with dynamic updates.
- **Player Information**: Displays detailed player stats (kills, playtime) for each server.
- **Auto-Refresh**: Updates server status every 30 seconds.
- **Reaction-Based Refresh**: Users can refresh the status by reacting with an emoji.
- **Message Cleanup**: Automatically cleans up old messages to maintain a tidy channel.
- **Customizable Embeds**: Customize status messages and embeds with markdown support.
- **Error Handling**: Gracefully handles server errors and status changes.
- **Leaderboard**: Tracks player stats and displays a leaderboard.
- **Monthly Reset**: Automatically resets the leaderboard at the end of each month.

---

## Installation

### Prerequisites
- Python 3.9 or higher
- Discord Bot Token (from [Discord Developer Portal](https://discord.com/developers/applications))
- Game server IPs and ports

### Installation Steps

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/jishnukarri/a2s-discord-status-bot.git
   cd a2s-discord-status-bot
   ```

2. **Install Dependencies**:
   Install the required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set Up Environment Variables**:
   Create a `.env` file in the root directory and add the following:
   ```env
   API_KEY=your_discord_bot_token
   CHANNEL_ID=your_discord_channel_id
   REFRESH_INTERVAL=30
   SERVERS=[{"ip": "1.2.3.4", "port": 27015}]
   ```

4. **Run the Bot**:
   Start the bot using Python:
   ```bash
   python bot.py
   ```

---

## Requirements

The following Python packages are required to run the bot:

- `discord.py`: For interacting with the Discord API.
- `python-a2s`: For querying game servers using the A2S protocol.
- `python-dotenv`: For loading environment variables from a `.env` file.
- `sqlite3`: For storing leaderboard and message data (built into Python).

You can install all dependencies using the provided `requirements.txt` file:
```bash
pip install -r requirements.txt
```

---

## Usage

### Executable (EXE) File
For a hassle-free installation, download the pre-built executable from the [Releases](https://github.com/jishnukarri/a2s-discord-status-bot/releases) section.

1. Download the EXE file.
2. Place the EXE in a folder with the `.env` file and any required assets (e.g., `icon.ico`).
3. Run the EXE.

---

## Configuration

### `.env` File
The bot uses a `.env` file for configuration. Here’s an example:
```env
API_KEY=your_discord_bot_token
CHANNEL_ID=your_discord_channel_id
REFRESH_INTERVAL=30
SERVERS=[{"ip": "1.2.3.4", "port": 27015}]
```

- `API_KEY`: Your Discord bot token.
- `CHANNEL_ID`: The ID of the channel where the bot will post updates.
- `REFRESH_INTERVAL`: How often (in seconds) the bot updates the status.
- `SERVERS`: A JSON array of server IPs and ports to monitor.

---

## Customization

### Custom Text and Title
You can customize the bot’s status message by editing the following variables in the `bot.py` file:
```python
CUSTOM_TITLE = "THIS BOT PING IS FROM THE UK 🇬🇧"
CUSTOM_TEXT = """
**DM Brenner650 or any Helpers to join our servers!  🎮**
"""
```

### Leaderboard
The bot tracks player stats and displays a leaderboard. The leaderboard resets automatically at the end of each month.

---

## Troubleshooting

### Common Issues
1. **Bot Doesn’t Start**:
   - Ensure the `.env` file is correctly configured.
   - Check that the bot has the necessary permissions in the Discord channel.

2. **Server Query Fails**:
   - Verify the server IP and port are correct.
   - Ensure the server is online and accessible.

3. **Missing Permissions**:
   - Grant the bot the following permissions in Discord:
     - `Read Messages`
     - `Send Messages`
     - `Manage Messages`
     - `Add Reactions`

---

## Contributing

Contributions are welcome! Please follow these steps:
1. Fork the repository.
2. Create a new branch for your feature or bugfix.
3. Submit a pull request.

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

## Support

For support, please open an issue on the [GitHub repository](https://github.com/jishnukarri/a2s-discord-status-bot/issues) or contact the maintainer.

### **Files You Need**
Here’s a list of files you’ll need for the bot:

1. **`bot.py`**: The main bot script.
2. **`.env`**: Environment variables file (contains API key, channel ID, etc.).
3. **`requirements.txt`**: Lists all Python dependencies.
4. **`README.md`**: Documentation for the bot.
