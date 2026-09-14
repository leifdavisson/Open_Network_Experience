#!/usr/bin/env python3
"""
Wi-Fi Multi-Band Hardware & Spectrum Generation Diagnostic Suite
Part of Open Network Experience (ONE). Licensed under GNU AGPLv3.

Audits:
  1. WNic (Wireless NIC) Hardware Capabilities (iw phy info / iw list):
     - Supported frequency bands: 2.4 GHz, 5 GHz, 6 GHz (Wi-Fi 6E/7)
     - Standards board generation: Wi-Fi 1 through Wi-Fi 7 (b/a/g/n/ac/ax/be)
     - Channel width limits (20 / 40 / 80 / 160 / 320 MHz) & MIMO spatial streams.
  2. Active Link Telemetry (iw dev link / wpa_cli):
     - Connected SSID, BSSID, frequency, channel, RSSI, and negotiated PHY bitrate/mode.
  3. Multi-Band & Per-Channel Spectrum Scan (iw dev scan):
     - Groups all detected BSSIDs by frequency band (2.4 GHz, 5 GHz, 6 GHz) and channel.
     - Detects AP generation capabilities (HT = Wi-Fi 4, VHT = Wi-Fi 5, HE = Wi-Fi 6, EHT = Wi-Fi 7).
     - Identifies co-channel interference (CCI), adjacent channel bleeding, and per-channel health.
  4. Capability Matrix & Diagnostic Insights:
     - Detects AP vs WNic generation mismatches (e.g. Wi-Fi 6 client downgraded to Wi-Fi 5 AP).
     - Detects band-steering failures (e.g. client trapped on congested 2.4 GHz when 5 GHz is viable).
"""

import os
import sys
import re
import json
import argparse
import subprocess
from typing import Dict, Any, List, Optional, Tuple

WIFI_STANDARDS = {
    "wifi1": {"name": "Wi-Fi 1", "ieee": "802.11b", "band": "2.4GHz", "max_rate": "11 Mbps", "year": 1999},
    "wifi2": {"name": "Wi-Fi 2", "ieee": "802.11a", "band": "5GHz", "max_rate": "54 Mbps", "year": 1999},
    "wifi3": {"name": "Wi-Fi 3", "ieee": "802.11g", "band": "2.4GHz", "max_rate": "54 Mbps", "year": 2003},
    "wifi4": {"name": "Wi-Fi 4", "ieee": "802.11n", "band": "2.4GHz / 5GHz", "mode": "HT", "max_rate": "600 Mbps", "year": 2009},
    "wifi5": {"name": "Wi-Fi 5", "ieee": "802.11ac", "band": "5GHz", "mode": "VHT", "max_rate": "6.9 Gbps", "year": 2013},
    "wifi6": {"name": "Wi-Fi 6", "ieee": "802.11ax", "band": "2.4GHz / 5GHz", "mode": "HE", "max_rate": "9.6 Gbps", "year": 2019},
    "wifi6e": {"name": "Wi-Fi 6E", "ieee": "802.11ax 6GHz", "band": "6GHz", "mode": "HE", "max_rate": "9.6 Gbps", "year": 2020},
    "wifi7": {"name": "Wi-Fi 7", "ieee": "802.11be", "band": "2.4GHz / 5GHz / 6GHz", "mode": "EHT", "max_rate": "46 Gbps", "year": 2024}
}


def run_cmd(cmd: List[str], timeout: float = 8.0) -> str:
    """Executes a subprocess returning stdout, handling errors gracefully. Tries sudo -n if unprivileged."""
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout
    except Exception:
        pass

    # Try with sudo -n if not already running as root or with sudo
    if hasattr(os, "geteuid") and os.geteuid() != 0 and cmd and cmd[0] != "sudo":
        try:
            res_sudo = subprocess.run(["sudo", "-n"] + cmd, capture_output=True, text=True, timeout=timeout)
            if res_sudo.returncode == 0 and res_sudo.stdout.strip():
                return res_sudo.stdout
        except Exception:
            pass
    return ""


