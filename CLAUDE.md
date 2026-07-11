# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A2S is a Discord bot for a private Arma 3 / Source-engine community server. It posts and continuously
updates two pinned embeds in a Discord channel (server status + player leaderboard), and provides slash
commands for fetching mod lists and Creator DLC download info.

This is a clean rewrite of an earlier implementation kept under [archived/](archived/) for reference —
the user-facing behavior (commands, embeds, admin commands) is unchanged, but the code has been
reorganized into a proper `app/` package with fixed imports, deduplicated logic, Sentry-based error
reporting instead of local log files, and Docker Compose support for two configuration styles.
[archived/](archived/) is historical only — do not import from it or treat it as live code (it doesn't
even run: every module there imports from a nonexistent `old.*` package).

## Running

```
pip install -r requirements.txt
cp .env.example .env   # fill in API_KEY, CHANNEL_ID, SERVERS at minimum
python main.py
```

Docker (two variants — see README.md for details):
- `docker compose up --build` — uses a checked-out `.env` file (`docker-compose.yml`)
- `docker compose -f docker-compose.container-env.yml up --build` — expects config already present in
  the calling shell/orchestrator's environment, no `.env` file needed

Standalone executable build tooling from the old implementation was not carried over — `archived/build.py`
is reference only.

There are no automated tests, lint config, or CI in this repo.

## Architecture

- `app/config.py` — loads env vars (via `.env` or the process environment) into a single `CONFIG` dict,
  plus remote GitHub URLs (`CONTENT_URL`, `STEAM_URL`, `SERVERS_URL`) pointing at
  `Benkol003/CAC-Config` on GitHub. That external repo supplies mod/DLC download links (`content.json`),
  Steam mod ID mappings (`steam.json`), and the server preset list (`servers.json`) — all fetched at
  runtime and cached for 1 hour. `validate_config()` hard-fails fast on startup if `API_KEY`/`CHANNEL_ID`
  are missing.
- `app/logging_setup.py` — console logging only; ships warnings/errors to Sentry via `SENTRY_DSN` if set.
  There is intentionally no file handler / local log persistence.
- `app/models.py` — `PlayerStats` dataclass (kills, time played, session tracking) and
  `format_time_readable()`.
- `app/database.py` — raw `sqlite3` persistence (no ORM). Three tables: `messages` (tracks the
  persistent status/leaderboard embed message IDs so they survive restarts), `leaderboard` (all-time
  stats per player), `monthly_leaderboard` (stats scoped to a monthly period keyed by
  `MONTHLY_RESET_DAY`). `DATABASE_FILE` defaults to `database/bot_data.db`, which is the volume mounted
  by both Docker Compose files.
- `app/server_monitor.py` — `ServerMonitor` is the core stateful object: polls each configured server via
  the `a2s` (Source A2S query) protocol, holds `server_data` (live query results) and `player_stats` /
  `monthly_leaderboard` (accumulated via `DataManager`), and builds the two Discord embeds
  (`format_server_status()`, `format_leaderboard()`). Also detects Arma 3 servers and pulls extra rules
  data via `arma3query` (optional dependency, degrades gracefully if unavailable).
  - Kill/playtime tracking is delta-based against each player's last known in-session kill count and
    session duration reported by the server, with heuristics (`server_reset`, `rejoined`,
    `MISSION_SYNC_DELAY`) to avoid double-counting across mission restarts or player reconnects. This
    logic (`_apply_player_update`) is intentionally defensive/fragile — read it carefully before
    changing, since server-reported counters reset unpredictably on mission change.
- `app/preset_manager.py` — `PresetServerManager` fetches `servers.json` (server presets with mods list,
  address, password) and applies a `LOCAL_IP` override for any preset whose address contains `ddns`, for
  LAN-vs-WAN routing.
- `app/mod_generator.py` — `ModListGenerator` fetches `content.json`/`steam.json` and formats
  human-readable mod/CDLC install instructions (used by the `/server` and `/cdlc` slash commands).
- `app/commands.py` — `register_commands(bot, monitor, mod_generator)` wires up `/server`, `/cdlc` slash
  commands (with autocomplete) and `!reset_player` / `!leaderboard_info` prefix commands (admin-only via
  `commands.has_guild_permissions(administrator=True)`). Slash command responses are deferred ephemeral,
  then the actual content is DM'd to the invoking user in chunks (`_chunk_message`/`_send_as_dm`) to stay
  under Discord's 2000-char limit.
- `app/client.py` — `build_bot()` constructs the `discord.ext.commands.Bot`, registers commands, and
  defines `on_ready` (purges old bot messages, sends fresh status/leaderboard placeholders, starts the
  update loop). `status_update_loop()` is the single source of truth for the refresh loop — there is no
  duplicate/dead-code version like the old `bot.py` had.
- `main.py` — thin entrypoint: `setup_logging()` → `validate_config()` → `init_db()` → `build_bot()` →
  `bot.run()`.

## Optional VPN (Docker only)

`docker-compose.vpn.yml` is an overlay that puts the bot container entirely behind a WireGuard tunnel
(`network_mode: service:vpn` against a `linuxserver/wireguard` sidecar reading `wireguard.txt`, a
gitignored wg-quick config — see `wireguard.txt.example`). There is deliberately no host/python-level VPN
support — running `python main.py` directly never routes through a VPN, only
`docker compose -f docker-compose.yml -f docker-compose.vpn.yml up` (or the container-env base file) does.

## Data flow

1. `status_update_loop()` (in `app/client.py`) runs forever on `CONFIG['REFRESH_INTERVAL']`: queries all
   configured servers → updates player stats → edits the two persistent Discord embed messages →
   persists state to SQLite via `DataManager.save_leaderboard`.
2. Message IDs for the status/leaderboard embeds are saved in the `messages` table so the bot can find
   and update the same messages across restarts (`on_ready` also purges old bot messages in the channel
   first).
3. Slash commands (`/server`, `/cdlc`) pull from the community's external GitHub config repo, not from
   local files — expect network calls and 1-hour caching (`fetch_preset_servers`, `fetch_config_data`).
