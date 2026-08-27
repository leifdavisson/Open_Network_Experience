#!/usr/bin/env python3
"""
Scheduled Bandwidth & Throughput Tester (iperf3)
Executes scheduled, rate-limited throughput and jitter tests across wired and wireless NICs.

Features:
  - Bandwidth throttling (e.g. -b 100M) to prevent saturating production school links.
  - Allowed time window enforcement (e.g. off-peak hours 20:00-06:00 only).
  - Staggered dual-NIC testing (runs wired baseline first, cools down, then wireless).
  - Emits atomic Prometheus textfile metrics.
"""

import os
import sys
import json
import time
import socket
import datetime
import subprocess
from typing import Dict, Any, Optional, List, Tuple

DEFAULT_PROM_FILE = "/var/lib/node_exporter/textfile_collector/iperf3.prom"

def is_within_allowed_hours(allowed_hours: Optional[List[str]]) -> bool:
    """
    Checks if the current local time falls within allowed time windows.
    Format of allowed_hours entries: 'HH:MM-HH:MM' (e.g. '20:00-06:00' for overnight).
    """
    if not allowed_hours:
        return True  # No restriction

    now = datetime.datetime.now().time()
    for window in allowed_hours:
        try:
            start_str, end_str = window.split("-")
            start_h, start_m = map(int, start_str.strip().split(":"))
            end_h, end_m = map(int, end_str.strip().split(":"))

            start_time = datetime.time(start_h, start_m)
            end_time = datetime.time(end_h, end_m)

            if start_time <= end_time:
                # Normal window (e.g. 09:00-17:00)
                if start_time <= now <= end_time:
                    return True
            else:
                # Overnight window crossing midnight (e.g. 20:00-06:00)
                if now >= start_time or now <= end_time:
                    return True
        except Exception as e:
            print(f"Invalid time window format '{window}': {e}", file=sys.stderr)

    return False

def get_interface_ip(interface: str) -> Optional[str]:
    """Retrieves the IPv4 address assigned to a specific network interface."""
    try:
        out = subprocess.check_output(
            ["ip", "-4", "addr", "show", interface],
            stderr=subprocess.DEVNULL,
            text=True
        )
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("inet "):
                return line.split()[1].split("/")[0]
    except Exception:
        pass
    return None

