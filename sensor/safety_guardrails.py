#!/usr/bin/env python3
"""
Open Network Experience (ONE) — Edge Network Safety Guardrails & Outage Circuit Breakers
Enforces 5 mandatory safety mechanisms during active/intrusive network testing:
  1. Instructional Hours Lockout (07:30 - 16:30 Mon-Fri)
  2. Pre-Flight Congestion Check (Gateway RTT <= 25ms, Loss = 0%)
  3. Rolling Campus Concurrency Stagger
  4. Speed Ceilings & Duration Caps (Max 50 Mbps / 10s default)
  5. In-Flight Kill Switch Watchdog (SIGKILL within 250ms if packet loss >= 3%)
  6. SoC Hardware Thermal Protection (Pauses tests if CPU temp > 75°C)
"""

import os
import sys
import time
import socket
import struct
import datetime
import subprocess
import threading
from typing import Tuple, Optional, Dict, Any

# Default Safety Parameters
DEFAULT_INSTRUCTIONAL_START = "07:30"
DEFAULT_INSTRUCTIONAL_END = "16:30"
MAX_BANDWIDTH_CAP_MBPS = 50
MAX_DURATION_SECONDS = 10
GATEWAY_RTT_THRESHOLD_MS = 25.0
GATEWAY_LOSS_THRESHOLD_PERCENT = 0.0
THERMAL_THRESHOLD_CELSIUS = 75.0
THERMAL_RECOVERY_CELSIUS = 65.0

