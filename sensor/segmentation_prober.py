#!/usr/bin/env python3
"""
OpenUX Lateral East-West Segmentation Validator
Performs controlled, allowlist-only TCP connection checks to verify that
network segmentation policies (e.g. Student VLAN cannot reach Switch SSH,
Camera subnets, or Admin Web Portals) are properly enforced.

Emits Prometheus metrics alerting if restricted management ports are accessible.
"""

import os
import sys
import time
import socket
import argparse
from typing import List, Dict, Any, Tuple

DEFAULT_PROM_FILE = "/var/lib/node_exporter/textfile_collector/segmentation.prom"

# Standard segmentation test matrix for educational networks
DEFAULT_PROBE_TARGETS = [
    {
        "id": "switch_management_ssh",
        "name": "Core Switch SSH Management",
        "host": "10.0.0.1",
        "port": 22,
        "expected_state": "blocked",  # Client VLAN should NEVER reach switch SSH
        "timeout_sec": 2
    },
    {
        "id": "firewall_admin_gui",
        "name": "Security Gateway Admin GUI",
        "host": "192.168.1.1",
        "port": 443,
        "expected_state": "blocked",  # Client VLAN should NOT reach firewall GUI
        "timeout_sec": 2
    },
    {
        "id": "district_dns_internal",
        "name": "District Internal DNS",
        "host": "10.0.0.2",
        "port": 53,
        "expected_state": "allowed",  # DNS should be reachable
        "timeout_sec": 2
    }
]

def probe_target(target: Dict[str, Any], interface: Optional[str] = None) -> Tuple[int, float, bool]:
    """
    Tests TCP connectivity to target host:port.
    Returns: (is_reachable [1=connected, 0=blocked/timeout], latency_seconds, is_compliant)
    """
    host = target["host"]
    port = target["port"]
    timeout = target.get("timeout_sec", 2)
    expected_state = target.get("expected_state", "blocked")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)

    # Optional Linux socket binding to specific interface
    if interface and hasattr(socket, "SO_BINDTODEVICE"):
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, interface.encode())
        except Exception:
            pass

    start = time.time()
    try:
        sock.connect((host, port))
        latency = time.time() - start
        sock.close()
        is_reachable = 1
    except (socket.timeout, ConnectionRefusedError, OSError):
        latency = time.time() - start
        is_reachable = 0

    # Compliance check:
    # If expected_state == 'blocked', compliance = True when reachable == 0
    # If expected_state == 'allowed', compliance = True when reachable == 1
    if expected_state == "blocked":
        is_compliant = (is_reachable == 0)
    else:
        is_compliant = (is_reachable == 1)

    return is_reachable, latency, is_compliant

def write_metrics(results: List[Dict[str, Any]], output_path: str):
    """Atomically writes Prometheus metrics for segmentation compliance."""
    prom_lines = [
        "# HELP openux_segmentation_reachable Whether TCP connection to target succeeded (1=Connected, 0=Blocked/Timeout)",
        "# TYPE openux_segmentation_reachable gauge",
        "# HELP openux_segmentation_compliant Whether isolation state matches expected security policy (1=Compliant, 0=Breached/Non-Compliant)",
        "# TYPE openux_segmentation_compliant gauge",
        "# HELP openux_segmentation_latency_seconds Connection latency in seconds",
        "# TYPE openux_segmentation_latency_seconds gauge"
    ]

    all_compliant = 1
    for r in results:
        t_id = r["id"]
        t_name = r["name"]
        expected = r["expected_state"]

        reachable = r["reachable"]
        compliant = 1 if r["compliant"] else 0
        latency = r["latency"]

        if not r["compliant"]:
            all_compliant = 0

        prom_lines.append(f'openux_segmentation_reachable{{id="{t_id}",name="{t_name}",expected="{expected}"}} {reachable}')
        prom_lines.append(f'openux_segmentation_compliant{{id="{t_id}",name="{t_name}",expected="{expected}"}} {compliant}')
        prom_lines.append(f'openux_segmentation_latency_seconds{{id="{t_id}",name="{t_name}"}} {latency:.4f}')

    prom_lines.append("# HELP openux_segmentation_overall_compliant Site-wide lateral segmentation compliance (1=Fully Isolated, 0=Policy Breach Detected)")
    prom_lines.append("# TYPE openux_segmentation_overall_compliant gauge")
    prom_lines.append(f"openux_segmentation_overall_compliant {all_compliant}")

    content = "\n".join(prom_lines) + "\n"
    if output_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        tmp = output_path + ".tmp"
        with open(tmp, "w") as f:
            f.write(content)
        os.replace(tmp, output_path)
        print(f"Segmentation metrics written to: {output_path}")
    else:
        print(content)

def main():
    parser = argparse.ArgumentParser(description="OpenUX Lateral East-West Segmentation Validator")
    parser.add_argument("--interface", default=None, help="Bind probe to specific network interface (e.g., wlan0)")
    parser.add_argument("--output", default=DEFAULT_PROM_FILE, help="Prometheus metric file output path")

    args = parser.parse_args()

    print("Running OpenUX Lateral Segmentation Validation Probes...")
    results = []

    for target in DEFAULT_PROBE_TARGETS:
        reachable, latency, compliant = probe_target(target, interface=args.interface)
        t_name = target["name"]
        expected = target["expected_state"]

        status_str = "\033[92mCOMPLIANT\033[0m" if compliant else "\033[91mPOLICY BREACH / NON-COMPLIANT\033[0m"
        state_str = "REACHABLE" if reachable else "BLOCKED/TIMEOUT"
        print(f" - [{t_name}]: {status_str} (Observed: {state_str}, Expected: {expected.upper()}, Latency: {latency*1000:.1f}ms)")

        results.append({
            "id": target["id"],
            "name": target["name"],
            "expected_state": expected,
            "reachable": reachable,
            "latency": latency,
            "compliant": compliant
        })

    write_metrics(results, args.output)

if __name__ == "__main__":
    main()
