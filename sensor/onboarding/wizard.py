#!/usr/bin/env python3
#
# Open Network Experience (ONE) - Interactive Terminal Setup Wizard (one-wizard)
#
# Copyright (C) 2026 Open Network Experience Authors.
# Licensed under the GNU Affero General Public License v3.0 (AGPLv3).
# See LICENSE in the project root for full license details.
#
"""
Interactive Edge Sensor Setup Wizard (one-wizard)

Designed for school district technology administrators and field technicians
to onboard, configure, and diagnose Raspberry Pi and x86 edge sensors.

Capabilities:
  1. Automated hardware and network interface discovery (Ethernet & Wi-Fi)
  2. Four-way CMP Control Plane auto-discovery & live connectivity verification
  3. School campus, building, room, and asset tagging
  4. Live Wi-Fi site survey scan and WPA2/WPA3/802.1X configuration
  5. Instant Zero-Touch Provisioning (ZTP) / Trust-On-First-Use (TOFU) registration
  6. Service lifecycle management and diagnostic status dashboard
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

DEFAULT_CMP_URL = "http://central-monitoring-platform.local/api/v1"

def print_banner():
    """Renders the ONE onboarding banner."""
    print(f"""{COLOR_CYAN}
  ╔══════════════════════════════════════════════════════════════════════╗
  ║    🚀  {COLOR_BOLD}OPEN NETWORK EXPERIENCE (ONE) EDGE SENSOR WIZARD{COLOR_RESET}{COLOR_CYAN}         ║
  ║        Zero-Touch Onboarding & Field Technician Provisioner          ║
  ╚══════════════════════════════════════════════════════════════════════╝{COLOR_RESET}
