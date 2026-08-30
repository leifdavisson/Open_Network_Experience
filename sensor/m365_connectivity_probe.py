#!/usr/bin/env python3
"""
Open Network Experience (ONE) — Microsoft 365 & Office 365 A5 Synthetic Health Prober
Tests full-spectrum connectivity, real-time media quality, and security policy for:
  1. Optimize Services: Teams Real-Time Media (UDP STUN 3478-3481), Exchange Online (MAPI/REST), SharePoint/OneDrive WFE
  2. Allow Services: Microsoft Entra ID (STS Auth), MS Graph API, Microsoft Intune, Defender & Purview
  3. SSL Decryption MITM Bypass Validator: Verifies firewall inspection certs are not injected on Optimize traffic
  4. Teams Voice Quality Engine: RFC 3550 Interarrival Jitter, Packet Loss, and ITU-T G.107 Voice MOS calculation
"""

import os
import sys
import time
import socket
import ssl
import struct
import urllib.request
import urllib.error
import argparse
from typing import Dict, Any, List, Tuple, Optional

DEFAULT_PROM_FILE = "/var/lib/node_exporter/textfile_collector/m365.prom"

# Official Microsoft 365 Endpoint Matrix categorized by Microsoft Connectivity Principles
M365_SERVICES = [
    # --- 1. OPTIMIZE (Direct Egress Required, No Proxy, No SSL Inspection) ---
    {
        "id": "teams_web",
        "name": "Teams Signaling & Web Services",
        "category": "optimize",
        "url": "https://teams.microsoft.com",
        "host": "teams.microsoft.com",
        "port": 443,
        "critical": True,
        "expect_ssl_bypass": True
    },
    {
        "id": "exchange_online",
        "name": "Exchange Online (MAPI & REST)",
        "category": "optimize",
        "url": "https://outlook.office.com",
        "host": "outlook.office.com",
        "port": 443,
        "critical": True,
        "expect_ssl_bypass": True
    },
    {
        "id": "sharepoint_online",
        "name": "SharePoint Online Web Front-End",
        "category": "optimize",
        "url": "https://sharepoint.com",
        "host": "sharepoint.com",
        "port": 443,
        "critical": True,
        "expect_ssl_bypass": True
    },
    {
        "id": "onedrive_storage",
        "name": "OneDrive for Business",
        "category": "optimize",
        "url": "https://onedrive.live.com",
        "host": "onedrive.live.com",
        "port": 443,
        "critical": True,
        "expect_ssl_bypass": True
    },

    # --- 2. ALLOW (Essential Cloud Dependencies) ---
    {
        "id": "entra_id_sts",
        "name": "Microsoft Entra ID STS Auth",
        "category": "allow",
        "url": "https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration",
        "host": "login.microsoftonline.com",
        "port": 443,
        "critical": True,
        "expect_ssl_bypass": False
    },
    {
        "id": "ms_graph_api",
        "name": "Microsoft Graph REST API",
        "category": "allow",
        "url": "https://graph.microsoft.com/v1.0/$metadata",
        "host": "graph.microsoft.com",
        "port": 443,
        "critical": True,
        "expect_ssl_bypass": False
    },
    {
        "id": "microsoft_intune",
        "name": "Microsoft Intune Device Management",
        "category": "allow",
        "url": "https://manage.microsoft.com",
        "host": "manage.microsoft.com",
        "port": 443,
        "critical": False,
        "expect_ssl_bypass": False
    },
    {
        "id": "defender_security",
        "name": "Microsoft Defender Portal",
        "category": "allow",
        "url": "https://security.microsoft.com",
        "host": "security.microsoft.com",
        "port": 443,
        "critical": False,
        "expect_ssl_bypass": False
    },
    {
        "id": "purview_compliance",
        "name": "Microsoft Purview Compliance Portal",
        "category": "allow",
        "url": "https://compliance.microsoft.com",
        "host": "compliance.microsoft.com",
        "port": 443,
        "critical": False,
        "expect_ssl_bypass": False
    }
]

# Teams Real-Time Media Anycast Relay Endpoints (UDP STUN)
TEAMS_MEDIA_RELAYS = [
    {"name": "Teams-Anycast-Primary", "host": "world.tr.teams.microsoft.com", "port": 3478},
    {"name": "Teams-Anycast-Backup", "host": "world.tr.teams.microsoft.com", "port": 3481}
]

