#!/usr/bin/env python3
"""
OpenUX Multi-Resolver DNS Health & Benchmark Prober
Discovers all local DHCP/configured DNS servers from /etc/resolv.conf and benchmarks
them against major public DNS providers (Cloudflare, Google, Quad9, OpenDNS).

Validates:
  - Internal district namespace resolution (e.g. domain controllers, local portals)
  - Public internet domain resolution
  - Query latency (ms) per resolver
  - Response codes (NOERROR, SERVFAIL, NXDOMAIN, TIMEOUT)
  - Detects if an internal DNS forwarder or ISP upstream is broken or slow

Emits Prometheus metrics for instant visualization in Grafana.
"""

import os
import sys
import time
import socket
import argparse
from typing import List, Dict, Any, Tuple, Optional

DEFAULT_PROM_FILE = "/var/lib/node_exporter/textfile_collector/dns_resolvers.prom"

# Public Recursive Resolvers for Baseline Benchmarking
PUBLIC_DNS_PROVIDERS = [
    {"name": "Cloudflare-Primary", "ip": "1.1.1.1", "is_public": True},
    {"name": "Google-Primary", "ip": "8.8.8.8", "is_public": True},
    {"name": "Quad9-Secure", "ip": "9.9.9.9", "is_public": True},
    {"name": "OpenDNS-Home", "ip": "208.67.222.222", "is_public": True}
]

# Critical educational/enterprise domains to benchmark
DEFAULT_BENCHMARK_DOMAINS = [
    {"domain": "google.com", "type": "public_web"},
    {"domain": "microsoft.com", "type": "public_web"},
    {"domain": "caaspp-elpac.org", "type": "testing_portal"},
    {"domain": "canvas.net", "type": "lms"}
]

def discover_local_resolvers() -> List[Dict[str, Any]]:
    """Parses /etc/resolv.conf to find active local/DHCP DNS servers."""
    resolvers: List[Dict[str, Any]] = []
    if os.path.exists("/etc/resolv.conf"):
        try:
            with open("/etc/resolv.conf", "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("nameserver"):
                        parts = line.split()
                        if len(parts) >= 2:
                            ip = parts[1]
                            # Avoid duplicate entries
                            if not any(r["ip"] == ip for r in resolvers):
                                resolvers.append({
                                    "name": f"Local-DNS ({ip})",
                                    "ip": ip,
                                    "is_public": False
                                })
        except Exception:
            pass
    if not resolvers:
        resolvers.append({"name": "System-Default", "ip": "127.0.0.53", "is_public": False})
    return resolvers

def build_dns_query(domain: str, query_type: int = 1) -> bytes:
    """Builds a raw RFC 1035 UDP DNS query packet (Type 1 = A Record)."""
    import random
    tx_id = random.randint(0, 65535)
    header = tx_id.to_bytes(2, byteorder="big") + b"\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00"

    question = b""
    for part in domain.split("."):
        question += len(part).to_bytes(1, byteorder="big") + part.encode("utf-8")
    question += b"\x00" + query_type.to_bytes(2, byteorder="big") + b"\x00\x01" # IN Class

    return header + question

def parse_dns_response(response: bytes) -> Tuple[int, str]:
    """Parses DNS header for RCODE (0=NOERROR, 2=SERVFAIL, 3=NXDOMAIN, etc.)."""
    if len(response) < 4:
        return -1, "MALFORMED"
    flags = int.from_bytes(response[2:4], byteorder="big")
    rcode = flags & 0x000F

    rcode_map = {
        0: "NOERROR",
        1: "FORMERR",
        2: "SERVFAIL",
        3: "NXDOMAIN",
        4: "NOTIMP",
        5: "REFUSED"
    }
    return rcode, rcode_map.get(rcode, f"RCODE_{rcode}")

def probe_dns_server(
    server_ip: str,
    domain: str,
    timeout_sec: float = 2.0,
    interface: Optional[str] = None
) -> Dict[str, Any]:
    """
    Sends raw UDP DNS query to specific nameserver IP and measures exact response latency.
    """
    query = build_dns_query(domain)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout_sec)

    if interface and hasattr(socket, "SO_BINDTODEVICE"):
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, interface.encode())
        except Exception:
            pass

    start = time.time()
    try:
        sock.sendto(query, (server_ip, 53))
        resp, _ = sock.recvfrom(4096)
        latency = time.time() - start
        rcode, rcode_str = parse_dns_response(resp)
        is_success = 1 if rcode == 0 else 0
        sock.close()
        return {
            "status": is_success,
            "latency_seconds": latency,
            "rcode": rcode,
            "rcode_str": rcode_str
        }
    except socket.timeout:
        sock.close()
        return {"status": 0, "latency_seconds": timeout_sec, "rcode": -1, "rcode_str": "TIMEOUT"}
    except Exception as e:
        sock.close()
        return {"status": 0, "latency_seconds": time.time() - start, "rcode": -2, "rcode_str": f"ERROR_{e}"}

