import os
import PyInstaller.__main__

# Configuration
SCRIPT_NAME = "bot.py"  # Your main script
ICON_PATH = os.path.abspath("icon.ico")  # Absolute path to root icon

# Output directories
OUTPUT_DIR_BACKGROUND = os.path.abspath("build/background")
OUTPUT_DIR_CONSOLE = os.path.abspath("build/console")

# Create output directories
os.makedirs(OUTPUT_DIR_BACKGROUND, exist_ok=True)
os.makedirs(OUTPUT_DIR_CONSOLE, exist_ok=True)

# Build background version (no console)
print("Building background version...")
PyInstaller.__main__.run([
    '--onefile',
    '--noconsole',
    '--distpath', OUTPUT_DIR_BACKGROUND,
    '--workpath', os.path.join(OUTPUT_DIR_BACKGROUND, 'temp'),
    '--icon', ICON_PATH,  # Use root icon directly
    SCRIPT_NAME
])

# Build console version
print("Building console version...")
PyInstaller.__main__.run([
    '--onefile',
    '--distpath', OUTPUT_DIR_CONSOLE,
    '--workpath', os.path.join(OUTPUT_DIR_CONSOLE, 'temp'),
    '--icon', ICON_PATH,  # Use root icon directly
    SCRIPT_NAME
])

print("Build completed!")