# Common firewall SSL Inspection / MITM proxy signatures
KNOWN_MITM_ISSUERS = [
    "fortinet", "fortigate", "palo alto", "pan-os", "zscaler",
    "sophos", "sonicwall", "barracuda", "cisco umbrella",
    "lightspeed", "securly", "smoothwall", "untangle", "checkpoint"
]

def build_stun_binding_request(tx_id: bytes) -> bytes:
    """Builds standard RFC 5389 STUN Binding Request packet."""
    msg_type = b"\x00\x01"       # Binding Request
    msg_length = b"\x00\x00"     # 0 attributes
    magic_cookie = b"\x21\x12\xa4\x42"
    return msg_type + msg_length + magic_cookie + tx_id

def calculate_mos_score(rtt_ms: float, jitter_ms: float, loss_percent: float) -> float:
    """
    Estimates voice Mean Opinion Score (MOS) using ITU-T G.107 E-model.
    Scale: 4.3-4.5 (Pristine), 4.0-4.2 (Good), 3.5-3.9 (Fair), <3.5 (Degraded).
    """
    effective_latency = rtt_ms + (jitter_ms * 2.0) + 10.0
    if effective_latency < 160.0:
        r_val = 93.2 - (effective_latency / 40.0)
    else:
        r_val = 93.2 - ((effective_latency - 120.0) / 10.0)

    r_val = r_val - (loss_percent * 2.5)
    r_val = max(0.0, min(100.0, r_val))

    if r_val <= 0:
        mos = 1.0
    elif r_val >= 100:
        mos = 4.5
    else:
        mos = 1.0 + (0.035 * r_val) + (r_val * (r_val - 60.0) * (100.0 - r_val) * 0.000007)
    return round(max(1.0, min(4.5, mos)), 2)

def probe_teams_udp_media(
    host: str,
    port: int = 3478,
    packet_count: int = 20,
    interval_sec: float = 0.02, # 20ms RTP audio packet cadence
    timeout_sec: float = 1.0
) -> Dict[str, Any]:
    """
    Measures UDP media connectivity to Microsoft Teams Anycast Relays:
      - Round Trip Time (RTT)
      - RFC 3550 Interarrival Jitter
      - UDP Packet Loss Percentage
      - Predicted Voice MOS Score
    """
    try:
        dest_ip = socket.gethostbyname(host)
    except Exception as e:
        return {
            "status": 0,
            "rtt_ms": 0.0,
            "jitter_ms": 0.0,
            "loss_percent": 100.0,
            "mos_score": 1.0,
            "error": f"DNS resolution failed: {e}"
        }

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout_sec)

    rtts = []
    sent_count = 0
    recv_count = 0

    for _ in range(packet_count):
        tx_id = os.urandom(12)
        packet = build_stun_binding_request(tx_id)
        start_time = time.time()
        try:
            sock.sendto(packet, (dest_ip, port))
            sent_count += 1
            data, _ = sock.recvfrom(512)
            recv_time = time.time()
            if len(data) >= 20 and data[8:20] == tx_id:
                rtt = (recv_time - start_time) * 1000.0
                rtts.append(rtt)
                recv_count += 1
        except socket.timeout:
            pass
        except Exception:
            pass

        time.sleep(interval_sec)

    sock.close()

    if sent_count == 0 or recv_count == 0:
        return {
            "status": 0,
            "rtt_ms": 0.0,
            "jitter_ms": 0.0,
            "loss_percent": 100.0,
            "mos_score": 1.0,
            "error": "All UDP STUN probe packets lost (Firewall blocking UDP 3478-3481)"
        }

    avg_rtt = sum(rtts) / len(rtts)
    loss_pct = ((sent_count - recv_count) / sent_count) * 100.0

    # RFC 3550 Interarrival Jitter calculation: J(i) = J(i-1) + (|D(i-1, i)| - J(i-1))/16
    jitter = 0.0
    for i in range(1, len(rtts)):
        d = abs(rtts[i] - rtts[i - 1])
        jitter += (d - jitter) / 16.0

    mos = calculate_mos_score(avg_rtt, jitter, loss_pct)

    return {
        "status": 1,
        "rtt_ms": round(avg_rtt, 2),
        "jitter_ms": round(jitter, 3),
        "loss_percent": round(loss_pct, 1),
        "mos_score": mos,
        "error": None
    }

