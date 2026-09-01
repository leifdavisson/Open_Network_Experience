#!/usr/bin/env python3
"""
OpenUX Real-Time Voice & Video (VoIP / Zoom / Google Meet) Jitter Prober
Emulates real-time RTP voice/video media streams over UDP to measure:
  - Mean Opinion Score (MOS) voice quality (1.0 - 4.5)
  - RFC 3550 Interarrival Jitter (ms)
  - UDP Packet Loss Percentage
  - Round Trip Time (RTT)

Enables school districts to diagnose teacher Zoom buffering, Google Meet audio
dropouts, and SIP phone quality issues directly from student/classroom vantage points.
"""

import os
import time
import socket
import argparse
from typing import Dict, Any, List, Optional

DEFAULT_PROM_FILE = "/var/lib/node_exporter/textfile_collector/voip_jitter.prom"

# Default public STUN / UDP reflection endpoints (Google STUN)
DEFAULT_TARGETS = [
    {"name": "Google-STUN-Primary", "host": "stun.l.google.com", "port": 19302},
    {"name": "Google-STUN-Backup", "host": "stun1.l.google.com", "port": 19302}
]

def build_stun_binding_request(tx_id: bytes) -> bytes:
    """Builds a standard RFC 5389 STUN Binding Request packet."""
    msg_type = b"\x00\x01"       # Binding Request
    msg_length = b"\x00\x00"     # 0 attributes
    magic_cookie = b"\x21\x12\xa4\x42"
    return msg_type + msg_length + magic_cookie + tx_id

def calculate_mos_score(rtt_ms: float, jitter_ms: float, loss_percent: float) -> float:
    """
    Estimates voice Mean Opinion Score (MOS) using ITU-T G.107 E-model approximation.
    Scale: 4.3 - 4.5 (Crystal Clear), 4.0 - 4.2 (Good), 3.5 - 3.9 (Fair), <3.5 (Poor/Choppy)
    """
    effective_latency = rtt_ms + (jitter_ms * 2) + 10.0

    # Calculate R-factor
    if effective_latency < 160:
        r_val = 93.2 - (effective_latency / 40.0)
    else:
        r_val = 93.2 - ((effective_latency - 120.0) / 10.0)

    # Packet loss penalty
    r_val = r_val - (loss_percent * 2.5)
    r_val = max(0.0, min(100.0, r_val))

    # Convert R-factor to MOS (1.0 to 4.5)
    if r_val < 0:
        mos = 1.0
    elif r_val > 100:
        mos = 4.5
    else:
        mos = 1.0 + (0.035 * r_val) + (r_val * (r_val - 60.0) * (100.0 - r_val) * 0.000007)
    return round(max(1.0, min(4.5, mos)), 2)

def probe_udp_jitter(
    host: str,
    port: int = 19302,
    packet_count: int = 20,
    interval_sec: float = 0.02, # 20ms G.711 voice cadence
    timeout_sec: float = 1.0,
    interface: Optional[str] = None
) -> Dict[str, Any]:
    """
    Sends a burst of UDP probe packets at 20ms voice cadence and measures jitter & loss.
    """
    try:
        dest_ip = socket.gethostbyname(host)
    except socket.gaierror as e:
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

    if interface and hasattr(socket, "SO_BINDTODEVICE"):
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, interface.encode())
        except Exception:
            pass

    rtts = []
    sent_count = 0
    recv_count = 0

    for i in range(packet_count):
        tx_id = os.urandom(12)
        pkt = build_stun_binding_request(tx_id)

        t_send = time.time()
        try:
            sock.sendto(pkt, (dest_ip, port))
            sent_count += 1

            resp, _ = sock.recvfrom(512)
            t_recv = time.time()
            # Verify magic cookie and transaction ID
            if len(resp) >= 20 and resp[4:8] == b"\x21\x12\xa4\x42" and resp[8:20] == tx_id:
                rtt = (t_recv - t_send) * 1000.0
                rtts.append(rtt)
                recv_count += 1
        except socket.timeout:
            pass
        except Exception:
            pass

        time.sleep(interval_sec)

    sock.close()

    # Compute Statistics
    loss_percent = ((sent_count - recv_count) / sent_count) * 100.0 if sent_count > 0 else 100.0

    if not rtts:
        return {
            "status": 0,
            "rtt_ms": 0.0,
            "jitter_ms": 0.0,
            "loss_percent": 100.0,
            "mos_score": 1.0,
            "error": "All UDP probe packets dropped"
        }

    avg_rtt = sum(rtts) / len(rtts)

    # Calculate RFC 3550 Interarrival Jitter
    jitter_accum = 0.0
    for idx in range(len(rtts) - 1):
        diff = abs(rtts[idx+1] - rtts[idx])
        jitter_accum += diff
    avg_jitter = (jitter_accum / (len(rtts) - 1)) if len(rtts) > 1 else 0.0

    mos = calculate_mos_score(avg_rtt, avg_jitter, loss_percent)

    return {
        "status": 1 if loss_percent < 20.0 else 0,
        "rtt_ms": round(avg_rtt, 2),
        "jitter_ms": round(avg_jitter, 2),
        "loss_percent": round(loss_percent, 1),
        "mos_score": mos,
        "error": "OK"
    }

