#!/usr/bin/env python3
"""
Wi-Fi Association & DHCP Lease Timing Exporter
Parses systemd journal logs to measure L2/L3 onboarding metrics:
  - Wi-Fi Association Time (seconds)
  - Wi-Fi Authentication Time (seconds)
  - DHCP Lease Acquisition Time (seconds)
Outputs metrics in Prometheus format for Node Exporter textfile collector.
"""

import os
import sys
import re
import time
import subprocess

# Output Prometheus metrics path
DEFAULT_OUTPUT_FILE = "/var/lib/node_exporter/textfile_collector/wifi_dhcp.prom"

# Log patterns for systemd journal parser
PATTERNS = {
    "wifi_assoc_start": re.compile(r"wpa_supplicant.*Trying to associate with SSID '(?P<ssid>[^']+)'"),
    "wifi_assoc_end": re.compile(r"wpa_supplicant.*Associated with (?P<bssid>[0-9a-fA-F:]{17})"),
    "wifi_auth_complete": re.compile(r"wpa_supplicant.*CTRL-EVENT-CONNECTED"),
    
    # DHCP triggers (dhclient, dhcpcd, NetworkManager)
    "dhcp_start": re.compile(
        r"(dhclient.*DHCPDISCOVER|dhcpcd.*soliciting a DHCP lease|NetworkManager.*DHCP.*state.*changed.*select|systemd-networkd.*DHCPv4.*request)"
    ),
    "dhcp_ack": re.compile(
        r"(dhclient.*bound to (?P<ip>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})|dhcpcd.*leased (?P<ip2>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})|NetworkManager.*DHCP.*state.*changed.*bound|systemd-networkd.*DHCPv4.*address.*added)"
    )
}

def parse_journal():
    """Queries systemd journal for recent network manager and supplicant logs."""
    try:
        # Fetch the last 2000 lines of system logs
        cmd = ["journalctl", "-n", "2000", "--no-pager", "-o", "short-iso"]
        output = subprocess.check_output(cmd, text=True)
        return output.splitlines()
    except Exception as e:
        print(f"Error reading systemd journal: {e}", file=sys.stderr)
        return []

def calculate_timings(log_lines):
    """Calculates association, authentication, and DHCP lease times from logs."""
    metrics = {
        "wifi_association_seconds": -1.0,
        "wifi_authentication_seconds": -1.0,
        "dhcp_lease_seconds": -1.0,
        "onboarding_success": 0,
        "ssid": "unknown",
        "bssid": "unknown"
    }

    # Tracking variables for timestamps
    t_assoc_start = None
    t_assoc_end = None
    t_auth_complete = None
    t_dhcp_start = None
    t_dhcp_ack = None

    # Parse ISO-8601 timestamps in journal output (e.g., "2026-08-24T19:37:25-0700")
    # Matches the timestamp portion at the beginning of each line
    timestamp_pattern = re.compile(r"^(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:?\d{2}?)")

    def parse_time(line):
        match = timestamp_pattern.match(line)
        if match:
            ts_str = match.group("ts")
            # Replace final colon in offset (e.g. -07:00 -> -0700) for standard ISO parser compatibility
            if len(ts_str) > 19 and ts_str[-3] == ":":
                ts_str = ts_str[:-3] + ts_str[-2:]
            try:
                # ISO-8601 parser fallback for python 3.7+
                from datetime import datetime
                dt = datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%S%z")
                return dt.timestamp()
            except Exception:
                pass
        return None

    # Walk through log lines chronologically
    for line in log_lines:
        t_val = parse_time(line)
        if not t_val:
            continue

        # Match Wi-Fi association initiation
        m = PATTERNS["wifi_assoc_start"].search(line)
        if m:
            t_assoc_start = t_val
            metrics["ssid"] = m.group("ssid")
            # Reset subsequent markers to trace a fresh cycle
            t_assoc_end = None
            t_auth_complete = None
            t_dhcp_start = None
            t_dhcp_ack = None
            continue

        # Match Wi-Fi association completion
        m = PATTERNS["wifi_assoc_end"].search(line)
        if m and t_assoc_start:
            t_assoc_end = t_val
            metrics["bssid"] = m.group("bssid")
            metrics["wifi_association_seconds"] = max(0.0, t_assoc_end - t_assoc_start)
            continue

        # Match Wi-Fi auth completion (CTRL-EVENT-CONNECTED)
        m = PATTERNS["wifi_auth_complete"].search(line)
        if m and t_assoc_end:
            t_auth_complete = t_val
            metrics["wifi_authentication_seconds"] = max(0.0, t_auth_complete - t_assoc_end)
            continue

        # Match DHCP initiation
        m = PATTERNS["dhcp_start"].search(line)
        if m:
            t_dhcp_start = t_val
            continue

        # Match DHCP bound / ACK
        m = PATTERNS["dhcp_ack"].search(line)
        if m and t_dhcp_start:
            t_dhcp_ack = t_val
            metrics["dhcp_lease_seconds"] = max(0.0, t_dhcp_ack - t_dhcp_start)
            metrics["onboarding_success"] = 1
            continue

    return metrics

def main():
    output_file = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_OUTPUT_FILE
    
    print("Parsing system log events for L2/L3 onboarding timing...")
    log_lines = parse_journal()
    metrics = calculate_timings(log_lines)

    prom_lines = [
        "# HELP wifi_association_duration_seconds Time taken to associate with the AP",
        "# TYPE wifi_association_duration_seconds gauge",
        f'wifi_association_duration_seconds{{ssid="{metrics["ssid"]}",bssid="{metrics["bssid"]}"}} {metrics["wifi_association_seconds"]:.4f}',
        
        "# HELP wifi_authentication_duration_seconds Time taken to complete WPA/EAP authentication",
        "# TYPE wifi_authentication_duration_seconds gauge",
        f'wifi_authentication_duration_seconds{{ssid="{metrics["ssid"]}",bssid="{metrics["bssid"]}"}} {metrics["wifi_authentication_seconds"]:.4f}',
        
        "# HELP wifi_dhcp_lease_duration_seconds Time taken to obtain a DHCP lease",
        "# TYPE wifi_dhcp_lease_duration_seconds gauge",
        f'wifi_dhcp_lease_duration_seconds{{ssid="{metrics["ssid"]}",bssid="{metrics["bssid"]}"}} {metrics["dhcp_lease_seconds"]:.4f}',
        
        "# HELP wifi_onboarding_success Indicates if the onboarding handshake completed successfully. 1 = Success, 0 = Failure/Incomplete",
        "# TYPE wifi_onboarding_success gauge",
        f'wifi_onboarding_success{{ssid="{metrics["ssid"]}"}} {metrics["onboarding_success"]}'
    ]

    prom_content = "\n".join(prom_lines) + "\n"

    # Write the output metrics atomically
    try:
        dirname = os.path.dirname(output_file)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        tmp_path = output_file + ".tmp"
        with open(tmp_path, "w") as f:
            f.write(prom_content)
        os.replace(tmp_path, output_file)
        print(f"Onboarding metrics written to {output_file}")
        print(f" - SSID: {metrics['ssid']} | BSSID: {metrics['bssid']}")
        print(f" - Association Time:    {metrics['wifi_association_seconds']:.4f}s")
        print(f" - Authentication Time: {metrics['wifi_authentication_seconds']:.4f}s")
        print(f" - DHCP Lease Time:     {metrics['dhcp_lease_seconds']:.4f}s")
    except Exception as e:
        print(f"Failed to write metrics: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
