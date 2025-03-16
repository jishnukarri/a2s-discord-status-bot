import os
import PyInstaller.__main__

# Configuration
SCRIPT_NAME = "bot.py"
ICON_PATH = r"D:\Github Projects\a2s-discord-status-bot\icon.ico"  # Optional: Path to your icon file

# Output directories
OUTPUT_DIR_BACKGROUND = "build/background"
OUTPUT_DIR_CONSOLE = "build/console"

# Create output directories if they don't exist
os.makedirs(OUTPUT_DIR_BACKGROUND, exist_ok=True)
os.makedirs(OUTPUT_DIR_CONSOLE, exist_ok=True)

# Build the background version (no console)
print("Building background version (no console)...")
PyInstaller.__main__.run([
    '--onefile',
    '--noconsole',  # No console window
    '--distpath', OUTPUT_DIR_BACKGROUND,
    '--workpath', os.path.join(OUTPUT_DIR_BACKGROUND, 'temp'),
    '--specpath', OUTPUT_DIR_BACKGROUND,
    '--icon', ICON_PATH,  # Optional: Add an icon
    SCRIPT_NAME
])

# Build the normal version (with console)
print("Building normal version (with console)...")
PyInstaller.__main__.run([
    '--onefile',
    '--distpath', OUTPUT_DIR_CONSOLE,
    '--workpath', os.path.join(OUTPUT_DIR_CONSOLE, 'temp'),
    '--specpath', OUTPUT_DIR_CONSOLE,
    '--icon', ICON_PATH,  # Optional: Add an icon
    SCRIPT_NAME
])

print("Build completed successfully!")