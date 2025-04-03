# Server Monitor Bot Setup Guide

This guide will help you set up and run the Server Monitor Bot quickly. Follow the steps below to get started.

---

## **Setup Instructions**

1. **Download the Required Files**:
   - Go to the [Releases](#) section of the repository.
   - Download the executable file (`bot.exe`) and the `.env` configuration file.

2. **Edit the `.env` File**:
   - Open the `.env` file in a text editor.
   - Update the following fields with your specific details:
     - `API_KEY`: Your Discord bot token.
     - `CHANNEL_ID`: The ID of the Discord channel where the bot will post updates.
     - `SERVERS`: A JSON array of server IPs and ports (e.g., `[{"ip": "127.0.0.1", "port": 27015}]`).
     - Other optional fields like `CUSTOM_TITLE`, `LEADERBOARD_TITLE`, etc., can be customized as needed.

3. **Run the Bot**:
   - Place both files (`bot.exe` and `.env`) in the same folder.
   - Double-click on `bot.exe` to start the bot.
   - The bot will automatically connect to your Discord server and begin monitoring servers.

---

## **Frequently Asked Questions (FAQ)**

### **Q: What is this bot for?**
A: This bot monitors game servers, posts their status in a Discord channel, and displays player leaderboards.

### **Q: How do I find my Discord Channel ID?**
A: Enable Developer Mode in Discord settings, right-click on your channel, and select "Copy ID."

### **Q: What happens if I don't configure all `.env` fields?**
A: Default values are used for unspecified fields, but critical fields like `API_KEY` and `CHANNEL_ID` must be set.

### **Q: How do I stop the bot?**
A: Close the terminal or stop the executable process.

### **Q: Can I add more servers later?**
A: Yes, update the `SERVERS` field in your `.env` file and restart the bot.

### **Q: Where are logs stored?**
A: Logs are saved in a file named `bot_runtime.log` in the same directory as the executable.

---

Enjoy using your Server Monitor Bot!
