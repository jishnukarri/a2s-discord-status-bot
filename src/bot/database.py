# src/bot/database.py

import os
import json
import asyncio
from datetime import datetime
from ..config import CONFIG

class JSONDatabase:
    def __init__(self, filename):
        self.filename = filename
        self.lock = asyncio.Lock()
        self._initialize()

    def _initialize(self):
        if not os.path.exists(self.filename):
            with open(self.filename, 'w') as f:
                json.dump({
                    "messages": {},
                    "leaderboard": {},
                    "monthly_leaderboard": {}
                }, f)

    async def save_message(self, message_id, channel_id, message_type):
        async with self.lock:
            data = await self._read()
            data['messages'][message_type] = {
                "message_id": str(message_id),
                "channel_id": str(channel_id)
            }
            await self._write(data)

    async def get_message(self, message_type):
        data = await self._read()
        msg = data.get('messages', {}).get(message_type)
        return (msg['message_id'], msg['channel_id']) if msg else None

    async def save_leaderboard(self, player_stats, monthly_stats):
        async with self.lock:
            data = await self._read()
            current_month = datetime.now().strftime('%Y-%m')
            data['leaderboard'] = player_stats
            data['monthly_leaderboard'] = monthly_stats
            await self._write(data)

    async def load_leaderboard(self):
        data = await self._read()
        return data.get('leaderboard', {}), data.get('monthly_leaderboard', {})

    async def _read(self):
        async with self.lock:
            with open(self.filename, 'r') as f:
                return json.load(f)

    async def _write(self, data):
        async with self.lock:
            with open(self.filename, 'w') as f:
                json.dump(data, f, indent=2)