#!/usr/bin/env python3
"""
Open Network Experience (ONE) - Chromebook Sensor Packager
Automates packaging the ChromeOS Manifest V3 extension for Google Workspace Admin Console
deployment and Chrome Web Store publishing.
License: GNU AGPLv3
"""

import os
import json
import zipfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SENSOR_DIR = ROOT_DIR / "chromebook-sensor"
DIST_DIR = ROOT_DIR / "dist"

def package_extension():
    manifest_path = SENSOR_DIR / "manifest.json"

    if not manifest_path.exists():
        print(f"❌ Error: manifest.json not found at {manifest_path}")
        return

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    version = manifest.get("version", "1.0.0")
    name = manifest.get("name", "one-chromebook-sensor")
    zip_filename = f"one-chromebook-sensor-v{version}.zip"

    DIST_DIR.mkdir(parents=True, exist_ok=True)
    zip_output_path = DIST_DIR / zip_filename

    # Files and folders to package
    include_paths = [
        "manifest.json",
        "schema.json",
        "icons",
        "src"
    ]

    print(f"📦 Packaging {name} v{version}...")

    with zipfile.ZipFile(zip_output_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for item in include_paths:
            src_item = SENSOR_DIR / item
            if not src_item.exists():
                print(f"⚠️ Warning: {item} does not exist in {SENSOR_DIR}")
                continue

            if src_item.is_file():
                zipf.write(src_item, arcname=item)
                print(f"  ✓ Added file: {item}")
            elif src_item.is_dir():
                for root, _, files in os.walk(src_item):
                    for file in files:
                        if file.endswith((".test.js", ".spec.js", ".DS_Store")):
                            continue
                        file_path = Path(root) / file
                        arcname = file_path.relative_to(SENSOR_DIR)
                        zipf.write(file_path, arcname=str(arcname))
                        print(f"  ✓ Added: {arcname}")

    # Generate Google Workspace Admin Console Policy Template
    policy_output_path = DIST_DIR / f"google_workspace_policy_v{version}.json"
    default_policy = {
        "cmp_server_url": {
            "Value": "http://10.98.2.125:8000"
        },
        "api_key": {
            "Value": "TestAPIKEYCHROMEBOOK"
        },
        "campus_id": {
            "Value": "CAMPUS-CHROMEBOOK-FLEET"
        },
        "probe_interval_seconds": {
            "Value": 60
        },
        "settings_locked": {
            "Value": True
        },
        "helpdesk_pin": {
            "Value": "4357"
        },
        "enable_webrtc_probing": {
            "Value": True
        },
        "enable_offline_buffer": {
            "Value": True
        },
        "max_offline_records": {
            "Value": 1000
        }
    }

    with open(policy_output_path, "w", encoding="utf-8") as f:
        json.dump(default_policy, f, indent=2)

    zip_size_kb = round(os.path.getsize(zip_output_path) / 1024, 2)
    print("\n🎉 Package created successfully!")
    print(f"  • Release ZIP: {zip_output_path} ({zip_size_kb} KB)")
    print(f"  • Google Admin Policy: {policy_output_path}")
    print("\n📋 Google Workspace Admin Console Deployment Steps:")
    print("  1. Go to: Devices → Chrome → Apps & extensions → Users & browsers")
    print("  2. Click '+' → 'Add Chrome app or extension by ID / upload ZIP'")
    print(f"  3. In 'Policy for extensions', paste the content of {policy_output_path.name}")
    print("  4. Set Installation policy to 'Force install + pin to browser taskbar'")

if __name__ == "__main__":
    package_extension()