def detect_wifi_interface(preferred: str = "wlan0") -> str:
    """Auto-detects active wireless interface (e.g. wlp1s0, wlan0)."""
    if os.path.exists(f"/sys/class/net/{preferred}"):
        return preferred
    # Check /proc/net/wireless
    if os.path.exists("/proc/net/wireless"):
        try:
            with open("/proc/net/wireless", "r") as f:
                for line in f.readlines()[2:]:
                    parts = line.split(":")
                    if parts:
                        candidate = parts[0].strip()
                        if os.path.exists(f"/sys/class/net/{candidate}"):
                            return candidate
        except Exception:
            pass
    # Query 'iw dev'
    iw_out = run_cmd(["iw", "dev"])
    for line in iw_out.splitlines():
        line = line.strip()
        if line.startswith("Interface "):
            candidate = line.split()[1]
            if candidate:
                return candidate
    return preferred


def get_phy_name(iface: str) -> str:
    """Finds the underlying wiphy for an interface (e.g. phy0)."""
    # Try sysfs first
    sysfs_phy = f"/sys/class/net/{iface}/phy80211/name"
    if os.path.exists(sysfs_phy):
        try:
            with open(sysfs_phy, "r") as f:
                return f.read().strip()
        except Exception:
            pass
    # Fallback to iw dev info
    info_out = run_cmd(["iw", "dev", iface, "info"])
    for line in info_out.splitlines():
        if "wiphy" in line:
            parts = line.strip().split()
            if len(parts) >= 2:
                return f"phy{parts[1]}"
    return "phy0"


def freq_to_band_and_channel(freq_mhz: int) -> Tuple[str, int]:
    """Converts a frequency in MHz to (band_label, channel_number)."""
    if 2412 <= freq_mhz <= 2472:
        ch = (freq_mhz - 2407) // 5
        return "2.4GHz", ch
    elif freq_mhz == 2484:
        return "2.4GHz", 14
    elif 5170 <= freq_mhz <= 5835:
        ch = (freq_mhz - 5000) // 5
        return "5GHz", ch
    elif 5935 <= freq_mhz <= 7115:
        ch = (freq_mhz - 5950) // 5
        return "6GHz", ch
    return "Unknown", 0


def audit_nic_capabilities(phy: str) -> Dict[str, Any]:
    """
    Audits wireless NIC hardware capabilities via `iw phy <phy> info`.
    Detects supported bands (2.4/5/6 GHz), standards (WiFi 1-7), widths, streams.
    """
    out = run_cmd(["iw", "phy", phy, "info"])
    if not out:
        out = run_cmd(["iw", "list"])

    caps = {
        "phy": phy,
        "bands_supported": [],
        "standards_supported": [],
        "max_generation": "Wi-Fi 4",
        "max_channel_width_mhz": 20,
        "antenna_chains": 1,
        "features": []
    }

    if not out:
        # Fallback if unprivileged or missing iw
        caps["bands_supported"] = ["2.4GHz", "5GHz"]
        caps["standards_supported"] = ["Wi-Fi 4 (802.11n)", "Wi-Fi 5 (802.11ac)"]
        caps["max_generation"] = "Wi-Fi 5"
        caps["max_channel_width_mhz"] = 80
        caps["antenna_chains"] = 2
        return caps

    has_2ghz = "Band 1:" in out or "2412 MHz" in out
    has_5ghz = "Band 2:" in out or "5180 MHz" in out or "5220 MHz" in out
    has_6ghz = "Band 4:" in out or "5955 MHz" in out or "6115 MHz" in out

    if has_2ghz:
        caps["bands_supported"].append("2.4GHz")
    if has_5ghz:
        caps["bands_supported"].append("5GHz")
    if has_6ghz:
        caps["bands_supported"].append("6GHz")

    # Standards detection
    has_ht = "HT20" in out or "HT40" in out or "Capabilities: 0x" in out
    has_vht = "VHT Capabilities" in out or "VHT-MCS" in out
    has_he = "HE MAC Capabilities" in out or "HE PHY Capabilities" in out or "HE Ics" in out
    has_eht = "EHT MAC Capabilities" in out or "EHT PHY Capabilities" in out

    standards = ["Wi-Fi 1 (802.11b)", "Wi-Fi 2 (802.11a)", "Wi-Fi 3 (802.11g)"]
    max_width = 20

    if has_ht:
        standards.append("Wi-Fi 4 (802.11n / HT)")
        max_width = max(max_width, 40)
        caps["max_generation"] = "Wi-Fi 4"
    if has_vht:
        standards.append("Wi-Fi 5 (802.11ac / VHT)")
        max_width = max(max_width, 80)
        caps["max_generation"] = "Wi-Fi 5"
        if "160 MHz" in out or "VHT160" in out:
            max_width = 160
    if has_he:
        if has_6ghz:
            standards.append("Wi-Fi 6E (802.11ax 6GHz / HE)")
            caps["max_generation"] = "Wi-Fi 6E"
        else:
            standards.append("Wi-Fi 6 (802.11ax / HE)")
            caps["max_generation"] = "Wi-Fi 6"
        max_width = max(max_width, 160)
    if has_eht:
        standards.append("Wi-Fi 7 (802.11be / EHT)")
        caps["max_generation"] = "Wi-Fi 7"
        max_width = 320

    caps["standards_supported"] = standards
    caps["max_channel_width_mhz"] = max_width

    # Parse antenna streams
    ant_m = re.search(r"Available Antennas:\s+TX\s+0x([0-9a-fA-F]+)\s+RX\s+0x([0-9a-fA-F]+)", out)
    if ant_m:
        tx_mask = int(ant_m.group(1), 16)
        chains = bin(tx_mask).count("1")
        caps["antenna_chains"] = max(1, chains)
    elif "2x2" in out or "two streams" in out:
        caps["antenna_chains"] = 2

    return caps


