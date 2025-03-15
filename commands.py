from discord.ext import commands
from discord import app_commands, Embed
from datetime import timedelta
from admin_ui import AdminApprovalView
import discord

class UserCommands(commands.Cog):
    def __init__(self, bot, tracker):
        self.bot = bot
        self.tracker = tracker

    @app_commands.command(name="register", description="Register your in-game username")
    @app_commands.describe(username="Your in-game username")
    async def register(self, interaction: discord.Interaction, username: str):
        """Register command handler"""
        username = username.strip()
        if not username:
            await interaction.response.send_message(
                "❌ Please provide a valid username",
                ephemeral=True
            )
            return
            
        if self.tracker.add_pending_request(interaction.user.id, username):
            await self.notify_admins(interaction, username)
            await interaction.response.send_message(
                "✅ Registration request sent to admins!",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "❌ Username already registered or pending approval",
                ephemeral=True
            )

    @app_commands.command(name="mystats", description="View your game statistics")
    async def mystats(self, interaction: discord.Interaction):
        """View personal stats"""
        username = next(
            (uname for uname, data in self.tracker.data['players'].items() 
             if data.get('discord_id') == str(interaction.user.id)),
            None
        )
        
        if not username:
            await interaction.response.send_message(
                "❌ No linked account found. Use /register first",
                ephemeral=True
            )
            return
            
        stats = self.tracker.data['players'][username]
        embed = Embed(title=f"Stats for {username}", color=0x00ff00)
        embed.add_field(name="Total Score", value=stats['score'], inline=True)
        embed.add_field(name="Play Time", value=str(timedelta(seconds=stats['duration'])), inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="pending", description="View pending registrations (Admin only)")
    @app_commands.default_permissions(administrator=True)
    async def pending(self, interaction: discord.Interaction):
        """Admin command to view pending requests"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Administrator permission required",
                ephemeral=True
            )
            return
            
        pending = self.tracker.get_pending_requests()
        if not pending:
            await interaction.response.send_message(
                "✅ No pending registrations",
                ephemeral=True
            )
            return
            
        embed = Embed(title="Pending Registrations", color=0xffa500)
        for username, data in pending.items():
            user = self.bot.get_user(int(data['discord_id']))
            embed.add_field(
                name=username,
                value=f"Requested by: {user.mention if user else 'Unknown'}",
                inline=False
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def notify_admins(self, interaction, username):
        """Notify admins about new registration"""
        view = AdminApprovalView(self.tracker, username, interaction.user.id)
        for member in interaction.guild.members:
            if member.guild_permissions.administrator:
                try:
                    await member.send(
                        f"New registration request from {interaction.user.mention}\n"
                        f"Username: `{username}`",
                        view=view
                    )
                except discord.Forbidden:
                    continue
                except Exception as e:
                    print(f"Error notifying admin {member}: {e}")