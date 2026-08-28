#!/usr/bin/env python3
"""
Forensic Evidence Snapshot Bundler (Phase 2 Diagnostic Packaging)
Aggregates incident PCAP slices, Playwright HAR files, systemd journal logs,
Wi-Fi RF parameters, and routing state into an audit-ready diagnostic bundle (.tar.gz).

Used for:
  - Immediate incident escalation to ISP or firewall vendors (Fortinet / Palo Alto).
  - Proof of intermittent state testing (CAASPP) or Wi-Fi degradation.
  - One-click NOC diagnostic package downloads.
"""

import os
import sys
import json
import time
import tarfile
import tempfile
import subprocess
from typing import Dict, Any, Optional, List

SNAPSHOTS_DIR = "/var/lib/sensor/snapshots"
EVIDENCE_BUNDLE_DIR = "/var/lib/sensor/evidence_bundles"

def ensure_dirs():
    os.makedirs(SNAPSHOTS_DIR, exist_ok=True)
    os.makedirs(EVIDENCE_BUNDLE_DIR, exist_ok=True)

def collect_system_telemetry(staging_dir: str):
    """Gathers networking, Wi-Fi, and routing diagnostics into staging folder."""
    # 1. Wi-Fi RF state
    try:
        wlan_out = subprocess.check_output(["iw", "dev", "wlan0", "link"], stderr=subprocess.DEVNULL, text=True)
        with open(os.path.join(staging_dir, "wifi_link.txt"), "w") as f:
            f.write(wlan_out)
    except Exception:
        pass

    # 2. IP addresses and routing tables
    try:
        ip_addr = subprocess.check_output(["ip", "addr"], stderr=subprocess.DEVNULL, text=True)
        ip_route = subprocess.check_output(["ip", "route", "show", "table", "all"], stderr=subprocess.DEVNULL, text=True)
        with open(os.path.join(staging_dir, "network_ip_route.txt"), "w") as f:
            f.write(f"=== IP ADDR ===\n{ip_addr}\n\n=== IP ROUTE ===\n{ip_route}")
    except Exception:
        pass

    # 3. DNS Resolvers
    if os.path.exists("/etc/resolv.conf"):
        try:
            with open("/etc/resolv.conf", "r") as src, open(os.path.join(staging_dir, "resolv.conf"), "w") as dst:
                dst.write(src.read())
        except Exception:
            pass

    # 4. System journal (Wi-Fi & DHCP events)
    try:
        journal_out = subprocess.check_output(
            ["journalctl", "-n", "200", "--no-pager"],
            stderr=subprocess.DEVNULL,
            text=True
        )
        with open(os.path.join(staging_dir, "journal_recent.log"), "w") as f:
            f.write(journal_out)
    except Exception:
        pass

def package_evidence_bundle(
    sensor_id: str,
    reason: str = "manual_trigger",
    include_latest_pcap: bool = True
) -> Optional[str]:
    """
    Creates a compressed tarball containing logs, RF states, metrics, and the latest PCAP slice.
    Returns the absolute path to the generated .tar.gz bundle.
    """
    ensure_dirs()
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    bundle_name = f"evidence_{sensor_id}_{timestamp}_{reason}.tar.gz"
    bundle_path = os.path.join(EVIDENCE_BUNDLE_DIR, bundle_name)

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Collect system state
        collect_system_telemetry(tmp_dir)

        # Include latest PCAP snapshot if available
        if include_latest_pcap and os.path.exists(SNAPSHOTS_DIR):
            import glob
            pcaps = sorted(glob.glob(f"{SNAPSHOTS_DIR}/*.pcap"), key=os.path.getmtime)
            if pcaps:
                latest_pcap = pcaps[-1]
                subprocess.run(["cp", latest_pcap, tmp_dir], check=False)
                if os.path.exists(latest_pcap + ".json"):
                    subprocess.run(["cp", latest_pcap + ".json", tmp_dir], check=False)

        # Include current metric prom files
        metrics_dir = "/var/lib/node_exporter/textfile_collector"
        if os.path.exists(metrics_dir):
            prom_files = glob.glob(f"{metrics_dir}/*.prom")
            metrics_stage = os.path.join(tmp_dir, "metrics")
            os.makedirs(metrics_stage, exist_ok=True)
            for pf in prom_files:
                subprocess.run(["cp", pf, metrics_stage], check=False)

        # Write bundle metadata manifest
        manifest = {
            "sensor_id": sensor_id,
            "timestamp": int(time.time()),
            "datetime": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "reason": reason,
            "bundle_file": bundle_name
        }
        with open(os.path.join(tmp_dir, "manifest.json"), "w") as f:
            json.dump(manifest, f, indent=2)

        # Create .tar.gz archive
        with tarfile.open(bundle_path, "w:gz") as tar:
            tar.add(tmp_dir, arcname=f"evidence_{timestamp}")

    print(f"\033[92m[EVIDENCE BUNDLE CREATED]\033[0m {bundle_path} ({os.path.getsize(bundle_path)} bytes)")
    return bundle_path

def main():
    import argparse
    parser = argparse.ArgumentParser(description="OpenUX Diagnostic Evidence Bundler")
    parser.add_argument("--sensor-id", default="local-sensor", help="Sensor hardware identifier")
    parser.add_argument("--reason", default="manual_export", help="Reason for evidence capture")
    parser.add_argument("--no-pcap", action="store_true", help="Exclude PCAP snapshots")

    args = parser.parse_args()

    bundle = package_evidence_bundle(
        sensor_id=args.sensor_id,
        reason=args.reason,
        include_latest_pcap=not args.no_pcap
    )

    if bundle:
        print(f"Archive path: {bundle}")
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