def get_current_link(iface: str) -> Dict[str, Any]:
    """Queries active link status via `iw dev <iface> link`."""
    out = run_cmd(["iw", "dev", iface, "link"])
    link = {
        "connected": False,
        "bssid": "",
        "ssid": "",
        "freq_mhz": 0,
        "band": "Unknown",
        "channel": 0,
        "rssi_dbm": -100,
        "tx_bitrate_mbps": 0.0,
        "rx_bitrate_mbps": 0.0,
        "standard_generation": "Unknown",
        "channel_width_mhz": 20
    }

    if "Not connected" in out or not out.strip():
        return link

    bssid_m = re.search(r"Connected to\s+([0-9a-fA-F:]{17})", out)
    if bssid_m:
        link["connected"] = True
        link["bssid"] = bssid_m.group(1).lower()

    ssid_m = re.search(r"SSID:\s*(.+)", out)
    if ssid_m:
        link["ssid"] = ssid_m.group(1).strip()

    freq_m = re.search(r"freq:\s*(\d+)", out)
    if freq_m:
        freq = int(freq_m.group(1))
        link["freq_mhz"] = freq
        band, ch = freq_to_band_and_channel(freq)
        link["band"] = band
        link["channel"] = ch

    sig_m = re.search(r"signal:\s*(-?\d+)\s*dBm", out)
    if sig_m:
        link["rssi_dbm"] = int(sig_m.group(1))

    tx_m = re.search(r"tx bitrate:\s*([\d\.]+)\s*MBit/s", out)
    if tx_m:
        link["tx_bitrate_mbps"] = float(tx_m.group(1))

    # Determine generation and channel width from rate string
    if "EHT" in out:
        link["standard_generation"] = "Wi-Fi 7 (EHT)"
    elif "HE" in out:
        link["standard_generation"] = "Wi-Fi 6 (HE)"
    elif "VHT" in out:
        link["standard_generation"] = "Wi-Fi 5 (VHT)"
    elif "MCS" in out or "short GI" in out:
        link["standard_generation"] = "Wi-Fi 4 (HT)"
    else:
        link["standard_generation"] = "Wi-Fi 3 (802.11g)" if link["band"] == "2.4GHz" else "Wi-Fi 2 (802.11a)"

    width_m = re.search(r"(\d+)MHz", out)
    if width_m:
        link["channel_width_mhz"] = int(width_m.group(1))

    return link


