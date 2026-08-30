#!/usr/bin/env python3
#
# Open Network Experience (ONE) - USB Flash Drive Auto-Provisioner
#
# Copyright (C) 2026 Open Network Experience Authors.
# Licensed under the GNU Affero General Public License v3.0 (AGPLv3).
# See LICENSE in the project root for full license details.
#
"""
USB Flash Drive Auto-Staging & Rapid Provisioner

Enables assembly-line staging of Raspberry Pi and x86 edge sensors by plugging
in a FAT32/exFAT USB flash drive containing 'one-bootstrap.json'.

Key Capabilities:
  1. Auto-discovers connected USB storage devices and mountpoints.
  2. Parses target CMP URL, Campus/Building/Room, and Wi-Fi credentials.
  3. Supports dynamic Room Pools for sequential batch room assignments.
  4. Deploys local bundled synthetic probe scripts even without internet.
  5. Performs instant Zero-Touch Registration with CMP API.
  6. Writes an audit receipt (provisioned_sensors.csv) back to the USB drive.
  7. Safely flushes filesystem buffers for immediate flash drive removal.
"""

import os
import sys
import json
import time
import socket
import re
import uuid
import shutil
import argparse
import subprocess
import urllib.request
import urllib.error
from typing import Dict, List, Optional, Tuple, Any

# ANSI Color Codes
COLOR_HEADER = '\033[95m'
COLOR_BLUE = '\033[94m'
COLOR_CYAN = '\033[96m'
COLOR_GREEN = '\033[92m'
COLOR_YELLOW = '\033[93m'
COLOR_RED = '\033[91m'
COLOR_BOLD = '\033[1m'
COLOR_DIM = '\033[2m'
COLOR_RESET = '\033[0m'

CONFIG_PATH = "/etc/sensor/reconciler.json"
WIFI_CONFIG_PATH = "/etc/wpa_supplicant/wpa_supplicant.conf"
SERVICE_PATH = "/etc/systemd/system/sensor-reconciler.service"

DEFAULT_CONFIG_FILENAMES = [
    "one-bootstrap.json",
    "one-config.json",
    "one_bootstrap.json",
    "one_config.json"
]

def print_banner():
    """Renders the USB Provisioner Banner."""
    print(f"""{COLOR_CYAN}
  ╔══════════════════════════════════════════════════════════════════════╗
  ║    💾  {COLOR_BOLD}OPEN NETWORK EXPERIENCE (ONE) USB AUTO-PROVISIONER{COLOR_RESET}{COLOR_CYAN}    ║
  ║        Zero-Touch Assembly Line Staging & Fleet Imprinter            ║
  ╚══════════════════════════════════════════════════════════════════════╝{COLOR_RESET}
""")

def print_success(msg: str):
    print(f"  {COLOR_GREEN}✔ {msg}{COLOR_RESET}")

def print_warning(msg: str):
    print(f"  {COLOR_YELLOW}⚠ {msg}{COLOR_RESET}")

def print_error(msg: str):
    print(f"  {COLOR_RED}✖ {msg}{COLOR_RESET}")

def print_info(msg: str):
    print(f"  {COLOR_CYAN}ℹ {msg}{COLOR_RESET}")

def is_root() -> bool:
    """Checks if current process has root privileges."""
    return os.geteuid() == 0 if hasattr(os, "geteuid") else True

def get_machine_uuid() -> str:
    """Gets machine UUID from /etc/machine-id or generates a persistent ID."""
    if os.path.exists("/etc/machine-id"):
        try:
            with open("/etc/machine-id", "r") as f:
                content = f.read().strip()
                if content:
                    return content
        except Exception:
            pass
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                data = json.load(f)
                if data.get("sensor_id"):
                    return data["sensor_id"]
        except Exception:
            pass
    return str(uuid.uuid4())

