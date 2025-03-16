import os
import PyInstaller.__main__

# Configuration
SCRIPT_NAME = "bot.py"  # Replace with your main script file
ICON_PATH_BACKGROUND = "build/background/icon.ico"  # Path to icon in background directory
ICON_PATH_CONSOLE = "build/console/icon.ico"  # Path to icon in console directory

# Output directories
OUTPUT_DIR_BACKGROUND = "build/background"
OUTPUT_DIR_CONSOLE = "build/console"

# Create output directories if they don't exist
os.makedirs(OUTPUT_DIR_BACKGROUND, exist_ok=True)
os.makedirs(OUTPUT_DIR_CONSOLE, exist_ok=True)

# Build the background version (no console)
print("Building background version (no console)...")
PyInstaller.__main__.run([
    '--onefile',  # Package into a single executable
    '--noconsole',  # No console window
    '--distpath', OUTPUT_DIR_BACKGROUND,
    '--workpath', os.path.join(OUTPUT_DIR_BACKGROUND, 'temp'),
    '--specpath', OUTPUT_DIR_BACKGROUND,
    '--icon', ICON_PATH_BACKGROUND,  # Use icon in background directory
    SCRIPT_NAME
])

# Build the normal version (with console)
print("Building normal version (with console)...")
PyInstaller.__main__.run([
    '--onefile',  # Package into a single executable
    '--distpath', OUTPUT_DIR_CONSOLE,
    '--workpath', os.path.join(OUTPUT_DIR_CONSOLE, 'temp'),
    '--specpath', OUTPUT_DIR_CONSOLE,
    '--icon', ICON_PATH_CONSOLE,  # Use icon in console directory
    SCRIPT_NAME
])

print("Build completed successfully!")