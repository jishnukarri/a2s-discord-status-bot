# migrations/sqlite_to_json.py

import os
import json
import sqlite3
from datetime import datetime

def migrate_database(sqlite_db_path, json_db_path):
    """
    Migrates data from an SQLite database to a JSON file.
    
    Args:
        sqlite_db_path (str): Path to the SQLite database file.
        json_db_path (str): Path to the target JSON file.
    """
    print("Starting database migration...")
    
    # Ensure SQLite database exists
    if not os.path.exists(sqlite_db_path):
        raise FileNotFoundError(f"SQLite database not found at: {sqlite_db_path}")
    
    # Connect to SQLite database
    conn = sqlite3.connect(sqlite_db_path)
    cursor = conn.cursor()
    
    # Initialize JSON structure
    json_data = {
        "messages": {},
        "leaderboard": {},
        "monthly_leaderboard": []
    }
    
    try:
        # Migrate messages table
        cursor.execute("SELECT message_type, message_id, channel_id FROM messages")
        for row in cursor.fetchall():
            message_type, message_id, channel_id = row
            json_data["messages"][message_type] = {
                "message_id": str(message_id),
                "channel_id": str(channel_id)
            }
        
        # Migrate leaderboard table
        cursor.execute("SELECT player_name, kills, time_played, last_seen, last_kill_update, current_session_kills FROM leaderboard")
        for row in cursor.fetchall():
            player_name, kills, time_played, last_seen, last_kill_update, current_session_kills = row
            json_data["leaderboard"][player_name] = {
                "kills": kills,
                "time_played": time_played,
                "last_seen": last_seen,
                "last_kill_update": last_kill_update,
                "current_session_kills": current_session_kills
            }
        
        # Migrate monthly leaderboard table
        cursor.execute("SELECT month, player_name, kills, time_played FROM monthly_leaderboard")
        monthly_entries = {}
        for row in cursor.fetchall():
            month, player_name, kills, time_played = row
            if month not in monthly_entries:
                monthly_entries[month] = {}
            monthly_entries[month][player_name] = {
                "kills": kills,
                "time_played": time_played
            }
        
        json_data["monthly_leaderboard"] = [
            {"month": month, "stats": stats}
            for month, stats in monthly_entries.items()
        ]
        
        # Write data to JSON file
        with open(json_db_path, 'w') as f:
            json.dump(json_data, f, indent=2)
        
        print(f"Database successfully migrated to: {json_db_path}")
    
    except Exception as e:
        print(f"Error during migration: {str(e)}")
        raise
    
    finally:
        conn.close()

if __name__ == "__main__":
    # Example usage
    SQLITE_DB_PATH = "old_bot_data.db"
    JSON_DB_PATH = "data.json"
    
    migrate_database(SQLITE_DB_PATH, JSON_DB_PATH)