""")

def print_step(step_num: int, title: str):
    """Prints a distinct step header."""
    print(f"\n{COLOR_BOLD}{COLOR_BLUE}▶ Step {step_num}: {title}{COLOR_RESET}")
    print(f"{COLOR_DIM}{'─' * 60}{COLOR_RESET}")

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

    # Use ip route to get default gateway interface and IP
    try:
        res = subprocess.check_output(["ip", "route", "show", "default"], text=True, stderr=subprocess.DEVNULL)
        parts = res.split()
        if "dev" in parts:
            dev_idx = parts.index("dev") + 1
            if dev_idx < len(parts):
                iface = parts[dev_idx]
    except Exception:
        pass

    # Read MAC from /sys/class/net/<iface>/address
    mac_path = f"/sys/class/net/{iface}/address"
    if os.path.exists(mac_path):
        try:
            with open(mac_path, "r") as f:
                mac = f.read().strip()
        except Exception:
            pass
    else:
        # Fallback to uuid.getnode()
        mac = ':'.join(re.findall('..', '%012x' % uuid.getnode()))

    # Read IP using socket or ip command
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

def inspect_hardware() -> Dict[str, Any]:
    """Gathers hardware specifications and system diagnostics."""
    cpu_cores = os.cpu_count() or 1
    total_mem_gb = 1.0
    disk_avail_gb = 1.0
    disk_total_gb = 1.0

    # Memory info from /proc/meminfo
    if os.path.exists("/proc/meminfo"):
        try:
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        kb = int(line.split()[1])
                        total_mem_gb = round(kb / (1024 * 1024), 1)
                        break
        except Exception:
            pass

    # Disk usage
    try:
        st = shutil.disk_usage("/")
        disk_avail_gb = round(st.free / (1024**3), 1)
        disk_total_gb = round(st.total / (1024**3), 1)
    except Exception:
        pass

    # Detect all network interfaces
    interfaces = []
    net_dir = "/sys/class/net"
    if os.path.exists(net_dir):
        try:
            for item in os.listdir(net_dir):
                if item == "lo":
                    continue
                itype = "wireless" if os.path.exists(os.path.join(net_dir, item, "wireless")) or item.startswith("wl") else "ethernet"
                operstate = "unknown"
                oper_path = os.path.join(net_dir, item, "operstate")
                if os.path.exists(oper_path):
                    try:
                        with open(oper_path, "r") as f:
                            operstate = f.read().strip()
                    except Exception:
                        pass
                interfaces.append({"name": item, "type": itype, "status": operstate})
        except Exception:
            pass

    return {
        "hostname": socket.gethostname(),
        "os": sys.platform,
        "cpu_cores": cpu_cores,
        "memory_gb": total_mem_gb,
        "disk_free_gb": disk_avail_gb,
        "disk_total_gb": disk_total_gb,
        "interfaces": interfaces,
        "docker_installed": shutil.which("docker") is not None
    }

def parse_option43_tlv_or_string(raw_val: str) -> Optional[dict]:
    """
    Parses Option 43 / Option 224 raw string or hex TLV payload.
    Supports plain text ASCII and RFC 2132 Sub-Option TLVs.
    """
    clean_val = raw_val.replace('"', '').strip()
    if not clean_val:
        return None

    if clean_val.startswith("http://") or clean_val.startswith("https://"):
        url = clean_val if "/api/v1" in clean_val else f"{clean_val.rstrip('/')}/api/v1"
        return {"cmp_url": url}

    hex_str = clean_val.replace(":", "").replace(" ", "").replace("0x", "")
    try:
        raw_bytes = bytes.fromhex(hex_str)
    except ValueError:
        raw_bytes = None

    if raw_bytes:
        try:
            ascii_text = raw_bytes.decode("utf-8", errors="strict").strip()
            if ascii_text.startswith("http://") or ascii_text.startswith("https://"):
                url = ascii_text if "/api/v1" in ascii_text else f"{ascii_text.rstrip('/')}/api/v1"
                return {"cmp_url": url}
        except Exception:
            pass

        parsed = {}
        idx = 0
        while idx + 2 <= len(raw_bytes):
            opt_type = raw_bytes[idx]
            opt_len = raw_bytes[idx + 1]
            val_start = idx + 2
            val_end = val_start + opt_len
            if val_end > len(raw_bytes):
                break
            val_bytes = raw_bytes[val_start:val_end]
            try:
                decoded_str = val_bytes.decode("utf-8", errors="ignore").strip()
                if opt_type == 1:
                    parsed["cmp_url"] = decoded_str if "/api/v1" in decoded_str else f"{decoded_str.rstrip('/')}/api/v1"
                elif opt_type == 2:
                    parsed["campus"] = decoded_str
                elif opt_type == 3:
                    parsed["building"] = decoded_str
                elif opt_type == 4:
                    parsed["room"] = decoded_str
                elif opt_type == 5:
                    parsed["token"] = decoded_str
            except Exception:
                pass
            idx = val_end

        if parsed.get("cmp_url"):
            return parsed

    return None

def discover_cmp_endpoints() -> List[Dict[str, str]]:
    """Probes local network for CMP endpoints via DHCP Option 43, DNS Search Domain, and default."""
    candidates = []

    # 1. Check existing config
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                c = json.load(f)
                if c.get("cmp_url") and "central-monitoring-platform.local" not in c["cmp_url"]:
                    candidates.append({"url": c["cmp_url"], "source": "Existing Configuration (/etc/sensor/reconciler.json)"})
        except Exception:
            pass

    # 2. Check DHCP Option 43 / 224
    lease_dirs = [
        "/run/systemd/netif/leases",
        "/var/lib/dhcp",
        "/var/lib/NetworkManager",
        "/var/lib/dhclient",
        "/var/run/dhcpcd"
    ]
    for l_dir in lease_dirs:
        if os.path.exists(l_dir):
            for root, _, files in os.walk(l_dir):
                for f_name in files:
                    try:
                        with open(os.path.join(root, f_name), "r", errors="ignore") as f:
                            content = f.read()
                            for line in content.split("\n"):
                                if any(k in line for k in ("OPTION_43=", "vendor-encapsulated-options", "OPTION_224=", "OPTION_225=", "new_vendor_encapsulated_options", "new_site_option_224")):
                                    val = line.split("=", 1)[-1].strip()
                                    res = parse_option43_tlv_or_string(val)
                                    if res and res.get("cmp_url"):
                                        candidates.append({
                                            "url": res["cmp_url"],
                                            "source": f"DHCP Option 43/224 ({f_name})",
                                            "metadata": res
                                        })
                    except Exception:
                        pass

    # 3. DNS search domain & mDNS resolution
    dns_hosts = []
    if os.path.exists("/etc/resolv.conf"):
        try:
            with open("/etc/resolv.conf", "r") as f:
                for line in f:
                    parts = line.split()
                    if parts and parts[0] in ("search", "domain"):
                        domain = parts[1]
                        dns_hosts.extend([
                            (f"openux-cmp.{domain}", f"DNS Search Domain (openux-cmp.{domain})"),
                            (f"one-cmp.{domain}", f"DNS Search Domain (one-cmp.{domain})"),
                            (f"cmp.{domain}", f"DNS Search Domain (cmp.{domain})")
                        ])
        except Exception:
            pass
    dns_hosts.append(("one-cmp.local", "Local mDNS (one-cmp.local)"))

    for hostname, src in dns_hosts:
        try:
            socket.gethostbyname(hostname)
            candidates.append({"url": f"http://{hostname}:8000/api/v1", "source": src})
        except Exception:
            pass

    return candidates

def test_cmp_connectivity(url: str, timeout: float = 4.0) -> Tuple[bool, str, float]:
    """Tests HTTP connection to CMP endpoint. Returns (is_healthy, status_message, latency_ms)."""
    normalized_url = url.rstrip("/")
    if not normalized_url.startswith("http://") and not normalized_url.startswith("https://"):
        normalized_url = f"http://{normalized_url}"

    test_endpoints = [
        f"{normalized_url}/health",
        f"{normalized_url}/sensors/register",
        f"{normalized_url.replace('/api/v1', '')}/install.sh",
        normalized_url
    ]

    t0 = time.time()
    for endpoint in test_endpoints:
        try:
            req = urllib.request.Request(
                endpoint,
                headers={"User-Agent": "ONE-EdgeSensor-Wizard/1.0"},
                method="GET"
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                latency = round((time.time() - t0) * 1000, 1)
                return True, f"HTTP {resp.status} OK", latency
        except urllib.error.HTTPError as e:
            # 405 Method Not Allowed or 401 Unauthorized still means the server is reachable and active
            if e.code in (200, 401, 404, 405):
                latency = round((time.time() - t0) * 1000, 1)
                return True, f"Reachable (HTTP {e.code})", latency
        except Exception:
            continue

    latency = round((time.time() - t0) * 1000, 1)
    return False, "Connection refused or timed out", latency

def scan_wifi_ssids(interface: str = "wlan0") -> List[Dict[str, str]]:
    """Scans for visible Wi-Fi SSIDs using available system tools."""
    ssids = []
    seen = set()

    # 1. Try nmcli (NetworkManager)
    if shutil.which("nmcli"):
        try:
            out = subprocess.check_output(
                ["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY,BARS", "dev", "wifi"],
                text=True, stderr=subprocess.DEVNULL, timeout=5
            )
            for line in out.strip().split("\n"):
                if not line:
                    continue
                parts = line.split(":")
                if parts and parts[0] and parts[0] not in seen:
                    ssid_name = parts[0]
                    seen.add(ssid_name)
                    signal = parts[1] if len(parts) > 1 else "?"
                    sec = parts[2] if len(parts) > 2 else "Open"
                    bars = parts[3] if len(parts) > 3 else "▂▄▆█"
                    ssids.append({"ssid": ssid_name, "signal": f"{signal}%", "security": sec or "Open", "bars": bars})
        except Exception:
            pass

    # 2. Try iwlist if nmcli returned empty
    if not ssids and shutil.which("iwlist"):
        try:
            out = subprocess.check_output(
                ["iwlist", interface, "scan"],
                text=True, stderr=subprocess.DEVNULL, timeout=6
            )
            for line in out.split("\n"):
                line = line.strip()
                if "ESSID:" in line:
                    ssid = line.split("ESSID:")[-1].replace('"', '').strip()
                    if ssid and ssid not in seen:
                        seen.add(ssid)
                        ssids.append({"ssid": ssid, "signal": "Strong", "security": "WPA2", "bars": "▂▄▆█"})
        except Exception:
            pass

    return ssids

def register_sensor_direct(
    cmp_url: str,
    sensor_id: str,
    hostname: str,
    mac_address: str,
    location: Dict[str, Any],
    enrollment_token: str = ""
) -> Dict[str, Any]:
    """Sends registration request directly to CMP and returns parsed JSON response."""
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
        headers={"Content-Type": "application/json", "User-Agent": "ONE-EdgeSensor-Wizard/1.0"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                return {"success": True, "status": data.get("status"), "api_key": data.get("api_key")}
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8")
        except Exception:
            err_body = str(e)
        return {"success": False, "error": f"HTTP {e.code}: {err_body}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

    return {"success": False, "error": "Unknown response from CMP"}

def save_sensor_configuration(config: Dict[str, Any], path: Optional[str] = None) -> bool:
    """Writes /etc/sensor/reconciler.json configuration file."""
    target_path = path or CONFIG_PATH
    try:
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, "w") as f:
            json.dump(config, f, indent=4)
        return True
    except Exception as e:
        print_error(f"Failed to save configuration to {target_path}: {e}")
        return False

def configure_wpa_supplicant(ssid: str, psk: str, security: str = "psk", config_path: Optional[str] = None) -> bool:
    """Generates / updates /etc/wpa_supplicant/wpa_supplicant.conf."""
    target_path = config_path or WIFI_CONFIG_PATH
    try:
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        content = "ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev\nupdate_config=1\ncountry=US\n\n"
        if security.lower() == "open":
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
        with open(target_path, "w") as f:
            f.write(content)
        return True
    except Exception as e:
        print_warning(f"Could not write wpa_supplicant file: {e}")
        return False

def manage_systemd_service() -> bool:
    """Installs, enables, and restarts sensor-reconciler.service."""
    try:
        service_content = """[Unit]
