# tests/test_commands.py
import pytest
from discord import Interaction
from src.bot.commands import status, leaderboard

@pytest.fixture
def mock_interaction():
    return MagicMock(spec=Interaction)

class TestCommands:
    @pytest.mark.asyncio
    async def test_status_command(self, mock_interaction):
        with patch("src.bot.commands.generate_status_embed") as mock_embed:
            await status(mock_interaction)
            mock_embed.assert_called_once()
            mock_interaction.response.send_message.assert_called_with(
                embed=mock_embed.return_value,
                ephemeral=True
            )

    @pytest.mark.asyncio
    async def test_leaderboard_command(self, mock_interaction):
        with patch("src.bot.commands.format_leaderboard") as mock_embed:
            await leaderboard(mock_interaction)
            mock_embed.assert_called_once()
            mock_interaction.response.send_message.assert_called_with(
                embed=mock_embed.return_value,
                ephemeral=True
            )