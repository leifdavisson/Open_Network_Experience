#!/usr/bin/env python3
"""
Forensic Evidence Snapshot Bundler (Phase 2 Enhanced)
Aggregates incident PCAP slices, Playwright HAR files, systemd journal logs,
Wi-Fi RF parameters, and routing state into an audit-ready diagnostic bundle (.tar.gz).

Includes a Plain-English Human-Readable Incident Summary (HTML & Text)
designed for teachers, school principals, district leadership, and NOC technicians.
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

def generate_plain_english_summary(sensor_id: str, reason: str, timestamp: str) -> Tuple[str, str]:
    """
    Translates technical telemetry into plain-English answers for non-technical stakeholders:
    1. What happened?
    2. Who is affected?
    3. What is the root cause?
    4. How do we fix it?
    """
    human_explanations = {
        "caaspp_failure": {
            "title": "State Testing (CAASPP / ELPAC) Connection Failure",
            "what_happened": "The sensor could not connect to California State Assessment testing servers, or the firewall attempted to inspect secure test traffic.",
            "impact": "Students taking online CAASPP/ELPAC tests in this room/wing may be kicked out or receive Secure Browser certificate errors.",
            "recommended_action": "Verify that firewall SSL inspection is completely bypassed for *.caaspp-elpac.org and *.tds.cambiumast.com."
        },
        "wifi_flapping": {
            "title": "Excessive Wi-Fi Channel Hopping (AP Flapping)",
            "what_happened": "The local Wi-Fi Access Point changed radio channels multiple times within the hour due to radio interference.",
            "impact": "Laptops and Chromebooks will experience intermittent 5-10 second pauses and video buffering.",
            "recommended_action": "Check for microwave/radar interference or lock the Access Point channel to avoid aggressive dynamic channel hopping (DARRP/GSK)."
        },
        "dhcp_exhaustion": {
            "title": "DHCP Address Assignment Failure",
            "what_happened": "The sensor asked for an IP address but the network router/server did not respond in time.",
            "impact": "New student devices arriving in this classroom will show 'Connected, No Internet' or fail to connect.",
            "recommended_action": "Expand the DHCP pool scope on the core network switch/router for this VLAN."
        },
        "high_latency_spike": {
            "title": "Internet Connection Latency Spike (>200ms)",
            "what_happened": "Internet response times surged dramatically, creating noticeable slowdowns.",
            "impact": "Websites will load sluggishly and teacher video lessons may freeze.",
            "recommended_action": "Check if an active bandwidth test, large software update, or ISP circuit congestion is occurring."
        },
        "cipa_filter_failure": {
            "title": "CIPA Web Content Filter Policy Alert",
            "what_happened": "A designated restricted category test token was accessible without being blocked by the school internet filter.",
            "impact": "Potential compliance warning for E-Rate federal funding requirements.",
            "recommended_action": "Review the content filter category policies on the school firewall or web security proxy."
        }
    }

    info = human_explanations.get(reason, {
        "title": f"Network Diagnostic Incident ({reason})",
        "what_happened": f"An automated network diagnostic check detected an anomaly ({reason}).",
        "impact": "Users connected in this area may experience connectivity or application slowness.",
        "recommended_action": "Review the attached PCAP packet slice and system logs for detailed root cause."
    })

    # Plain Text Summary
    text_summary = f"""================================================================================
                    OPENUX INCIDENT FORENSIC REPORT
================================================================================
Sensor ID:            {sensor_id}
Incident Date/Time:   {timestamp}
Incident Category:    {info['title']}

--------------------------------------------------------------------------------
1. WHAT HAPPENED?
   {info['what_happened']}

2. WHO IS AFFECTED?
   {info['impact']}

3. RECOMMENDED ACTION FOR IT / VENDOR:
   {info['recommended_action']}

--------------------------------------------------------------------------------
ATTACHED FORENSIC EVIDENCE IN THIS BUNDLE:
  - incident_*.pcap       : Raw network packet capture (128-byte header slice)
  - wifi_link.txt         : Physical Wi-Fi signal strength (RSSI) & SNR details
  - journal_recent.log    : System event logs (Association, WPA Handshake, DHCP)
  - network_ip_route.txt  : Network routing table and gateway configuration
  - metrics/              : Exact numeric Prometheus performance records
