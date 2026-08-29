#!/usr/bin/env python3
"""
Wi-Fi Radio Resource Management (RRM) & Dynamic RF Optimization Monitor
Validates vendor-agnostic Radio Resource Management (RRM), Distributed Automatic
Radio Provisioning, and Centralized Spectrum Knowledge channel optimization algorithms.

What this monitor tracks:
  - Dynamic Channel Switches: Detects when the AP changes operating channels via RRM.
  - Channel Flapping Detection: Alerts if APs bounce channels too frequently (> 3 times/hour),
    which causes student disconnections during instruction.
  - Co-Channel Interference (CCI): Scans neighbor beacons to measure how many competing APs
    share the same channel.
  - Channel Dwell Time: Measures the operational stability duration on the assigned frequency.
  - SNR, Noise Floor & Channel Width (20/40/80/160/320 MHz).
"""

import os
import sys
import re
import json
import time
import subprocess
from typing import Dict, Any, List, Optional, Tuple

STATE_FILE = "/var/lib/sensor/rrm_state.json"
DEFAULT_PROM_FILE = "/var/lib/node_exporter/textfile_collector/wifi_rrm.prom"

def load_state() -> Dict[str, Any]:
    """Loads historical RRM channel switch history."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "current_channel": 0,
        "current_bssid": "",
        "channel_start_epoch": int(time.time()),
        "switch_history": [],  # Timestamps of channel switches in the past 24h
        "total_switches": 0
    }

def save_state(state: Dict[str, Any]):
    """Persists RRM tracking state."""
    try:
        dirname = os.path.dirname(STATE_FILE)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
    except Exception as e:
        print(f"Warning: Could not save RRM state: {e}", file=sys.stderr)

def get_connected_wifi_info(interface: str = "wlan0") -> Dict[str, Any]:
    """
    Parses 'iw dev <interface> link' and 'iw dev <interface> info' to get
    connected BSSID, SSID, frequency, channel, RSSI, and TX/RX bitrates.
    """
    info = {
        "connected": False,
        "ssid": "",
        "bssid": "",
        "freq_mhz": 0,
        "channel": 0,
        "rssi_dbm": 0,
        "tx_rate_mbps": 0.0,
        "rx_rate_mbps": 0.0,
        "channel_width_mhz": 20
    }

    try:
        # Run 'iw dev <iface> link'
        out = subprocess.check_output(
            ["iw", "dev", interface, "link"],
            stderr=subprocess.DEVNULL,
            text=True
        )
        if "Connected to" in out:
            info["connected"] = True

            # Extract BSSID
            bssid_match = re.search(r"Connected to ([0-9a-fA-F:]{17})", out)
            if bssid_match:
                info["bssid"] = bssid_match.group(1).lower()

            # Extract SSID
            ssid_match = re.search(r"SSID:\s*(.+)", out)
            if ssid_match:
                info["ssid"] = ssid_match.group(1).strip()

            # Extract Frequency
            freq_match = re.search(r"freq:\s*(\d+)", out)
            if freq_match:
                freq = int(freq_match.group(1))
                info["freq_mhz"] = freq
                info["channel"] = freq_to_channel(freq)

            # Extract Signal (RSSI)
            signal_match = re.search(r"signal:\s*(-?\d+)\s*dBm", out)
            if signal_match:
                info["rssi_dbm"] = int(signal_match.group(1))

            # Extract TX Bitrate
            tx_match = re.search(r"tx bitrate:\s*([0-9.]+)\s*MBit/s", out)
            if tx_match:
                info["tx_rate_mbps"] = float(tx_match.group(1))

            # Extract RX Bitrate
            rx_match = re.search(r"rx bitrate:\s*([0-9.]+)\s*MBit/s", out)
            if rx_match:
                info["rx_rate_mbps"] = float(rx_match.group(1))

            # Channel width detection (e.g., 80MHz, 160MHz)
            if "80MHz" in out:
                info["channel_width_mhz"] = 80
            elif "160MHz" in out:
                info["channel_width_mhz"] = 160
            elif "320MHz" in out:
                info["channel_width_mhz"] = 320
            elif "40MHz" in out:
                info["channel_width_mhz"] = 40
            else:
                info["channel_width_mhz"] = 20
    except Exception:
        pass

    return info

def freq_to_channel(freq_mhz: int) -> int:
    """Translates 2.4 GHz, 5 GHz, and 6 GHz frequencies into Wi-Fi channel numbers."""
    if freq_mhz == 2484:
        return 14
    elif 2412 <= freq_mhz <= 2472:
        return (freq_mhz - 2412) // 5 + 1
    elif 5180 <= freq_mhz <= 5885:
        return (freq_mhz - 5000) // 5
    elif 5955 <= freq_mhz <= 7115:
        # 6 GHz band (Wi-Fi 6E / Wi-Fi 7)
        return (freq_mhz - 5950) // 5
    return 0

def scan_cochannel_interference(interface: str, target_freq_mhz: int, connected_bssid: str) -> Tuple[int, List[Dict[str, Any]]]:
    """
    Performs an active/passive scan of neighboring BSSIDs to count co-channel APs
    broadcasting on the exact same primary frequency.
    """
    cochannel_count = 0
    neighbors = []

    try:
        out = subprocess.check_output(
            ["iw", "dev", interface, "scan", "dump"],
            stderr=subprocess.DEVNULL,
            text=True
        )

        current_bssid = None
        current_freq = 0
        current_signal = 0
        current_ssid = ""

        for line in out.splitlines():
            line = line.strip()
            if line.startswith("BSS "):
                # Save previous if matches
                if current_bssid and current_bssid != connected_bssid and current_freq == target_freq_mhz:
                    cochannel_count += 1
                    neighbors.append({
                        "bssid": current_bssid,
                        "ssid": current_ssid,
                        "signal_dbm": current_signal
                    })
                # Start new BSS
                b_match = re.match(r"BSS ([0-9a-fA-F:]{17})", line)
                if b_match:
                    current_bssid = b_match.group(1).lower()
                current_freq = 0
                current_signal = 0
                current_ssid = ""
            elif line.startswith("freq:"):
                f_match = re.search(r"freq:\s*(\d+)", line)
                if f_match:
                    current_freq = int(f_match.group(1))
            elif line.startswith("signal:"):
                s_match = re.search(r"signal:\s*(-?\d+)", line)
                if s_match:
                    current_signal = int(s_match.group(1))
            elif line.startswith("SSID:"):
                current_ssid = line.replace("SSID:", "").strip()

        # Final check
        if current_bssid and current_bssid != connected_bssid and current_freq == target_freq_mhz:
            cochannel_count += 1
            neighbors.append({
                "bssid": current_bssid,
                "ssid": current_ssid,
                "signal_dbm": current_signal
            })
    except Exception:
        pass

    return cochannel_count, neighbors

def write_metrics(prom_lines: List[str], output_file: str):
    """Atomically writes Prometheus metrics."""
    prom_content = "\n".join(prom_lines) + "\n"
    if output_file:
        dirname = os.path.dirname(output_file)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        tmp_path = output_file + ".tmp"
        with open(tmp_path, "w") as f:
            f.write(prom_content)
        os.replace(tmp_path, output_file)
        print(f"Metrics written to {output_file}")
    else:
        print(prom_content)

def main():
    output_file = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PROM_FILE
    interface = sys.argv[2] if len(sys.argv) > 2 else "wlan0"

    prom_lines = [
        "# HELP wifi_rrm_connected Whether the sensor is currently associated to a Wi-Fi AP (1=Connected, 0=Disconnected)",
        "# TYPE wifi_rrm_connected gauge",
        "# HELP wifi_rrm_current_channel Current Wi-Fi channel assigned by DARRP/GSK RRM algorithm",
        "# TYPE wifi_rrm_current_channel gauge",
        "# HELP wifi_rrm_channel_width_mhz Operating channel width in MHz (20, 40, 80, 160, 320)",
        "# TYPE wifi_rrm_channel_width_mhz gauge",
        "# HELP wifi_rrm_channel_switches_total Total number of dynamic channel changes executed by DARRP/GSK",
        "# TYPE wifi_rrm_channel_switches_total counter",
        "# HELP wifi_rrm_channel_dwell_seconds Number of seconds the AP has remained stable on the current channel",
        "# TYPE wifi_rrm_channel_dwell_seconds gauge",
        "# HELP wifi_rrm_switches_last_hour Channel switch frequency in the past 60 minutes",
        "# TYPE wifi_rrm_switches_last_hour gauge",
        "# HELP wifi_rrm_flapping_detected 1 if DARRP/GSK is excessively flapping (>3 channel changes in 1h), 0 if stable",
        "# TYPE wifi_rrm_flapping_detected gauge",
        "# HELP wifi_rrm_cochannel_neighbors Number of competing neighbor APs sharing the exact same primary channel (CCI)",
        "# TYPE wifi_rrm_cochannel_neighbors gauge",
        "# HELP wifi_rrm_rssi_dbm Received Signal Strength Indicator in dBm",
        "# TYPE wifi_rrm_rssi_dbm gauge",
        "# HELP wifi_rrm_snr_db Estimated Signal-to-Noise Ratio in dB",
        "# TYPE wifi_rrm_snr_db gauge"
    ]

    print(f"Polling Wi-Fi RRM / DARRP / GSK Radio Optimization on {interface}...")
    wifi = get_connected_wifi_info(interface)

    if not wifi["connected"]:
        print(f"\033[93mInterface {interface} is not associated to any SSID.\033[0m")
        prom_lines.append(f'wifi_rrm_connected{{interface="{interface}"}} 0')
        prom_lines.append(f'wifi_rrm_current_channel{{interface="{interface}"}} 0')
        prom_lines.append(f'wifi_rrm_channel_width_mhz{{interface="{interface}"}} 0')
        prom_lines.append(f'wifi_rrm_switches_last_hour{{interface="{interface}"}} 0')
        prom_lines.append(f'wifi_rrm_flapping_detected{{interface="{interface}"}} 0')
        prom_lines.append(f'wifi_rrm_cochannel_neighbors{{interface="{interface}",channel="0"}} 0')
        prom_lines.append(f'wifi_rrm_rssi_dbm{{interface="{interface}"}} -100')
        prom_lines.append(f'wifi_rrm_snr_db{{interface="{interface}"}} 0')
        write_metrics(prom_lines, output_file)
        return

    state = load_state()
    now_epoch = int(time.time())

    # Prune switch history older than 24 hours
    one_day_ago = now_epoch - 86400
    one_hour_ago = now_epoch - 3600
    state["switch_history"] = [t for t in state.get("switch_history", []) if t >= one_day_ago]

    curr_chan = wifi["channel"]
    curr_bssid = wifi["bssid"]
    prev_chan = state.get("current_channel", 0)

    # Check if a DARRP / GSK dynamic channel switch occurred
    if prev_chan > 0 and curr_chan != prev_chan and curr_chan > 0:
        print(f"\033[96m[RRM EVENT] Dynamic Channel Switch Detected!\033[0m Channel changed from {prev_chan} -> {curr_chan}")
        state["total_switches"] = state.get("total_switches", 0) + 1
        state["switch_history"].append(now_epoch)
        state["channel_start_epoch"] = now_epoch
        state["current_channel"] = curr_chan
        state["current_bssid"] = curr_bssid
    elif prev_chan == 0 and curr_chan > 0:
        # First initialization
        state["current_channel"] = curr_chan
        state["current_bssid"] = curr_bssid
        state["channel_start_epoch"] = now_epoch

    # Calculate dwell time and flapping
    dwell_time = max(0, now_epoch - state.get("channel_start_epoch", now_epoch))
    switches_last_hour = sum(1 for t in state["switch_history"] if t >= one_hour_ago)
    is_flapping = 1 if switches_last_hour >= 3 else 0

    save_state(state)

    # Scan co-channel interference
    cci_count, neighbors = scan_cochannel_interference(interface, wifi["freq_mhz"], curr_bssid)

    # Noise floor estimate (-95 dBm default reference on clean 5/6 GHz, -90 dBm on 2.4 GHz)
    noise_est = -90 if wifi["freq_mhz"] < 3000 else -95
    snr_est = max(0, wifi["rssi_dbm"] - noise_est)

    # Metric lines
    labels = f'interface="{interface}",ssid="{wifi["ssid"]}",bssid="{curr_bssid}"'
    prom_lines.append(f'wifi_rrm_connected{{{labels}}} 1')
    prom_lines.append(f'wifi_rrm_current_channel{{{labels}}} {curr_chan}')
    prom_lines.append(f'wifi_rrm_channel_width_mhz{{{labels}}} {wifi["channel_width_mhz"]}')
    prom_lines.append(f'wifi_rrm_channel_switches_total{{{labels}}} {state.get("total_switches", 0)}')
    prom_lines.append(f'wifi_rrm_channel_dwell_seconds{{{labels}}} {dwell_time}')
    prom_lines.append(f'wifi_rrm_switches_last_hour{{{labels}}} {switches_last_hour}')
    prom_lines.append(f'wifi_rrm_flapping_detected{{{labels}}} {is_flapping}')
    prom_lines.append(f'wifi_rrm_cochannel_neighbors{{{labels},channel="{curr_chan}"}} {cci_count}')
    prom_lines.append(f'wifi_rrm_rssi_dbm{{{labels}}} {wifi["rssi_dbm"]}')
    prom_lines.append(f'wifi_rrm_snr_db{{{labels}}} {snr_est}')

    print(f" - SSID: {wifi['ssid']} (BSSID: {curr_bssid})")
    print(f" - Operating Channel: {curr_chan} ({wifi['channel_width_mhz']} MHz width, {wifi['freq_mhz']} MHz)")
    print(f" - Channel Stability: Dwell time {dwell_time}s | Switches (1h): {switches_last_hour} | Flapping: {'YES (Degraded)' if is_flapping else 'NO (Stable)'}")
    print(f" - Co-Channel Interference (CCI): {cci_count} neighbor APs sharing channel {curr_chan}")
    print(f" - RF Signal: RSSI {wifi['rssi_dbm']} dBm | SNR: {snr_est} dB\n")

    write_metrics(prom_lines, output_file)

if __name__ == "__main__":
    main()
