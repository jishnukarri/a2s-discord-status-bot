import os
import sys
import platform
import subprocess
import shutil

# Configuration for the build process
APP_NAME = "ServerMonitorBot"
MAIN_SCRIPT = "bot.py"  # Main script to be built into an executable
BUILD_DIR = "build"    # Directory for build output
ICON_PATH = r"icon.ico"  # Optional: Icon file for Windows/macOS

# Minimal client requirements
CLIENT_REQUIREMENTS = [
    "discord.py==2.5.2",
    "python-a2s==1.4.1",
    "python-dotenv==1.1.0",
    "tabulate==0.9.0",
    "matplotlib==3.10.1"
]

def clean_build():
    """Remove previous build artifacts to ensure a clean slate."""
    for folder in ["build", BUILD_DIR, f"{APP_NAME}.spec"]:
        if os.path.exists(folder):
            if os.path.isdir(folder):
                shutil.rmtree(folder)
            else:
                os.remove(folder)

def install_client_dependencies():
    """Install only the dependencies required by the client."""
    print("Installing client dependencies...")
    subprocess.run([sys.executable, "-m", "pip", "install", *CLIENT_REQUIREMENTS], check=True)

def build_executable():
    """Build the executable for the current platform using PyInstaller."""
    system = platform.system().lower()
    clean_build()
    install_client_dependencies()

    pyinstaller_cmd = [
        "pyinstaller",
        "--name", APP_NAME,
        "--onefile",  # Package as a single executable
        "--clean",  # Ensure a clean build
        MAIN_SCRIPT
    ]

    # Add icon for Windows or macOS if it exists
    if system in ["windows", "darwin"] and os.path.exists(ICON_PATH):
        pyinstaller_cmd.extend(["--icon", ICON_PATH])

    try:
        print("Building executable...")
        subprocess.run(pyinstaller_cmd, check=True)
        print(f"Successfully built {APP_NAME} for {system}")

        # Set up platform-specific output directory
        platform_dir_map = {"windows": "windows", "darwin": "macos", "linux": "linux"}
        platform_dir = platform_dir_map.get(system, system)
        output_dir = os.path.join(BUILD_DIR, platform_dir)
        os.makedirs(output_dir, exist_ok=True)

        # Move executable to output directory
        src = os.path.join("dist", APP_NAME)
        dest = os.path.join(output_dir, f"{APP_NAME}.exe" if system == "windows" else APP_NAME)
        if system == "windows":
            src += ".exe"
        shutil.move(src, dest)

        # Copy .env file if present
        if os.path.exists(".env"):
            shutil.copy(".env", output_dir)

    except subprocess.CalledProcessError as e:
        print(f"Build failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    build_executable()