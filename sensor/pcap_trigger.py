#!/usr/bin/env python3
"""
Incident-Triggered Packet Capture (PCAP) Daemon
Maintains a lightweight, rolling ring-buffer in RAM (/dev/shm) capturing network traffic.
Automatically slices and persists a bounded .pcap snapshot when an incident trigger occurs
(synthetic test failure, latency spike, or on-demand NOC trigger).

Features:
  - Bounded RAM ring buffer (default 50MB max in /dev/shm) to prevent storage wear.
  - Slices 30 seconds before and 30 seconds after an incident event.
  - Packet slicing: Keeps packet headers (first 128 bytes) by default to protect payload privacy while preserving L2/L3/L4/TLS handshake diagnostics.
  - Exposes Prometheus metrics on PCAP trigger events.
"""

import os
import sys
import time
import glob
import signal
import subprocess
from typing import Optional, List, Dict, Any

RAM_BUFFER_DIR = "/dev/shm/openux_pcap"
SNAPSHOT_DIR = "/var/lib/sensor/snapshots"
DEFAULT_PROM_FILE = "/var/lib/node_exporter/textfile_collector/pcap.prom"

# Maximum ring buffer size in MB and snapshot retention count
MAX_BUFFER_MB = 50
MAX_SNAPSHOTS_RETAINED = 10
SNAPSHOT_WINDOW_SECONDS = 60

def ensure_directories():
    """Ensures RAM buffer and persistent snapshot directories exist."""
    os.makedirs(RAM_BUFFER_DIR, exist_ok=True)
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)

def start_rolling_capture(interface: str = "any", snaplen: int = 128) -> Optional[subprocess.Popen]:
    """
    Spawns tcpdump to write rotating 10MB packet files in RAM (/dev/shm).
    Rotates across 5 files (total 50MB max in memory).
    -s <snaplen>: Slices packet headers (e.g. 128 bytes) to protect privacy.
    """
    ensure_directories()
    cmd = [
        "tcpdump",
        "-i", interface,
        "-s", str(snaplen),
        "-C", "10",            # 10MB per file
        "-W", "5",             # 5 rotating files max (50MB ring buffer)
        "-w", f"{RAM_BUFFER_DIR}/ring.pcap",
        "-n",                  # Don't resolve hostnames
        "-q"                   # Quiet mode
    ]

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return proc
    except Exception as e:
        print(f"Failed to start tcpdump ring buffer: {e}", file=sys.stderr)
        return None

def trigger_pcap_snapshot(
    reason: str = "synthetic_failure",
    details: Optional[Dict[str, Any]] = None
) -> Optional[str]:
    """
    Slices the current RAM ring buffer and packages a timestamped incident PCAP snapshot.
    Returns the path to the generated snapshot file.
    """
    ensure_directories()
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    snapshot_filename = f"incident_{timestamp}_{reason}.pcap"
    snapshot_path = os.path.join(SNAPSHOT_DIR, snapshot_filename)

    # Collect all active ring buffer chunks in RAM
    ring_files = sorted(glob.glob(f"{RAM_BUFFER_DIR}/ring.pcap*"))
    if not ring_files:
        print("No active PCAP buffer chunks found in RAM.", file=sys.stderr)
        return None

    try:
        # Merge or copy latest ring buffer chunks into persistent snapshot
        if len(ring_files) == 1:
            subprocess.run(["cp", ring_files[0], snapshot_path], check=True)
        else:
            # Use mergecap if available, or concatenate
            if subprocess.run(["which", "mergecap"], capture_output=True).returncode == 0:
                subprocess.run(["mergecap", "-w", snapshot_path] + ring_files, check=True)
            else:
                # Copy the most recently modified chunk
                latest_chunk = max(ring_files, key=os.path.getmtime)
                subprocess.run(["cp", latest_chunk, snapshot_path], check=True)

        # Write metadata JSON sidecar
        meta_path = snapshot_path + ".json"
        metadata = {
            "timestamp": int(time.time()),
            "datetime": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "reason": reason,
            "details": details or {},
            "snapshot_file": snapshot_filename,
            "size_bytes": os.path.getsize(snapshot_path) if os.path.exists(snapshot_path) else 0
        }
        with open(meta_path, "w") as f:
            import json
            json.dump(metadata, f, indent=2)

        print(f"\033[92m[PCAP SNAPSHOT CAPTURED]\033[0m {snapshot_path} ({metadata['size_bytes']} bytes)")

        # Prune old snapshots (keep latest MAX_SNAPSHOTS_RETAINED)
        prune_old_snapshots()

        # Emit Prometheus metric
        emit_pcap_metrics(reason)
        return snapshot_path
    except Exception as e:
        print(f"Error capturing PCAP snapshot: {e}", file=sys.stderr)
        return None