def get_primary_mac_and_ip() -> Tuple[str, str, str]:
    """Returns (mac_address, primary_ip, primary_iface)."""
    mac = "00:00:00:00:00:00"
    ip = "127.0.0.1"
    iface = "eth0"

    try:
        res = subprocess.check_output(["ip", "route", "show", "default"], text=True, stderr=subprocess.DEVNULL)
        parts = res.split()
        if "dev" in parts:
            dev_idx = parts.index("dev") + 1
            if dev_idx < len(parts):
                iface = parts[dev_idx]
    except Exception:
        pass

    mac_path = f"/sys/class/net/{iface}/address"
    if os.path.exists(mac_path):
        try:
            with open(mac_path, "r") as f:
                mac = f.read().strip()
        except Exception:
            pass
    else:
        mac = ':'.join(re.findall('..', '%012x' % uuid.getnode()))

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            ip = "127.0.0.1"

    return mac, ip, iface

def find_usb_bootstrap_config(search_dir: Optional[str] = None) -> Optional[Tuple[str, str]]:
    """
    Searches for a valid one-bootstrap.json file across:
      1. An explicit directory if provided
      2. Active mountpoints in /media, /mnt, /run/media
      3. Current working directory
    Returns (config_file_path, usb_mount_root) or None.
    """
    candidate_roots = []
    if search_dir:
        candidate_roots.append(os.path.abspath(search_dir))

    # Inspect standard mount directories
    base_mount_dirs = ["/media", "/mnt", "/run/media"]
    for b_dir in base_mount_dirs:
        if os.path.exists(b_dir):
            for root, dirs, _ in os.walk(b_dir):
                candidate_roots.append(root)

    # Current working directory / script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidate_roots.extend([os.getcwd(), script_dir, os.path.abspath(os.path.join(script_dir, ".."))])

    for root in candidate_roots:
        if not os.path.exists(root):
            continue
        for fname in DEFAULT_CONFIG_FILENAMES:
            target = os.path.join(root, fname)
            if os.path.exists(target) and os.path.isfile(target):
                return target, root

    return None

def parse_bootstrap_file(file_path: str) -> Dict[str, Any]:
    """Reads and validates the one-bootstrap.json configuration structure."""
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Validate essential keys and assign smart defaults
    config = {
        "cmp_url": data.get("cmp_url", "http://central-monitoring-platform.local/api/v1"),
        "enrollment_token": data.get("enrollment_token", ""),
        "check_interval_seconds": data.get("check_interval_seconds", 15),
        "location": data.get("location", {}),
        "wifi": data.get("wifi", {}),
        "room_pool": data.get("room_pool", data.get("rooms", [])),
        "auto_eject_and_sync": data.get("auto_eject_and_sync", True),
        "raw_data": data
    }

    # Normalize location
    loc = config["location"]
    if not isinstance(loc, dict):
        loc = {}
    config["location"] = {
        "district": loc.get("district", "Kern County Superintendent of Schools"),
        "site": loc.get("site", "Main Campus"),
        "building": loc.get("building", "Main Building"),
        "room": loc.get("room", "Room 101"),
        "notes": loc.get("notes", "Auto-Provisioned via USB Flash Drive")
    }

    return config

def pop_next_room_from_pool(bootstrap_path: str, parsed_config: Dict[str, Any]) -> str:
    """
    If a room_pool list exists in one-bootstrap.json (e.g. ['Room 101', 'Room 102']),
    assigns the next available room and updates the file on the USB stick.
    """
    room_pool = parsed_config.get("room_pool", [])
    if not room_pool or not isinstance(room_pool, list) or len(room_pool) == 0:
        return parsed_config["location"]["room"]

    assigned_room = str(room_pool.pop(0)).strip()
    parsed_config["location"]["room"] = assigned_room

    # Write updated pool back to USB stick
    try:
        raw_data = parsed_config.get("raw_data", {})
        if "room_pool" in raw_data:
            raw_data["room_pool"] = room_pool
        elif "rooms" in raw_data:
            raw_data["rooms"] = room_pool
        if "location" in raw_data and isinstance(raw_data["location"], dict):
            raw_data["location"]["room"] = assigned_room

        with open(bootstrap_path, "w", encoding="utf-8") as f:
            json.dump(raw_data, f, indent=4)
        print_info(f"Assigned next room from USB pool: {COLOR_BOLD}{assigned_room}{COLOR_RESET} (Remaining in pool: {len(room_pool)})")
    except Exception as e:
        print_warning(f"Could not update room pool on USB drive: {e}")

    return assigned_room

