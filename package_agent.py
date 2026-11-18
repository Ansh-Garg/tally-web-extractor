#!/usr/bin/env python3
"""
Packages the agent directory into website/downloads/tally-web-agent.zip
"""
import os
import zipfile
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
AGENT_DIR = BASE_DIR / "agent"
OUTPUT_ZIP = BASE_DIR / "website" / "downloads" / "tally-web-agent.zip"

OUTPUT_ZIP.parent.mkdir(parents=True, exist_ok=True)

# Exclude unwanted build artifacts
EXCLUDES = {
    "__pycache__", ".git", "output", "build", "dist", "*.pyc"
}

def should_exclude(rel_path):
    parts = rel_path.parts
    for p in parts:
        if p in EXCLUDES or p.endswith(".pyc"):
            return True
    return False

print(f"Packaging {AGENT_DIR} -> {OUTPUT_ZIP}...")

with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED) as z:
    for root, dirs, files in os.walk(AGENT_DIR):
        root_path = Path(root)
        rel_root = root_path.relative_to(AGENT_DIR)
        if should_exclude(rel_root):
            continue
        for file in files:
            file_path = root_path / file
            rel_file = file_path.relative_to(AGENT_DIR)
            if should_exclude(rel_file):
                continue
            z.write(file_path, arcname=str(rel_file))
            print(f"  + {rel_file}")

print(f"Successfully created: {OUTPUT_ZIP} ({OUTPUT_ZIP.stat().st_size:,} bytes)")
