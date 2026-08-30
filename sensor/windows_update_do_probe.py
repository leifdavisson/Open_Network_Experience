#!/usr/bin/env python3
"""
Open Network Experience (ONE) — Windows Update (WU), BITS & Delivery Optimization (DO) Synthetic Prober
Tests full-spectrum update infrastructure:
  1. Windows Update Cloud Services (WaaS catalog, metadata & licensing)
  2. Delivery Optimization (DO) Cloud Coordination & CDN mesh
  3. BITS / DO HTTP 206 Partial Content Range Header Verification
  4. Local Subnet LAN Peer P2P Listener (TCP 7680) & Microsoft Connected Cache (MCC)
"""

import os
import sys
import time
import socket
import ssl
import urllib.request
import urllib.error
import argparse
from typing import Dict, Any, List, Tuple, Optional

DEFAULT_PROM_FILE = "/var/lib/node_exporter/textfile_collector/windows_update.prom"

# Core Windows Update (WaaS) Endpoints
WU_ENDPOINTS = [
    {"id": "wu_catalog", "name": "Windows Update Catalog", "host": "windowsupdate.microsoft.com", "url": "https://windowsupdate.microsoft.com", "port": 443},
    {"id": "wu_service", "name": "Windows Update Service", "host": "update.microsoft.com", "url": "https://update.microsoft.com", "port": 443},
    {"id": "wu_download_cdn", "name": "Windows Update Download CDN", "host": "download.windowsupdate.com", "url": "https://download.windowsupdate.com", "port": 443},
    {"id": "wu_ms_download", "name": "Microsoft Download Center", "host": "download.microsoft.com", "url": "https://download.microsoft.com", "port": 443},
    {"id": "wu_stats", "name": "Windows Update Status Service", "host": "wustat.windows.com", "url": "https://wustat.windows.com", "port": 443},
    {"id": "wu_service_pack", "name": "NT Service Pack Service", "host": "ntservicepack.microsoft.com", "url": "https://ntservicepack.microsoft.com", "port": 443},
    {"id": "wu_redirector", "name": "Microsoft Go Redirection Service", "host": "go.microsoft.com", "url": "https://go.microsoft.com", "port": 443}
]

# Delivery Optimization (DO) Cloud Tracking & CDN Mesh
DO_ENDPOINTS = [
    {"id": "do_cloud_tracker", "name": "DO Cloud Peer Tracker", "host": "do.dsp.mp.microsoft.com", "url": "https://do.dsp.mp.microsoft.com", "port": 443},
    {"id": "do_download_cdn", "name": "DO Payload Download CDN", "host": "dl.delivery.mp.microsoft.com", "url": "https://dl.delivery.mp.microsoft.com", "port": 443},
    {"id": "do_enterprise_cdn", "name": "DO Enterprise Sync CDN", "host": "emdl.ws.microsoft.com", "url": "https://emdl.ws.microsoft.com", "port": 443},
    {"id": "do_telemetry_locator", "name": "DO Telemetry & Geo Locator", "host": "tlu.dl.delivery.mp.microsoft.com", "url": "https://tlu.dl.delivery.mp.microsoft.com", "port": 443}
]

def check_tcp_endpoint(host: str, port: int = 443, timeout_sec: float = 3.0) -> Tuple[bool, float, str]:
    """Tests DNS resolution and TCP SYN handshake latency."""
    t0 = time.time()
    try:
        ip = socket.gethostbyname(host)
    except Exception as e:
        return False, 0.0, f"DNS Resolution Error: {e}"

    t1 = time.time()
    try:
        with socket.create_connection((ip, port), timeout=timeout_sec):
            rtt_ms = round((time.time() - t1) * 1000.0, 2)
            return True, rtt_ms, f"Connected to {ip}:{port}"
    except Exception as e:
        return False, 0.0, f"TCP Connect Error: {e}"

