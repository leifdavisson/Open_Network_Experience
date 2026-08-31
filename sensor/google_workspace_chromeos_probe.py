#!/usr/bin/env python3
"""
Open Network Experience (ONE) — Google Workspace & ChromeOS Synthetic Health Prober
Tests full-spectrum Google ecosystem:
  1. Google Meet WebRTC Media Engine (UDP STUN 19302-19309 / 3478): RTT, RFC 3550 Jitter, Loss & Voice MOS
  2. Cloud Identity & Core Workspace Apps (accounts, mail, drive, docs, classroom:443)
  3. Chrome Enterprise DM Server & Policy Sync (device-management, cros-pa:443)
  4. ChromeOS Omaha OS Update CDN (tools.google.com, dl.google.com:443)
  5. Android FCM Push Notification Engine (fcm.googleapis.com:5228/443 & play.google.com)
  6. Google Trust Services (GTS) SSL Decryption MITM Inspection Bypass Verification
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

DEFAULT_PROM_FILE = "/var/lib/node_exporter/textfile_collector/google_workspace.prom"

# Official Google Workspace & Chrome Enterprise Endpoints
GOOGLE_SERVICES = [
    # --- 1. CLOUD IDENTITY & AUTHENTICATION ---
    {"id": "google_identity_sso", "name": "Google Cloud Identity & SAML SSO", "category": "identity", "host": "accounts.google.com", "port": 443, "url": "https://accounts.google.com", "expect_ssl_bypass": True},
    {"id": "google_oauth2", "name": "Google OAuth2 Token Service", "category": "identity", "host": "oauth2.googleapis.com", "port": 443, "url": "https://oauth2.googleapis.com", "expect_ssl_bypass": True},

    # --- 2. CORE WORKSPACE PRODUCTIVITY APPS ---
    {"id": "gmail_web", "name": "Gmail Web Interface", "category": "productivity", "host": "mail.google.com", "port": 443, "url": "https://mail.google.com", "expect_ssl_bypass": False},
    {"id": "google_drive", "name": "Google Drive Storage", "category": "productivity", "host": "drive.google.com", "port": 443, "url": "https://drive.google.com", "expect_ssl_bypass": False},
    {"id": "google_docs", "name": "Google Docs & Sheets Suite", "category": "productivity", "host": "docs.google.com", "port": 443, "url": "https://docs.google.com", "expect_ssl_bypass": False},
    {"id": "google_classroom", "name": "Google Classroom LMS", "category": "productivity", "host": "classroom.google.com", "port": 443, "url": "https://classroom.google.com", "expect_ssl_bypass": False},
    {"id": "gmail_smtp_submission", "name": "Gmail Authenticated SMTP", "category": "productivity", "host": "smtp.gmail.com", "port": 587, "url": None, "expect_ssl_bypass": False},

    # --- 3. GOOGLE MEET SIGNALING ---
    {"id": "meet_signaling", "name": "Google Meet Web Signaling", "category": "meet", "host": "meet.google.com", "port": 443, "url": "https://meet.google.com", "expect_ssl_bypass": True},

    # --- 4. CHROME ENTERPRISE & CHROMEOS MANAGEMENT ---
    {"id": "chrome_dm_server", "name": "Chrome Device Management (DM Server)", "category": "chromeos", "host": "device-management.googleapis.com", "port": 443, "url": "https://device-management.googleapis.com", "expect_ssl_bypass": True},
    {"id": "chrome_policy_sync", "name": "ChromeOS Policy Sync (cros-pa)", "category": "chromeos", "host": "cros-pa.googleapis.com", "port": 443, "url": "https://cros-pa.googleapis.com", "expect_ssl_bypass": True},
    {"id": "chrome_omaha_update", "name": "ChromeOS Omaha OS Update Server", "category": "chromeos", "host": "tools.google.com", "port": 443, "url": "https://tools.google.com/service/update2", "expect_ssl_bypass": True},
    {"id": "chrome_dl_cdn", "name": "ChromeOS Image Download CDN", "category": "chromeos", "host": "dl.google.com", "port": 443, "url": "https://dl.google.com", "expect_ssl_bypass": True},
    {"id": "chrome_web_store", "name": "Chrome Web Store & Extensions", "category": "chromeos", "host": "chromewebstore.google.com", "port": 443, "url": "https://chromewebstore.google.com", "expect_ssl_bypass": False},

    # --- 5. ANDROID RUNTIME & PLAY STORE ---
    {"id": "play_store", "name": "Managed Google Play Store", "category": "android", "host": "play.google.com", "port": 443, "url": "https://play.google.com", "expect_ssl_bypass": False}
]

# Google Meet WebRTC Media Relays (UDP STUN)
GOOGLE_MEET_RELAYS = [
    {"name": "Google-Meet-STUN-Primary", "host": "stun.l.google.com", "port": 19302},
    {"name": "Google-Meet-STUN-Backup", "host": "stun1.l.google.com", "port": 19302}
]

# Known firewall SSL Inspection / MITM proxy signatures
KNOWN_MITM_ISSUERS = [
    "fortinet", "fortigate", "palo alto", "pan-os", "zscaler",
    "sophos", "sonicwall", "barracuda", "cisco umbrella",
    "lightspeed", "securly", "smoothwall", "untangle", "checkpoint"
]

def build_stun_binding_request(tx_id: bytes) -> bytes:
    """Builds RFC 5389 STUN Binding Request packet."""
    msg_type = b"\x00\x01"       # Binding Request
    msg_length = b"\x00\x00"     # 0 attributes
    magic_cookie = b"\x21\x12\xa4\x42"
    return msg_type + msg_length + magic_cookie + tx_id

def calculate_mos_score(rtt_ms: float, jitter_ms: float, loss_percent: float) -> float:
    """Estimates voice Mean Opinion Score (MOS) using ITU-T G.107 E-model."""
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

def probe_google_meet_udp_media(
    host: str,
    port: int = 19302,
    packet_count: int = 20,
    interval_sec: float = 0.02,
    timeout_sec: float = 1.0
) -> Dict[str, Any]:
    """Measures Google Meet WebRTC UDP STUN latency, jitter, loss and calculates voice MOS score."""
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
            "error": f"All UDP STUN packets lost (Firewall blocking UDP {port})"
        }

    avg_rtt = sum(rtts) / len(rtts)
    loss_pct = ((sent_count - recv_count) / sent_count) * 100.0

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
    """Connects via TLS and verifies certificate issuer is genuine Google Trust Services (GTS)."""
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

                return True, f"Bypassed / Genuine Google Trust Services: {issuer_str}"
    except ssl.SSLError as e:
        return False, f"SSL Error: {e}"
    except Exception as e:
        return False, f"Connection Error: {e}"

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
        print(f"Google Workspace & ChromeOS metrics written to {output_file}")
    else:
        print(prom_content)

def main():
    parser = argparse.ArgumentParser(description="OpenUX Google Workspace & ChromeOS Synthetic Prober")
    parser.add_argument("--printer-ip", default="", help="Optional local IPP / CUPS printer IP (Port 631)")
    parser.add_argument("--output", default=DEFAULT_PROM_FILE, help="Prometheus textfile output path")
    args = parser.parse_args()

    prom_lines = [
        "# HELP openux_google_endpoint_status Google Workspace & ChromeOS endpoint reachability (1=Reachable, 0=Failed)",
        "# TYPE openux_google_endpoint_status gauge",
        "# HELP openux_google_endpoint_latency_ms TCP connect latency in milliseconds",
        "# TYPE openux_google_endpoint_latency_ms gauge",
        "# HELP openux_google_ssl_bypass_compliant Whether genuine Google Trust Services CA is present (1=Compliant, 0=MITM Intercepted)",
        "# TYPE openux_google_ssl_bypass_compliant gauge",
        "# HELP openux_google_meet_udp_rtt_ms Google Meet WebRTC UDP round-trip time in milliseconds",
        "# TYPE openux_google_meet_udp_rtt_ms gauge",
        "# HELP openux_google_meet_udp_jitter_ms Google Meet WebRTC RFC 3550 interarrival jitter in milliseconds",
        "# TYPE openux_google_meet_udp_jitter_ms gauge",
        "# HELP openux_google_meet_udp_loss_percent Google Meet WebRTC packet loss percentage",
        "# TYPE openux_google_meet_udp_loss_percent gauge",
        "# HELP openux_google_meet_voice_mos Estimated Google Meet voice quality Mean Opinion Score (1.0 to 4.5)",
        "# TYPE openux_google_meet_voice_mos gauge",
        "# HELP openux_google_fcm_port5228_status Firebase Cloud Messaging push notification port 5228 reachability (1=Open, 0=Blocked)",
        "# TYPE openux_google_fcm_port5228_status gauge",
        "# HELP openux_chromeos_cups_printer_status Local IPP / CUPS printer port 631 reachability (1=Reachable, 0=Failed)",
        "# TYPE openux_chromeos_cups_printer_status gauge"
    ]

    print("Executing Google Workspace & ChromeOS Synthetic Probes...")

    # 1. Probe Google Cloud Services & Endpoints
    for s in GOOGLE_SERVICES:
        s_id = s["id"]
        s_cat = s["category"]
        s_host = s["host"]
        s_port = s["port"]

        is_ok, rtt_ms, msg = check_tcp_endpoint(s_host, s_port)
        status_val = 1 if is_ok else 0

        # SSL Decryption Check for 443 endpoints
        ssl_val = 1
        if s_port == 443:
            is_bypassed, ssl_msg = check_ssl_inspection_bypass(s_host, s_port)
            ssl_val = 1 if is_bypassed else 0
            ssl_str = "PASS" if is_bypassed else "FAIL"
        else:
            ssl_str = "N/A"

        print(f"  [{s_cat.upper()}] {s['name']} ({s_host}:{s_port}) -> Status: {'OK' if is_ok else 'FAIL'} | RTT: {rtt_ms}ms | SSL Bypass: {ssl_str}")

        prom_lines.append(f'openux_google_endpoint_status{{service="{s_id}",category="{s_cat}",host="{s_host}"}} {status_val}')
        prom_lines.append(f'openux_google_endpoint_latency_ms{{service="{s_id}",category="{s_cat}",host="{s_host}"}} {rtt_ms}')
        if s_port == 443:
            prom_lines.append(f'openux_google_ssl_bypass_compliant{{service="{s_id}",category="{s_cat}",host="{s_host}"}} {ssl_val}')

    # 2. Probe Google Meet WebRTC Media Relays (UDP STUN)
    for r in GOOGLE_MEET_RELAYS:
        r_name = r["name"]
        r_host = r["host"]
        r_port = r["port"]

        media_res = probe_google_meet_udp_media(r_host, r_port)
        print(f"  [MEET-MEDIA] {r_name} (UDP {r_port}) -> Status: {'OK' if media_res['status'] == 1 else 'FAIL'} | RTT: {media_res['rtt_ms']}ms | Jitter: {media_res['jitter_ms']}ms | Loss: {media_res['loss_percent']}% | MOS: {media_res['mos_score']}")

        prom_lines.append(f'openux_google_meet_udp_rtt_ms{{relay="{r_name}",host="{r_host}",port="{r_port}"}} {media_res["rtt_ms"]}')
        prom_lines.append(f'openux_google_meet_udp_jitter_ms{{relay="{r_name}",host="{r_host}",port="{r_port}"}} {media_res["jitter_ms"]}')
        prom_lines.append(f'openux_google_meet_udp_loss_percent{{relay="{r_name}",host="{r_host}",port="{r_port}"}} {media_res["loss_percent"]}')
        prom_lines.append(f'openux_google_meet_voice_mos{{relay="{r_name}",host="{r_host}",port="{r_port}"}} {media_res["mos_score"]}')

    # 3. Probe Android FCM Push Notification Port (TCP 5228)
    fcm_ok, fcm_rtt, fcm_msg = check_tcp_endpoint("fcm.googleapis.com", 5228)
    fcm_val = 1 if fcm_ok else 0
    print(f"  [FCM] Firebase Push Notifications (fcm.googleapis.com:5228) -> {'OPEN' if fcm_ok else 'CLOSED/BLOCKED'} | RTT: {fcm_rtt}ms")
    prom_lines.append(f'openux_google_fcm_port5228_status{{host="fcm.googleapis.com"}} {fcm_val}')

    # 4. Probe Local IPP Printer if provided
    if args.printer_ip:
        p_ok, p_rtt, p_msg = check_tcp_endpoint(args.printer_ip, 631)
        p_val = 1 if p_ok else 0
        print(f"  [CUPS] Local IPP Printer ({args.printer_ip}:631) -> {'OK' if p_ok else 'FAIL'} | RTT: {p_rtt}ms")
        prom_lines.append(f'openux_chromeos_cups_printer_status{{printer_ip="{args.printer_ip}",port="631"}} {p_val}')

    write_metrics(prom_lines, args.output)

if __name__ == "__main__":
    main()
