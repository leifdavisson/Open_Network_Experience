#!/usr/bin/env python3
"""
Open Network Experience (ONE) — Lightspeed Systems Filter & Classroom Synthetic Health Prober
Tests full-spectrum Lightspeed ecosystem:
  1. Cloud Control Plane & Admin Portal (relay.school, admin.relay.school)
  2. SmartAgent Heartbeat & Check-In Gateways (agent.lightspeedsystems.app, rules.lightspeedsystems.com)
  3. Config Delivery CDN (cdn-global.configcat.com, lsaccess.me, lsfilter.com)
  4. Lightspeed Classroom Real-Time WebSocket Infrastructure (classroom.lightspeedsystems.app, realtime.ably.io)
  5. Certificate Pinning & SSL Decryption MITM Bypass Verification
  6. SmartShield Anycast DNS Filtering Reachability
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

DEFAULT_PROM_FILE = "/var/lib/node_exporter/textfile_collector/lightspeed.prom"

# Core Lightspeed Filter & Classroom Infrastructure Endpoints
LIGHTSPEED_ENDPOINTS = [
    # --- 1. CORE CLOUD MANAGEMENT & CONTROL PLANE ---
    {"id": "ls_relay_school", "name": "Lightspeed Filter Portal (relay.school)", "category": "control_plane", "host": "relay.school", "port": 443, "url": "https://relay.school", "expect_ssl_bypass": True},
    {"id": "ls_admin_portal", "name": "Lightspeed Filter Admin Console", "category": "control_plane", "host": "admin.relay.school", "port": 443, "url": "https://admin.relay.school", "expect_ssl_bypass": True},
    {"id": "ls_rules_engine", "name": "Lightspeed Policy & Rules Engine", "category": "control_plane", "host": "rules.lightspeedsystems.com", "port": 443, "url": "https://rules.lightspeedsystems.com", "expect_ssl_bypass": True},

    # --- 2. SMARTAGENT HEARTBEAT & CHECK-IN ---
    {"id": "ls_smartagent_gateway", "name": "SmartAgent Cloud Check-In Gateway", "category": "smartagent", "host": "agent.lightspeedsystems.app", "port": 443, "url": "https://agent.lightspeedsystems.app", "expect_ssl_bypass": True},
    {"id": "ls_production_relay", "name": "Relay Production Gateway", "category": "smartagent", "host": "production-relay.lightspeedsystems.app", "port": 443, "url": "https://production-relay.lightspeedsystems.app", "expect_ssl_bypass": True},

    # --- 3. CONFIG DELIVERY & REDIRECTIONS ---
    {"id": "ls_configcat_cdn", "name": "ConfigCat Policy Delivery CDN", "category": "config_cdn", "host": "cdn-global.configcat.com", "port": 443, "url": "https://cdn-global.configcat.com", "expect_ssl_bypass": False},
    {"id": "ls_access_redirect", "name": "Lightspeed Access Redirection Host", "category": "config_cdn", "host": "lsaccess.me", "port": 443, "url": "https://lsaccess.me", "expect_ssl_bypass": False},
    {"id": "ls_filter_redirect", "name": "Lightspeed Filter Redirection Host", "category": "config_cdn", "host": "lsfilter.com", "port": 443, "url": "https://lsfilter.com", "expect_ssl_bypass": False},

    # --- 4. LIGHTSPEED CLASSROOM & REAL-TIME STREAMING ---
    {"id": "ls_classroom_portal", "name": "Lightspeed Classroom Portal", "category": "classroom", "host": "classroom.lightspeedsystems.app", "port": 443, "url": "https://classroom.lightspeedsystems.app", "expect_ssl_bypass": True},
    {"id": "ls_realtime_ably", "name": "Ably Real-Time Message Bus", "category": "classroom", "host": "realtime.ably.io", "port": 443, "url": "https://realtime.ably.io", "expect_ssl_bypass": True}
]

# Known firewall SSL Inspection / MITM proxy signatures
KNOWN_MITM_ISSUERS = [
    "fortinet", "fortigate", "palo alto", "pan-os", "zscaler",
    "sophos", "sonicwall", "barracuda", "cisco umbrella",
    "securly", "smoothwall", "untangle", "checkpoint"
]

def check_tcp_endpoint(host: str, port: int = 443, timeout_sec: float = 4.0) -> Tuple[bool, float, str]:
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

def check_ssl_inspection_bypass(host: str, port: int = 443) -> Tuple[bool, str]:
    """Connects via TLS and verifies certificate issuer is genuine and NOT intercepted by a firewall proxy."""
    ctx = ssl.create_default_context()
    try:
        with socket.create_connection((host, port), timeout=5) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
                issuer_dict: Dict[str, str] = {}
                if cert and isinstance(cert, dict):
                    raw_issuer = cert.get('issuer', ())
                    for rdn in raw_issuer:
                        for entry in rdn:
                            if isinstance(entry, tuple) and len(entry) >= 2:
                                issuer_dict[str(entry[0])] = str(entry[1])
                common_name = issuer_dict.get('commonName', '')
                org_name = issuer_dict.get('organizationName', '')
                issuer_str = f"{common_name} ({org_name})"

                lower_issuer = issuer_str.lower()
                for keyword in KNOWN_MITM_ISSUERS:
                    if keyword in lower_issuer:
                        return False, f"MITM Inspection Detected: {issuer_str}"

                return True, f"Bypassed / Genuine CA: {issuer_str}"
    except ssl.SSLError as e:
        return False, f"SSL Error: {e}"
    except Exception as e:
        return False, f"Connection Error: {e}"

def probe_smartshield_dns(dns_ip: str, timeout_sec: float = 2.0) -> Tuple[bool, float, str]:
    """Tests SmartShield Anycast DNS resolver query responsiveness on UDP 53."""
    t0 = time.time()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(timeout_sec)
            # Standard DNS query for google.com
            query = b"\xaa\xaa\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x06google\x03com\x00\x00\x01\x00\x01"
            sock.sendto(query, (dns_ip, 53))
            resp, _ = sock.recvfrom(512)
            rtt_ms = round((time.time() - t0) * 1000.0, 2)
            if len(resp) >= 12:
                return True, rtt_ms, f"SmartShield DNS OK ({rtt_ms}ms)"
    except Exception as e:
        return False, 0.0, f"SmartShield DNS Error: {e}"
    return False, 0.0, "Invalid DNS response"

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
        print(f"Lightspeed metrics written to {output_file}")
    else:
        print(prom_content)

def main():
    parser = argparse.ArgumentParser(description="OpenUX Lightspeed Systems Filter & Classroom Synthetic Prober")
    parser.add_argument("--dns-server", default="", help="Optional Lightspeed SmartShield DNS resolver IP to test")
    parser.add_argument("--output", default=DEFAULT_PROM_FILE, help="Prometheus textfile output path")
    args = parser.parse_args()

    prom_lines = [
        "# HELP openux_lightspeed_endpoint_status Lightspeed endpoint reachability (1=Reachable, 0=Failed)",
        "# TYPE openux_lightspeed_endpoint_status gauge",
        "# HELP openux_lightspeed_endpoint_latency_ms TCP connection latency in milliseconds",
        "# TYPE openux_lightspeed_endpoint_latency_ms gauge",
        "# HELP openux_lightspeed_ssl_bypass_compliant Whether genuine CA is present without firewall MITM (1=Compliant, 0=MITM Intercepted)",
        "# TYPE openux_lightspeed_ssl_bypass_compliant gauge",
        "# HELP openux_lightspeed_smartshield_dns_status SmartShield Anycast DNS resolver status (1=OK, 0=Failed)",
        "# TYPE openux_lightspeed_smartshield_dns_status gauge",
        "# HELP openux_lightspeed_smartshield_dns_latency_ms SmartShield DNS query latency in milliseconds",
        "# TYPE openux_lightspeed_smartshield_dns_latency_ms gauge"
    ]

    print("Executing Lightspeed Systems Filter & Classroom Synthetic Probes...")

    # 1. Probe Core Lightspeed Endpoints
    for s in LIGHTSPEED_ENDPOINTS:
        s_id = s["id"]
        s_cat = s["category"]
        s_host = s["host"]
        s_port = s["port"]

        is_ok, rtt_ms, msg = check_tcp_endpoint(s_host, s_port)
        status_val = 1 if is_ok else 0

        # SSL Decryption check for 443 endpoints
        ssl_val = 1
        if s_port == 443:
            is_bypassed, ssl_msg = check_ssl_inspection_bypass(s_host, s_port)
            ssl_val = 1 if is_bypassed else 0
            ssl_str = "PASS" if is_bypassed else "FAIL"
        else:
            ssl_str = "N/A"

        print(f"  [{s_cat.upper()}] {s['name']} ({s_host}:{s_port}) -> Status: {'OK' if is_ok else 'FAIL'} | RTT: {rtt_ms}ms | SSL Bypass: {ssl_str}")

        prom_lines.append(f'openux_lightspeed_endpoint_status{{service="{s_id}",category="{s_cat}",host="{s_host}"}} {status_val}')
        prom_lines.append(f'openux_lightspeed_endpoint_latency_ms{{service="{s_id}",category="{s_cat}",host="{s_host}"}} {rtt_ms}')
        if s_port == 443:
            prom_lines.append(f'openux_lightspeed_ssl_bypass_compliant{{service="{s_id}",category="{s_cat}",host="{s_host}"}} {ssl_val}')

    # 2. Optional SmartShield DNS Resolver Check
    if args.dns_server:
        dns_ok, dns_rtt, dns_msg = probe_smartshield_dns(args.dns_server)
        dns_val = 1 if dns_ok else 0
        print(f"  [SMARTSHIELD] Anycast DNS Resolver ({args.dns_server}:53) -> {'OK' if dns_ok else 'FAIL'} | RTT: {dns_rtt}ms")
        prom_lines.append(f'openux_lightspeed_smartshield_dns_status{{resolver="{args.dns_server}"}} {dns_val}')
        prom_lines.append(f'openux_lightspeed_smartshield_dns_latency_ms{{resolver="{args.dns_server}"}} {dns_rtt}')

    write_metrics(prom_lines, args.output)

if __name__ == "__main__":
    main()