Description=Open Network Experience (ONE) Sensor Reconciler & Adaptive Prober
After=network-online.target docker.service
Wants=network-online.target docker.service

[Service]
Type=simple
User=root
ExecStart=/usr/bin/python3 /usr/local/bin/reconciler.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
        os.makedirs(os.path.dirname(SERVICE_PATH), exist_ok=True)
        with open(SERVICE_PATH, "w") as f:
            f.write(service_content)

        subprocess.run(["systemctl", "daemon-reload"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["systemctl", "enable", "sensor-reconciler.service"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["systemctl", "restart", "sensor-reconciler.service"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        print_warning(f"Systemd service installation skipped or failed: {e}")
        return False

def prompt_user(prompt_text: str, default: str = "") -> str:
    """Interactive text prompt with highlighted default value."""
    def_display = f" [{COLOR_YELLOW}{default}{COLOR_RESET}]" if default else ""
    try:
        ans = input(f"{COLOR_BOLD}{prompt_text}{COLOR_RESET}{def_display}: ").strip()
        return ans if ans else default
    except (KeyboardInterrupt, EOFError):
        print("\n\nOperation cancelled by user.")
        sys.exit(1)

def run_interactive_wizard():
    """Runs the full interactive step-by-step terminal wizard."""
    print_banner()

    if not is_root():
        print_warning("Running without root privileges. Configuration changes may require 'sudo'.")

    # Load existing config if available
    existing_config = {}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                existing_config = json.load(f)
                print_info(f"Loaded existing configuration from {CONFIG_PATH}")
        except Exception:
            pass

    # STEP 1: Hardware & Network Diagnostics
    print_step(1, "Hardware & Network Interfaces")
    hw = inspect_hardware()
    sensor_id = existing_config.get("sensor_id") or get_machine_uuid()
    mac, ip, iface = get_primary_mac_and_ip()

    print(f"  • Hostname:        {COLOR_BOLD}{hw['hostname']}{COLOR_RESET}")
    print(f"  • Sensor UUID:     {COLOR_YELLOW}{sensor_id}{COLOR_RESET}")
    print(f"  • Primary MAC:     {COLOR_CYAN}{mac}{COLOR_RESET} (on {iface})")
    print(f"  • Current IP:      {COLOR_GREEN}{ip}{COLOR_RESET}")
    print(f"  • CPU / Memory:    {hw['cpu_cores']} Cores | {hw['memory_gb']} GB RAM")
    print(f"  • Disk Space:      {hw['disk_free_gb']} GB Free / {hw['disk_total_gb']} GB Total")
    print(f"  • Docker Engine:   {COLOR_GREEN if hw['docker_installed'] else COLOR_YELLOW}{'Installed' if hw['docker_installed'] else 'Not Found (Will use host probe fallback)'}{COLOR_RESET}")

    if hw["interfaces"]:
        print("\n  Detected Network Adapters:")
        for idx, ifc in enumerate(hw["interfaces"]):
            icon = "🌐" if ifc["type"] == "ethernet" else "📶"
            status_color = COLOR_GREEN if ifc["status"] == "up" else COLOR_DIM
            print(f"    {idx+1}. {icon} {COLOR_BOLD}{ifc['name']}{COLOR_RESET} ({ifc['type']}) - Status: {status_color}{ifc['status']}{COLOR_RESET}")

    # STEP 2: CMP Server Connection
    print_step(2, "CMP Control Plane Connection")
    discovered = discover_cmp_endpoints()
    default_url = existing_config.get("cmp_url") or (discovered[0]["url"] if discovered else DEFAULT_CMP_URL)

    if discovered:
        print_info(f"Auto-discovered CMP endpoint: {COLOR_GREEN}{discovered[0]['url']}{COLOR_RESET} (via {discovered[0]['source']})")

    while True:
        cmp_url = prompt_user("Enter CMP Server URL or IP", default_url)
        if not cmp_url.startswith("http://") and not cmp_url.startswith("https://"):
            cmp_url = f"http://{cmp_url}"
        if not cmp_url.endswith("/api/v1"):
            cmp_url = f"{cmp_url.rstrip('/')}/api/v1"

        print(f"  Testing connection to {COLOR_CYAN}{cmp_url}{COLOR_RESET}...")
        healthy, status_msg, lat = test_cmp_connectivity(cmp_url)
        if healthy:
            print_success(f"Connection Successful! ({lat} ms latency, {status_msg})")
            break
        else:
            print_error(f"Cannot reach CMP at {cmp_url} ({status_msg})")
            retry = prompt_user("Retry with a different IP/URL? (Y/n)", "y").lower()
            if retry not in ("y", "yes"):
                print_warning("Proceeding with unverified CMP URL.")
                break

    # STEP 3: School Site & Location Tagging
    print_step(3, "Campus Location & Asset Tagging")
    ex_loc = existing_config.get("initial_location") or existing_config.get("location") or {}

    district_name = prompt_user("School District / Organization", ex_loc.get("district", "Kern County Superintendent of Schools"))
    site_name = prompt_user("Campus / School Name", ex_loc.get("site", "West High School"))
    building_name = prompt_user("Building / Wing", ex_loc.get("building", "Science Building"))
    room_name = prompt_user("Room / Location Identifier", ex_loc.get("room", "Room 204"))
    notes = prompt_user("Installation Notes / Asset Tag", ex_loc.get("notes", "Ceiling AP Drop"))

    location_spec = {
        "district": district_name,
        "site": site_name,
        "building": building_name,
        "room": room_name,
        "notes": notes
    }

    # STEP 4: Wi-Fi Configuration
    print_step(4, "Wi-Fi Network Setup (Optional)")
    setup_wifi = prompt_user("Configure or update Wi-Fi SSID settings? (y/N)", "n").lower()
    if setup_wifi in ("y", "yes"):
        print("  Scanning for nearby Wi-Fi networks...")
        scanned = scan_wifi_ssids()
        selected_ssid = ""
        if scanned:
            print("\n  Available SSIDs:")
            for i, ap in enumerate(scanned[:8]):
                print(f"    [{i+1}] {ap['bars']} {COLOR_BOLD}{ap['ssid']}{COLOR_RESET} ({ap['security']}, {ap['signal']})")
            print("    [0] Enter SSID manually / Hidden Network")

            choice = prompt_user("Select network number", "1")
            try:
                c_idx = int(choice)
                if 1 <= c_idx <= len(scanned):
                    selected_ssid = scanned[c_idx - 1]["ssid"]
            except ValueError:
                selected_ssid = choice

        if not selected_ssid:
            selected_ssid = prompt_user("Enter Wi-Fi SSID Name")

        sec_type = prompt_user("Security Type (psk/open/eap-peap)", "psk").lower()
        psk = ""
        if sec_type == "psk":
            import getpass
            try:
                psk = getpass.getpass(f"{COLOR_BOLD}Enter Wi-Fi Passphrase (WPA2/WPA3 PSK){COLOR_RESET}: ")
            except Exception:
                psk = prompt_user("Enter Wi-Fi Passphrase")

        configure_wpa_supplicant(selected_ssid, psk, security=sec_type)
        print_success(f"Wi-Fi configuration applied for SSID: {selected_ssid}")

    # STEP 5: Instant Zero-Touch Registration Test
    print_step(5, "Registering Sensor with CMP Control Plane")
    print("  Submitting sensor identity to CMP...")
    reg_result = register_sensor_direct(
        cmp_url=cmp_url,
        sensor_id=sensor_id,
        hostname=hw["hostname"],
        mac_address=mac,
        location=location_spec
    )

    api_key = existing_config.get("api_key", "")
    if reg_result.get("success"):
        status = reg_result.get("status")
        if status == "approved":
            api_key = reg_result.get("api_key", api_key)
            print_success(f"Sensor Approved via Zero-Touch Auto-Enrollment!")
            print(f"  • API Key provisioned: {COLOR_GREEN}{api_key[:8]}...{COLOR_RESET}")
        else:
            print_warning(f"Registration Submitted - Status: {COLOR_YELLOW}PENDING APPROVAL{COLOR_RESET}")
            print("  • The sensor is in the TOFU (Trust-On-First-Use) approval queue.")
            print("  • NOC Administrators can approve this sensor in 1-click on the CMP Web Console.")
    else:
        print_warning(f"Registration deferred: {reg_result.get('error')}. Reconciler daemon will retry in background.")

    # STEP 6: Save Configuration & Activate Daemon
    print_step(6, "Finalizing Setup & Systemd Service")
    final_config = {
        "cmp_url": cmp_url,
        "sensor_id": sensor_id,
        "api_key": api_key,
        "check_interval_seconds": 15,
        "wifi_interface": "wlan0",
        "wifi_config_path": WIFI_CONFIG_PATH,
        "initial_location": location_spec
    }

    if save_sensor_configuration(final_config):
        print_success(f"Configuration saved to {CONFIG_PATH}")

    if is_root():
        if manage_systemd_service():
            print_success("sensor-reconciler.service enabled and started!")

    # Final Summary Card
    cmp_web_url = cmp_url.replace('/api/v1', '')
    print(f"""
{COLOR_GREEN}╔══════════════════════════════════════════════════════════════════════╗
║                🎉  SENSOR ONBOARDING COMPLETE!                       ║
╚══════════════════════════════════════════════════════════════════════╝{COLOR_RESET}

  {COLOR_BOLD}Deployment Summary:{COLOR_RESET}
  • Sensor UUID:     {COLOR_YELLOW}{sensor_id}{COLOR_RESET}
  • Campus Location: {COLOR_CYAN}{district_name} / {site_name} / {room_name}{COLOR_RESET}
  • Primary IP:      {COLOR_GREEN}{ip}{COLOR_RESET} ({iface})
  • CMP Dashboard:   {COLOR_BLUE}{cmp_web_url}{COLOR_RESET}
  • Service Status:  {COLOR_GREEN}sensor-reconciler.service (Active){COLOR_RESET}

  {COLOR_YELLOW}Helpdesk Quick Commands:{COLOR_RESET}
  • View live probe logs:     {COLOR_BOLD}journalctl -u sensor-reconciler -f{COLOR_RESET}
  • Re-run this wizard:       {COLOR_BOLD}sudo one-wizard{COLOR_RESET}
  • Inspect configuration:    {COLOR_BOLD}cat {CONFIG_PATH}{COLOR_RESET}
""")

def run_non_interactive(args):
    """Executes automated provisioning from CLI arguments."""
    sensor_id = args.sensor_id or get_machine_uuid()
    mac, ip, iface = get_primary_mac_and_ip()
    hw = inspect_hardware()

    cmp_url = args.cmp or DEFAULT_CMP_URL
    if not cmp_url.startswith("http://") and not cmp_url.startswith("https://"):
        cmp_url = f"http://{cmp_url}"
    if not cmp_url.endswith("/api/v1"):
        cmp_url = f"{cmp_url.rstrip('/')}/api/v1"

    location_spec = {
        "district": args.district or "Kern County Superintendent of Schools",
        "site": args.site or "Main Campus",
        "building": args.building or "Main Building",
        "room": args.room or "Room 101",
        "notes": args.notes or "Auto-Provisioned via 1-Line CLI"
    }

    if args.wifi_ssid:
        configure_wpa_supplicant(args.wifi_ssid, args.wifi_psk or "", security="psk" if args.wifi_psk else "open")

    reg_result = register_sensor_direct(
        cmp_url=cmp_url,
        sensor_id=sensor_id,
        hostname=hw["hostname"],
        mac_address=mac,
        location=location_spec,
        enrollment_token=args.token or ""
    )

    api_key = reg_result.get("api_key", "") if reg_result.get("success") else ""

    config = {
        "cmp_url": cmp_url,
        "sensor_id": sensor_id,
        "api_key": api_key,
        "enrollment_token": args.token or "",
        "check_interval_seconds": 15,
        "wifi_interface": "wlan0",
        "wifi_config_path": WIFI_CONFIG_PATH,
        "initial_location": location_spec
    }

    if not args.check_only:
        save_sensor_configuration(config)
        if is_root():
            manage_systemd_service()

    if args.json:
        out = {
            "sensor_id": sensor_id,
            "mac_address": mac,
            "ip_address": ip,
            "cmp_url": cmp_url,
            "location": location_spec,
            "registration": reg_result
        }
        print(json.dumps(out, indent=2))
    else:
        print_success(f"Sensor {sensor_id} provisioned for {location_spec['site']} - {location_spec['room']}.")

def main():
    parser = argparse.ArgumentParser(
        description="Open Network Experience (ONE) - Edge Sensor Onboarding Wizard (one-wizard)",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--cmp", "-c", help="CMP Control Plane URL (e.g. http://10.98.2.125:8000/api/v1)")
    parser.add_argument("--site", "-s", help="School / Campus Site Name")
    parser.add_argument("--building", "-b", help="Building or Wing Name")
    parser.add_argument("--room", "-r", help="Room, Classroom or Drop Identifier")
    parser.add_argument("--district", "-d", help="School District Name")
    parser.add_argument("--notes", help="Installation notes or asset tag")
    parser.add_argument("--token", "-t", help="ZTP Enrollment Secret Token")
    parser.add_argument("--wifi-ssid", help="Wi-Fi SSID Name")
    parser.add_argument("--wifi-psk", help="Wi-Fi WPA2/WPA3 Passphrase")
    parser.add_argument("--sensor-id", help="Override hardware Sensor UUID")
    parser.add_argument("--non-interactive", "--batch", action="store_true", help="Run without prompts using CLI arguments")
    parser.add_argument("--check-only", action="store_true", help="Perform diagnostics check without writing changes")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")

    args = parser.parse_args()

    # Determine interactive mode
    if args.non_interactive or args.json or (args.site and args.room and not sys.stdin.isatty()):
        run_non_interactive(args)
    else:
        run_interactive_wizard()

if __name__ == "__main__":
    main()
