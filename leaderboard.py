from discord import Embed
from tabulate import tabulate
from datetime import timedelta

class LeaderboardManager:
    def __init__(self, tracker):
        self.tracker = tracker
        self.leaderboard_message = None

    async def update_leaderboard(self, channel):
        """Update or create the leaderboard embed"""
        try:
            if not channel:
                print("Error: No channel provided for leaderboard")
                return

            # Create the embed
            embed = Embed(title="🏆 Monthly Leaderboards", color=0xffd700)
            
            # Score Leaderboard
            score_data = self._format_leaderboard_data('score')
            if score_data:
                embed.add_field(
                    name="Top Scores",
                    value=f"```\n{tabulate(score_data, headers=['Rank', 'Player', 'Score'], tablefmt='simple')}\n```",
                    inline=False
                )

            # Playtime Leaderboard
            time_data = self._format_leaderboard_data('duration')
            if time_data:
                embed.add_field(
                    name="Top Playtime",
                    value=f"```\n{tabulate(time_data, headers=['Rank', 'Player', 'Time'], tablefmt='simple')}\n```",
                    inline=False
                )

            # Add reset information
            reset_date = self.tracker.get_reset_date()
            embed.set_footer(text=f"Resets on {reset_date}")

            # Update or create message
            if self.leaderboard_message:
                await self.leaderboard_message.edit(embed=embed)
            else:
                await channel.purge(check=lambda m: m.author == channel.guild.me)
                self.leaderboard_message = await channel.send(embed=embed)
                
        except Exception as e:
            print(f"Leaderboard error: {e}")

    def _format_leaderboard_data(self, category):
        """Format leaderboard data for display"""
        try:
            leaderboard = self.tracker.get_leaderboard(category)
            if not leaderboard:
                return None

            formatted_data = []
            for i, (name, data) in enumerate(leaderboard):
                if category == 'score':
                    value = data['score']
                else:
                    value = str(timedelta(seconds=data['duration']))
                
                formatted_data.append([
                    f"{i+1}.",
                    self._format_player_name(name, data.get('discord_id')),
                    value
                ])
            return formatted_data
        except Exception as e:
            print(f"Error formatting {category} leaderboard: {e}")
            return None

    def _format_player_name(self, name, discord_id=None):
        """Format player name with Discord mention if available"""
        if discord_id:
            return f"<@{discord_id}>"
        return name[:20]  # Truncate long names