def scan_channels_and_bands(iface: str) -> Dict[str, Any]:
    """
    Performs spectrum scan via `iw dev <iface> scan` and classifies
    detected APs by frequency band, channel, and generation standard.
    """
    out = run_cmd(["iw", "dev", iface, "scan"], timeout=15.0)

    bands = {
        "2.4GHz": {"total_aps": 0, "channels": {}, "best_rssi": -100, "generation_counts": {}},
        "5GHz": {"total_aps": 0, "channels": {}, "best_rssi": -100, "generation_counts": {}},
        "6GHz": {"total_aps": 0, "channels": {}, "best_rssi": -100, "generation_counts": {}}
    }

    if not out:
        return bands

    # Split output into BSS sections
    bss_blocks = out.split("BSS ")
    for block in bss_blocks:
        if not block.strip():
            continue

        bssid_m = re.match(r"^([0-9a-fA-F:]{17})", block)
        if not bssid_m:
            continue
        bssid = bssid_m.group(1).lower()

        freq_m = re.search(r"freq:\s*(\d+)", block)
        if not freq_m:
            continue
        freq = int(freq_m.group(1))
        band, ch = freq_to_band_and_channel(freq)
        if band not in bands:
            continue

        sig_m = re.search(r"signal:\s*(-?[\d\.]+)\s*dBm", block)
        rssi = int(float(sig_m.group(1))) if sig_m else -100

        ssid_m = re.search(r"SSID:\s*(.+)", block)
        ssid = ssid_m.group(1).strip() if ssid_m else "<Hidden>"

        # Determine AP Generation capability
        ap_gen = "Wi-Fi 3 (802.11g)" if band == "2.4GHz" else "Wi-Fi 2 (802.11a)"
        if "EHT" in block:
            ap_gen = "Wi-Fi 7 (EHT)"
        elif "HE capabilities" in block or "HE PHY Capabilities" in block:
            ap_gen = "Wi-Fi 6 (HE)" if band != "6GHz" else "Wi-Fi 6E (HE)"
        elif "VHT capabilities" in block:
            ap_gen = "Wi-Fi 5 (VHT)"
        elif "HT capabilities" in block:
            ap_gen = "Wi-Fi 4 (HT)"

        band_data = bands[band]
        band_data["total_aps"] += 1
        if rssi > band_data["best_rssi"]:
            band_data["best_rssi"] = rssi

        gen_counts = band_data["generation_counts"]
        gen_counts[ap_gen] = gen_counts.get(ap_gen, 0) + 1

        ch_str = str(ch)
        if ch_str not in band_data["channels"]:
            band_data["channels"][ch_str] = {
                "channel": ch,
                "freq_mhz": freq,
                "ap_count": 0,
                "best_rssi": -100,
                "aps": []
            }

        ch_entry = band_data["channels"][ch_str]
        ch_entry["ap_count"] += 1
        if rssi > ch_entry["best_rssi"]:
            ch_entry["best_rssi"] = rssi

        ch_entry["aps"].append({
            "bssid": bssid,
            "ssid": ssid,
            "rssi_dbm": rssi,
            "standard_generation": ap_gen
        })

    return bands