def run_multi_resolver_probes(interface: Optional[str] = None) -> List[Dict[str, Any]]:
    """Runs DNS resolution benchmark across local and public providers."""
    local_resolvers = discover_local_resolvers()
    all_resolvers = local_resolvers + PUBLIC_DNS_PROVIDERS
    results = []

    print("Running OpenUX Multi-Resolver DNS Health Probes...")
    for res in all_resolvers:
        r_name = res["name"]
        r_ip = res["ip"]
        is_pub = "Public" if res["is_public"] else "Local/DHCP"

        for dom in DEFAULT_BENCHMARK_DOMAINS:
            domain_name = dom["domain"]
            probe = probe_dns_server(r_ip, domain_name, timeout_sec=2.0, interface=interface)

            status_color = "\033[92mOK\033[0m" if probe["status"] == 1 else "\033[91mFAIL\033[0m"
            print(f" - [{is_pub}] {r_name} -> {domain_name}: {status_color} ({probe['latency_seconds']*1000:.1f}ms, {probe['rcode_str']})")

            results.append({
                "resolver_name": r_name,
                "resolver_ip": r_ip,
                "is_public": 1 if res["is_public"] else 0,
                "domain": domain_name,
                "status": probe["status"],
                "latency_seconds": probe["latency_seconds"],
                "rcode": probe["rcode"],
                "rcode_str": probe["rcode_str"]
            })

    return results

def write_metrics(results: List[Dict[str, Any]], output_path: str):
    """Atomically writes Prometheus metrics for all tested DNS resolvers."""
    prom_lines = [
        "# HELP openux_dns_resolver_status DNS resolution status (1=NOERROR/Success, 0=Failed/Timeout/SERVFAIL)",
        "# TYPE openux_dns_resolver_status gauge",
        "# HELP openux_dns_resolver_latency_seconds DNS query response duration in seconds",
        "# TYPE openux_dns_resolver_latency_seconds gauge",
        "# HELP openux_dns_resolver_rcode DNS numeric response code (0=NOERROR, 3=NXDOMAIN, -1=TIMEOUT)",
        "# TYPE openux_dns_resolver_rcode gauge"
    ]

    for r in results:
        labels = f'resolver="{r["resolver_name"]}",ip="{r["resolver_ip"]}",domain="{r["domain"]}",public="{r["is_public"]}"'
        prom_lines.append(f'openux_dns_resolver_status{{{labels}}} {r["status"]}')
        prom_lines.append(f'openux_dns_resolver_latency_seconds{{{labels}}} {r["latency_seconds"]:.4f}')
        prom_lines.append(f'openux_dns_resolver_rcode{{{labels}}} {r["rcode"]}')

    content = "\n".join(prom_lines) + "\n"
    if output_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        tmp = output_path + ".tmp"
        with open(tmp, "w") as f:
            f.write(content)
        os.replace(tmp, output_path)
        print(f"DNS metrics written to: {output_path}")
    else:
        print(content)

def main():
    parser = argparse.ArgumentParser(description="OpenUX Multi-Resolver DNS Health Prober")
    parser.add_argument("--interface", default=None, help="Bind query to network interface (e.g. eth0 or wlan0)")
    parser.add_argument("--output", default=DEFAULT_PROM_FILE, help="Prometheus metric output path")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Output results as JSON to stdout (for CMP remote delegation)")

    args = parser.parse_args()

    if args.json_output:
        import json
        # Suppress print output from run_multi_resolver_probes by redirecting stdout temporarily
        import io
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            results = run_multi_resolver_probes(interface=args.interface)
        finally:
            sys.stdout = old_stdout

        # Aggregate: one entry per resolver (take best domain result)
        seen = {}
        for r in results:
            key = r["resolver_ip"]
            lat_ms = r["latency_seconds"] * 1000
            if key not in seen or (r["status"] == 1 and seen[key]["status"] != "ok"):
                seen[key] = {
                    "name": r["resolver_name"],
                    "ip": r["resolver_ip"],
                    "is_public": bool(r["is_public"]),
                    "status": "ok" if r["status"] == 1 else ("timeout" if r["rcode_str"] == "TIMEOUT" else "error"),
                    "latency_ms": round(lat_ms, 2),
                    "rcode": r["rcode_str"]
                }
        print(json.dumps({"resolvers": list(seen.values()), "status": "ok"}))
    else:
        results = run_multi_resolver_probes(interface=args.interface)
        write_metrics(results, args.output)

if __name__ == "__main__":
    main()
