#!/usr/bin/env python3
"""
CAASPP & ELPAC State Testing Readiness Checker
Validates network readiness, Cambium Assessment TDS/TIDE endpoints, ETS TOMS,
Smarter Balanced SSO, and verifies SSL Inspection bypass (certificate pinning).

California Assessment of Student Performance and Progress (CAASPP) requirements:
  - Cambium TDS / Student Testing Interface reachable without content filter blocks
  - SSL Decryption / MITM inspection MUST be bypassed for Cambium/ETS/SmarterBalanced
    (Secure Browser fails if firewall inspection certs are injected)
  - DNS resolution and TLS handshake latency within operational thresholds (< 1.5s)
"""

import os
import sys
import time
import socket
import ssl
import urllib.request
import urllib.error
from typing import Dict, Any, List, Tuple

DEFAULT_PROM_FILE = "/var/lib/node_exporter/textfile_collector/caaspp.prom"

# Official CAASPP / ELPAC Essential Network Endpoints
CAASPP_ENDPOINTS = [
    {
        "id": "student_testing_interface",
        "name": "Cambium Student Testing Interface",
        "url": "https://ca.cambiumtds.com/student",
        "host": "ca.cambiumtds.com",
        "port": 443,
        "critical": True
    },
    {
        "id": "test_admin_interface",
        "name": "Cambium Test Administrator Interface",
        "url": "https://ca.cambiumtds.com/testadmin",
        "host": "ca.cambiumtds.com",
        "port": 443,
        "critical": True
    },
    {
        "id": "tide_completion_status",
        "name": "Cambium TIDE & Completion Status",
        "url": "https://ca.tide.cambiumast.com",
        "host": "ca.tide.cambiumast.com",
        "port": 443,
        "critical": True
    },
    {
        "id": "interim_assessment_viewing",
        "name": "Interim Assessment Viewing System",
        "url": "https://capt.cambiumtds.com/student/?a=ResponseEntry",
        "host": "capt.cambiumtds.com",
        "port": 443,
        "critical": False
    },
    {
        "id": "ets_toms",
        "name": "ETS Test Operations Management System (TOMS)",
        "url": "https://mytoms.ets.org",
        "host": "mytoms.ets.org",
        "port": 443,
        "critical": True
    },
    {
        "id": "smarter_balanced_sso",
        "name": "Smarter Balanced CERS / SSO",
        "url": "https://login.smarterbalanced.org",
        "host": "login.smarterbalanced.org",
        "port": 443,
        "critical": True
    },
    {
        "id": "trcs_readiness_checker",
        "name": "Technology Readiness Checker for Students (TRCS)",
        "url": "https://trcs.ets.org",
        "host": "trcs.ets.org",
        "port": 443,
        "critical": False
    },
    {
        "id": "cambium_netdiag",
        "name": "Cambium Network Diagnostics Tool",
        "url": "https://netdiag.cambiumtds.com",
        "host": "netdiag.cambiumtds.com",
        "port": 443,
        "critical": False
    }
]

# Common firewall SSL Inspection / MITM Issuer keywords
KNOWN_MITM_ISSUERS = [
    "fortinet", "fortigate", "palo alto", "pan-os", "zscaler",
    "sophos", "sonicwall", "barracuda", "cisco umbrella",
    "lightspeed", "securly", "smoothwall", "untangle", "checkpoint"
]

