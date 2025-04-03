# tests/test_database.py
import pytest
import json
import os
import asyncio
from src.bot.database import JSONDatabase
from src.bot.utils import PlayerStats

@pytest.fixture
def test_db():
    db_path = "test_data.json"
    db = JSONDatabase(db_path)
    yield db
    os.remove(db_path)

class TestJSONDatabase:
    @pytest.mark.asyncio
    async def test_save_and_get_message(self, test_db):
        # Test saving and retrieving message data
        await test_db.save_message("123", "456", "test_type")
        message = await test_db.get_message("test_type")
        assert message == ("123", "456"), "Message data mismatch"

    @pytest.mark.asyncio
    async def test_leaderboard_persistence(self, test_db):
        # Test leaderboard save/load
        stats = PlayerStats(kills=10, time_played=100)
        await test_db.save_leaderboard({"player1": stats}, {"player1": stats})
        loaded_leaderboard, _ = await test_db.load_leaderboard()
        assert loaded_leaderboard["player1"].kills == 10, "Leaderboard data not persisted"

    def test_migration(self):
        # Test SQLite to JSON migration
        # This requires a mock SQLite database
        pass  # Implement with a mock SQLite file

    @pytest.mark.asyncio
    async def test_concurrent_writes(self, test_db):
        # Test thread safety
        tasks = [test_db.save_message(f"id{i}", f"channel{i}", f"type{i}") for i in range(10)]
        await asyncio.gather(*tasks)
        assert len(test_db.data["messages"]) == 10, "Concurrent writes failed"