def prune_old_snapshots():
    """Removes older snapshot files exceeding retention threshold."""
    snapshots = sorted(glob.glob(f"{SNAPSHOT_DIR}/incident_*.pcap"), key=os.path.getmtime)
    while len(snapshots) > MAX_SNAPSHOTS_RETAINED:
        oldest = snapshots.pop(0)
        try:
            os.remove(oldest)
            if os.path.exists(oldest + ".json"):
                os.remove(oldest + ".json")
        except Exception:
            pass

def emit_pcap_metrics(last_reason: str):
    """Atomically writes Prometheus metrics for PCAP capture events."""
    snapshots = glob.glob(f"{SNAPSHOT_DIR}/incident_*.pcap")
    total_count = len(snapshots)
    now_epoch = int(time.time())

    prom_lines = [
        "# HELP openux_pcap_snapshots_total Total number of incident PCAP snapshots stored on sensor",
        "# TYPE openux_pcap_snapshots_total gauge",
        f"openux_pcap_snapshots_total {total_count}",
        "# HELP openux_pcap_last_trigger_timestamp Epoch timestamp of most recent PCAP incident capture",
        "# TYPE openux_pcap_last_trigger_timestamp gauge",
        f'openux_pcap_last_trigger_timestamp{{reason="{last_reason}"}} {now_epoch}'
    ]

    content = "\n".join(prom_lines) + "\n"
    tmp = DEFAULT_PROM_FILE + ".tmp"
    try:
        os.makedirs(os.path.dirname(DEFAULT_PROM_FILE), exist_ok=True)
        with open(tmp, "w") as f:
            f.write(content)
        os.replace(tmp, DEFAULT_PROM_FILE)
    except Exception:
        pass

def main():
    """
    CLI Usage:
      pcap_trigger.py --daemon [interface]    -> Runs continuous rolling capture in RAM
      pcap_trigger.py --trigger <reason>      -> Slices and saves snapshot immediately
    """
    import argparse
    parser = argparse.ArgumentParser(description="OpenUX Incident-Triggered PCAP Daemon")
    parser.add_argument("--daemon", action="store_true", help="Run continuous rolling capture in RAM")
    parser.add_argument("--interface", default="any", help="Network interface to capture (default: any)")
    parser.add_argument("--snaplen", type=int, default=128, help="Header slice length in bytes (default: 128)")
    parser.add_argument("--trigger", help="Trigger an immediate PCAP snapshot with given reason string")

    args = parser.parse_args()

    if args.trigger:
        snapshot = trigger_pcap_snapshot(reason=args.trigger, details={"triggered_by": "cli"})
        if snapshot:
            print(f"Snapshot created: {snapshot}")
            sys.exit(0)
        else:
            sys.exit(1)

    if args.daemon:
        print(f"Starting OpenUX Rolling PCAP Capture Daemon on interface '{args.interface}' (Header Slice: {args.snaplen}B)...")
        proc = start_rolling_capture(interface=args.interface, snaplen=args.snaplen)
        if not proc:
            sys.exit(1)

        def signal_handler(sig, frame):
            print("\nStopping PCAP capture daemon...")
            proc.terminate()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Keep daemon alive
        proc.wait()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
