#!/usr/bin/env python3
"""
Open Network Experience (ONE) — Clever K-12 Identity, Badges & SSO Synthetic Health Prober
Tests full-spectrum Clever ecosystem:
  1. Clever Badges (QR Code Camera Ingestion & Badger Service)
  2. Clever IDM & Roster API Pipeline (api.clever.com, idm.clever.com)
  3. Single Sign-On (SSO) & District Portals (clever.com/in/<district-shortname>)
  4. Classroom MFA Safe Zone Public Egress IP Audit
  5. Optional On-Premises Active Directory LDAPS (TCP 636) Sync Port
  6. SSL Decryption MITM Bypass Validator (Amazon/DigiCert vs Firewall Proxy)
"""

import os
import sys
import time
import socket
import ssl
import json
import urllib.request
import urllib.error
import argparse
from typing import Dict, Any, List, Tuple, Optional

DEFAULT_PROM_FILE = "/var/lib/node_exporter/textfile_collector/clever.prom"

# Core Clever Ecosystem Endpoints
CLEVER_ENDPOINTS = [
    # --- 1. CLEVER BADGES QR AUTHENTICATION ---
    {"id": "clever_badger", "name": "Clever Badges QR Scanner Service", "category": "badges", "host": "badger.clever.com", "port": 443, "url": "https://badger.clever.com", "expect_ssl_bypass": True},
    {"id": "clever_assets", "name": "Clever Badge & Portal Static Assets", "category": "badges", "host": "assets.clever.com", "port": 443, "url": "https://assets.clever.com", "expect_ssl_bypass": False},
    {"id": "aws_s3_storage", "name": "AWS S3 Asset Cloud Storage", "category": "badges", "host": "s3.amazonaws.com", "port": 443, "url": "https://s3.amazonaws.com", "expect_ssl_bypass": False},

    # --- 2. SINGLE SIGN-ON & PORTAL ---
    {"id": "clever_portal_root", "name": "Clever District Portal Gateway", "category": "sso", "host": "clever.com", "port": 443, "url": "https://clever.com", "expect_ssl_bypass": True},
    {"id": "clever_oauth_tokens", "name": "Clever OAuth2 Token Grant", "category": "sso", "host": "clever.com", "port": 443, "url": "https://clever.com/oauth/tokens", "expect_ssl_bypass": True},
    {"id": "clever_saml_acs", "name": "Clever SAML 2.0 Assertion Consumer", "category": "sso", "host": "clever.com", "port": 443, "url": "https://clever.com/saml/acs", "expect_ssl_bypass": True},

    # --- 3. CLEVER IDM & DATA PIPELINE ---
    {"id": "clever_rest_api", "name": "Clever REST API v3.0", "category": "idm", "host": "api.clever.com", "port": 443, "url": "https://api.clever.com/v3.0/me", "expect_ssl_bypass": False},
    {"id": "clever_idm_engine", "name": "Clever IDM Directory Provisioner", "category": "idm", "host": "idm.clever.com", "port": 443, "url": "https://idm.clever.com", "expect_ssl_bypass": False}
]

