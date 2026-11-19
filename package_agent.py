#!/usr/bin/env python3
"""
Packages both the Agent and the Chrome Extension into website/downloads/
The extension zip includes INSTALL_EXTENSION.bat for 1-click Windows setup.
"""
import os
import zipfile
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
AGENT_DIR = BASE_DIR / "agent"
EXT_DIR = BASE_DIR / "extension"
DOWNLOADS_DIR = BASE_DIR / "website" / "downloads"

DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

EXCLUDES = {"__pycache__", ".git", "output", "build", "dist", "*.pyc"}

def should_exclude(rel_path):
    for p in rel_path.parts:
        if p in EXCLUDES or p.endswith(".pyc"):
            return True
    return False

def package_dir(source_dir, zip_dest, label):
    print(f"Packaging {label} from {source_dir} -> {zip_dest}...")
    with zipfile.ZipFile(zip_dest, "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(source_dir):
            root_path = Path(root)
            rel_root = root_path.relative_to(source_dir)
            if should_exclude(rel_root):
                continue
            for file in files:
                file_path = root_path / file
                rel_file = file_path.relative_to(source_dir)
                if should_exclude(rel_file):
                    continue
                z.write(file_path, arcname=str(rel_file))
    print(f"  -> Created {zip_dest.name} ({zip_dest.stat().st_size:,} bytes)")

# 1. Package Agent
package_dir(AGENT_DIR, DOWNLOADS_DIR / "tally-web-agent.zip", "Agent Bundle")

# 2. Package Chrome Extension (all files from extension/ folder)
ext_zip_path = DOWNLOADS_DIR / "tally-web-extension.zip"
print(f"Packaging Chrome Extension (with installer) -> {ext_zip_path}...")
with zipfile.ZipFile(ext_zip_path, "w", zipfile.ZIP_DEFLATED) as z:
    for root, dirs, files in os.walk(EXT_DIR):
        root_path = Path(root)
        rel_root = root_path.relative_to(EXT_DIR)
        if should_exclude(rel_root):
            continue
        for file in files:
            file_path = root_path / file
            rel_file = file_path.relative_to(EXT_DIR)
            if should_exclude(rel_file):
                continue
            z.write(file_path, arcname=str(rel_file))
print(f"  -> Created {ext_zip_path.name} ({ext_zip_path.stat().st_size:,} bytes)")

print("All distribution packages ready in website/downloads/")