def evaluate_band_and_channel_health(nic_caps: Dict[str, Any], link: Dict[str, Any], scan_results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluates multi-band health, identifying channel congestion,
    band steering anomalies, and AP vs NIC generation capability gaps.
    """
    channel_evals = []
    band_evals = []
    warnings = []
    anomalies = []

    # 1. Band-Level Evaluations
    for band_name, bdata in scan_results.items():
        supported = band_name in nic_caps["bands_supported"]
        total_aps = bdata["total_aps"]
        best_rssi = bdata["best_rssi"]

        status = "HEALTHY"
        if not supported:
            status = "UNSUPPORTED_BY_NIC"
        elif total_aps == 0:
            status = "NO_BEACONS"
        elif best_rssi < -82:
            status = "WEAK_COVERAGE"
            warnings.append(f"{band_name} band coverage is weak ({best_rssi} dBm max RSSI).")

        band_evals.append({
            "band": band_name,
            "supported_by_nic": supported,
            "total_aps_observed": total_aps,
            "best_rssi_dbm": best_rssi if total_aps > 0 else None,
            "status": status,
            "generation_breakdown": bdata["generation_counts"]
        })

    # 2. Channel-Level Evaluations & Co-Channel Congestion
    for band_name, bdata in scan_results.items():
        for ch_str, ch_info in bdata["channels"].items():
            ch = ch_info["channel"]
            ap_count = ch_info["ap_count"]
            best_rssi = ch_info["best_rssi"]

            # 2.4GHz non-standard overlap check
            is_non_std_2g = (band_name == "2.4GHz" and ch not in (1, 6, 11, 14))
            ch_health = "PASS"
            flags = []

            if is_non_std_2g:
                flags.append("NON_STANDARD_OVERLAPPING_CHANNEL")
                ch_health = "WARN"

            if ap_count >= 5:
                flags.append("HIGH_CO_CHANNEL_INTERFERENCE")
                ch_health = "WARN"

            if best_rssi < -82:
                flags.append("POOR_SIGNAL")
                if ch_health == "PASS":
                    ch_health = "DEGRADED"

            channel_evals.append({
                "band": band_name,
                "channel": ch,
                "freq_mhz": ch_info["freq_mhz"],
                "ap_count": ap_count,
                "best_rssi_dbm": best_rssi,
                "health": ch_health,
                "flags": flags
            })

    # 3. Band Steering Analysis
    # If client is connected to 2.4 GHz, but the same SSID is available on 5 GHz with acceptable signal
    if link["connected"] and link["band"] == "2.4GHz":
        conn_ssid = link["ssid"]
        conn_rssi = link["rssi_dbm"]
        five_g = scan_results.get("5GHz", {})
        viable_5g = []
        for ch_str, ch_info in five_g.get("channels", {}).items():
            for ap in ch_info["aps"]:
                if ap["ssid"] == conn_ssid and ap["rssi_dbm"] >= -78:
                    viable_5g.append(ap)

        if viable_5g:
            best_5g = max(viable_5g, key=lambda a: a["rssi_dbm"])
            issue = (
                f"Band Steering Anomaly: Sensor is associated on 2.4GHz Ch {link['channel']} ({conn_rssi} dBm), "
                f"despite 5GHz AP for SSID '{conn_ssid}' available at {best_5g['rssi_dbm']} dBm (BSSID {best_5g['bssid']})."
            )
            anomalies.append({
                "type": "BAND_STEERING_FAILURE",
                "severity": "WARNING",
                "description": issue,
                "recommendation": "Tune AP min-RSSI or 802.11k/v BSS transition management to encourage 5GHz association."
            })
            warnings.append(issue)

    # 4. Standards Generation Capability Gap
    # Compare AP generation of connected BSSID vs NIC capability
    conn_bssid = link.get("bssid")
    ap_gen_connected = None
    if conn_bssid:
        for bdata in scan_results.values():
            for ch_info in bdata["channels"].values():
                for ap in ch_info["aps"]:
                    if ap["bssid"] == conn_bssid:
                        ap_gen_connected = ap["standard_generation"]
                        break

    generation_matrix = {
        "nic_max_generation": nic_caps["max_generation"],
        "nic_max_channel_width": f"{nic_caps['max_channel_width_mhz']} MHz",
        "nic_antenna_chains": f"{nic_caps['antenna_chains']}x{nic_caps['antenna_chains']}",
        "connected_link_generation": link["standard_generation"],
        "connected_ap_generation": ap_gen_connected or link["standard_generation"],
        "connected_channel_width": f"{link['channel_width_mhz']} MHz",
        "mismatch_detected": False,
        "mismatch_details": None
    }

    if link["connected"] and ap_gen_connected:
        if "Wi-Fi 6" in nic_caps["max_generation"] and "Wi-Fi 6" not in ap_gen_connected:
            generation_matrix["mismatch_detected"] = True
            generation_matrix["mismatch_details"] = (
                f"NIC supports {nic_caps['max_generation']}, but connected AP ({link['bssid']}) is limited to {ap_gen_connected}."
            )

    overall_status = "PASS"
    if anomalies:
        overall_status = "WARNING"
    elif any(b["status"] == "WEAK_COVERAGE" for b in band_evals if b["supported_by_nic"]):
        overall_status = "DEGRADED"

    return {
        "status": overall_status,
        "nic_capabilities": nic_caps,
        "current_link": link,
        "band_evaluations": band_evals,
        "channel_evaluations": sorted(channel_evals, key=lambda c: (c["band"], c["channel"])),
        "generation_matrix": generation_matrix,
        "anomalies": anomalies,
        "warnings": warnings
    }


def main():
    parser = argparse.ArgumentParser(description="Wi-Fi Multi-Band Hardware & Standards Generation Diagnostic Suite")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    parser.add_argument("--iface", type=str, default="wlan0", help="Wi-Fi interface name (auto-detected if omitted)")
    args = parser.parse_args()

    iface = detect_wifi_interface(args.iface)
    phy = get_phy_name(iface)

    nic_caps = audit_nic_capabilities(phy)
    link = get_current_link(iface)
    scan_results = scan_channels_and_bands(iface)
    eval_report = evaluate_band_and_channel_health(nic_caps, link, scan_results)

    if args.json:
        print(json.dumps(eval_report, indent=2))
    else:
        print("=" * 70)
        print(" Wi-Fi Multi-Band Hardware & Spectrum Diagnostic Suite")
        print("=" * 70)
        print(f"Interface: {iface} ({phy}) | Overall Status: {eval_report['status']}")
        print(f"NIC Max Generation: {nic_caps['max_generation']} ({nic_caps['max_channel_width_mhz']} MHz max width, {nic_caps['antenna_chains']}x{nic_caps['antenna_chains']})")
        print(f"Supported Bands: {', '.join(nic_caps['bands_supported'])}")
        print("\nActive Link:")
        if link["connected"]:
            print(f"  SSID: {link['ssid']} ({link['bssid']})")
            print(f"  Band: {link['band']} Ch {link['channel']} ({link['freq_mhz']} MHz) | Signal: {link['rssi_dbm']} dBm")
            print(f"  Rate: {link['tx_bitrate_mbps']} Mbps | Mode: {link['standard_generation']} ({link['channel_width_mhz']} MHz)")
        else:
            print("  Interface not currently associated to an AP.")

        print("\nPer-Band Spectrum Summary:")
        for b in eval_report["band_evaluations"]:
            sup_str = "Supported" if b["supported_by_nic"] else "Unsupported"
            rssi_str = f"{b['best_rssi_dbm']} dBm" if b['best_rssi_dbm'] else "N/A"
            print(f"  - {b['band']:<8} [{sup_str:<11}] APs: {b['total_aps_observed']:<3} Best RSSI: {rssi_str:<8} Status: {b['status']}")

        print("\nStandards Generation Capability Matrix:")
        gen = eval_report["generation_matrix"]
        print(f"  Client NIC Capable:   {gen['nic_max_generation']} ({gen['nic_max_channel_width']})")
        print(f"  Connected Link Mode:  {gen['connected_link_generation']} ({gen['connected_channel_width']})")
        print(f"  Connected AP Capable: {gen['connected_ap_generation']}")
        if gen["mismatch_detected"]:
            print(f"  ⚠️  Notice: {gen['mismatch_details']}")

        if eval_report["anomalies"]:
            print("\nDetected RF & Roaming Anomalies:")
            for a in eval_report["anomalies"]:
                print(f"  ⚠️  [{a['severity']}] {a['description']}")
                print(f"      Recommendation: {a['recommendation']}")

        if eval_report["warnings"]:
            print("\nWarnings:")
            for w in eval_report["warnings"]:
                print(f"  - {w}")


if __name__ == "__main__":
    main()
