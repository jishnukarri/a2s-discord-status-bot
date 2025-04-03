# web/gui.py
import os
import json
import sqlite3
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinterdnd2 import TkinterDnD, DND_FILES
import customtkinter as ctk
from ..src.bot.database import JSONDatabase
from ..src.bot.utils import sanitize_input

class MigrationGUI:
    def __init__(self):
        self.root = TkinterDnD.Tk()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.root.title("Database Migration Tool 2025")
        self.root.geometry("1200x800")
        
        self.frame = ctk.CTkFrame(self.root, corner_radius=20)
        self.frame.pack(padx=20, pady=20, fill="both", expand=True)
        
        self.header = ctk.CTkLabel(
            self.frame, 
            text="SQLite → JSON Migration", 
            font=("Arial Bold", 28),
            text_color="#6A5ACD"
        )
        self.header.pack(pady=20)
        
        self.drop_zone = ctk.CTkLabel(
            self.frame,
            text="Drop SQLite DB Here",
            fg_color="#333333",
            corner_radius=10,
            height=100,
            font=("Arial", 16)
        )
        self.drop_zone.pack(padx=20, pady=10, fill="x")
        self.drop_zone.drop_target_register(DND_FILES)
        self.drop_zone.dnd_bind('<<Drop>>', self.handle_drop)
        
        self.status = ctk.CTkTextbox(
            self.frame,
            height=150,
            state="disabled",
            fg_color="#2D2D2D"
        )
        self.status.pack(padx=20, pady=10, fill="x")
        
        self.convert_btn = ctk.CTkButton(
            self.frame,
            text="Convert Database",
            command=self.start_conversion,
            height=50,
            font=("Arial Bold", 18)
        )
        self.convert_btn.pack(pady=20)
        
        self.progress = ctk.CTkProgressBar(
            self.frame,
            width=400
        )
        self.progress.pack(pady=10)
        self.progress.set(0)
        
        self.sqlite_path = None
        self.json_path = None

    def log(self, message):
        self.status.configure(state="normal")
        self.status.insert("end", f"> {message}\n")
        self.status.see("end")
        self.status.configure(state="disabled")

    def handle_drop(self, event):
        self.sqlite_path = event.data.strip('{}')
        self.log(f"Detected SQLite file: {os.path.basename(self.sqlite_path)}")
        self.drop_zone.configure(text=f"Ready: {os.path.basename(self.sqlite_path)}")

    def start_conversion(self):
        if not self.sqlite_path:
            messagebox.showerror("Error", "No SQLite file selected")
            return
            
        try:
            self.progress.start()
            self.log("Starting database migration...")
            
            # Create JSON database instance
            self.json_path = os.path.join(
                os.path.dirname(self.sqlite_path),
                f"migrated_{os.path.basename(self.sqlite_path).replace('.db', '.json')}"
            )
            json_db = JSONDatabase(self.json_path)
            
            # Migrate data
            conn = sqlite3.connect(self.sqlite_path)
            cursor = conn.cursor()
            
            # Migrate messages table
            cursor.execute("SELECT * FROM messages")
            for row in cursor.fetchall():
                json_db.save_message(row[1], row[2], row[3])
            
            # Migrate leaderboard tables
            cursor.execute("SELECT * FROM leaderboard")
            for row in cursor.fetchall():
                # Convert SQLite data to JSON format
                stats = {
                    "kills": row[1],
                    "time_played": row[2],
                    "last_seen": row[3],
                    "last_kill_update": row[4],
                    "current_session_kills": row[5]
                }
                json_db.update("leaderboard", {row[0]: stats})
            
            cursor.execute("SELECT * FROM monthly_leaderboard")
            for row in cursor.fetchall():
                stats = {
                    "kills": row[1],
                    "time_played": row[2],
                    "month": row[3]
                }
                json_db.update("monthly_leaderboard", {row[0]: stats})
            
            self.log("Migration completed successfully")
            self.progress.stop()
            self.progress.set(1)
            
            # Show completion message
            messagebox.showinfo(
                "Success",
                f"Database migrated to:\n{self.json_path}"
            )
            
        except Exception as e:
            self.log(f"ERROR: {str(e)}")
            messagebox.showerror("Migration Error", str(e))
            self.progress.stop()

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    # Check dependencies on startup
    try:
        import sqlite3
        import customtkinter
    except ImportError as e:
        messagebox.showerror(
            "Dependency Error",
            f"Missing required modules: {e}\n\n"
            "Please install dependencies using:\n"
            "pip install -r requirements.txt"
        )
        sys.exit(1)
        
    app = MigrationGUI()
    app.run()