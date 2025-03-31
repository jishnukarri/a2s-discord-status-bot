import os
import sys
import platform
import subprocess
import shutil

# Configuration
APP_NAME = "ServerMonitorBot"
MAIN_SCRIPT = "bot.py"  # Your main bot script
BUILD_DIR = "build"    # Changed from "dist" to "build"
ICON_PATH = r"icon.ico" # Optional: Add an icon file for Windows/macOS

def clean_build():
    """Remove previous build artifacts"""
    for folder in ["build", BUILD_DIR, f"{APP_NAME}.spec"]:
        if os.path.exists(folder):
            if os.path.isdir(folder):
                shutil.rmtree(folder)
            else:
                os.remove(folder)

def build_executable():
    """Build the executable for the current platform"""
    system = platform.system().lower()
    clean_build()

    pyinstaller_cmd = [
        "pyinstaller",
        "--name", APP_NAME,
        "--onefile",
        "--hidden-import", "a2s",       # Explicitly include a2s
        "--hidden-import", "sqlite3",   # Include sqlite3
        "--add-data", f".env{os.pathsep}.",  # Bundle .env file
        "--add-data", f"icon.ico{os.pathsep}.",  # Bundle icon (if used)
        MAIN_SCRIPT
    ]
    if system == "windows" and os.path.exists(ICON_PATH):
        pyinstaller_cmd.extend(["--icon", ICON_PATH])
    elif system == "darwin" and os.path.exists(ICON_PATH):
        pyinstaller_cmd.extend(["--icon", ICON_PATH])

    try:
        subprocess.run(pyinstaller_cmd, check=True)
        print(f"Successfully built {APP_NAME} for {system}")
        
        # Define platform-specific output directory
        platform_dir_map = {
            "windows": "windows",
            "darwin": "macos",
            "linux": "linux"
        }
        platform_dir = platform_dir_map.get(system, system)
        output_dir = os.path.join(BUILD_DIR, platform_dir)
        os.makedirs(output_dir, exist_ok=True)

        # Move the executable
        src = os.path.join("dist", APP_NAME)
        if system == "windows":
            src += ".exe"
            dest = os.path.join(output_dir, f"{APP_NAME}.exe")
        else:
            dest = os.path.join(output_dir, APP_NAME)
        
        shutil.move(src, dest)
        
        # Copy .env file if it exists
        if os.path.exists(".env"):
            shutil.copy(".env", output_dir)
            
    except subprocess.CalledProcessError as e:
        print(f"Build failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    build_executable()