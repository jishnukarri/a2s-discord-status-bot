import os
import sys
import platform
import subprocess
import shutil

# Configuration for the build process
APP_NAME = "ServerMonitorBot"
MAIN_SCRIPT = "bot.py"
BUILD_DIR = "build"
ICON_PATH = r"icon.ico"

def clean_build():
    """Remove previous build artifacts."""
    for folder in ["build", "dist", f"{APP_NAME}.spec"]:
        if os.path.exists(folder):
            if os.path.isdir(folder):
                shutil.rmtree(folder)
            else:
                os.remove(folder)

def build_executable():
    """Build the executable with JSON database support."""
    system = platform.system().lower()
    clean_build()
    
    pyinstaller_cmd = [
        "pyinstaller",
        "--name", APP_NAME,
        "--onefile",
        "--add-data", f"database{os.pathsep}database",  # Include database directory
        "--icon", ICON_PATH,
        MAIN_SCRIPT
    ]
    
    try:
        subprocess.run(pyinstaller_cmd, check=True)
        platform_dir = {
            "windows": "win",
            "darwin": "macos",
            "linux": "linux"
        }[system]
        
        output_dir = os.path.join(BUILD_DIR, platform_dir)
        os.makedirs(output_dir, exist_ok=True)
        
        # Move executable and .env
        shutil.move(
            os.path.join("dist", f"{APP_NAME}.exe" if system == "windows" else APP_NAME),
            os.path.join(output_dir, f"{APP_NAME}.exe" if system == "windows" else APP_NAME)
        )
        
        if os.path.exists(".env"):
            shutil.copy(".env", output_dir)
        
        print(f"Build successful for {system}!")
    
    except subprocess.CalledProcessError as e:
        print(f"Build failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    build_executable()