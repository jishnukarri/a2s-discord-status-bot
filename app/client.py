"""Bot entrypoint: wires together config, database, monitor and commands, then
runs the Discord client and the background status-update loop.
"""
from __future__ import annotations
import asyncio
import logging

import discord
from discord.ext import commands

from .commands import register_commands
from .config import CONFIG, validate_config
from .database import init_db, DataManager
from .logging_setup import setup_logging
from .mod_generator import ModListGenerator
from .server_monitor import ServerMonitor


def build_bot() -> tuple[commands.Bot, ServerMonitor]:
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix='!', intents=intents)

    monitor = ServerMonitor()
    mod_generator = ModListGenerator()
    register_commands(bot, monitor, mod_generator)

    @bot.event
    async def on_ready():
        logging.info('Logged in as %s', bot.user)
        try:
            synced = await bot.tree.sync()
            logging.info('Synced %d command(s)', len(synced))
        except Exception:
            logging.exception('Command sync failed')

        # Warm the GitHub config caches in the background so the first
        # /server or /cdlc autocomplete after a restart isn't served from an
        # empty cache (autocomplete never awaits these fetches directly -
        # see app/commands.py - since a cold fetch can take longer than
        # Discord's ~3s autocomplete response budget).
        bot.loop.create_task(monitor.preset_manager.fetch_preset_servers())
        bot.loop.create_task(mod_generator.fetch_config_data())

        channel = bot.get_channel(CONFIG['CHANNEL_ID'])
        if not channel:
            logging.error('Channel ID %s not found', CONFIG['CHANNEL_ID'])
            return

        async for message in channel.history(limit=100):
            if message.author == bot.user:
                await message.delete()

        monitor.leaderboard_message = await channel.send('Initializing leaderboard...')
        DataManager.save_message(monitor.leaderboard_message.id, CONFIG['CHANNEL_ID'], 'leaderboard')

        monitor.status_message = await channel.send('Initializing server status...')
        DataManager.save_message(monitor.status_message.id, CONFIG['CHANNEL_ID'], 'status')

        bot.loop.create_task(status_update_loop(monitor))

    return bot, monitor


async def status_update_loop(monitor: ServerMonitor) -> None:
    while True:
        try:
            await monitor.update_all_servers()
        except Exception:
            logging.exception('Error updating servers')

        for message, formatter in (
            (monitor.leaderboard_message, monitor.format_leaderboard),
            (monitor.status_message, monitor.format_server_status),
        ):
            if not message:
                continue
            try:
                await message.edit(content='', embed=formatter())
            except Exception:
                logging.exception('Error updating message %s', message.id)

        await asyncio.sleep(CONFIG['REFRESH_INTERVAL'])


def main() -> None:
    setup_logging()
    validate_config()
    init_db()
    bot, _monitor = build_bot()
    bot.run(CONFIG['API_KEY'], log_handler=None)


if __name__ == '__main__':
    main()
