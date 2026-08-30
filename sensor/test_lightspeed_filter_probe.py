#!/usr/bin/env python3
"""
Unit Test Suite for Lightspeed Systems Filter & Classroom Synthetic Prober (sensor/lightspeed_filter_probe.py).
Tests:
  1. Lightspeed Endpoints Matrix Registration (Control Plane, SmartAgent & Classroom)
  2. TCP SYN Handshake & Response Latency Benchmarks
  3. Certificate Pinning & SSL Decryption MITM Bypass Detection
  4. SmartShield Anycast DNS UDP 53 Query Engine
"""

import os
import sys
import socket
import pytest
from unittest.mock import patch, MagicMock

# Ensure sensor directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import lightspeed_filter_probe

# ====================================================
# 1. Endpoints & TCP Connectivity Tests
# ====================================================

def test_lightspeed_endpoints_matrix_populated():
    """Verifies all standard Lightspeed Filter, SmartAgent, and Classroom endpoints are registered."""
    service_ids = [s["id"] for s in lightspeed_filter_probe.LIGHTSPEED_ENDPOINTS]
    assert "ls_relay_school" in service_ids
    assert "ls_admin_portal" in service_ids
    assert "ls_rules_engine" in service_ids
    assert "ls_smartagent_gateway" in service_ids
    assert "ls_production_relay" in service_ids
    assert "ls_configcat_cdn" in service_ids
    assert "ls_classroom_portal" in service_ids
    assert "ls_realtime_ably" in service_ids

def test_lightspeed_tcp_endpoint_success():
    """Verifies TCP SYN connection succeeds and measures latency."""
    with patch("socket.gethostbyname", return_value="104.18.20.10"), \
         patch("socket.create_connection", MagicMock()):
        is_ok, rtt_ms, msg = lightspeed_filter_probe.check_tcp_endpoint("relay.school", 443)
        assert is_ok is True
        assert rtt_ms >= 0.0
        assert "Connected to 104.18.20.10:443" in msg

def test_lightspeed_tcp_endpoint_dns_failure():
    """Verifies handling when DNS resolution fails."""
    with patch("socket.gethostbyname", side_effect=socket.gaierror("Name resolution failed")):
        is_ok, rtt_ms, msg = lightspeed_filter_probe.check_tcp_endpoint("nonexistent.relay.school", 443)
        assert is_ok is False
        assert rtt_ms == 0.0
        assert "DNS Resolution Error" in msg

# ====================================================
# 2. SSL Inspection Bypass Tests
# ====================================================

def test_lightspeed_ssl_bypass_genuine_ca():
    """Verifies genuine Cloudflare / DigiCert CA passes SSL inspection check."""
    mock_cert = {
        'issuer': [
            (('countryName', 'US'),),
            (('organizationName', 'Cloudflare, Inc.'),),
            (('commonName', 'Cloudflare Inc ECC CA-3'),)
        ]
    }
    mock_ssock = MagicMock()
    mock_ssock.getpeercert.return_value = mock_cert
    mock_ssock.__enter__.return_value = mock_ssock

    with patch("socket.create_connection"), \
         patch("ssl.create_default_context") as mock_ctx:
        mock_ctx.return_value.wrap_socket.return_value = mock_ssock
        is_bypassed, summary = lightspeed_filter_probe.check_ssl_inspection_bypass("relay.school", 443)
        assert is_bypassed is True
        assert "Genuine CA" in summary

def test_lightspeed_ssl_bypass_mitm_firewall_detected():
    """Verifies firewall MITM decryption proxy on Lightspeed is flagged."""
    mock_cert = {
        'issuer': [
            (('countryName', 'US'),),
            (('organizationName', 'Palo Alto Networks'),),
            (('commonName', 'PAN-OS Decryption CA'),)
        ]
    }
    mock_ssock = MagicMock()
    mock_ssock.getpeercert.return_value = mock_cert
    mock_ssock.__enter__.return_value = mock_ssock

    with patch("socket.create_connection"), \
         patch("ssl.create_default_context") as mock_ctx:
        mock_ctx.return_value.wrap_socket.return_value = mock_ssock
        is_bypassed, summary = lightspeed_filter_probe.check_ssl_inspection_bypass("agent.lightspeedsystems.app", 443)
        assert is_bypassed is False
        assert "MITM Inspection Detected" in summary

# ====================================================
# 3. SmartShield DNS Tests
# ====================================================

def test_smartshield_dns_probe_success():
    """Verifies SmartShield DNS query over UDP 53 returns valid response."""
    mock_sock = MagicMock()
    mock_sock.recvfrom.return_value = (b"\xaa\xaa\x81\x80\x00\x01\x00\x01\x00\x00\x00\x00" + b"\x00" * 32, ("198.51.100.1", 53))

    with patch("socket.socket") as mock_sock_cls:
        mock_sock_cls.return_value.__enter__.return_value = mock_sock
        is_ok, rtt_ms, msg = lightspeed_filter_probe.probe_smartshield_dns("198.51.100.1")
        assert is_ok is True
        assert rtt_ms >= 0.0
        assert "SmartShield DNS OK" in msg

def test_smartshield_dns_probe_timeout():
    """Verifies handling when SmartShield DNS times out."""
    mock_sock = MagicMock()
    mock_sock.recvfrom.side_effect = socket.timeout("Timed out")

    with patch("socket.socket") as mock_sock_cls:
        mock_sock_cls.return_value.__enter__.return_value = mock_sock
        is_ok, rtt_ms, msg = lightspeed_filter_probe.probe_smartshield_dns("198.51.100.1")
        assert is_ok is False
        assert rtt_ms == 0.0
        assert "SmartShield DNS Error" in msg
