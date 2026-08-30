#!/usr/bin/env python3
"""
Unit Test Suite for Windows Update (WU), BITS & Delivery Optimization (DO) Synthetic Prober (sensor/windows_update_do_probe.py).
Tests:
  1. TCP SYN & Latency Benchmarks for Windows Update Catalog & Cloud Endpoints
  2. Delivery Optimization (DO) Cloud Tracking Coordination
  3. BITS & DO HTTP 206 Partial Content Range Header Validation
  4. Delivery Optimization LAN Peer P2P Listener (Port 7680)
"""

import os
import sys
import socket
import pytest
from unittest.mock import patch, MagicMock

# Ensure sensor directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import windows_update_do_probe

# ====================================================
# 1. Windows Update & DO Cloud Handshake Tests
# ====================================================

def test_wu_and_do_endpoints_matrix_populated():
    """Verifies all standard Windows Update and Delivery Optimization endpoints are registered."""
    wu_ids = [e["id"] for e in windows_update_do_probe.WU_ENDPOINTS]
    assert "wu_catalog" in wu_ids
    assert "wu_service" in wu_ids
    assert "wu_download_cdn" in wu_ids
    assert "wu_ms_download" in wu_ids

    do_ids = [e["id"] for e in windows_update_do_probe.DO_ENDPOINTS]
    assert "do_cloud_tracker" in do_ids
    assert "do_download_cdn" in do_ids
    assert "do_enterprise_cdn" in do_ids

def test_wu_tcp_endpoint_success():
    """Verifies TCP handshake succeeds and returns valid RTT."""
    with patch("socket.gethostbyname", return_value="20.190.159.1"), \
         patch("socket.create_connection", MagicMock()):
        is_ok, rtt_ms, msg = windows_update_do_probe.check_tcp_endpoint("windowsupdate.microsoft.com", 443)
        assert is_ok is True
        assert rtt_ms >= 0.0
        assert "Connected to 20.190.159.1:443" in msg

def test_wu_tcp_endpoint_dns_failure():
    """Verifies handling when DNS resolution fails."""
    with patch("socket.gethostbyname", side_effect=socket.gaierror("Name resolution failed")):
        is_ok, rtt_ms, msg = windows_update_do_probe.check_tcp_endpoint("nonexistent.update.microsoft.com", 443)
        assert is_ok is False
        assert rtt_ms == 0.0
        assert "DNS Resolution Error" in msg

def test_wu_tcp_endpoint_connect_timeout():
    """Verifies handling when TCP connection times out."""
    with patch("socket.gethostbyname", return_value="20.190.159.1"), \
         patch("socket.create_connection", side_effect=socket.timeout("Timed out")):
        is_ok, rtt_ms, msg = windows_update_do_probe.check_tcp_endpoint("windowsupdate.microsoft.com", 443)
        assert is_ok is False
        assert rtt_ms == 0.0
        assert "TCP Connect Error" in msg

# ====================================================
# 2. BITS & DO HTTP 206 Partial Content Range Tests
# ====================================================

def test_bits_http_range_support_success_206():
    """Verifies HTTP 206 Partial Content with Content-Range header passes."""
    mock_resp = MagicMock()
    mock_resp.status = 206
    mock_resp.headers = {"Content-Range": "bytes 0-1023/1048576"}
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        is_ok, status, msg = windows_update_do_probe.check_http_range_support("https://download.windowsupdate.com")
        assert is_ok is True
        assert status == 206
        assert "HTTP 206 Partial Content Supported" in msg

def test_bits_http_range_support_proxy_stripped_200():
    """Verifies when a proxy strips the Range header and returns HTTP 200, a failure is flagged."""
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.headers = {}
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        is_ok, status, msg = windows_update_do_probe.check_http_range_support("https://download.windowsupdate.com")
        assert is_ok is False
        assert status == 200
        assert "Range header ignored by Proxy" in msg

# ====================================================
# 3. Delivery Optimization LAN Peer P2P Tests (Port 7680)
# ====================================================

def test_do_lan_p2p_port_open():
    """Verifies DO LAN peer listener on TCP 7680 is detected as OPEN."""
    with patch("socket.create_connection", MagicMock()):
        is_open, rtt_ms, msg = windows_update_do_probe.check_lan_p2p_port("10.0.10.50", 7680)
        assert is_open is True
        assert rtt_ms >= 0.0
        assert "OPEN on 10.0.10.50" in msg

def test_do_lan_p2p_port_closed_or_filtered():
    """Verifies DO LAN peer port is reported closed when connection fails."""
    with patch("socket.create_connection", side_effect=ConnectionRefusedError("Connection refused")):
        is_open, rtt_ms, msg = windows_update_do_probe.check_lan_p2p_port("10.0.10.50", 7680)
        assert is_open is False
        assert rtt_ms == 0.0
        assert "Closed/Filtered" in msg
