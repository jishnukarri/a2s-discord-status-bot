# tests/test_monitor.py
import pytest
import asyncio
from unittest.mock import MagicMock, patch
from src.bot.monitor import ServerMonitor
from src.bot.database import JSONDatabase

@pytest.fixture
def mock_server():
    return MagicMock(
        info=MagicMock(server_name="Test Server", player_count=5),
        players=[MagicMock(name="Player1", score=10)]
    )

class TestServerMonitor:
    @pytest.mark.asyncio
    @patch("src.bot.monitor.a2s")
    async def test_query_server(self, mock_a2s, mock_server):
        # Mock successful server response
        mock_a2s.ainfo.return_value = mock_server.info
        mock_a2s.aplayers.return_value = mock_server.players
        
        monitor = ServerMonitor(JSONDatabase(":memory:"))
        info, players, ping = await monitor.query_server(("127.0.0.1", 27015))
        
        assert info.server_name == "Test Server"
        assert len(players) == 1
        assert players[0].name == "Player1"

    @pytest.mark.asyncio
    @patch("src.bot.monitor.a2s")
    async def test_query_failure(self, mock_a2s):
        # Mock query failure
        mock_a2s.ainfo.side_effect = Exception("Test error")
        
        monitor = ServerMonitor(JSONDatabase(":memory:"))
        info, players, ping = await monitor.query_server(("invalid", 0))
        
        assert info is None
        assert len(players) == 0

    @pytest.mark.asyncio
    async def test_player_stats_update(self, mock_server):
        # Test player stat tracking
        monitor = ServerMonitor(JSONDatabase(":memory:"))
        await monitor.update_single_server("127.0.0.1", 27015)
        
        stats = monitor.player_stats.get("Player1")
        assert stats.kills == 10
        assert stats.time_played == 1