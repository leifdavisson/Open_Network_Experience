#!/usr/bin/env python3
"""
Unit Test Suite for Infrastructure & Firewall SNMP Collector (server/snmp_collector.py).
Tests:
  1. FortiGate OID polling, CPU/Memory extraction & Conserve Mode detection (>= 88%)
  2. Generic Host OID polling
  3. Reachability and failure state handling
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Ensure server path is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import snmp_collector

def test_snmp_fortigate_normal_load():
    """Verifies FortiGate SNMP parsing under normal load (<88% memory)."""
    def mock_snmp_get(host, community, oid, timeout_sec=2):
        if oid == snmp_collector.FORTIGATE_OIDS["cpu"]:
            return 24.5
        elif oid == snmp_collector.FORTIGATE_OIDS["memory"]:
            return 62.0
        elif oid == snmp_collector.FORTIGATE_OIDS["sessions"]:
            return 14500.0
        return None

    with patch("snmp_collector.snmp_get_value", side_effect=mock_snmp_get):
        res = snmp_collector.poll_firewall("10.0.0.1", "public", "fortigate", "core-fw-01")
        assert res["is_reachable"] == 1
        assert res["cpu_percent"] == 24.5
        assert res["memory_percent"] == 62.0
        assert res["conserve_mode"] == 0  # Not in conserve mode

def test_snmp_fortigate_conserve_mode_alert():
    """Verifies FortiGate Conserve Mode trigger when memory utilization >= 88%."""
    def mock_snmp_get(host, community, oid, timeout_sec=2):
        if oid == snmp_collector.FORTIGATE_OIDS["cpu"]:
            return 91.0
        elif oid == snmp_collector.FORTIGATE_OIDS["memory"]:
            return 89.5  # Conserve mode threshold breached
        elif oid == snmp_collector.FORTIGATE_OIDS["sessions"]:
            return 85000.0
        return None

    with patch("snmp_collector.snmp_get_value", side_effect=mock_snmp_get):
        res = snmp_collector.poll_firewall("10.0.0.1", "public", "fortigate", "core-fw-01")
        assert res["is_reachable"] == 1
        assert res["conserve_mode"] == 1  # Alert triggered

def test_snmp_firewall_unreachable():
    """Verifies handling when firewall does not respond to SNMP queries."""
    with patch("snmp_collector.snmp_get_value", return_value=None):
        res = snmp_collector.poll_firewall("10.0.0.99", "public", "fortigate", "core-fw-down")
        assert res["is_reachable"] == 0
        assert res["cpu_percent"] == 0.0
        assert res["conserve_mode"] == 0