# Known firewall SSL Inspection / MITM proxy signatures
KNOWN_MITM_ISSUERS = [
    "fortinet", "fortigate", "palo alto", "pan-os", "zscaler",
    "sophos", "sonicwall", "barracuda", "cisco umbrella",
    "lightspeed", "securly", "smoothwall", "untangle", "checkpoint"
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
                issuer = dict(x[0] for x in cert.get('issuer', []))
                common_name = issuer.get('commonName', '')
                org_name = issuer.get('organizationName', '')
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

def fetch_public_egress_ip(timeout_sec: float = 3.0) -> Tuple[bool, str]:
    """Discovers current WAN public egress IP for Classroom MFA Safe Zone verification."""
    urls = ["https://api.ipify.org?format=json", "https://icanhazip.com"]
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ONE-Clever-Prober/1.0"})
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                content = resp.read().decode("utf-8").strip()
                if "{" in content:
                    data = json.loads(content)
                    return True, data.get("ip", "unknown")
                return True, content
        except Exception:
            continue
    return False, "unknown"

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
        print(f"Clever metrics written to {output_file}")
    else:
        print(prom_content)

def main():
    parser = argparse.ArgumentParser(description="OpenUX Clever K-12 Identity, Badges & SSO Synthetic Prober")
    parser.add_argument("--district", default="", help="District shortname for custom portal check (e.g. 'kernhigh' for clever.com/in/kernhigh)")
    parser.add_argument("--ldaps-server", default="", help="Optional on-prem AD Domain Controller LDAPS (e.g. 'dc01.district.local:636')")
    parser.add_argument("--output", default=DEFAULT_PROM_FILE, help="Prometheus textfile output path")
    args = parser.parse_args()

    services_to_probe = list(CLEVER_ENDPOINTS)
    if args.district:
        dist_slug = args.district.strip()
        services_to_probe.append({
            "id": f"district_portal_{dist_slug}",
            "name": f"District Clever Portal ({dist_slug})",
            "category": "sso",
            "host": "clever.com",
            "port": 443,
            "url": f"https://clever.com/in/{dist_slug}",
            "expect_ssl_bypass": True
        })

    prom_lines = [
        "# HELP openux_clever_endpoint_status Clever endpoint reachability (1=Reachable, 0=Failed)",
        "# TYPE openux_clever_endpoint_status gauge",
        "# HELP openux_clever_endpoint_latency_ms TCP connection latency in milliseconds",
        "# TYPE openux_clever_endpoint_latency_ms gauge",
        "# HELP openux_clever_ssl_bypass_compliant Whether genuine CA is present without firewall MITM (1=Compliant, 0=MITM Intercepted)",
        "# TYPE openux_clever_ssl_bypass_compliant gauge",
        "# HELP openux_clever_safezone_egress_status Public WAN egress IP discovery for Safe Zones (1=Resolved, 0=Failed)",
        "# TYPE openux_clever_safezone_egress_status gauge",
        "# HELP openux_clever_idm_ldaps_status On-premise Active Directory LDAPS sync port 636 reachability (1=Open, 0=Closed)",
        "# TYPE openux_clever_idm_ldaps_status gauge"
    ]

    print("Executing Clever K-12 Identity, Badges & SSO Synthetic Probes...")

    # 1. Probe Core Clever Endpoints
    for s in services_to_probe:
        s_id = s["id"]
        s_cat = s["category"]
        s_host = s["host"]
        s_port = s["port"]

        is_ok, rtt_ms, msg = check_tcp_endpoint(s_host, s_port)
        status_val = 1 if is_ok else 0

        # SSL Decryption check for 443
        ssl_val = 1
        if s_port == 443:
            is_bypassed, ssl_msg = check_ssl_inspection_bypass(s_host, s_port)
            ssl_val = 1 if is_bypassed else 0
            ssl_str = "PASS" if is_bypassed else "FAIL"
        else:
            ssl_str = "N/A"

        print(f"  [{s_cat.upper()}] {s['name']} ({s_host}:{s_port}) -> Status: {'OK' if is_ok else 'FAIL'} | RTT: {rtt_ms}ms | SSL Bypass: {ssl_str}")

        prom_lines.append(f'openux_clever_endpoint_status{{service="{s_id}",category="{s_cat}",host="{s_host}"}} {status_val}')
        prom_lines.append(f'openux_clever_endpoint_latency_ms{{service="{s_id}",category="{s_cat}",host="{s_host}"}} {rtt_ms}')
        if s_port == 443:
            prom_lines.append(f'openux_clever_ssl_bypass_compliant{{service="{s_id}",category="{s_cat}",host="{s_host}"}} {ssl_val}')

    # 2. Check Classroom MFA Safe Zone Public Egress IP
    ip_ok, public_ip = fetch_public_egress_ip()
    ip_val = 1 if ip_ok else 0
    print(f"  [SAFEZONE] Classroom MFA WAN Egress IP -> {public_ip} ({'RESOLVED' if ip_ok else 'FAILED'})")
    prom_lines.append(f'openux_clever_safezone_egress_status{{public_ip="{public_ip}"}} {ip_val}')

    # 3. Optional On-Premises Active Directory LDAPS (Port 636) Check
    if args.ldaps_server:
        host, port_str = args.ldaps_server.split(":") if ":" in args.ldaps_server else (args.ldaps_server, "636")
        ldaps_ok, ldaps_rtt, ldaps_msg = check_tcp_endpoint(host, int(port_str))
        ldaps_val = 1 if ldaps_ok else 0
        print(f"  [IDM-LDAPS] On-Prem Active Directory ({args.ldaps_server}) -> {'OPEN' if ldaps_ok else 'CLOSED'} | RTT: {ldaps_rtt}ms")
        prom_lines.append(f'openux_clever_idm_ldaps_status{{host="{host}",port="{port_str}"}} {ldaps_val}')

    write_metrics(prom_lines, args.output)

if __name__ == "__main__":
    main()