def run_iperf3_test(
    server: str,
    port: int = 5201,
    duration: int = 10,
    bandwidth_cap_mbps: Optional[int] = 100,
    bind_ip: Optional[str] = None,
    protocol: str = "tcp",
    reverse: bool = False
) -> Dict[str, Any]:
    """
    Runs iperf3 client and returns parsed metrics.
    Uses -J for JSON output.
    """
    cmd = [
        "iperf3",
        "-c", server,
        "-p", str(port),
        "-t", str(duration),
        "-J"
    ]

    if bind_ip:
        cmd.extend(["-B", bind_ip])

    if bandwidth_cap_mbps and bandwidth_cap_mbps > 0:
        cmd.extend(["-b", f"{bandwidth_cap_mbps}M"])

    if protocol.lower() == "udp":
        cmd.append("-u")

    if reverse:
        cmd.append("-R")  # Download test (server to client)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=duration + 15
        )
        if result.returncode != 0:
            error_msg = result.stderr.strip() or "iperf3 execution failed"
            return {"success": False, "error": error_msg}

        data = json.loads(result.stdout)
        end_data = data.get("end", {})

        # Extract sender/receiver bandwidth
        sum_sent = end_data.get("sum_sent", {})
        sum_received = end_data.get("sum_received", {})

        # Bits per second to Mbps
        tx_mbps = (sum_sent.get("bits_per_second", 0)) / 1_000_000.0
        rx_mbps = (sum_received.get("bits_per_second", 0)) / 1_000_000.0

        retransmits = sum_sent.get("retransmits", 0)

        # UDP metrics (jitter & loss)
        sum_data = end_data.get("sum", {})
        jitter_ms = sum_data.get("jitter_ms", 0.0)
        lost_percent = sum_data.get("lost_percent", 0.0)

        return {
            "success": True,
            "tx_mbps": round(tx_mbps, 2),
            "rx_mbps": round(rx_mbps, 2),
            "retransmits": retransmits,
            "jitter_ms": round(jitter_ms, 3),
            "lost_percent": round(lost_percent, 2),
            "protocol": protocol
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Test timed out"}
    except Exception as e:
        return {"success": False, "error": str(e)}

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
    """
    CLI Usage:
      iperf3_runner.py <server> [options in JSON string or flags]
    """
    import argparse
    parser = argparse.ArgumentParser(description="OpenUX Scheduled Bandwidth Tester")
    parser.add_argument("--server", required=True, help="iperf3 target server IP or hostname")
    parser.add_argument("--port", type=int, default=5201, help="iperf3 target port")
    parser.add_argument("--duration", type=int, default=10, help="Test duration in seconds")
    parser.add_argument("--bandwidth-cap", type=int, default=100, help="Bandwidth limit in Mbps (0 for unlimited)")
    parser.add_argument("--interfaces", nargs="+", default=["eth0", "wlan0"], help="Interfaces to test")
    parser.add_argument("--allowed-hours", nargs="*", default=None, help="Allowed windows e.g. 20:00-06:00")
    parser.add_argument("--force", action="store_true", help="Bypass allowed hours check")
    parser.add_argument("--output", default=DEFAULT_PROM_FILE, help="Path to Prometheus output file")

    args = parser.parse_args()

    prom_lines = [
        "# HELP openux_iperf3_throughput_tx_mbps Outbound bandwidth measured by iperf3 in Mbps",
        "# TYPE openux_iperf3_throughput_tx_mbps gauge",
        "# HELP openux_iperf3_throughput_rx_mbps Inbound bandwidth measured by iperf3 in Mbps",
        "# TYPE openux_iperf3_throughput_rx_mbps gauge",
        "# HELP openux_iperf3_retransmits_total Number of TCP retransmissions during test",
        "# TYPE openux_iperf3_retransmits_total gauge",
        "# HELP openux_iperf3_test_status Status of bandwidth test: 1=Success, 0=Failed, -1=Skipped (Outside Allowed Hours)",
        "# TYPE openux_iperf3_test_status gauge"
    ]

    # Check time window
    if not args.force and not is_within_allowed_hours(args.allowed_hours):
        print("Current time is outside allowed maintenance window. Skipping test.")
        for iface in args.interfaces:
            prom_lines.append(f'openux_iperf3_test_status{{interface="{iface}",server="{args.server}"}} -1')
        write_metrics(prom_lines, args.output)
        return

    print(f"Starting Scheduled Bandwidth Test against {args.server}:{args.port} (Cap: {args.bandwidth_cap} Mbps)...")

    for i, iface in enumerate(args.interfaces):
        if i > 0:
            print("Applying 5-second anti-contention cooldown between interface tests...")
            time.sleep(5)

        bind_ip = get_interface_ip(iface)
        if not bind_ip:
            print(f"Interface {iface} has no active IP address. Skipping.")
            prom_lines.append(f'openux_iperf3_test_status{{interface="{iface}",server="{args.server}"}} 0')
            continue

        medium = "wireless" if iface.startswith("wl") else "wired"
        print(f"Running test on {iface} ({medium}, IP: {bind_ip})...")

        res = run_iperf3_test(
            server=args.server,
            port=args.port,
            duration=args.duration,
            bandwidth_cap_mbps=args.bandwidth_cap,
            bind_ip=bind_ip
        )

        if res["success"]:
            print(f"  -> {iface} Result: TX {res['tx_mbps']} Mbps | RX {res['rx_mbps']} Mbps | Retransmits: {res['retransmits']}")
            prom_lines.append(f'openux_iperf3_test_status{{interface="{iface}",medium="{medium}",server="{args.server}"}} 1')
            prom_lines.append(f'openux_iperf3_throughput_tx_mbps{{interface="{iface}",medium="{medium}",server="{args.server}"}} {res["tx_mbps"]}')
            prom_lines.append(f'openux_iperf3_throughput_rx_mbps{{interface="{iface}",medium="{medium}",server="{args.server}"}} {res["rx_mbps"]}')
            prom_lines.append(f'openux_iperf3_retransmits_total{{interface="{iface}",medium="{medium}",server="{args.server}"}} {res["retransmits"]}')
        else:
            print(f"  -> {iface} Test FAILED: {res.get('error')}")
            prom_lines.append(f'openux_iperf3_test_status{{interface="{iface}",medium="{medium}",server="{args.server}"}} 0')

    write_metrics(prom_lines, args.output)

if __name__ == "__main__":
    main()
