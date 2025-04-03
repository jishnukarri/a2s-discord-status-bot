import os
import sys
import platform
import subprocess
import shutil

# Build configuration
APP_NAME = "ServerMonitorBot"
MAIN_SCRIPT = "bot.py"  # Entry point for the bot
BUILD_DIR = "build"      # Directory to store build artifacts
ICON_PATH = "icon.ico"   # Optional: Icon file for Windows/macOS

def clean_previous_build():
    """
    Remove old build artifacts to ensure a clean build process.
    Deletes `build`, `dist`, and `.spec` files if they exist.
    """
    print("Cleaning previous build artifacts...")
    for folder in ["build", "dist", f"{APP_NAME}.spec"]:
        if os.path.exists(folder):
            if os.path.isdir(folder):
                shutil.rmtree(folder)
            else:
                os.remove(folder)

def get_platform_details():
    """
    Determine the current platform and return platform-specific settings.
    Returns:
        platform_dir (str): Directory name for the platform (e.g., 'windows', 'macos', 'linux').
        executable_name (str): Name of the executable with the appropriate extension.
    """
    system = platform.system().lower()
    platform_map = {
        "windows": ("windows", f"{APP_NAME}.exe"),
        "darwin": ("macos", APP_NAME),
        "linux": ("linux", APP_NAME)
    }
    return platform_map.get(system, (system, APP_NAME))

def build_executable():
    """
    Build the bot executable using PyInstaller.
    Handles platform-specific configurations and outputs the executable to the build directory.
    """
    print("Starting build process...")
    clean_previous_build()

    # Get platform-specific details
    platform_dir, executable_name = get_platform_details()

    # Construct PyInstaller command
    pyinstaller_cmd = [
        "pyinstaller",
        "--name", APP_NAME,
        "--onefile",  # Single executable output
        MAIN_SCRIPT
    ]

    # Add icon if it exists and is relevant to the platform
    if os.path.exists(ICON_PATH) and platform_dir in ["windows", "macos"]:
        pyinstaller_cmd.extend(["--icon", ICON_PATH])

    try:
        # Run PyInstaller
        print("Running PyInstaller...")
        subprocess.run(pyinstaller_cmd, check=True)

        # Create platform-specific output directory
        output_dir = os.path.join(BUILD_DIR, platform_dir)
        os.makedirs(output_dir, exist_ok=True)

        # Move the built executable to the output directory
        src_path = os.path.join("dist", executable_name)
        dest_path = os.path.join(output_dir, executable_name)
        shutil.move(src_path, dest_path)
        print(f"Executable moved to: {dest_path}")

        # Copy .env file if it exists
        if os.path.exists(".env"):
            shutil.copy(".env", output_dir)
            print(".env file copied to build directory.")

        print(f"Build successful for {platform_dir}!")

    except subprocess.CalledProcessError as e:
        print(f"Build failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    build_executable()