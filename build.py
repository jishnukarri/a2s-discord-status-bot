import os
import sys
import platform
import subprocess
import shutil

# Configuration (Version now hardcoded in bot.py)
APP_NAME = "ServerMonitorBot"
MAIN_SCRIPT = "bot.py"
BUILD_DIR = "build"
DIST_DIR = "dist"
ICON_PATH = "icon.ico"
DATA_DIRS = ["database"]
ENV_TEMPLATE = ".env.example"

def clean_build_dirs():
    """Clean previous build artifacts"""
    print("Cleaning previous builds...")
    for dir_path in [BUILD_DIR, DIST_DIR]:
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)

def get_platform_info():
    """Get platform-specific settings"""
    return {
        "name": "windows",
        "icon_format": ".ico",
        "folder": "win",
        "ext": ".exe"
    }

def build_executable():
    """Build the executable using PyInstaller"""
    print("Starting build process...")
    
    platform_info = get_platform_info()
    executable_name = f"{APP_NAME}{platform_info['ext']}"
    
    # Create spec file content
    spec_content = f"""# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.building.build_main import Analysis, PYZ, EXE

block_cipher = None

a = Analysis(
    ['{MAIN_SCRIPT}'],
    pathex=['.'],
    binaries=[],
    datas=[{', '.join(f"('{d}', '{d}')" for d in DATA_DIRS)}],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    macosx_bundle_identifier=None
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='{executable_name}',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True
)
coll = a.collect(exe, name='{APP_NAME}')
"""

    with open(f"{APP_NAME}.spec", "w") as f:
        f.write(spec_content)

    # Build command
    build_cmd = [
        "pyinstaller",
        "--name", APP_NAME,
        "--specpath", BUILD_DIR,
        "--distpath", DIST_DIR,
        "--workpath", os.path.join(BUILD_DIR, "temp"),
        "--clean",
        "--noconfirm",
        "--onefile"
    ]

    # Handle icon only for Windows
    #if os.path.exists(ICON_PATH) and platform.system() == "Windows":
      #  build_cmd.extend(["--icon", ICON_PATH])

    build_cmd.append(MAIN_SCRIPT)

    try:
        print("Running PyInstaller...")
        subprocess.run(build_cmd, check=True)
        
        # Create output folder
        output_dir = os.path.join(BUILD_DIR, platform_info['folder'])
        os.makedirs(output_dir, exist_ok=True)
        
        # Move executable
        source_path = os.path.join(DIST_DIR, executable_name)
        target_path = os.path.join(output_dir, executable_name)
        shutil.move(source_path, target_path)

        # Copy data files
        for data_dir in DATA_DIRS:
            if os.path.exists(data_dir):
                shutil.copytree(data_dir, os.path.join(output_dir, data_dir), dirs_exist_ok=True)
        
        # Copy config file
        if os.path.exists(ENV_TEMPLATE):
            shutil.copy(ENV_TEMPLATE, os.path.join(output_dir, ".env"))
        
        print(f"Build successful! Output in: {output_dir}")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"Build failed: {e}")
        return False
    finally:
        # Clean up temporary files
        for f in [f"{APP_NAME}.spec"]:
            if os.path.exists(f):
                os.remove(f)

if __name__ == "__main__":
    clean_build_dirs()
    
    if not os.path.exists(MAIN_SCRIPT):
        print(f"Error: Main script '{MAIN_SCRIPT}' not found!")
        sys.exit(1)
        
    success = build_executable()
    sys.exit(0 if success else 1)
