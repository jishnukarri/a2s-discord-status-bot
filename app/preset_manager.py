"""Preset server configuration manager.

Fetches server presets from the community's remote `servers.json` and caches
them for an hour. Resolves a LAN override for DDNS-hosted addresses via
LOCAL_IP so the bot can reach a server on the local network instead of
round-tripping through the internet.
"""
from __future__ import annotations
import asyncio
import datetime
import logging
from typing import Any, Dict

import requests

from .config import LOCAL_IP, SERVERS_URL

CACHE_TTL_SECONDS = 3600


class PresetServerManager:
    def __init__(self) -> None:
        self.preset_servers: Dict[str, Dict[str, Any]] = {}
        self.last_preset_update: datetime.datetime = datetime.datetime.min

    async def fetch_preset_servers(self) -> None:
        now = datetime.datetime.now()
        if (now - self.last_preset_update).total_seconds() < CACHE_TTL_SECONDS:
            return
        try:
            resp = await asyncio.to_thread(requests.get, SERVERS_URL, timeout=15)
            if resp.status_code != 200:
                logging.error("Failed to fetch preset servers (%s): HTTP %s", SERVERS_URL, resp.status_code)
                return
            data = resp.json()
            for name, info in data.items():
                address = info.get('address')
                is_ddns = address and ('ddns' in address)
                info['resolved_address'] = LOCAL_IP if (LOCAL_IP and is_ddns) else address
            self.preset_servers = data
            self.last_preset_update = now
            logging.info("Fetched %d preset server(s)", len(self.preset_servers))
        except Exception:
            logging.exception("Error fetching preset servers")

    def get_preset_server_info(self, server_name: str) -> Dict[str, Any] | None:
        return self.preset_servers.get(server_name)

    def get_all_preset_servers(self) -> Dict[str, Dict[str, Any]]:
        return self.preset_servers


__all__ = ["PresetServerManager"]
