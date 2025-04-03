import os
import json
import sqlite3
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinterdnd2 import TkinterDnD, DND_FILES
import customtkinter as ctk
from datetime import datetime

class DatabaseMigratorGUI:
    def __init__(self):
        self.root = TkinterDnD.Tk()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.root.title("DB Migration Tool 2025")
        self.root.geometry("800x600")
        
        self.frame = ctk.CTkFrame(self.root, corner_radius=20)
        self.frame.pack(padx=20, pady=20, fill="both", expand=True)
        
        self.drop_zone = ctk.CTkLabel(
            self.frame,
            text="Drop SQLite DB Here",
            fg_color="#333333",
            corner_radius=10,
            height=100
        )
        self.drop_zone.pack(padx=20, pady=10, fill="x")
        self.drop_zone.drop_target_register(DND_FILES)
        self.drop_zone.dnd_bind('<<Drop>>', self.handle_drop)
        
        self.status = ctk.CTkTextbox(
            self.frame,
            state="disabled",
            fg_color="#2D2D2D",
            height=200
        )
        self.status.pack(padx=20, pady=10, fill="x")
        
        self.convert_btn = ctk.CTkButton(
            self.frame,
            text="Convert to JSON",
            command=self.start_migration,
            height=50
        )
        self.convert_btn.pack(pady=20)
        
        self.progress = ctk.CTkProgressBar(self.frame, width=400)
        self.progress.pack(pady=10)
        self.progress.set(0)
        
        self.sqlite_path = None

    def log(self, message):
        self.status.configure(state="normal")
        self.status.insert("end", f"> {message}\n")
        self.status.configure(state="disabled")
        self.status.see("end")

    def handle_drop(self, event):
        self.sqlite_path = event.data.strip('{}')
        self.log(f"Detected file: {os.path.basename(self.sqlite_path)}")
        self.drop_zone.configure(text=f"Ready: {os.path.basename(self.sqlite_path)}")

    def start_migration(self):
        if not self.sqlite_path:
            messagebox.showerror("Error", "No SQLite file selected")
            return
        
        try:
            self.progress.start()
            self.log("Starting migration...")
            
            # Load SQLite data
            conn = sqlite3.connect(self.sqlite_path)
            cursor = conn.cursor()
            
            # Initialize JSON database
            json_db = JSONDatabase("migrated_data.json")
            
            # Migrate messages
            cursor.execute("SELECT message_id, channel_id, type FROM messages")
            for row in cursor.fetchall():
                json_db.update("messages", {row[2]: {"message_id": row[0], "channel_id": row[1]}})
            
            # Migrate leaderboard
            cursor.execute("SELECT player_name, kills, time_played, last_seen, last_kill_update, current_session_kills FROM leaderboard")
            for row in cursor.fetchall():
                stats = {
                    "kills": row[1],
                    "time_played": row[2],
                    "last_seen": row[3],
                    "last_kill_update": row[4],
                    "current_session_kills": row[5]
                }
                json_db.update("leaderboard", {row[0]: stats})
            
            # Migrate monthly leaderboards
            cursor.execute("SELECT player_name, kills, time_played, month FROM monthly_leaderboard")
            monthly_data = defaultdict(dict)
            for row in cursor.fetchall():
                monthly_data[row[3]][row[0]] = {"kills": row[1], "time_played": row[2]}
            
            for month, stats in monthly_data.items():
                json_db.update("monthly_leaderboards", {"month": month, "stats": stats})
            
            self.log("Migration completed successfully!")
            self.progress.stop()
            messagebox.showinfo("Success", f"Database migrated to: migrated_data.json")
        
        except Exception as e:
            self.log(f"ERROR: {str(e)}")
            messagebox.showerror("Migration Error", str(e))
            self.progress.stop()

if __name__ == "__main__":
    app = DatabaseMigratorGUI()
    app.root.mainloop()