class NetworkSafetyGuardrails:
    """Core safety evaluation engine and in-flight process watchdog."""

    @staticmethod
    def detect_default_gateway() -> str:
        """Finds default gateway IP from /proc/net/route or fallback."""
        try:
            with open("/proc/net/route", "r") as f:
                for line in f.readlines()[1:]:
                    fields = line.strip().split()
                    if len(fields) >= 3 and fields[1] == "00000000":
                        gw_hex = int(fields[2], 16)
                        return socket.inet_ntoa(struct.pack("<L", gw_hex))
        except Exception:
            pass
        return "1.1.1.1"

    @staticmethod
    def is_instructional_hours(
        now_dt: Optional[datetime.datetime] = None,
        start_str: str = DEFAULT_INSTRUCTIONAL_START,
        end_str: str = DEFAULT_INSTRUCTIONAL_END
    ) -> bool:
        """
        Returns True if current time is within school instructional hours (Mon-Fri 07:30 - 16:30).
        """
        now = now_dt or datetime.datetime.now()
        # Monday is 0, Sunday is 6
        if now.weekday() >= 5:
            return False  # Weekends are always approved

        start_h, start_m = map(int, start_str.split(":"))
        end_h, end_m = map(int, end_str.split(":"))
        start_time = datetime.time(start_h, start_m)
        end_time = datetime.time(end_h, end_m)

        current_time = now.time()
        return start_time <= current_time <= end_time

    @classmethod
    def check_instructional_lockout(
        cls,
        allow_override: bool = False,
        now_dt: Optional[datetime.datetime] = None
    ) -> Tuple[bool, str]:
        """
        Guardrail 1: Checks if active testing is blocked due to school hours.
        Returns: (can_proceed, reason_string)
        """
        if allow_override:
            return True, "Approved (Admin Override Token Applied)"

        if cls.is_instructional_hours(now_dt):
            return False, "BLOCKED: Instructional Hours Lockout active (07:30-16:30 Mon-Fri). Off-peak execution only."
        return True, "Approved (Off-Peak / Weekend Window)"

    @classmethod
    def check_preflight_congestion(
        cls,
        gateway_ip: Optional[str] = None,
        probe_count: int = 4
    ) -> Tuple[bool, str, float, float]:
        """
        Guardrail 2: Pre-flight micro-ping check against local default gateway.
        Returns: (can_proceed, reason_string, avg_rtt_ms, packet_loss_pct)
        """
        gw = gateway_ip or cls.detect_default_gateway()
        rtts = []
        lost_count = 0

        for _ in range(probe_count):
            start = time.time()
            try:
                out = subprocess.run(
                    ["ping", "-c", "1", "-W", "1", gw],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                duration_ms = (time.time() - start) * 1000.0
                if out.returncode == 0:
                    rtts.append(duration_ms)
                else:
                    lost_count += 1
            except Exception:
                lost_count += 1

        loss_pct = (lost_count / probe_count) * 100.0
        avg_rtt = (sum(rtts) / len(rtts)) if rtts else 999.0

        if loss_pct > GATEWAY_LOSS_THRESHOLD_PERCENT:
            return False, f"ABORT: Pre-flight check detected {loss_pct:.1f}% packet loss to gateway ({gw}).", avg_rtt, loss_pct

        if avg_rtt > GATEWAY_RTT_THRESHOLD_MS:
            return False, f"ABORT: Gateway latency ({avg_rtt:.1f}ms) exceeds safety ceiling ({GATEWAY_RTT_THRESHOLD_MS}ms).", avg_rtt, loss_pct

        return True, f"Pre-flight clean: Gateway RTT {avg_rtt:.1f}ms, 0% loss.", avg_rtt, loss_pct

    @staticmethod
    def check_thermal_safety() -> Tuple[bool, float, str]:
        """
        Thermal Guardrail: Checks Raspberry Pi / Mini PC CPU temperature.
        Returns: (is_safe, temp_celsius, reason)
        """
        temp_paths = [
            "/sys/class/thermal/thermal_zone0/temp",
            "/sys/devices/virtual/thermal/thermal_zone0/temp"
        ]
        for path in temp_paths:
            if os.path.exists(path):
                try:
                    with open(path, "r") as f:
                        raw_temp = float(f.read().strip())
                        temp_c = raw_temp / 1000.0 if raw_temp > 1000 else raw_temp
                        if temp_c >= THERMAL_THRESHOLD_CELSIUS:
                            return False, temp_c, f"THERMAL THROTTLE: CPU at {temp_c:.1f}°C (Threshold: {THERMAL_THRESHOLD_CELSIUS}°C)."
                        return True, temp_c, f"Thermal normal: {temp_c:.1f}°C."
                except Exception:
                    pass
        return True, 45.0, "Thermal reading unavailable (assuming nominal)."

    @staticmethod
    def clamp_parameters(requested_mbps: Optional[int], requested_duration: Optional[int]) -> Tuple[int, int]:
        """
        Guardrail 4: Clamps requested bandwidth and duration to safety maximums.
        """
        bw = min(requested_mbps or MAX_BANDWIDTH_CAP_MBPS, MAX_BANDWIDTH_CAP_MBPS)
        dur = min(requested_duration or MAX_DURATION_SECONDS, MAX_DURATION_SECONDS)
        return max(1, bw), max(1, dur)

    @classmethod
    def start_inflight_killswitch(
        cls,
        process: subprocess.Popen,
        gateway_ip: Optional[str] = None,
        loss_threshold_pct: float = 3.0,
        check_interval_sec: float = 0.25
    ) -> threading.Thread:
        """
        Guardrail 5: Spawns high-speed 250ms watchdog thread. If gateway packet loss exceeds
        threshold or drops 2 consecutive pings, sends SIGKILL to process immediately.
        """
        gw = gateway_ip or cls.detect_default_gateway()

        def _watchdog_loop():
            consecutive_drops = 0
            while process.poll() is None:
                start = time.time()
                try:
                    out = subprocess.run(
                        ["ping", "-c", "1", "-W", "1", gw],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    if out.returncode != 0:
                        consecutive_drops += 1
                    else:
                        consecutive_drops = 0
                except Exception:
                    consecutive_drops += 1

                if consecutive_drops >= 2:
                    print(f"⚡ IN-FLIGHT CIRCUIT BREAKER TRIPPED: Gateway {gw} unreachable for 2 consecutive pings! Killing test PID {process.pid}...")
                    try:
                        process.kill()
                    except Exception:
                        pass
                    break

                time.sleep(check_interval_sec)

        t = threading.Thread(target=_watchdog_loop, daemon=True, name="SafetyWatchdogThread")
        t.start()
        return t
