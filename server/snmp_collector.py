#!/usr/bin/env python3
"""
OpenUX Security Gateway & Firewall Telemetry Collector (SNMP)
Polls core network firewalls (FortiGate, Palo Alto, Cisco) for CPU, Memory,
Active Sessions, and Conserve Mode status.

Enables Grafana NOC dashboards to correlate synthetic user latency spikes
with firewall resource utilization and deep SSL inspection pressure.
"""

import os
import sys
import time
import subprocess
import argparse
from typing import Dict, Any, Optional

DEFAULT_PROM_FILE = "/var/lib/node_exporter/textfile_collector/firewall_snmp.prom"

# Standard & Enterprise MIB OIDs
FORTIGATE_OIDS = {
    "cpu": "1.3.6.1.4.1.12356.101.4.1.3.0",        # fgSysCpuUsage (0-100%)
    "memory": "1.3.6.1.4.1.12356.101.4.1.4.0",     # fgSysMemUsage (0-100%)
    "sessions": "1.3.6.1.4.1.12356.101.4.1.8.0",   # fgSysSesCount
    "session_rate": "1.3.6.1.4.1.12356.101.4.1.11.0" # fgSysSesRate
}

GENERIC_HOST_OIDS = {
    "cpu": "1.3.6.1.4.1.2021.11.11.0",             # ssCpuIdle (100 - idle = usage)
    "memory": "1.3.6.1.4.1.2021.4.6.0"             # memAvailReal
}

def snmp_get_value(host: str, community: str, oid: str, timeout_sec: int = 2) -> Optional[float]:
    """Queries an SNMP OID using snmpget command line utility."""
    cmd = [
        "snmpget",
        "-v2c",
        "-c", community,
        "-t", str(timeout_sec),
        "-Oqv",  # Quick format: value only
        host,
        oid
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec + 1)
        if res.returncode == 0:
            val_str = res.stdout.strip().replace('"', '').replace('Gauge32: ', '').replace('INTEGER: ', '').replace('Counter32: ', '')
            return float(val_str)
        return None
    except Exception:
        return None

def poll_firewall(
    host: str,
    community: str = "public",
    device_type: str = "fortigate",
    device_name: str = "core-firewall"
) -> Dict[str, Any]:
    """Polls firewall metrics and returns health status dictionary."""
    oids = FORTIGATE_OIDS if device_type.lower() == "fortigate" else GENERIC_HOST_OIDS

    cpu = snmp_get_value(host, community, oids.get("cpu", ""))
    mem = snmp_get_value(host, community, oids.get("memory", ""))
    sessions = snmp_get_value(host, community, oids.get("sessions", ""))

    # Check for conserve mode (memory > 88% on FortiGate)
    conserve_mode = 1 if (mem is not None and mem >= 88.0) else 0
    is_reachable = 1 if cpu is not None else 0

    return {
        "device_name": device_name,
        "host": host,
        "device_type": device_type,
        "is_reachable": is_reachable,
        "cpu_percent": cpu if cpu is not None else 0.0,
        "memory_percent": mem if mem is not None else 0.0,
        "active_sessions": int(sessions) if sessions is not None else 0,
        "conserve_mode": conserve_mode
    }

def write_metrics(results: Dict[str, Any], output_path: str):
    """Atomically writes Prometheus metrics for firewall utilization."""
    dev = results["device_name"]
    host = results["host"]
    dtype = results["device_type"]

    prom_lines = [
        f'# HELP openux_firewall_reachable Whether the Security Gateway responds to SNMP queries (1=Up, 0=Down)',
        f'# TYPE openux_firewall_reachable gauge',
        f'openux_firewall_reachable{{device="{dev}",host="{host}",type="{dtype}"}} {results["is_reachable"]}',

        f'# HELP openux_firewall_cpu_utilization_percent Firewall CPU usage percent',
        f'# TYPE openux_firewall_cpu_utilization_percent gauge',
        f'openux_firewall_cpu_utilization_percent{{device="{dev}",host="{host}"}} {results["cpu_percent"]}',

        f'# HELP openux_firewall_memory_utilization_percent Firewall RAM usage percent',
        f'# TYPE openux_firewall_memory_utilization_percent gauge',
        f'openux_firewall_memory_utilization_percent{{device="{dev}",host="{host}"}} {results["memory_percent"]}',

        f'# HELP openux_firewall_active_sessions Count of active concurrent firewall sessions',
        f'# TYPE openux_firewall_active_sessions gauge',
        f'openux_firewall_active_sessions{{device="{dev}",host="{host}"}} {results["active_sessions"]}',

        f'# HELP openux_firewall_conserve_mode Alert flag indicating firewall conserve mode (1=Active Conserve Mode, 0=Normal)',
        f'# TYPE openux_firewall_conserve_mode gauge',
        f'openux_firewall_conserve_mode{{device="{dev}",host="{host}"}} {results["conserve_mode"]}'
    ]

    content = "\n".join(prom_lines) + "\n"

    if output_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        tmp = output_path + ".tmp"
        with open(tmp, "w") as f:
            f.write(content)
        os.replace(tmp, output_path)
        print(f"Firewall metrics atomically written to: {output_path}")
    else:
        print(content)

def main():
    parser = argparse.ArgumentParser(description="OpenUX Security Gateway SNMP Poller")
    parser.add_argument("--host", default="192.168.1.1", help="Target firewall IP/hostname")
    parser.add_argument("--community", default="public", help="SNMP v2c read community string")
    parser.add_argument("--device-name", default="core-security-gateway", help="Descriptive device label")
    parser.add_argument("--device-type", default="fortigate", choices=["fortigate", "generic"], help="Firewall brand MIB")
    parser.add_argument("--output", default=DEFAULT_PROM_FILE, help="Path to write .prom metrics file")

    args = parser.parse_args()

    print(f"Polling Security Gateway {args.device_name} ({args.host})...")
    metrics = poll_firewall(
        host=args.host,
        community=args.community,
        device_type=args.device_type,
        device_name=args.device_name
    )

    status_str = "\033[92mONLINE\033[0m" if metrics["is_reachable"] else "\033[91mUNREACHABLE\033[0m"
    print(f"Status: {status_str} | CPU: {metrics['cpu_percent']}% | Mem: {metrics['memory_percent']}% | Sessions: {metrics['active_sessions']} | Conserve Mode: {metrics['conserve_mode']}")

    write_metrics(metrics, args.output)

if __name__ == "__main__":
    main()