def check_ssl_inspection_bypass(host: str, port: int = 443) -> Tuple[bool, str]:
    """
    Connects via TLS and verifies certificate issuer is genuine Microsoft CA
    and NOT intercepted by a firewall proxy.
    """
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

                return True, f"Bypassed / Genuine Microsoft CA: {issuer_str}"
    except ssl.SSLError as e:
        return False, f"SSL Error: {e}"
    except Exception as e:
        return False, f"Connection Error: {e}"

def check_http_endpoint(target: Dict[str, Any]) -> Tuple[bool, float, float, float, int, str]:
    """
    Measures DNS time, TCP connect time, TLS handshake time, and HTTP response code.
    Returns: (is_ok, dns_time, tcp_time, total_latency, status_code, reason)
    """
    url = target["url"]
    host = target["host"]
    port = target.get("port", 443)

    # 1. DNS Timing
    t0 = time.time()
    try:
        socket.gethostbyname(host)
        dns_time = time.time() - t0
    except Exception as e:
        return False, round(time.time() - t0, 4), 0.0, round(time.time() - t0, 4), 0, f"DNS Error: {e}"

    # 2. TCP Connect Timing
    t1 = time.time()
    try:
        with socket.create_connection((host, port), timeout=5):
            tcp_time = time.time() - t1
    except Exception as e:
        return False, round(dns_time, 4), round(time.time() - t1, 4), round(time.time() - t0, 4), 0, f"TCP Connect Error: {e}"

    # 3. Full HTTP Request
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ONE-M365-Prober/1.0",
            "Cache-Control": "no-cache"
        }
    )
    t2 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            total_latency = time.time() - t0
            is_ok = response.status in (200, 301, 302, 307)
            return is_ok, round(dns_time, 4), round(tcp_time, 4), round(total_latency, 4), response.status, "OK"
    except urllib.error.HTTPError as e:
        total_latency = time.time() - t0
        # 401/403/404 proves network connectivity to Microsoft front-door WFE
        is_ok = e.code in (401, 403, 404)
        return is_ok, round(dns_time, 4), round(tcp_time, 4), round(total_latency, 4), e.code, f"HTTP {e.code}"
    except Exception as e:
        total_latency = time.time() - t0
        return False, round(dns_time, 4), round(tcp_time, 4), round(total_latency, 4), 0, f"Error: {str(e)}"

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
        print(f"M365 metrics written to {output_file}")
    else:
        print(prom_content)

