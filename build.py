import os
import sys
import platform
import subprocess
import shutil
from argparse import ArgumentParser
import hashlib  # Added missing import

# Configuration
APP_NAME = "ServerMonitorBot"
MAIN_SCRIPT = "bot.py"
BUILD_DIR = "build"
DIST_DIR = "dist"
ICON_PATH = "icon.ico"
DATA_DIRS = ["database"]
ENV_TEMPLATE = ".env.example"
SCHEMA_VERSION = 1

def parse_args():
    parser = ArgumentParser(description="Build the bot executable")
    parser.add_argument("--version", required=True, help="Version number (e.g., 1.4.2)")
    return parser.parse_args()

def clean_build_dirs():
    """Clean previous build artifacts"""
    print("Cleaning previous builds...")
    for dir_path in [BUILD_DIR, DIST_DIR]:
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)

def setup_build_env(version):
    """Set up environment variables for build"""
    env = os.environ.copy()
    env["BOT_VERSION"] = version
    env["SCHEMA_VERSION"] = str(SCHEMA_VERSION)
    
    # Create temporary .env with version info
    temp_env = f".env.build"
    with open(ENV_TEMPLATE, 'r') as src, open(temp_env, 'w') as dst:
        for line in src:
            if line.startswith("BOT_VERSION"):
                dst.write(f"BOT_VERSION={version}\n")
            elif line.startswith("SCHEMA_VERSION"):
                dst.write(f"SCHEMA_VERSION={SCHEMA_VERSION}\n")
            else:
                dst.write(line)
    
    return env

def get_platform_info():
    """Get platform-specific settings"""
    system = platform.system().lower()
    platforms = {
        "windows": {"ext": ".exe", "plat": "win", "args": []},
        "darwin": {"ext": "", "plat": "macos", "args": ["--windowed"]},
        "linux": {"ext": "", "plat": "linux", "args": []}
    }
    return platforms.get(system, {"ext": "", "plat": "unknown", "args": []})

def build_executable(version, env):
    """Build the executable using PyInstaller"""
    print(f"Building version {version}...")
    
    platform_info = get_platform_info()
    executable_name = f"{APP_NAME}{platform_info['ext']}"
    
    # Generate datas string in the format ('dir','dir')
    datas = []
    for d in DATA_DIRS + [os.path.dirname(ENV_TEMPLATE)]:
        datas.append(f"('{d}', '{d}')")
    
    # Create spec file with version info
    spec_content = f"""# -*- mode: python ; coding: utf-8 -*-
block_cipher = None

a = Analysis(['{MAIN_SCRIPT}'],
             pathex=['.'],
             binaries=[],
             datas=[{', '.join(datas)}],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             macosx_bundle_identifier=None)
pyz = PYZ(a.pure, a.zipped_data,
          cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.datas,
          [],
          name='{executable_name}',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          runtime_tmpdir=None,
          console=True)
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
        "--noconfirm"
    ]

    if ICON_PATH and os.path.exists(ICON_PATH):
        build_cmd.extend(["--icon", ICON_PATH])
    
    build_cmd.append(MAIN_SCRIPT)

    try:
        print("Running PyInstaller...")
        subprocess.run(build_cmd, check=True, env=env)
        
        # Create platform-specific distribution folder
        output_dir = os.path.join(BUILD_DIR, platform_info['plat'])
        os.makedirs(output_dir, exist_ok=True)
        
        # Copy executable
        shutil.move(os.path.join(DIST_DIR, executable_name), 
                   os.path.join(output_dir, executable_name))
        
        # Copy data files
        for data_dir in DATA_DIRS:
            shutil.copytree(data_dir, os.path.join(output_dir, data_dir), 
                          dirs_exist_ok=True)
        
        # Copy config file
        shutil.copy(".env.build", os.path.join(output_dir, ".env"))
        
        # Generate checksum
        executable_path = os.path.join(output_dir, executable_name)
        if os.path.exists(executable_path):
            with open(os.path.join(output_dir, "checksum.sha256"), "w") as f:
                with open(executable_path, 'rb') as f2:
                    content = f2.read()
                hash_str = hashlib.sha256(content).hexdigest()
                f.write(f"{hash_str}  {executable_name}")
        
        print(f"Build successful! Output in: {output_dir}")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"Build failed: {e}")
        return False
    finally:
        # Clean up temporary files
        for f in [f"{APP_NAME}.spec", ".env.build"]:
            if os.path.exists(f):
                os.remove(f)

if __name__ == "__main__":
    args = parse_args()
    clean_build_dirs()
    
    build_env = setup_build_env(args.version)
    
    if not os.path.exists(MAIN_SCRIPT):
        print(f"Error: Main script '{MAIN_SCRIPT}' not found!")
        sys.exit(1)
        
    success = build_executable(args.version, build_env)
    sys.exit(0 if success else 1)