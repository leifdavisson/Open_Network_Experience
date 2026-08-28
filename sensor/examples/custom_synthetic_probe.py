#!/usr/bin/env python3
"""
OpenUX Custom Synthetic Probe Template
Demonstrates how to build and deploy custom application probes for school/enterprise apps
(e.g., Canvas LMS, Student Information Systems, Print Servers, SIP Gateways).

How it works:
  1. Executes network probes (DNS, TCP Handshake, HTTP GET, Content Validation).
  2. Measures latency and success/failure status.
  3. Atomically writes metrics to Prometheus textfile collector path.
  4. Automatically scraped by Node Exporter and graphed in Grafana.
"""

import os
import sys
import time
import socket
import urllib.request
import urllib.error
from typing import Dict, Any, List, Tuple

# Path where Node Exporter reads custom metrics (.prom files)
DEFAULT_METRICS_PATH = "/var/lib/node_exporter/textfile_collector/custom_app.prom"

# Define your custom application targets here
CUSTOM_TARGETS = [
    {
        "id": "lms_portal",
        "name": "District Learning Management System",
        "url": "https://canvas.district.edu/login",
        "expected_status": 200,
        "required_string": None,  # Optional string that must appear in response body
        "timeout_seconds": 5
    },
    {
        "id": "sis_portal",
        "name": "Student Information System (SIS)",
        "url": "https://sis.district.edu",
        "expected_status": 200,
        "required_string": None,
        "timeout_seconds": 5
    }
]

def probe_http_target(target: Dict[str, Any]) -> Tuple[int, float, int, str]:
    """
    Executes an HTTP synthetic probe.
    Returns: (status_flag [1=OK, 0=FAIL], response_time_seconds, http_status_code, error_message)
    """
    url = target["url"]
    timeout = target.get("timeout_seconds", 5)
    expected_status = target.get("expected_status", 200)
    required_string = target.get("required_string")

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "OpenUX-Custom-Probe/1.0",
            "Cache-Control": "no-cache"
        }
    )

    start_time = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            latency = round(time.time() - start_time, 4)
            status_code = response.status

            if status_code != expected_status:
                return 0, latency, status_code, f"Unexpected HTTP status {status_code}"

            if required_string:
                body = response.read().decode("utf-8", errors="ignore")
                if required_string not in body:
                    return 0, latency, status_code, f"Required content '{required_string}' missing"

            return 1, latency, status_code, "OK"
    except urllib.error.HTTPError as e:
        latency = round(time.time() - start_time, 4)
        return 0, latency, e.code, f"HTTP Error {e.code}"
    except urllib.error.URLError as e:
        latency = round(time.time() - start_time, 4)
        return 0, latency, 0, f"Network/DNS Error: {e.reason}"
    except Exception as e:
        latency = round(time.time() - start_time, 4)
        return 0, latency, 0, f"Error: {str(e)}"

def write_metrics_atomically(prom_lines: List[str], output_path: str):
    """Writes metrics to a .tmp file then renames to prevent partial scrape reads."""
    content = "\n".join(prom_lines) + "\n"
    if output_path:
        dirname = os.path.dirname(output_path)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        tmp_path = output_path + ".tmp"
        with open(tmp_path, "w") as f:
            f.write(content)
        os.replace(tmp_path, output_path)
        print(f"Metrics atomically written to: {output_path}")
    else:
        print(content)

def main():
    output_file = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_METRICS_PATH

    prom_lines = [
        "# HELP custom_app_status Health status of custom internal application (1=Healthy/OK, 0=Degraded/Down)",
        "# TYPE custom_app_status gauge",
        "# HELP custom_app_response_seconds Response latency in seconds",
        "# TYPE custom_app_response_seconds gauge",
        "# HELP custom_app_http_code HTTP response status code",
        "# TYPE custom_app_http_code gauge"
    ]

    print("Running OpenUX Custom Synthetic Application Probes...")

    for target in CUSTOM_TARGETS:
        status_flag, latency, http_code, message = probe_http_target(target)
        t_id = target["id"]
        t_name = target["name"]

        prom_lines.append(f'custom_app_status{{id="{t_id}",name="{t_name}"}} {status_flag}')
        prom_lines.append(f'custom_app_response_seconds{{id="{t_id}",name="{t_name}"}} {latency}')
        prom_lines.append(f'custom_app_http_code{{id="{t_id}",name="{t_name}"}} {http_code}')

        color = "\033[92mOK\033[0m" if status_flag == 1 else "\033[91mFAILED\033[0m"
        print(f" - [{t_name}]: {color} ({latency*1000:.1f}ms, HTTP {http_code}) -> {message}")

    write_metrics_atomically(prom_lines, output_file)

if __name__ == "__main__":
    main()