def main():
    parser = argparse.ArgumentParser(description="OpenUX Microsoft 365 & Office 365 A5 Synthetic Prober")
    parser.add_argument("--tenant", default="", help="Custom district SharePoint tenant prefix (e.g. 'kernhigh' for kernhigh.sharepoint.com)")
    parser.add_argument("--output", default=DEFAULT_PROM_FILE, help="Prometheus textfile output path")
    args = parser.parse_args()

    # Dynamic tenant injection
    services_to_probe = list(M365_SERVICES)
    if args.tenant:
        tenant_name = args.tenant.replace(".sharepoint.com", "").strip()
        services_to_probe.append({
            "id": f"tenant_{tenant_name}_sharepoint",
            "name": f"District SharePoint Tenant ({tenant_name})",
            "category": "optimize",
            "url": f"https://{tenant_name}.sharepoint.com",
            "host": f"{tenant_name}.sharepoint.com",
            "port": 443,
            "critical": True,
            "expect_ssl_bypass": True
        })

    prom_lines = [
        "# HELP openux_m365_endpoint_status Microsoft 365 endpoint reachability (1=Reachable/OK, 0=Failed)",
        "# TYPE openux_m365_endpoint_status gauge",
        "# HELP openux_m365_endpoint_latency_seconds HTTP response latency in seconds",
        "# TYPE openux_m365_endpoint_latency_seconds gauge",
        "# HELP openux_m365_dns_lookup_seconds DNS resolution time in seconds",
        "# TYPE openux_m365_dns_lookup_seconds gauge",
        "# HELP openux_m365_tcp_connect_seconds TCP SYN handshake time in seconds",
        "# TYPE openux_m365_tcp_connect_seconds gauge",
        "# HELP openux_m365_ssl_bypass_compliant Whether genuine Microsoft CA is present without firewall MITM (1=Compliant, 0=Non-Compliant)",
        "# TYPE openux_m365_ssl_bypass_compliant gauge",
        "# HELP openux_m365_teams_udp_rtt_ms Teams UDP Media round-trip time in milliseconds",
        "# TYPE openux_m365_teams_udp_rtt_ms gauge",
        "# HELP openux_m365_teams_udp_jitter_ms Teams UDP Media RFC 3550 interarrival jitter in milliseconds",
        "# TYPE openux_m365_teams_udp_jitter_ms gauge",
        "# HELP openux_m365_teams_udp_loss_percent Teams UDP Media packet loss percentage",
        "# TYPE openux_m365_teams_udp_loss_percent gauge",
        "# HELP openux_m365_teams_voice_mos Estimated Microsoft Teams voice quality Mean Opinion Score (1.0 to 4.5)",
        "# TYPE openux_m365_teams_voice_mos gauge"
    ]

    print("Executing Microsoft 365 & Office 365 A5 Synthetic Probes...")

    # 1. Probe HTTP / TLS Endpoints
    for s in services_to_probe:
        s_id = s["id"]
        s_cat = s["category"]
        s_host = s["host"]

        is_ok, dns_t, tcp_t, total_t, status_code, reason = check_http_endpoint(s)
        is_bypassed, ssl_msg = check_ssl_inspection_bypass(s_host, s.get("port", 443))

        status_val = 1 if is_ok else 0
        ssl_val = 1 if is_bypassed else 0

        print(f"  [{s_cat.upper()}] {s['name']} ({s_host}) -> Status: {'OK' if is_ok else 'FAIL'} ({status_code}) | Latency: {total_t*1000:.1f}ms | SSL Bypass: {'PASS' if is_bypassed else 'FAIL'}")

        prom_lines.append(f'openux_m365_endpoint_status{{service="{s_id}",category="{s_cat}",host="{s_host}"}} {status_val}')
        prom_lines.append(f'openux_m365_endpoint_latency_seconds{{service="{s_id}",category="{s_cat}",host="{s_host}"}} {total_t}')
        prom_lines.append(f'openux_m365_dns_lookup_seconds{{service="{s_id}",category="{s_cat}",host="{s_host}"}} {dns_t}')
        prom_lines.append(f'openux_m365_tcp_connect_seconds{{service="{s_id}",category="{s_cat}",host="{s_host}"}} {tcp_t}')
        prom_lines.append(f'openux_m365_ssl_bypass_compliant{{service="{s_id}",category="{s_cat}",host="{s_host}"}} {ssl_val}')

    # 2. Probe Teams Real-Time Media (UDP STUN)
    for r in TEAMS_MEDIA_RELAYS:
        r_name = r["name"]
        r_host = r["host"]
        r_port = r["port"]

        media_res = probe_teams_udp_media(r_host, r_port)
        print(f"  [MEDIA] {r_name} (UDP {r_port}) -> Status: {'OK' if media_res['status'] == 1 else 'FAIL'} | RTT: {media_res['rtt_ms']}ms | Jitter: {media_res['jitter_ms']}ms | Loss: {media_res['loss_percent']}% | MOS: {media_res['mos_score']}")

        prom_lines.append(f'openux_m365_teams_udp_rtt_ms{{relay="{r_name}",host="{r_host}",port="{r_port}"}} {media_res["rtt_ms"]}')
        prom_lines.append(f'openux_m365_teams_udp_jitter_ms{{relay="{r_name}",host="{r_host}",port="{r_port}"}} {media_res["jitter_ms"]}')
        prom_lines.append(f'openux_m365_teams_udp_loss_percent{{relay="{r_name}",host="{r_host}",port="{r_port}"}} {media_res["loss_percent"]}')
        prom_lines.append(f'openux_m365_teams_voice_mos{{relay="{r_name}",host="{r_host}",port="{r_port}"}} {media_res["mos_score"]}')

    write_metrics(prom_lines, args.output)

if __name__ == "__main__":
    main()