================================================================================
"""

    # HTML Executive Incident Card
    html_summary = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>OpenUX Incident Report - {info['title']}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 30px; }}
        .card {{ max-width: 800px; margin: 0 auto; background: #1e293b; border-radius: 12px; padding: 30px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); border-left: 6px solid #ef4444; }}
        h1 {{ color: #f8fafc; font-size: 24px; margin-top: 0; }}
        .badge {{ display: inline-block; background: #dc2626; color: white; padding: 4px 12px; border-radius: 9999px; font-weight: bold; font-size: 12px; text-transform: uppercase; }}
        .meta {{ color: #94a3b8; font-size: 14px; margin: 15px 0 25px 0; }}
        .section {{ margin-bottom: 20px; }}
        .section-title {{ font-size: 14px; font-weight: bold; color: #38bdf8; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px; }}
        .section-body {{ font-size: 16px; line-height: 1.6; color: #e2e8f0; background: #334155; padding: 14px; border-radius: 8px; }}
        .action-box {{ background: #064e3b; border: 1px solid #059669; color: #a7f3d0; padding: 16px; border-radius: 8px; font-weight: 500; font-size: 15px; }}
        .evidence-list {{ list-style-type: none; padding-left: 0; font-size: 14px; color: #cbd5e1; }}
        .evidence-list li {{ padding: 6px 0; border-bottom: 1px solid #334155; }}
    </style>
</head>
<body>
    <div class="card">
        <span class="badge">Diagnostic Incident Alert</span>
        <h1>{info['title']}</h1>
        <div class="meta">Sensor: <strong>{sensor_id}</strong> &bull; Timestamp: <strong>{timestamp}</strong></div>

        <div class="section">
            <div class="section-title">1. What Happened?</div>
            <div class="section-body">{info['what_happened']}</div>
        </div>

        <div class="section">
            <div class="section-title">2. Who Is Impacted?</div>
            <div class="section-body">{info['impact']}</div>
        </div>

        <div class="section">
            <div class="section-title">3. How to Fix It (Remediation)</div>
            <div class="action-box">🛠️ {info['recommended_action']}</div>
        </div>

        <div class="section">
            <div class="section-title">4. Included Evidence in this Package</div>
            <ul class="evidence-list">
                <li>📁 <strong>Raw Packet Capture (PCAP)</strong>: First 128 bytes of packets preserved for TLS/DNS/TCP analysis.</li>
                <li>📁 <strong>Wi-Fi Link & RF State</strong>: Live signal strength (RSSI), SNR, channel width, and BSSID.</li>
                <li>📁 <strong>System Event Logs</strong>: Journal logs of 802.11 Association, WPA 4-way handshake, and DHCP DORA.</li>
                <li>📁 <strong>Network Routing & DNS</strong>: Subnet masks, default gateway, and active nameservers.</li>
            </ul>
        </div>
    </div>
</body>
</html>
"""
    return text_summary, html_summary

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
    Creates a compressed tarball containing logs, RF states, metrics, the latest PCAP slice,
    and a Plain-English Human-Readable Incident Summary.
    """
    ensure_dirs()
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    dt_formatted = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    bundle_name = f"evidence_{sensor_id}_{timestamp}_{reason}.tar.gz"
    bundle_path = os.path.join(EVIDENCE_BUNDLE_DIR, bundle_name)

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Collect system state
        collect_system_telemetry(tmp_dir)

        # Generate Plain-English Incident Summary (Text & HTML)
        txt_sum, html_sum = generate_plain_english_summary(sensor_id, reason, dt_formatted)
        with open(os.path.join(tmp_dir, "incident_summary.txt"), "w") as f:
            f.write(txt_sum)
        with open(os.path.join(tmp_dir, "incident_summary.html"), "w") as f:
            f.write(html_sum)

        # Include latest PCAP snapshot if available
        if include_latest_pcap and os.path.exists(SNAPSHOTS_DIR):
            import glob
            pcaps = sorted(glob.glob(f"{SNAPSHOTS_DIR}/*.pcap"), key=os.path.getmtime)
            if pcaps:
                latest_pcap = pcaps[-1]
                subprocess.run(["cp", latest_pcap, tmp_dir], check=False)
                if os.path.exists(latest_pcap + ".json"):
                    subprocess.run(["cp", latest_pcap + ".json", tmp_dir], check=False)

        # Include Playwright failure screenshots or HARs if present in snapshots
        import glob
        browser_snaps = glob.glob(f"{SNAPSHOTS_DIR}/browser_failure_*")
        for bs in browser_snaps:
            subprocess.run(["cp", bs, tmp_dir], check=False)

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
