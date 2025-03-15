from discord.ui import View, Button
from discord import Interaction, ButtonStyle
from datetime import datetime

class AdminApprovalView(View):
    def __init__(self, tracker, username, user_id):
        super().__init__(timeout=3600)  # 1 hour timeout
        self.tracker = tracker
        self.username = username
        self.user_id = user_id

        # Approve Button
        approve_button = Button(
            label="Approve",
            style=ButtonStyle.green,
            custom_id=f"approve_{username}"
        )
        approve_button.callback = self.approve_callback
        self.add_item(approve_button)

        # Reject Button
        reject_button = Button(
            label="Reject",
            style=ButtonStyle.red,
            custom_id=f"reject_{username}"
        )
        reject_button.callback = self.reject_callback
        self.add_item(reject_button)

    async def approve_callback(self, interaction: Interaction):
        if self.tracker.approve_request(self.username):
            await interaction.response.send_message(
                f"✅ Approved {self.username}",
                ephemeral=True
            )
            # Notify user
            user = interaction.client.get_user(int(self.user_id))
            if user:
                try:
                    await user.send(f"Your registration for {self.username} was approved!")
                except:
                    pass
        else:
            await interaction.response.send_message(
                "❌ Request no longer exists",
                ephemeral=True
            )
        self.stop()

    async def reject_callback(self, interaction: Interaction):
        if self.tracker.reject_request(self.username):
            await interaction.response.send_message(
                f"❌ Rejected {self.username}",
                ephemeral=True
            )
            # Notify user
            user = interaction.client.get_user(int(self.user_id))
            if user:
                try:
                    await user.send(f"Your registration for {self.username} was rejected.")
                except:
                    pass
        else:
            await interaction.response.send_message(
                "❌ Request no longer exists",
                ephemeral=True
            )
        self.stop()