def check_ssl_inspection_bypass(host: str, port: int = 443) -> Tuple[bool, str]:
    """
    Connects via TLS and checks certificate issuer.
    Returns: (is_bypassed, issuer_summary)
    True = Genuine CA certificate (SSL inspection bypassed - Compliant for CAASPP Secure Browser)
    False = Firewall inspection certificate detected (Will cause Secure Browser to throw error)
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

                # Check for firewall SSL interception certificates
                lower_issuer = issuer_str.lower()
                for keyword in KNOWN_MITM_ISSUERS:
                    if keyword in lower_issuer:
                        return False, f"MITM Detected: {issuer_str}"

                return True, f"Bypassed / Genuine CA: {issuer_str}"
    except ssl.SSLError as e:
        return False, f"SSL Error: {e}"
    except Exception as e:
        return False, f"Connection Error: {e}"

def check_http_endpoint(target: Dict[str, Any]) -> Tuple[bool, float, int, str]:
    """
    Measures HTTP GET latency and status code.
    Returns: (is_ok, latency_seconds, status_code, reason)
    """
    url = target["url"]
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CAASPP-Readiness-Probe/1.0",
            "Cache-Control": "no-cache"
        }
    )
    start_time = time.time()
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            latency = round(time.time() - start_time, 4)
            return (response.status in (200, 301, 302, 307)), latency, response.status, "OK"
    except urllib.error.HTTPError as e:
        latency = round(time.time() - start_time, 4)
        # Some endpoints return 401/403 when accessing root without session, which still proves network reachability
        is_ok = e.code in (401, 403)
        return is_ok, latency, e.code, f"HTTP {e.code}"
    except urllib.error.URLError as e:
        latency = round(time.time() - start_time, 4)
        return False, latency, 0, f"Network/DNS Error: {e.reason}"
    except Exception as e:
        latency = round(time.time() - start_time, 4)
        return False, latency, 0, f"Timeout/Error: {str(e)}"

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
    output_file = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PROM_FILE

    prom_lines = [
        "# HELP caaspp_endpoint_status CAASPP/ELPAC testing endpoint reachability. 1=Reachable/OK, 0=Failed",
        "# TYPE caaspp_endpoint_status gauge",
        "# HELP caaspp_endpoint_latency_seconds HTTP response latency to CAASPP testing endpoints in seconds",
        "# TYPE caaspp_endpoint_latency_seconds gauge",
        "# HELP caaspp_ssl_inspection_bypassed Whether SSL inspection is properly bypassed for CAASPP (1=Bypassed/Compliant, 0=MITM Intercepted/Invalid)",
        "# TYPE caaspp_ssl_inspection_bypassed gauge",
        "# HELP caaspp_readiness_overall Overall site readiness status for CAASPP online testing (1=Ready, 0=Degraded/Blocked)",
        "# TYPE caaspp_readiness_overall gauge"
    ]

    print("Running CAASPP & ELPAC State Testing Readiness Validation...")
    all_critical_ok = True

    for target in CAASPP_ENDPOINTS:
        # 1. Check HTTP reachability
        is_ok, latency, status_code, reason = check_http_endpoint(target)

        # 2. Check SSL Inspection Bypass (only need to check each distinct host once)
        is_bypassed, issuer_info = check_ssl_inspection_bypass(target["host"], target["port"])

        # Determine pass/fail
        if target["critical"] and (not is_ok or not is_bypassed):
            all_critical_ok = False

        endpoint_val = 1 if is_ok else 0
        ssl_val = 1 if is_bypassed else 0

        prom_lines.append(
            f'caaspp_endpoint_status{{id="{target["id"]}",host="{target["host"]}",name="{target["name"]}",critical="{str(target["critical"]).lower()}"}} {endpoint_val}'
        )
        prom_lines.append(
            f'caaspp_endpoint_latency_seconds{{id="{target["id"]}",host="{target["host"]}"}} {latency}'
        )
        prom_lines.append(
            f'caaspp_ssl_inspection_bypassed{{id="{target["id"]}",host="{target["host"]}"}} {ssl_val}'
        )

        status_color = "\033[92mPASS\033[0m" if (is_ok and is_bypassed) else "\033[91mFAIL\033[0m"
        ssl_color = "\033[92mBYPASSED\033[0m" if is_bypassed else "\033[91mINSPECTED (MITM)\033[0m"
        print(f" - [{target['name']}]: {status_color} ({latency*1000:.1f}ms) | SSL Inspection: {ssl_color} | {issuer_info}")

    overall_val = 1 if all_critical_ok else 0
    overall_str = "\033[92mREADY FOR CAASPP TESTING\033[0m" if all_critical_ok else "\033[91mNOT READY — CRITICAL TEST ENDPOINTS DEGRADED\033[0m"
    print(f"\nOverall Site Status: {overall_str}\n")

    # If critical testing endpoints failed, automatically slice and preserve an incident PCAP snapshot
    if overall_val == 0:
        print("[AUTO-TRIGGER] Critical state testing degradation detected. Slicing incident PCAP snapshot...")
        try:
            pcap_script = "/usr/local/bin/pcap_trigger.py"
            if not os.path.exists(pcap_script):
                pcap_script = os.path.abspath(os.path.join(os.path.dirname(__file__), "pcap_trigger.py"))
            if os.path.exists(pcap_script):
                import subprocess
                subprocess.Popen(["python3", pcap_script, "--trigger", "caaspp_failure"])
        except Exception:
            pass

    write_metrics(prom_lines, output_file)

if __name__ == "__main__":
    main()