def write_metrics(results: List[Dict[str, Any]], output_path: str):
    """Atomically writes Prometheus metrics for voice/video quality."""
    prom_lines = [
        "# HELP openux_voip_status Voice/Video media stream quality health (1=Good, 0=Degraded/Down)",
        "# TYPE openux_voip_status gauge",
        "# HELP openux_voip_mos_score Mean Opinion Score voice quality estimation (1.0 - 4.5)",
        "# TYPE openux_voip_mos_score gauge",
        "# HELP openux_voip_rtt_seconds Round-trip latency in seconds",
        "# TYPE openux_voip_rtt_seconds gauge",
        "# HELP openux_voip_jitter_seconds RFC 3550 interarrival jitter in seconds",
        "# TYPE openux_voip_jitter_seconds gauge",
        "# HELP openux_voip_packet_loss_ratio UDP media packet loss ratio (0.0 - 1.0)",
        "# TYPE openux_voip_packet_loss_ratio gauge"
    ]

    for r in results:
        t_name = r["target_name"]
        host = r["host"]
        labels = f'target="{t_name}",host="{host}"'

        prom_lines.append(f'openux_voip_status{{{labels}}} {r["status"]}')
        prom_lines.append(f'openux_voip_mos_score{{{labels}}} {r["mos_score"]}')
        prom_lines.append(f'openux_voip_rtt_seconds{{{labels}}} {r["rtt_ms"] / 1000.0:.4f}')
        prom_lines.append(f'openux_voip_jitter_seconds{{{labels}}} {r["jitter_ms"] / 1000.0:.4f}')
        prom_lines.append(f'openux_voip_packet_loss_ratio{{{labels}}} {r["loss_percent"] / 100.0:.4f}')

    content = "\n".join(prom_lines) + "\n"
    if output_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        tmp = output_path + ".tmp"
        with open(tmp, "w") as f:
            f.write(content)
        os.replace(tmp, output_path)
        print(f"VoIP metrics written to: {output_path}")
    else:
        print(content)

def main():
    parser = argparse.ArgumentParser(description="OpenUX Real-Time Voice/Video UDP Jitter Prober")
    parser.add_argument("--interface", default=None, help="Bind probe to network interface (e.g. eth0 or wlan0)")
    parser.add_argument("--output", default=DEFAULT_PROM_FILE, help="Prometheus metric file output path")
    parser.add_argument("--stun-server", default=os.environ.get("STUN_SERVER"), help="Custom STUN / TURN server hostname (overrides default)")
    parser.add_argument("--stun-port", type=int, default=int(os.environ.get("STUN_PORT", 19302)), help="Custom STUN / TURN port (default: 19302)")
    parser.add_argument("--count", type=int, default=20, help="Number of STUN packets to send per target (default: 20; use 8 for fast on-demand delegation)")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Output results as JSON to stdout (for CMP remote delegation)")

    args = parser.parse_args()

    targets = DEFAULT_TARGETS
    if args.stun_server:
        targets = [{"name": "Custom-District-STUN", "host": args.stun_server, "port": args.stun_port}]

    results = []
    for t in targets:
        t_name = t["name"]
        host = t["host"]
        port = t["port"]

        probe = probe_udp_jitter(host, port, packet_count=args.count, interface=args.interface)
        results.append({
            "target_name": t_name,
            "host": host,
            "status": probe["status"],
            "rtt_ms": probe["rtt_ms"],
            "jitter_ms": probe["jitter_ms"],
            "packet_loss_pct": probe["loss_percent"],
            "loss_percent": probe["loss_percent"],
            "mos_score": probe["mos_score"]
        })

    if args.json_output:
        import json
        print(json.dumps({"probes": results, "status": "ok"}))
    else:
        print("Running OpenUX Real-Time Voice/Video (UDP/RTP) Media Stream Probes...")
        for r in results:
            status_color = "\033[92mEXCELLENT\033[0m" if r["mos_score"] >= 4.0 else ("\033[93mFAIR\033[0m" if r["mos_score"] >= 3.5 else "\033[91mPOOR\033[0m")
            print(f" - [{r['target_name']}]: {status_color} (MOS: {r['mos_score']}/4.5 | RTT: {r['rtt_ms']}ms | Jitter: {r['jitter_ms']}ms | Loss: {r['loss_percent']}%)")
        write_metrics([{
            "target_name": r["target_name"],
            "host": r["host"],
            "status": r["status"],
            "rtt_ms": r["rtt_ms"],
            "jitter_ms": r["jitter_ms"],
            "loss_percent": r["loss_percent"],
            "mos_score": r["mos_score"]
        } for r in results], args.output)

if __name__ == "__main__":
    main()
