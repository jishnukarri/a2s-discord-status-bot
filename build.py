import os
import PyInstaller.__main__

# Configuration
SCRIPT_NAME = "bot.py"  # Replace with your main script file
ICON_PATH = r"icon.ico"  # Replace with the path to your icon file (optional)
VERSION_FILE = r"version.txt"  # Path to the version file

# Output directories
OUTPUT_DIR_BACKGROUND = "build/background"
OUTPUT_DIR_CONSOLE = "build/console"

# Create output directories if they don't exist
os.makedirs(OUTPUT_DIR_BACKGROUND, exist_ok=True)
os.makedirs(OUTPUT_DIR_CONSOLE, exist_ok=True)

# Include version.txt in the build
if os.path.exists(VERSION_FILE):
    print(f"Including {VERSION_FILE} in the build...")
else:
    print(f"Warning: {VERSION_FILE} not found. Skipping version information.")

# Build the background version (no console)
print("Building background version (no console)...")
PyInstaller.__main__.run([
    '--onefile',  # Package into a single executable
    '--noconsole',  # No console window
    '--distpath', OUTPUT_DIR_BACKGROUND,
    '--workpath', os.path.join(OUTPUT_DIR_BACKGROUND, 'temp'),
    '--specpath', OUTPUT_DIR_BACKGROUND,
    '--icon', ICON_PATH,  # Optional: Add an icon
    '--add-data', f'{VERSION_FILE}:.',  # Include version.txt in the build
    SCRIPT_NAME
])

# Build the normal version (with console)
print("Building normal version (with console)...")
PyInstaller.__main__.run([
    '--onefile',  # Package into a single executable
    '--distpath', OUTPUT_DIR_CONSOLE,
    '--workpath', os.path.join(OUTPUT_DIR_CONSOLE, 'temp'),
    '--specpath', OUTPUT_DIR_CONSOLE,
    '--icon', ICON_PATH,  # Optional: Add an icon
    '--add-data', f'{VERSION_FILE}:.',  # Include version.txt in the build
    SCRIPT_NAME
])

print("Build completed successfully!")