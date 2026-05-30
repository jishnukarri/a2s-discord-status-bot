"""Mod list and DLC download text generation.

Provides ModListGenerator with caching of remote content and steam metadata.
"""
from __future__ import annotations
import datetime
import asyncio
import logging
import requests
from typing import Dict, Any, List
from old.config import CONTENT_URL, STEAM_URL

class ModListGenerator:
    def __init__(self) -> None:
        self.steam_mods: Dict[str, Any] = {}
        self.content_links: Dict[str, Any] = {}
        self.last_config_update: datetime.datetime = datetime.datetime.min
        self.cache_ttl_seconds = 3600

    def _append_download_link_lines(self, parts: List[str], link_value: Any, *, single_label: str = "Download") -> None:
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

    async def fetch_config_data(self) -> None:
        now = datetime.datetime.now()
        if (now - self.last_config_update).total_seconds() < self.cache_ttl_seconds:
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
        except Exception as e:
            logging.error("Failed fetching mod configuration: %s", e)

    # ---------- Lookup helpers ----------
    def get_mod_name_from_steam_id(self, steam_id: int) -> str | None:
        for mod_name, mod_id in self.steam_mods.get('mods', {}).items():
            if isinstance(mod_id, int) and mod_id == steam_id:
                return mod_name
        return None

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
        normalized = self.normalize_mod_name(mod_name)
        val = mods.get(normalized)
        if isinstance(val, list):
            return val
        if isinstance(val, str):
            return [val]
        return None

    def sort_key_ignore_at(self, mod_name: str) -> str:
        return mod_name.lstrip('@').lower()

    def get_mod_display_name(self, mod_name: str) -> str:
        return mod_name

    # ---------- DLC helpers ----------
    def get_cdlc_info(self, key_or_id) -> Dict[str, Any] | None:
        # Accept short key (rf/ws/spe) or numeric steam id
        dlc_cfg = self.content_links.get('dlc', {})
        if isinstance(key_or_id, str):
            key = key_or_id.lower()
            return dlc_cfg.get(key)
        if isinstance(key_or_id, int):
            # Reverse map from steam ids if present
            steam_dlc = self.steam_mods.get('dlc', {})
            for k, v in steam_dlc.items():
                if v == key_or_id:
                    return dlc_cfg.get(k)
        return None

    # ---------- Message generation ----------
    async def generate_preset_server_mod_list(self, server_name: str, preset_info: Dict[str, Any]) -> str:
        await self.fetch_config_data()
        arma_info = self.content_links.get('arma', {})
        arma_version = arma_info.get('version', 'v2.20.152984')
        arma_link = arma_info.get('link', 'https://tinyurl.com/33taw7ds')

        parts: List[str] = []
        parts.append(f"**{server_name}**\n")
        parts.append(f"Server version: **{arma_version}**")
        parts.append(f"Required game version: **{arma_version}**\n")
        parts.append('-' * 80 + '\n')
        parts.append(f"Location: {preset_info.get('country', 'Unknown')}\n")
        parts.append('-' * 80 + '\n')
        parts.append("**>>>STEAM MUST BE RUNNING!<<<**")
        parts.append("**>>>BATTLEYE DISABLED!<<<**\n")
        parts.append('-' * 80 + '\n')
        parts.append("**Prerequisites:**")
        parts.append("Visual C++ Redistributable Runtimes All-in-One")
        parts.append("<https://www.techpowerup.com/download/visual-c-redistributable-runtime-package-all-in-one/>\n")
        parts.append(f"**Arma 3 {arma_version}**")
        parts.append("(Without CDLC's)")
        parts.append(f"Download link: <{arma_link}>")
        parts.append("(Yes, you need all 9!)\n")

        # DLCs
        preset_mods = preset_info.get('mods', [])
        cdlc_keys = []
        for m in preset_mods:
            if m in ['rf', 'ws', 'spe', 'gm', 'vn', 'csla'] or isinstance(m, int):
                if self.get_cdlc_info(m):
                    cdlc_keys.append(m)
        if cdlc_keys:
            parts.append("**Required CDLCs:**\n")
            for c in cdlc_keys:
                info = self.get_cdlc_info(c)
                if not info:
                    continue
                desc = info.get('description', str(c).upper())
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
                disp = self.get_mod_display_name(mod)
                if mod.lower() in ["@ace", "ace"] and links:
                    parts.append("**ACE Medical & Advanced Combat Environment**")
                    for l in links:
                        parts.append(f"Download: <{l}>")
                    parts.append("(ace_nouniformrestrictions is in @ace\\optionals\\@ace_nouniformrestrictions)\n")
                elif mod.lower() == "@ace_nouniformrestrictions":
                    parts.append("**@ace_nouniformrestrictions:** <@ace/optionals/>\n")
                elif links:
                    if len(links) == 1:
                        parts.append(f"**{disp}:** <{links[0]}>\n")
                    else:
                        parts.append(f"**{disp}**")
                        for l in links:
                            parts.append(f"Download: <{l}>")
                        parts.append("")
                else:
                    parts.append(f"**{disp}** - Download link not available\n")

        parts.append("\n**Optional mods:**\n")
        for mod_name, link in self.content_links.get('optionals', {}).items():
            disp = self.get_mod_display_name(mod_name)
            if isinstance(link, list):
                parts.append(f"**{disp}**")
                for l in link:
                    parts.append(f"Download: <{l}>")
                parts.append("")
            else:
                parts.append(f"**{disp}:** <{link}>\n")

        return "\n".join(parts)

__all__ = ["ModListGenerator"]
