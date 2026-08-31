#!/usr/bin/env python3
"""
Unit Test Suite for Network Safety Guardrails & In-Flight Circuit Breakers (sensor/safety_guardrails.py).
Tests:
  1. Instructional Hours Lockout (School Time Protection & Admin Override)
  2. Pre-Flight Congestion Checks & Automatic Aborts
  3. SoC Thermal Throttling Guardrail
  4. Parameter Ceilings & Duration Clamping
  5. In-Flight Kill Switch Watchdog (SIGKILL on Packet Drop)
"""

def verifies(req_id: str):
    def decorator(fn):
        fn.__verifies__ = req_id
        return fn
    return decorator


import os
import sys
import time
import datetime
import subprocess
import pytest
from unittest.mock import patch, MagicMock, mock_open

# Ensure sensor directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from safety_guardrails import NetworkSafetyGuardrails

# ====================================================
# 1. Guardrail 1: Instructional Hours Lockout Tests
# ====================================================

@verifies("REQ-SCH-002")
def test_guardrail_instructional_lockout_during_school():
    """Verifies that tests are blocked during Wednesday 10:30 AM school hours."""
    school_time = datetime.datetime(2026, 9, 2, 10, 30) # Wednesday 10:30 AM
    can_proceed, reason = NetworkSafetyGuardrails.check_instructional_lockout(
        allow_override=False,
        now_dt=school_time
    )
    assert can_proceed is False
    assert "BLOCKED: Instructional Hours Lockout active" in reason

def test_guardrail_instructional_approved_off_peak():
    """Verifies that tests are approved during Wednesday 07:00 PM off-peak maintenance window."""
    off_peak_time = datetime.datetime(2026, 9, 2, 19, 0) # Wednesday 07:00 PM
    can_proceed, reason = NetworkSafetyGuardrails.check_instructional_lockout(
        allow_override=False,
        now_dt=off_peak_time
    )
    assert can_proceed is True
    assert "Approved (Off-Peak / Weekend Window)" in reason

def test_guardrail_instructional_approved_weekend():
    """Verifies that tests are approved on Saturday/Sunday all day."""
    saturday_noon = datetime.datetime(2026, 9, 5, 12, 0) # Saturday 12:00 PM
    can_proceed, reason = NetworkSafetyGuardrails.check_instructional_lockout(
        allow_override=False,
        now_dt=saturday_noon
    )
    assert can_proceed is True

def test_guardrail_instructional_admin_override():
    """Verifies that explicit admin override permits on-demand tests during school hours."""
    school_time = datetime.datetime(2026, 9, 2, 10, 30)
    can_proceed, reason = NetworkSafetyGuardrails.check_instructional_lockout(
        allow_override=True,
        now_dt=school_time
    )
    assert can_proceed is True
    assert "Admin Override Token" in reason

# ====================================================
# 2. Guardrail 2: Pre-Flight Congestion Checks
# ====================================================

def test_guardrail_preflight_clean():
    """Verifies pre-flight check passes when gateway latency is low and loss is 0%."""
    mock_run = MagicMock()
    mock_run.returncode = 0

    with patch("subprocess.run", return_value=mock_run):
        can_proceed, reason, avg_rtt, loss_pct = NetworkSafetyGuardrails.check_preflight_congestion(gateway_ip="10.10.1.1")
        assert can_proceed is True
        assert loss_pct == 0.0

def test_guardrail_preflight_aborts_on_packet_loss():
    """Verifies pre-flight check aborts if ping packet loss is detected."""
    mock_fail = MagicMock()
    mock_fail.returncode = 1

    with patch("subprocess.run", return_value=mock_fail):
        can_proceed, reason, avg_rtt, loss_pct = NetworkSafetyGuardrails.check_preflight_congestion(gateway_ip="10.10.1.1")
        assert can_proceed is False
        assert loss_pct == 100.0
        assert "ABORT: Pre-flight check detected" in reason

# ====================================================
# 3. Guardrail 3: Thermal Protection
# ====================================================

def test_guardrail_thermal_safety_normal():
    """Verifies thermal check passes at normal CPU temperatures (48°C)."""
    with patch("os.path.exists", return_value=True), \
         patch("builtins.open", mock_open(read_data="48000\n")):
        is_safe, temp, reason = NetworkSafetyGuardrails.check_thermal_safety()
        assert is_safe is True
        assert temp == 48.0

def test_guardrail_thermal_throttles_at_high_temp():
    """Verifies thermal check triggers throttle when CPU exceeds 75°C."""
    with patch("os.path.exists", return_value=True), \
         patch("builtins.open", mock_open(read_data="78500\n")):
        is_safe, temp, reason = NetworkSafetyGuardrails.check_thermal_safety()
        assert is_safe is False
        assert temp == 78.5
        assert "THERMAL THROTTLE" in reason

# ====================================================
# 4. Guardrail 4: Speed Ceilings & Duration Caps
# ====================================================

def test_guardrail_clamping_ceilings():
    """Verifies requested parameters exceeding ceilings are clamped to 50 Mbps / 10s."""
    bw, dur = NetworkSafetyGuardrails.clamp_parameters(requested_mbps=500, requested_duration=60)
    assert bw == 50
    assert dur == 10

    # Normal parameters below ceiling remain unchanged
    bw_low, dur_low = NetworkSafetyGuardrails.clamp_parameters(requested_mbps=25, requested_duration=5)
    assert bw_low == 25
    assert dur_low == 5

# ====================================================
# 5. Guardrail 5: In-Flight Kill Switch Watchdog
# ====================================================

def test_guardrail_inflight_killswitch_trips_on_outage():
    """Verifies that the in-flight watchdog kills a running process if 2 consecutive pings fail."""
    mock_process = MagicMock()
    mock_process.poll.side_effect = [None, None, None, 0] # Running then exited
    mock_process.pid = 9999

    mock_ping_fail = MagicMock()
    mock_ping_fail.returncode = 1

    with patch("subprocess.run", return_value=mock_ping_fail):
        watchdog = NetworkSafetyGuardrails.start_inflight_killswitch(
            process=mock_process,
            gateway_ip="10.10.1.1",
            check_interval_sec=0.01
        )
        watchdog.join(timeout=1.0)
        assert mock_process.kill.call_count >= 1
