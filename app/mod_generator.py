"""Mod list and DLC download text generation.

Fetches the community's `content.json` (download links) and `steam.json`
(Steam mod ID mappings) and formats human-readable install instructions used
by the `/server` and `/cdlc` slash commands.
"""
from __future__ import annotations
import asyncio
import datetime
import logging
from typing import Any, Dict, List

import requests

from .config import CONTENT_URL, STEAM_URL

CACHE_TTL_SECONDS = 3600
CDLC_KEYS = {'rf', 'ws', 'spe', 'gm', 'vn', 'csla'}


class ModListGenerator:
    def __init__(self) -> None:
        self.steam_mods: Dict[str, Any] = {}
        self.content_links: Dict[str, Any] = {}
        self.last_config_update: datetime.datetime = datetime.datetime.min

    async def fetch_config_data(self) -> None:
        now = datetime.datetime.now()
        if (now - self.last_config_update).total_seconds() < CACHE_TTL_SECONDS:
            return
        try:
            steam_resp = await asyncio.to_thread(requests.get, STEAM_URL, timeout=15)
            if steam_resp.status_code == 200:
                self.steam_mods = steam_resp.json()
            else:
                logging.error("Failed to fetch steam.json: HTTP %s", steam_resp.status_code)

            content_resp = await asyncio.to_thread(requests.get, CONTENT_URL, timeout=15)
            if content_resp.status_code == 200:
                self.content_links = content_resp.json()
            else:
                logging.error("Failed to fetch content.json: HTTP %s", content_resp.status_code)

            self.last_config_update = now
            logging.info("Updated mod configuration from GitHub")
        except Exception:
            logging.exception("Failed fetching mod configuration")

    # ---------- Lookup helpers ----------
    def normalize_mod_name(self, mod_name: str) -> str:
        clean = mod_name.replace('@', '')
        mods = self.content_links.get('mods', {})
        if f"@{clean}" in mods:
            return f"@{clean}"
        if clean in mods:
            return clean
        return mod_name

    def get_download_links(self, mod_name: str) -> List[str] | None:
        mods = self.content_links.get('mods', {})
        val = mods.get(self.normalize_mod_name(mod_name))
        if isinstance(val, list):
            return val
        if isinstance(val, str):
            return [val]
        return None

    @staticmethod
    def sort_key_ignore_at(mod_name: str) -> str:
        return mod_name.lstrip('@').lower()

    def get_cdlc_info(self, key_or_id) -> Dict[str, Any] | None:
        dlc_cfg = self.content_links.get('dlc', {})
        if isinstance(key_or_id, str):
            return dlc_cfg.get(key_or_id.lower())
        if isinstance(key_or_id, int):
            steam_dlc = self.steam_mods.get('dlc', {})
            for key, steam_id in steam_dlc.items():
                if steam_id == key_or_id:
                    return dlc_cfg.get(key)
        return None

    @staticmethod
    def _append_download_link_lines(parts: List[str], link_value: Any, *, single_label: str = "Download") -> None:
        if isinstance(link_value, list):
            if len(link_value) == 1:
                parts.append(f"**{single_label}:** <{link_value[0]}>")
            else:
                parts.append("**Download Links:**")
                for i, link in enumerate(link_value, 1):
                    parts.append(f"{i}. <{link}>")
        elif isinstance(link_value, str):
            parts.append(f"**{single_label}:** <{link_value}>")
        else:
            parts.append(f"**{single_label}:** N/A")

    # ---------- Message generation ----------
    async def generate_preset_server_mod_list(self, server_name: str, preset_info: Dict[str, Any]) -> str:
        await self.fetch_config_data()
        arma_info = self.content_links.get('arma', {})
        arma_version = arma_info.get('version', 'v2.20.152984')
        arma_link = arma_info.get('link', 'https://tinyurl.com/33taw7ds')

        parts: List[str] = [
            f"**{server_name}**\n",
            f"Server version: **{arma_version}**",
            f"Required game version: **{arma_version}**\n",
            '-' * 80 + '\n',
            f"Location: {preset_info.get('country', 'Unknown')}\n",
            '-' * 80 + '\n',
            "**>>>STEAM MUST BE RUNNING!<<<**",
            "**>>>BATTLEYE DISABLED!<<<**\n",
            '-' * 80 + '\n',
            "**Prerequisites:**",
            "Visual C++ Redistributable Runtimes All-in-One",
            "<https://www.techpowerup.com/download/visual-c-redistributable-runtime-package-all-in-one/>\n",
            f"**Arma 3 {arma_version}**",
            "(Without CDLC's)",
            f"Download link: <{arma_link}>",
            "(Yes, you need all 9!)\n",
        ]

        preset_mods = preset_info.get('mods', [])
        cdlc_keys = [m for m in preset_mods if (m in CDLC_KEYS or isinstance(m, int)) and self.get_cdlc_info(m)]
        if cdlc_keys:
            parts.append("**Required CDLCs:**\n")
            for key in cdlc_keys:
                info = self.get_cdlc_info(key)
                desc = info.get('description', str(key).upper())
                parts.append(f"**{desc}**")
                self._append_download_link_lines(parts, info.get('link', 'N/A'))
                if info.get('pwd'):
                    parts.append(f"Password: {info['pwd']}")
                parts.append("")

        regular_mods = [m for m in preset_mods if m not in cdlc_keys]
        if regular_mods:
            parts.append("**Server-specific Mods (A-Z):**\n")
            for mod in sorted(regular_mods, key=self.sort_key_ignore_at):
                links = self.get_download_links(mod)
                if mod.lower() in ("@ace", "ace") and links:
                    parts.append("**ACE Medical & Advanced Combat Environment**")
                    for link in links:
                        parts.append(f"Download: <{link}>")
                    parts.append("(ace_nouniformrestrictions is in @ace\\optionals\\@ace_nouniformrestrictions)\n")
                elif mod.lower() == "@ace_nouniformrestrictions":
                    parts.append("**@ace_nouniformrestrictions:** <@ace/optionals/>\n")
                elif links:
                    if len(links) == 1:
                        parts.append(f"**{mod}:** <{links[0]}>\n")
                    else:
                        parts.append(f"**{mod}**")
                        for link in links:
                            parts.append(f"Download: <{link}>")
                        parts.append("")
                else:
                    parts.append(f"**{mod}** - Download link not available\n")

        parts.append("\n**Optional mods:**\n")
        for mod_name, link in self.content_links.get('optionals', {}).items():
            if isinstance(link, list):
                parts.append(f"**{mod_name}**")
                for l in link:
                    parts.append(f"Download: <{l}>")
                parts.append("")
            else:
                parts.append(f"**{mod_name}:** <{link}>\n")

        return "\n".join(parts)


__all__ = ["ModListGenerator"]