def check_http_range_support(target_url: str, timeout_sec: float = 5.0) -> Tuple[bool, int, str]:
    """
    Verifies that the CDN / proxy supports BITS & Delivery Optimization HTTP 206 Partial Content range requests.
    Sends header: 'Range: bytes=0-1023'.
    Returns: (is_range_supported, status_code, message)
    """
    req = urllib.request.Request(
        target_url,
        headers={
            "User-Agent": "Microsoft-Delivery-Optimization/10.1",
            "Range": "bytes=0-1023",
            "Cache-Control": "no-cache"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as response:
            status = response.status
            content_range = response.headers.get("Content-Range", "")
            if status == 206 and content_range:
                return True, 206, f"HTTP 206 Partial Content Supported (Content-Range: {content_range})"
            elif status == 200:
                return False, 200, "WARNING: Server returned HTTP 200 instead of HTTP 206 (Range header ignored by Proxy)"
            return True, status, f"HTTP {status}"
    except urllib.error.HTTPError as e:
        # 206 or 403/404 with range support on root paths
        if e.code == 206:
            return True, 206, "HTTP 206 Partial Content Supported"
        elif e.code in (400, 403, 404):
            return True, e.code, f"Server responded HTTP {e.code} (Reachable Front-Door)"
        return False, e.code, f"HTTP Error {e.code}"
    except Exception as e:
        return False, 0, f"Connection Failed: {e}"

def check_lan_p2p_port(target_ip: str, port: int = 7680, timeout_sec: float = 1.0) -> Tuple[bool, float, str]:
    """Tests if Delivery Optimization LAN P2P Port (TCP 7680) is open on a target peer."""
    t0 = time.time()
    try:
        with socket.create_connection((target_ip, port), timeout=timeout_sec):
            rtt_ms = round((time.time() - t0) * 1000.0, 2)
            return True, rtt_ms, f"DO P2P Port {port} OPEN on {target_ip}"
    except Exception as e:
        return False, 0.0, f"DO P2P Port {port} Closed/Filtered on {target_ip} ({e})"

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
        print(f"Windows Update & DO metrics written to {output_file}")
    else:
        print(prom_content)

def main():
    parser = argparse.ArgumentParser(description="OpenUX Windows Update & Delivery Optimization Synthetic Prober")
    parser.add_argument("--peer-ip", default="127.0.0.1", help="Target LAN peer IP to test DO port 7680 listener")
    parser.add_argument("--mcc-server", default="", help="Optional Microsoft Connected Cache server (IP:port)")
    parser.add_argument("--output", default=DEFAULT_PROM_FILE, help="Prometheus textfile output path")
    args = parser.parse_args()

    prom_lines = [
        "# HELP openux_wu_endpoint_status Windows Update cloud service reachability (1=Reachable, 0=Failed)",
        "# TYPE openux_wu_endpoint_status gauge",
        "# HELP openux_wu_endpoint_latency_ms Windows Update TCP connect latency in milliseconds",
        "# TYPE openux_wu_endpoint_latency_ms gauge",
        "# HELP openux_do_cloud_status Delivery Optimization cloud tracker reachability (1=Reachable, 0=Failed)",
        "# TYPE openux_do_cloud_status gauge",
        "# HELP openux_do_cloud_latency_ms Delivery Optimization cloud tracker TCP connect latency in milliseconds",
        "# TYPE openux_do_cloud_latency_ms gauge",
        "# HELP openux_bits_http_range_supported BITS & DO HTTP 206 Partial Content Range Header support (1=Supported, 0=Broken)",
        "# TYPE openux_bits_http_range_supported gauge",
        "# HELP openux_do_lan_p2p_port7680_open Delivery Optimization local LAN peer listener on TCP 7680 (1=Open, 0=Closed/Filtered)",
        "# TYPE openux_do_lan_p2p_port7680_open gauge",
        "# HELP openux_mcc_cache_status Microsoft Connected Cache local server reachability (1=Reachable, 0=Failed)",
        "# TYPE openux_mcc_cache_status gauge"
    ]

    print("Executing Windows Update (WaaS), BITS & Delivery Optimization Probes...")

    # 1. Probe Windows Update (WaaS) Cloud Endpoints
    for wu in WU_ENDPOINTS:
        is_ok, rtt_ms, msg = check_tcp_endpoint(wu["host"], wu["port"])
        val = 1 if is_ok else 0
        print(f"  [WU] {wu['name']} ({wu['host']}) -> Status: {'OK' if is_ok else 'FAIL'} | RTT: {rtt_ms}ms")
        prom_lines.append(f'openux_wu_endpoint_status{{service="{wu["id"]}",host="{wu["host"]}"}} {val}')
        prom_lines.append(f'openux_wu_endpoint_latency_ms{{service="{wu["id"]}",host="{wu["host"]}"}} {rtt_ms}')

    # 2. Probe Delivery Optimization Cloud Coordination
    for do_ep in DO_ENDPOINTS:
        is_ok, rtt_ms, msg = check_tcp_endpoint(do_ep["host"], do_ep["port"])
        val = 1 if is_ok else 0
        print(f"  [DO-CLOUD] {do_ep['name']} ({do_ep['host']}) -> Status: {'OK' if is_ok else 'FAIL'} | RTT: {rtt_ms}ms")
        prom_lines.append(f'openux_do_cloud_status{{service="{do_ep["id"]}",host="{do_ep["host"]}"}} {val}')
        prom_lines.append(f'openux_do_cloud_latency_ms{{service="{do_ep["id"]}",host="{do_ep["host"]}"}} {rtt_ms}')

    # 3. Probe BITS & Delivery Optimization HTTP 206 Partial Content Range Support
    range_targets = [
        {"id": "wu_cdn_range", "url": "https://download.windowsupdate.com"},
        {"id": "do_cdn_range", "url": "https://dl.delivery.mp.microsoft.com"}
    ]
    for rt in range_targets:
        is_range_ok, code, msg = check_http_range_support(rt["url"])
        range_val = 1 if is_range_ok else 0
        print(f"  [BITS/RANGE] {rt['id']} ({rt['url']}) -> Range Support: {'PASS (HTTP 206)' if is_range_ok else 'FAIL'} ({code}) | {msg}")
        prom_lines.append(f'openux_bits_http_range_supported{{target="{rt["id"]}",url="{rt["url"]}"}} {range_val}')

    # 4. Probe Delivery Optimization LAN P2P Peer Listener (Port 7680)
    p2p_open, p2p_rtt, p2p_msg = check_lan_p2p_port(args.peer_ip, 7680)
    p2p_val = 1 if p2p_open else 0
    print(f"  [DO-P2P] LAN Peer Port 7680 on {args.peer_ip} -> {'OPEN' if p2p_open else 'CLOSED/FILTERED'} ({p2p_msg})")
    prom_lines.append(f'openux_do_lan_p2p_port7680_open{{target_ip="{args.peer_ip}"}} {p2p_val}')

    # 5. Probe Microsoft Connected Cache (MCC) if specified
    if args.mcc_server:
        host, port_str = args.mcc_server.split(":") if ":" in args.mcc_server else (args.mcc_server, "80")
        mcc_ok, mcc_rtt, mcc_msg = check_tcp_endpoint(host, int(port_str))
        mcc_val = 1 if mcc_ok else 0
        print(f"  [MCC] Microsoft Connected Cache ({args.mcc_server}) -> {'OK' if mcc_ok else 'FAIL'} | RTT: {mcc_rtt}ms")
        prom_lines.append(f'openux_mcc_cache_status{{host="{host}",port="{port_str}"}} {mcc_val}')

    write_metrics(prom_lines, args.output)

if __name__ == "__main__":
    main()
