"""Preset server configuration manager.

Fetches server presets from remote JSON (servers.json) and caches for an hour.
Resolves potential local network override using LOCAL_IP.
"""
from __future__ import annotations
import datetime
import asyncio
import logging
import requests
from typing import Dict, Any
from config import SERVERS_URL, LOCAL_IP

class PresetServerManager:
    def __init__(self) -> None:
        self.preset_servers: Dict[str, Dict[str, Any]] = {}
        self.last_preset_update: datetime.datetime = datetime.datetime.min
        self.cache_ttl_seconds = 3600

    async def fetch_preset_servers(self) -> None:
        now = datetime.datetime.now()
        if (now - self.last_preset_update).total_seconds() < self.cache_ttl_seconds:
            return
        try:
            resp = await asyncio.to_thread(requests.get, SERVERS_URL, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                # Apply LOCAL_IP override if provided (e.g., map certain DNS hosts to LAN IP)
                if LOCAL_IP:
                    for name, info in data.items():
                        # Example heuristic: if address contains 'ddns' or matches known host pattern
                        if 'ddns' in info.get('address', '') or info.get('address') == 'theghost.ddns.net':
                            info['resolved_address'] = LOCAL_IP
                        else:
                            info['resolved_address'] = info.get('address')
                else:
                    for info in data.values():
                        info['resolved_address'] = info.get('address')
                self.preset_servers = data
                self.last_preset_update = now
                logging.info("Fetched preset servers: %d", len(self.preset_servers))
            else:
                logging.error("Failed to fetch preset servers (%s): HTTP %s", SERVERS_URL, resp.status_code)
        except Exception as e:
            logging.error("Error fetching preset servers: %s", e)

    def get_preset_server_info(self, server_name: str) -> Dict[str, Any] | None:
        return self.preset_servers.get(server_name)

    def get_all_preset_servers(self) -> Dict[str, Dict[str, Any]]:
        return self.preset_servers

__all__ = ["PresetServerManager"]
