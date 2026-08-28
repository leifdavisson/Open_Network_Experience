#!/usr/bin/env python3
"""
OpenUX Dynamic Custom Synthetic Probe Runner (WYSIWYG Engine)
Executes custom synthetic tests configured via the Central Management Web UI
(Canvas LMS, PowerSchool SIS, Lunch POS, Door Access, State Portals).

Supports:
  - HTTP/HTTPS Web & API Transactions
  - DNS Resolution Benchmarks
  - TCP Port Reachability

Atomically outputs Prometheus metrics for Grafana visualization and alerting.
"""

import os
import sys
import time
import json
import socket
import urllib.request
import urllib.error
import argparse
from typing import List, Dict, Any, Tuple

DEFAULT_PROBES_FILE = "/etc/sensor/custom_probes.json"
DEFAULT_PROM_FILE = "/var/lib/node_exporter/textfile_collector/custom_probes.prom"

def execute_http_probe(target: str, timeout: float = 5.0, expected_status: int = 200, match_regex: str = None) -> Tuple[int, float, int]:
    """Executes HTTP/HTTPS probe and measures latency."""
    start = time.time()
    req = urllib.request.Request(
        target,
        headers={"User-Agent": "Open-Network-Experience-CustomProbe/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            latency = time.time() - start
            status = response.getcode()
            body = response.read().decode('utf-8', errors='ignore') if match_regex else ""

            is_success = 1 if status == expected_status else 0
            if match_regex and match_regex not in body:
                is_success = 0
            return is_success, latency, status
    except urllib.error.HTTPError as e:
        latency = time.time() - start
        is_success = 1 if e.code == expected_status else 0
        return is_success, latency, e.code
    except Exception:
        latency = time.time() - start
        return 0, latency, -1

def execute_dns_probe(target: str, timeout: float = 2.0) -> Tuple[int, float, int]:
    """Executes DNS lookup probe."""
    start = time.time()
    try:
        socket.gethostbyname(target)
        latency = time.time() - start
        return 1, latency, 0
    except Exception:
        latency = time.time() - start
        return 0, latency, -1

def execute_tcp_probe(target: str, port: int, timeout: float = 2.0) -> Tuple[int, float, int]:
    """Executes TCP connection probe."""
    start = time.time()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((target, port))
        latency = time.time() - start
        sock.close()
        return 1, latency, 200
    except Exception:
        latency = time.time() - start
        sock.close()
        return 0, latency, -1

def run_probes(probes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Runs all enabled custom synthetic probes."""
    results = []
    for p in probes:
        if not p.get("enabled", True):
            continue

        p_id = p.get("id", "custom-probe")
        p_name = p.get("name", p_id)
        p_type = p.get("probe_type", "http").lower()
        target = p.get("target", "")
        timeout = float(p.get("timeout_seconds", 5.0))
        expected_status = int(p.get("expected_status_code", 200))
        match_regex = p.get("match_body_regex")

        if p_type in ("http", "api"):
            success, latency, status_code = execute_http_probe(target, timeout, expected_status, match_regex)
        elif p_type == "dns":
            success, latency, status_code = execute_dns_probe(target, timeout)
        elif p_type == "tcp":
            parts = target.split(":")
            host = parts[0]
            port = int(parts[1]) if len(parts) > 1 else 80
            success, latency, status_code = execute_tcp_probe(host, port, timeout)
        else:
            success, latency, status_code = 0, 0.0, -1

        results.append({
            "id": p_id,
            "name": p_name,
            "type": p_type,
            "target": target,
            "success": success,
            "latency": latency,
            "status_code": status_code
        })
    return results

def write_metrics(results: List[Dict[str, Any]], output_path: str):
    """Atomically writes Prometheus metrics for all custom probes."""
    prom_lines = [
        "# HELP openux_custom_probe_status Custom synthetic probe health (1=Pass, 0=Fail)",
        "# TYPE openux_custom_probe_status gauge",
        "# HELP openux_custom_probe_duration_seconds Custom synthetic probe latency in seconds",
        "# TYPE openux_custom_probe_duration_seconds gauge",
        "# HELP openux_custom_probe_http_status Custom synthetic probe HTTP status code",
        "# TYPE openux_custom_probe_http_status gauge"
    ]

    for r in results:
        labels = f'id="{r["id"]}",name="{r["name"]}",type="{r["type"]}",target="{r["target"]}"'
        prom_lines.append(f'openux_custom_probe_status{{{labels}}} {r["success"]}')
        prom_lines.append(f'openux_custom_probe_duration_seconds{{{labels}}} {r["latency"]:.4f}')
        prom_lines.append(f'openux_custom_probe_http_status{{{labels}}} {r["status_code"]}')

    content = "\n".join(prom_lines) + "\n"
    if output_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        tmp = output_path + ".tmp"
        with open(tmp, "w") as f:
            f.write(content)
        os.replace(tmp, output_path)
        print(f"Custom probe metrics written to: {output_path}")
    else:
        print(content)

def main():
    parser = argparse.ArgumentParser(description="OpenUX Custom Synthetic Probe Runner")
    parser.add_argument("--config", default=DEFAULT_PROBES_FILE, help="Path to custom_probes.json configuration")
    parser.add_argument("--output", default=DEFAULT_PROM_FILE, help="Prometheus metric file output path")

    args = parser.parse_args()

    probes = []
    if os.path.exists(args.config):
        try:
            with open(args.config, "r") as f:
                probes = json.load(f)
        except Exception as e:
            print(f"Error reading {args.config}: {e}", file=sys.stderr)

    if not probes:
        # Default starter test if no configuration exists yet
        probes = [{
            "id": "district-gateway",
            "name": "District Gateway Portal",
            "probe_type": "http",
            "target": "https://google.com",
            "timeout_seconds": 3.0,
            "expected_status_code": 200,
            "enabled": True
        }]

    print(f"Running {len(probes)} custom synthetic probes...")
    results = run_probes(probes)
    for r in results:
        status_str = "\033[92mPASS\033[0m" if r["success"] else "\033[91mFAIL\033[0m"
        print(f" - [{r['name']} ({r['type']})]: {status_str} (Latency: {r['latency']*1000:.1f}ms, Status: {r['status_code']})")

    write_metrics(results, args.output)

if __name__ == "__main__":
    main()
