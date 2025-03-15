import discord
import a2s
import asyncio
import json
from discord import app_commands
from discord.ext import commands, tasks
from datetime import timedelta
from competition import CompetitionTracker
from leaderboard import LeaderboardManager
from admin_ui import AdminApprovalView
from commands import UserCommands

class ServerMonitorBot(commands.Bot):
    def __init__(self):
        self.config = self.load_config()
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        
        super().__init__(
            command_prefix='!',
            intents=intents,
            application_id=int(self.config['application_id'])
        )
        
        self.tracker = CompetitionTracker()
        self.leaderboard = LeaderboardManager(self.tracker)
        self.server_states = {}
        self.status_message = None
        self.leaderboard_message = None

    def load_config(self):
        """Load configuration from file"""
        try:
            with open('config.json') as f:
                config = json.load(f)
                
            # Validate required fields
            required = ['token', 'application_id', 'channel_id', 'refresh_interval', 'servers']
            if not all(key in config for key in required):
                raise ValueError("Missing required configuration fields")
                
            return config
        except Exception as e:
            print(f"Config error: {e}")
            raise

    async def setup_hook(self):
        """Initialize bot components"""
        await self.add_cog(UserCommands(self, self.tracker))
        try:
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} commands")
        except Exception as e:
            print(f"Command sync error: {e}")
            
        self.update_task = tasks.loop(seconds=self.config['refresh_interval'])(self.update_servers)

    async def get_server_info(self, server):
        """Query server information"""
        try:
            address = (server['ip'], server['port'])
            info, players = await asyncio.gather(
                asyncio.to_thread(a2s.info, address),
                asyncio.to_thread(a2s.players, address)
            )
            return {
                'online': True,
                'players': players,
                'name': info.server_name,
                'map': info.map_name,
                'player_count': f"{info.player_count}/{info.max_players}"
            }
        except Exception as e:
            print(f"Query failed {server['ip']}:{server['port']} - {e}")
            return {'online': False, 'players': []}

    async def update_servers(self):
        """Main update loop"""
        try:
            channel = self.get_channel(int(self.config['channel_id']))
            if not channel:
                print("Error: Status channel not found")
                return

            # Query all servers
            tasks = [self.get_server_info(server) for server in self.config['servers']]
            results = await asyncio.gather(*tasks)
            
            # Process valid players
            all_players = []
            for result in results:
                if result['online']:
                    all_players.extend(result['players'])
            
            # Update competition stats
            if all_players:
                self.tracker.update_stats(all_players)
            
            # Update displays
            await self.update_status(channel, results)
            await self.leaderboard.update_leaderboard(channel)
            
        except Exception as e:
            print(f"Update error: {e}")

    async def update_status(self, channel, results):
        """Update server status message"""
        try:
            embed = discord.Embed(title="🕹️ LIVE SERVER STATUS", color=0x00ff00)
            online_count = 0
            
            for server, result in zip(self.config['servers'], results):
                status = "🟢 ONLINE" if result['online'] else "🔴 OFFLINE"
                field_value = f"**Status**: {status}"
                
                if result['online']:
                    online_count += 1
                    field_value += f"\n**Map**: {result.get('map', 'Unknown')}"
                    field_value += f"\n**Players**: {result.get('player_count', '0/0')}"
                    players = "\n".join([f"• {p.name[:15]}" for p in result['players'][:3]])
                    if players:
                        field_value += f"\n```\n{players}\n```"
                
                embed.add_field(
                    name=f"{server['ip']}:{server['port']}",
                    value=field_value,
                    inline=False
                )
            
            embed.set_footer(text=f"🟢 {online_count} online | 🔴 {len(results)-online_count} offline")
            
            if self.status_message:
                await self.status_message.edit(embed=embed)
            else:
                await channel.purge(check=lambda m: m.author == self.user)
                self.status_message = await channel.send(embed=embed)
                
        except Exception as e:
            print(f"Status update failed: {e}")

    async def on_ready(self):
        """Bot startup handler"""
        print(f"Logged in as {self.user}")
        self.update_task.start()

if __name__ == "__main__":
    try:
        bot = ServerMonitorBot()
        bot.run(bot.config['token'])
    except KeyboardInterrupt:
        print("Bot stopped by user")
    except Exception as e:
        print(f"Fatal error: {e}")