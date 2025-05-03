import os
import sys
import platform
import subprocess
import shutil
import hashlib

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

def build_executable():
    """Build the executable using PyInstaller"""
    print("Starting build process...")
    
    platform_info = get_platform_info()
    executable_name = f"{APP_NAME}{platform_info['ext']}"
    
    # Create spec file content
    spec_content = f"""# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT

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
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='{APP_NAME}'
)
"""

    with open(f"{APP_NAME}.spec", "w") as f:
        f.write(spec_content)

    # Build command (now using --onefile)
    build_cmd = [
        "pyinstaller",
        "--name", APP_NAME,
        "--specpath", BUILD_DIR,
        "--distpath", DIST_DIR,
        "--workpath", os.path.join(BUILD_DIR, "temp"),
        "--clean",
        "--noconfirm",
        "--onefile"  # This is critical for macOS builds
    ]

    if ICON_PATH and os.path.exists(ICON_PATH):
        build_cmd.extend(["--icon", ICON_PATH])
    
    build_cmd.append(MAIN_SCRIPT)

    try:
        print("Running PyInstaller...")
        subprocess.run(build_cmd, check=True)
        
        # Create platform-specific distribution folder
        output_dir = os.path.join(BUILD_DIR, platform_info['plat'])
        os.makedirs(output_dir, exist_ok=True)
        
        # macOS creates a nested directory for the executable
        if platform_info['plat'] == "macos":
            source_path = os.path.join(DIST_DIR, executable_name)
            target_path = os.path.join(output_dir, executable_name)
            
            # Handle macOS app bundle if present
            app_bundle = os.path.join(DIST_DIR, f"{APP_NAME}.app")
            if os.path.exists(app_bundle):
                print("Found macOS app bundle, moving it...")
                shutil.move(app_bundle, os.path.join(output_dir, f"{APP_NAME}.app"))
                target_path = os.path.join(output_dir, f"{APP_NAME}.app", "Contents", "MacOS", APP_NAME)
                source_path = target_path  # For checksum calculation
            else:
                shutil.move(source_path, target_path)
        else:
            shutil.move(os.path.join(DIST_DIR, executable_name), 
                       os.path.join(output_dir, executable_name))
        
        # Copy data files
        for data_dir in DATA_DIRS:
            if os.path.exists(data_dir):
                shutil.copytree(data_dir, os.path.join(output_dir, data_dir), 
                              dirs_exist_ok=True)
        
        # Copy config file
        if os.path.exists(ENV_TEMPLATE):
            shutil.copy(ENV_TEMPLATE, os.path.join(output_dir, ".env"))
        
        # Generate checksum
        if os.path.exists(source_path):
            with open(os.path.join(output_dir, "checksum.sha256"), "w") as f:
                with open(source_path, 'rb') as f2:
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
        for f in [f"{APP_NAME}.spec"]:
            if os.path.exists(f):
                os.remove(f)

def get_platform_info():
    """Get platform-specific settings"""
    system = platform.system().lower()
    platforms = {
        "windows": {"ext": ".exe", "plat": "win"},
        "darwin": {"ext": "", "plat": "macos"},
        "linux": {"ext": "", "plat": "linux"}
    }
    return platforms.get(system, {"ext": "", "plat": "unknown"})

if __name__ == "__main__":
    clean_build_dirs()
    
    if not os.path.exists(MAIN_SCRIPT):
        print(f"Error: Main script '{MAIN_SCRIPT}' not found!")
        sys.exit(1)
        
    success = build_executable()
    sys.exit(0 if success else 1)