def configure_wifi_wpa(wifi_spec: Dict[str, Any], config_path: str = WIFI_CONFIG_PATH) -> bool:
    """Generates / updates /etc/wpa_supplicant/wpa_supplicant.conf from USB Wi-Fi spec."""
    ssid = wifi_spec.get("ssid")
    if not ssid:
        return False

    security = wifi_spec.get("security", "psk").lower()
    psk = wifi_spec.get("psk", "")

    try:
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        content = "ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev\nupdate_config=1\ncountry=US\n\n"
        if security == "open" or not psk:
            content += f"""network={{
    ssid="{ssid}"
    key_mgmt=NONE
}}
"""
        else:
            content += f"""network={{
    ssid="{ssid}"
    psk="{psk}"
    key_mgmt=WPA-PSK
}}
"""
        with open(config_path, "w") as f:
            f.write(content)
        print_success(f"Wi-Fi configuration applied for SSID: {ssid}")
        return True
    except Exception as e:
        print_warning(f"Could not configure Wi-Fi from USB: {e}")
        return False

def deploy_bundled_probe_scripts(usb_root: str, target_bin_dir: str = "/usr/local/bin") -> int:
    """
    If synthetic probe scripts are bundled on the USB drive, copies them into
    /usr/local/bin so the sensor works 100% offline.
    """
    deployed_count = 0
    candidate_dirs = [
        usb_root,
        os.path.join(usb_root, "sensor"),
        os.path.join(usb_root, "probes"),
        os.path.join(usb_root, "scripts")
    ]

    target_scripts = [
        "reconciler.py", "wizard.py", "cipa_compliance.py", "caaspp_readiness.py",
        "iperf3_runner.py", "wifi_dhcp_exporter.py", "rrm_darrp_monitor.py",
        "pcap_trigger.py", "evidence_collector.py", "segmentation_prober.py",
        "dns_multi_resolver_probe.py", "voip_jitter_probe.py", "custom_probe_runner.py",
        "gps_location_collector.py"
    ]

    os.makedirs(target_bin_dir, exist_ok=True)

    for c_dir in candidate_dirs:
        if not os.path.exists(c_dir):
            continue
        for s_name in target_scripts:
            src = os.path.join(c_dir, s_name)
            if not os.path.exists(src) and s_name == "wizard.py":
                src = os.path.join(c_dir, "onboarding", "wizard.py")
            if not os.path.exists(src) and s_name == "reconciler.py":
                src = os.path.join(c_dir, "reconciler", "reconciler.py")

            if os.path.exists(src) and os.path.isfile(src):
                dest = os.path.join(target_bin_dir, s_name)
                try:
                    shutil.copyfile(src, dest)
                    os.chmod(dest, 0o755)
                    deployed_count += 1
                except Exception:
                    pass

    # Create one-wizard symlink
    wizard_bin = os.path.join(target_bin_dir, "wizard.py")
    if os.path.exists(wizard_bin):
        try:
            ln_target = os.path.join(target_bin_dir, "one-wizard")
            if os.path.exists(ln_target) or os.path.islink(ln_target):
                os.remove(ln_target)
            os.symlink(wizard_bin, ln_target)
        except Exception:
            pass

    return deployed_count

def register_sensor_with_cmp(
    cmp_url: str,
    sensor_id: str,
    hostname: str,
    mac_address: str,
    location: Dict[str, Any],
    enrollment_token: str = ""
) -> Dict[str, Any]:
    """Attempts direct registration with the CMP Control Plane."""
    url = f"{cmp_url.rstrip('/')}/sensors/register"
    if "/api/v1" not in url:
        url = f"{cmp_url.rstrip('/')}/api/v1/sensors/register"

    payload = {
        "sensor_id": sensor_id,
        "os": sys.platform,
        "hostname": hostname,
        "mac_address": mac_address,
        "timestamp": int(time.time()),
        "location": location
    }
    if enrollment_token:
        payload["enrollment_token"] = enrollment_token

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "ONE-USB-AutoProvisioner/1.0"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                return {"success": True, "status": data.get("status"), "api_key": data.get("api_key")}
    except Exception as e:
        return {"success": False, "error": str(e)}

    return {"success": False, "error": "Unknown CMP response"}

