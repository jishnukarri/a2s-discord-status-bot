# A2S Discord Server Status Bot

A Discord bot for a Source-engine / Arma 3 community server. It posts and continuously updates two
pinned embeds (live server status + player leaderboard) and provides `/server` and `/cdlc` slash
commands for mod list and Creator DLC download info.

## Features
- Live server status embed (map, player list, mission state) for one or more configured servers
- All-time and monthly player leaderboard (kills, time played), persisted in SQLite
- `/server` - DMs the mod/CDLC install list for a community-configured server
- `/cdlc` - DMs Arma 3 Creator DLC download info
- `!reset_player` / `!leaderboard_info` admin-only prefix commands
- Errors reported to Sentry.io - no local log files

## Project layout
```
app/                  bot package
  config.py           env var loading + validation
  logging_setup.py     console + Sentry logging
  models.py            PlayerStats, time formatting
  database.py           sqlite persistence
  preset_manager.py     fetches server presets from the community GitHub config repo
  mod_generator.py      builds mod/CDLC install text
  server_monitor.py     polls servers, tracks stats, builds embeds
  commands.py            slash + prefix command handlers
  client.py               bot wiring, on_ready, update loop
main.py                entrypoint (python main.py)
database/              sqlite volume (gitignored, mounted in Docker)
wireguard.txt.example   template for the optional VPN overlay (Docker only, see below)
archived/               previous implementation, kept for reference only
```

## Running locally
```
pip install -r requirements.txt
cp .env.example .env   # fill in API_KEY, CHANNEL_ID, SERVERS, ...
python main.py
```

## Running with Docker

Two compose files are provided depending on how you want to supply configuration:

**`docker-compose.yml`** - copy the repo, fill in `.env`, and go:
```
cp .env.example .env   # fill in your values
docker compose up --build
```

**`docker-compose.container-env.yml`** - for deployments where the host/orchestrator already injects
environment variables (CI, systemd, Portainer stacks, etc.) instead of a checked-in `.env` file. Export
the variables listed in `.env.example` in the calling shell/orchestrator, then:
```
docker compose -f docker-compose.container-env.yml up --build
```

Both mount `./database` for the SQLite file and expect an `API_KEY`, `CHANNEL_ID`, and `SERVERS` at
minimum. See `.env.example` for the full list of configuration keys.

### Optional: routing all traffic through WireGuard (Docker only)

`docker-compose.vpn.yml` is an overlay that puts the bot container entirely behind a WireGuard tunnel
(Discord API, A2S server queries, and the GitHub config fetches all go through it). There is no
host/python-level equivalent - running `python main.py` directly does not route through a VPN. Copy
`wireguard.txt.example` to `wireguard.txt` (gitignored - it holds your private key) and fill in your
peer config, then layer the overlay on top of whichever base compose file you're using:
```
cp wireguard.txt.example wireguard.txt   # fill in your WireGuard config
docker compose -f docker-compose.yml -f docker-compose.vpn.yml up --build
# or
docker compose -f docker-compose.container-env.yml -f docker-compose.vpn.yml up --build
```
This is entirely optional - omit `-f docker-compose.vpn.yml` to run without a VPN.

## Logging

There is no local log file. Console output goes to stdout/`docker compose logs`; warnings and errors are
additionally sent to Sentry when `SENTRY_DSN` is set.

## Requirements
- Python 3.11+ (or Docker)
- Discord bot token
- Game server access
