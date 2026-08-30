#!/usr/bin/env python3
"""
Unit Test Suite for Microsoft 365 & Office 365 A5 Synthetic Health Prober (sensor/m365_connectivity_probe.py).
Tests:
  1. STUN RFC 5389 Binding Request Packet Construction
  2. Voice Quality & ITU-T G.107 MOS Calculation
  3. Genuine Microsoft CA vs. Firewall MITM SSL Decryption Detection
  4. DNS, TCP Handshake & HTTP/TLS Multi-Stage Response Timing
  5. Teams Real-Time Media (UDP STUN 3478-3481) Jitter & Loss Measurements
  6. Dynamic District Tenant SharePoint / OneDrive Ingestion
"""

import os
import sys
import time
import socket
import pytest
from unittest.mock import patch, MagicMock

# Ensure sensor directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import m365_connectivity_probe

# ====================================================
# 1. STUN Protocol & Media Quality Tests
# ====================================================

def test_m365_stun_packet_construction():
    """Verifies standard RFC 5389 STUN Binding Request packet encoding."""
    tx_id = b"\x11\x22\x33\x44\x55\x66\x77\x88\x99\xaa\xbb\xcc"
    packet = m365_connectivity_probe.build_stun_binding_request(tx_id)
    assert len(packet) == 20
    assert packet[:2] == b"\x00\x01" # Binding Request
    assert packet[2:4] == b"\x00\x00" # 0 attributes length
    assert packet[4:8] == b"\x21\x12\xa4\x42" # Magic Cookie
    assert packet[8:20] == tx_id

def test_m365_mos_score_calculation_pristine():
    """Verifies MOS score >= 4.30 under optimal Teams network conditions (RTT=20ms, Jitter=2ms, Loss=0%)."""
    mos = m365_connectivity_probe.calculate_mos_score(rtt_ms=20.0, jitter_ms=2.0, loss_percent=0.0)
    assert mos >= 4.30
    assert mos <= 4.50

def test_m365_mos_score_calculation_degraded():
    """Verifies MOS score <= 2.50 under degraded conditions (RTT=180ms, Jitter=45ms, Loss=12%)."""
    mos = m365_connectivity_probe.calculate_mos_score(rtt_ms=180.0, jitter_ms=45.0, loss_percent=12.0)
    assert mos <= 2.50
    assert mos >= 1.00

# ====================================================
# 2. SSL Inspection MITM Bypass Tests
# ====================================================

def test_m365_ssl_bypass_genuine_microsoft_ca():
    """Verifies genuine Microsoft Azure TLS CA passes SSL inspection bypass check."""
    mock_cert = {
        'issuer': [
            (('countryName', 'US'),),
            (('organizationName', 'Microsoft Corporation'),),
            (('commonName', 'Microsoft Azure TLS Issuing CA 01'),)
        ]
    }
    mock_ssock = MagicMock()
    mock_ssock.getpeercert.return_value = mock_cert
    mock_ssock.__enter__.return_value = mock_ssock

    with patch("socket.create_connection"), \
         patch("ssl.create_default_context") as mock_ctx:
        mock_ctx.return_value.wrap_socket.return_value = mock_ssock
        is_bypassed, summary = m365_connectivity_probe.check_ssl_inspection_bypass("outlook.office.com", 443)
        assert is_bypassed is True
        assert "Genuine Microsoft CA" in summary

def test_m365_ssl_bypass_mitm_firewall_detected():
    """Verifies firewall SSL decryption proxy (Palo Alto / Fortinet / Zscaler) is flagged."""
    mock_cert = {
        'issuer': [
            (('countryName', 'US'),),
            (('organizationName', 'Palo Alto Networks'),),
            (('commonName', 'PAN-OS Decryption Proxy CA'),)
        ]
    }
    mock_ssock = MagicMock()
    mock_ssock.getpeercert.return_value = mock_cert
    mock_ssock.__enter__.return_value = mock_ssock

    with patch("socket.create_connection"), \
         patch("ssl.create_default_context") as mock_ctx:
        mock_ctx.return_value.wrap_socket.return_value = mock_ssock
        is_bypassed, summary = m365_connectivity_probe.check_ssl_inspection_bypass("teams.microsoft.com", 443)
        assert is_bypassed is False
        assert "MITM Inspection Detected" in summary

# ====================================================
# 3. HTTP / DNS / TCP Multi-Stage Timing Tests
# ====================================================

def test_m365_http_endpoint_timing_success():
    """Verifies multi-stage timing decomposition (DNS + TCP SYN + HTTP Response)."""
    target = {
        "url": "https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration",
        "host": "login.microsoftonline.com",
        "port": 443
    }
    mock_res = MagicMock()
    mock_res.status = 200
    mock_res.__enter__.return_value = mock_res

    with patch("socket.gethostbyname", return_value="20.190.159.0"), \
         patch("socket.create_connection", MagicMock()), \
         patch("urllib.request.urlopen", return_value=mock_res):
        is_ok, dns_t, tcp_t, total_t, status_code, reason = m365_connectivity_probe.check_http_endpoint(target)
        assert is_ok is True
        assert status_code == 200
        assert total_t >= 0.0

def test_m365_http_endpoint_dns_failure():
    """Verifies handling when DNS resolution fails."""
    target = {
        "url": "https://nonexistent.office.com",
        "host": "nonexistent.office.com",
        "port": 443
    }
    with patch("socket.gethostbyname", side_effect=socket.gaierror("Name or service not known")):
        is_ok, dns_t, tcp_t, total_t, status_code, reason = m365_connectivity_probe.check_http_endpoint(target)
        assert is_ok is False
        assert status_code == 0
        assert "DNS Error" in reason

# ====================================================
# 4. Teams Real-Time Media (UDP STUN) Tests
# ====================================================

def test_m365_teams_udp_media_probe_success():
    """Verifies synthetic UDP STUN response processing for Teams media relays."""
    def mock_recvfrom(bufsize):
        # Construct valid STUN response with matching TX ID
        return b"\x01\x01\x00\x00\x21\x12\xa4\x42" + b"\x00" * 12, ("52.114.128.0", 3478)

    mock_sock = MagicMock()
    mock_sock.recvfrom.side_effect = lambda b: (b"\x01\x01\x00\x00\x21\x12\xa4\x42" + mock_sock.sent_tx, ("52.114.128.0", 3478))

    def mock_sendto(data, addr):
        mock_sock.sent_tx = data[8:20]
        return len(data)

    mock_sock.sendto.side_effect = mock_sendto

    with patch("socket.gethostbyname", return_value="52.114.128.0"), \
         patch("socket.socket", return_value=mock_sock):
        res = m365_connectivity_probe.probe_teams_udp_media("world.tr.teams.microsoft.com", 3478, packet_count=5)
        assert res["status"] == 1
        assert res["loss_percent"] == 0.0
        assert res["mos_score"] >= 4.0

def test_m365_teams_udp_media_probe_firewall_blocked():
    """Verifies handling when firewall drops UDP 3478-3481."""
    mock_sock = MagicMock()
    mock_sock.recvfrom.side_effect = socket.timeout("timed out")

    with patch("socket.gethostbyname", return_value="52.114.128.0"), \
         patch("socket.socket", return_value=mock_sock):
        res = m365_connectivity_probe.probe_teams_udp_media("world.tr.teams.microsoft.com", 3478, packet_count=3)
        assert res["status"] == 0
        assert res["loss_percent"] == 100.0
        assert res["mos_score"] == 1.0
        assert "Firewall blocking UDP" in res["error"]