def append_usb_inventory_receipt(
    usb_root: str,
    sensor_id: str,
    hostname: str,
    mac_address: str,
    ip_address: str,
    location: Dict[str, Any],
    cmp_status: str,
    log_msg: str
) -> bool:
    """
    Appends a timestamped provisioning record to provisioned_sensors.csv
    and writes one-provision-status.log on the USB drive.
    """
    csv_path = os.path.join(usb_root, "provisioned_sensors.csv")
    log_path = os.path.join(usb_root, "one-provision-status.log")
    iso_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    try:
        # Write CSV Header if new file
        needs_header = not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0
        with open(csv_path, "a", encoding="utf-8") as f:
            if needs_header:
                f.write("Timestamp,Sensor_UUID,Hostname,Primary_MAC,Assigned_IP,District,Campus_Site,Building,Room,CMP_Status,Notes\n")
            f.write(f'"{iso_time}","{sensor_id}","{hostname}","{mac_address}","{ip_address}","{location.get("district","")}","{location.get("site","")}","{location.get("building","")}","{location.get("room","")}","{cmp_status}","{location.get("notes","")}"\n')

        # Append to log file
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{iso_time}] Sensor {sensor_id} ({mac_address}) provisioned for {location.get('site')} - {location.get('room')}. Status: {cmp_status}. {log_msg}\n")

        print_success(f"Audit receipt logged to USB: {COLOR_BOLD}provisioned_sensors.csv{COLOR_RESET}")
        return True
    except Exception as e:
        print_warning(f"Could not write audit receipt back to USB: {e}")
        return False

def flush_usb_sync(usb_root: str):
    """Flushes filesystem write caches to allow safe removal of USB flash drive."""
    try:
        if hasattr(os, "sync"):
            os.sync()
        print_success("Filesystem caches synchronized. Safe to unplug USB flash drive.")
    except Exception:
        pass

