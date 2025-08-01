import asyncio
import arma3query
import json

# Known CDLC Steam IDs and their likely folder names
CDLC_STEAM_IDS = {
    1042220: "Global Mobilization",       # GM
    1227700: "S.O.G. Prairie Fire",       # SOG
    1294440: "CSLA Iron Curtain",         # CSLA
    1681170: "Western Sahara",            # WS
    1175380: "Spearhead 1944",            # SH1944
    2647760: "Reaction Forces",           # RF
    2647830: "Expeditionary Forces"       # XF
}

# Reverse map: folder name patterns to expected name
CDLC_NAME_HINTS = {
    "gm": "Global Mobilization",
    "sog": "S.O.G. Prairie Fire",
    "csla": "CSLA Iron Curtain",
    "ws": "Western Sahara",
    "sh1944": "Spearhead 1944",
    "rf": "Reaction Forces",
    "xf": "Expeditionary Forces"
}
# List of servers to query
servers = [
    {"name": "Antistasi 1", "address": ("unladencoconut.ddns.net", 3303)},
    {"name": "Antistasi 2", "address": ("unladencoconut.ddns.net", 2703)},
    {"name": "Liberation", "address": ("192.168.0.22", 3303)},
    {"name": "King of The Hill", "address": ("cackoth.servebeer.com", 2323)},
    {"name": "Exile", "address": ("rkb1.home.ro", 2403)},
    {"name": "Exile Escape", "address": ("", 2373)}  # Skip invalid
]
# Sets to collect data
mods_with_steamid = {}
mods_without_steamid = set()
cdlcs_detected = {}  # workshop_id -> name

async def query_server(server):
    addr = server["address"]
    print(f"Querying {server['name']} at {addr[0]}:{addr[1]}...")
    try:
        rules_data = await arma3query.arma3rules_async(addr)

        for mod in rules_data.mods:
            name = mod.name.strip()
            workshop_id = mod.workshop_id

            # Check if it's a known CDLC by Steam ID
            if isinstance(workshop_id, int) and workshop_id in CDLC_STEAM_IDS:
                cdlcs_detected[str(workshop_id)] = CDLC_STEAM_IDS[workshop_id]
                print(f"  🟢 CDLC detected: {name} -> {CDLC_STEAM_IDS[workshop_id]} ({workshop_id})")
                continue  # Don't add CDLCs to regular mod lists

            # Check by name hint
            name_lower = name.lower()
            matched_cdlc = None
            for key, cdlc_name in CDLC_NAME_HINTS.items():
                if key in name_lower:
                    matched_cdlc = cdlc_name
                    break
            if matched_cdlc:
                # Use placeholder ID if not known
                fake_id = f"unknown_{key.upper()}"
                cdlcs_detected[fake_id] = matched_cdlc
                print(f"  🟡 Possible CDLC by name: {name} -> {matched_cdlc} ({fake_id})")
                continue

            # Regular mods
            if isinstance(workshop_id, int) and workshop_id > 0:
                mods_with_steamid[name] = str(workshop_id)
            else:
                mods_without_steamid.add(name)

    except Exception as e:
        print(f"❌ Failed to query {server['name']}: {e}")

async def main():
    tasks = [query_server(s) for s in servers]
    await asyncio.gather(*tasks)

    # Final result
    result = {
        "mods_with_steamid": dict(sorted(mods_with_steamid.items())),
        "mods_without_steamid": sorted(mods_without_steamid),
        "cdlcs": dict(sorted(cdlcs_detected.items()))
    }

    print("\n✅ Final Result with CDLCs:")
    print(json.dumps(result, indent=2))

    # Optional: Save to file
    # with open("arma3_mods_with_cdlcs.json", "w") as f:
    #     json.dump(result, f, indent=2)

if __name__ == "__main__":
    asyncio.run(main())