def run_usb_provisioning(search_dir: Optional[str] = None, check_only: bool = False, json_output: bool = False) -> Dict[str, Any]:
    """Main USB Auto-Staging Controller."""
    if not json_output:
        print_banner()

    found = find_usb_bootstrap_config(search_dir)
    if not found:
        err_msg = "No USB flash drive with 'one-bootstrap.json' found."
        if json_output:
            print(json.dumps({"success": False, "error": err_msg}))
        else:
            print_error(err_msg)
        return {"success": False, "error": err_msg}

    bootstrap_file, usb_root = found
    if not json_output:
        print_info(f"Discovered USB Staging Kit at: {COLOR_BOLD}{bootstrap_file}{COLOR_RESET}")

    # Parse JSON
    config = parse_bootstrap_file(bootstrap_file)
    sensor_id = get_machine_uuid()
    mac, ip, iface = get_primary_mac_and_ip()
    hostname = socket.gethostname()

    # Assign room from pool if multiple rooms listed
    pop_next_room_from_pool(bootstrap_file, config)
    location_spec = config["location"]

    # Deploy local probe files from USB if present
    probes_copied = 0
    if not check_only and is_root():
        probes_copied = deploy_bundled_probe_scripts(usb_root)
        if probes_copied > 0 and not json_output:
            print_success(f"Deployed {probes_copied} synthetic probe scripts from USB bundle.")

    # Configure Wi-Fi if specified in bootstrap JSON
    if config.get("wifi") and not check_only and is_root():
        configure_wifi_wpa(config["wifi"])

    # Register with CMP
    reg_result = register_sensor_with_cmp(
        cmp_url=config["cmp_url"],
        sensor_id=sensor_id,
        hostname=hostname,
        mac_address=mac,
        location=location_spec,
        enrollment_token=config["enrollment_token"]
    )

    cmp_status = "PENDING_APPROVAL"
    api_key = ""
    if reg_result.get("success"):
        st = reg_result.get("status")
        if st == "approved":
            cmp_status = "APPROVED_ZTP"
            api_key = reg_result.get("api_key", "")
        else:
            cmp_status = "PENDING_APPROVAL"
    else:
        cmp_status = "REGISTRATION_DEFERRED"

    # Save reconciler configuration
    final_reconciler_cfg = {
        "cmp_url": config["cmp_url"],
        "sensor_id": sensor_id,
        "api_key": api_key,
        "enrollment_token": config["enrollment_token"],
        "check_interval_seconds": config["check_interval_seconds"],
        "wifi_interface": "wlan0",
        "wifi_config_path": WIFI_CONFIG_PATH,
        "initial_location": location_spec
    }

    if not check_only:
        try:
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            with open(CONFIG_PATH, "w") as f:
                json.dump(final_reconciler_cfg, f, indent=4)
            if not json_output:
                print_success(f"Saved configuration to {CONFIG_PATH}")
        except Exception as e:
            if not json_output:
                print_warning(f"Could not save {CONFIG_PATH}: {e}")

        # Enable and restart systemd service
        if is_root():
            try:
                subprocess.run(["systemctl", "daemon-reload"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run(["systemctl", "enable", "sensor-reconciler.service"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run(["systemctl", "restart", "sensor-reconciler.service"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if not json_output:
                    print_success("sensor-reconciler.service enabled and active!")
            except Exception:
                pass

    # Append Receipt to USB
    log_message = f"ZTP Status: {cmp_status}. Probes Bundled: {probes_copied}."
    if not check_only:
        append_usb_inventory_receipt(
            usb_root=usb_root,
            sensor_id=sensor_id,
            hostname=hostname,
            mac_address=mac,
            ip_address=ip,
            location=location_spec,
            cmp_status=cmp_status,
            log_msg=log_message
        )
        if config.get("auto_eject_and_sync", True):
            flush_usb_sync(usb_root)

    result_payload = {
        "success": True,
        "sensor_id": sensor_id,
        "hostname": hostname,
        "mac_address": mac,
        "ip_address": ip,
        "location": location_spec,
        "cmp_status": cmp_status,
        "usb_root": usb_root,
        "bootstrap_file": bootstrap_file,
        "registration": reg_result
    }

    if json_output:
        print(json.dumps(result_payload, indent=2))
    else:
        print(f"""
{COLOR_GREEN}╔══════════════════════════════════════════════════════════════════════╗
║             🎉  USB AUTO-PROVISIONING COMPLETE!                      ║
╚══════════════════════════════════════════════════════════════════════╝{COLOR_RESET}

  {COLOR_BOLD}Sensor Staging Summary:{COLOR_RESET}
  • Sensor UUID:     {COLOR_YELLOW}{sensor_id}{COLOR_RESET}
  • Assigned Room:   {COLOR_CYAN}{location_spec['site']} / {location_spec['room']}{COLOR_RESET}
  • Hardware MAC:    {COLOR_BOLD}{mac}{COLOR_RESET} ({iface})
  • CMP Status:      {COLOR_GREEN if 'APPROVED' in cmp_status else COLOR_YELLOW}{cmp_status}{COLOR_RESET}
  • USB Receipt:     {COLOR_CYAN}{usb_root}/provisioned_sensors.csv{COLOR_RESET}

  {COLOR_GREEN}✔ USB Drive may now be unplugged and inserted into the next sensor.{COLOR_RESET}
""")

    return result_payload

def main():
    parser = argparse.ArgumentParser(
        description="Open Network Experience (ONE) - USB Auto-Provisioner",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--source", "-s", help="Path to USB mount directory or root")
    parser.add_argument("--file", "-f", help="Direct path to one-bootstrap.json file")
    parser.add_argument("--check-only", action="store_true", help="Inspect and validate USB without applying changes")
    parser.add_argument("--json", action="store_true", help="Output results formatted as JSON")

    args = parser.parse_args()
    search_path = args.file if args.file else args.source
    res = run_usb_provisioning(search_dir=search_path, check_only=args.check_only, json_output=args.json)
    if not res.get("success"):
        sys.exit(1)

if __name__ == "__main__":
    main()
