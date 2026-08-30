#!/usr/bin/env python3
"""
Unit Test Suite for Google Workspace & ChromeOS Synthetic Health Prober (sensor/google_workspace_chromeos_probe.py).
Tests:
  1. Google Meet WebRTC STUN Packet Encoding & Voice Quality MOS Calculation
  2. Google Meet Real-Time UDP Media (19302/3478) Jitter & Loss Measurements
  3. Google Services Matrix & TCP Connect Handshakes
  4. Google Trust Services (GTS) SSL Decryption MITM Bypass Detection
  5. Android FCM Push Notifications Port (TCP 5228) Check
"""

import os
import sys
import socket
import pytest
from unittest.mock import patch, MagicMock

# Ensure sensor directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import google_workspace_chromeos_probe

# ====================================================
# 1. Google Meet STUN & Voice Quality Tests
# ====================================================

def test_google_meet_stun_packet_encoding():
    """Verifies RFC 5389 STUN packet encoding for Google Meet media relays."""
    tx_id = b"\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c"
    packet = google_workspace_chromeos_probe.build_stun_binding_request(tx_id)
    assert len(packet) == 20
    assert packet[:2] == b"\x00\x01" # Binding Request
    assert packet[4:8] == b"\x21\x12\xa4\x42" # Magic Cookie
    assert packet[8:20] == tx_id

def test_google_meet_mos_score_calculation():
    """Verifies MOS score calculation for optimal vs degraded Meet calls."""
    mos_good = google_workspace_chromeos_probe.calculate_mos_score(rtt_ms=15.0, jitter_ms=1.5, loss_percent=0.0)
    assert mos_good >= 4.30

    mos_bad = google_workspace_chromeos_probe.calculate_mos_score(rtt_ms=180.0, jitter_ms=45.0, loss_percent=12.0)
    assert mos_bad <= 2.50

def test_google_meet_udp_media_probe_success():
    """Verifies WebRTC UDP STUN probe returns valid RTT, jitter, and MOS."""
    mock_sock = MagicMock()
    def mock_sendto(data, addr):
        mock_sock.sent_tx = data[8:20]
        return len(data)

    mock_sock.sendto.side_effect = mock_sendto
    mock_sock.recvfrom.side_effect = lambda b: (b"\x01\x01\x00\x00\x21\x12\xa4\x42" + mock_sock.sent_tx, ("74.125.250.1", 19302))

    with patch("socket.gethostbyname", return_value="74.125.250.1"), \
         patch("socket.socket", return_value=mock_sock):
        res = google_workspace_chromeos_probe.probe_google_meet_udp_media("stun.l.google.com", 19302, packet_count=5)
        assert res["status"] == 1
        assert res["loss_percent"] == 0.0
        assert res["mos_score"] >= 4.20
        assert res["error"] is None

def test_google_meet_udp_media_probe_blocked():
    """Verifies handling when firewall blocks UDP 19302."""
    mock_sock = MagicMock()
    mock_sock.recvfrom.side_effect = socket.timeout("Timed out")

    with patch("socket.gethostbyname", return_value="74.125.250.1"), \
         patch("socket.socket", return_value=mock_sock):
        res = google_workspace_chromeos_probe.probe_google_meet_udp_media("stun.l.google.com", 19302, packet_count=3)
        assert res["status"] == 0
        assert res["loss_percent"] == 100.0
        assert res["mos_score"] == 1.0
        assert "All UDP STUN packets lost" in res["error"]

# ====================================================
# 2. Services Matrix & SSL Decryption Bypass Tests
# ====================================================

def test_google_services_matrix_registered():
    """Verifies all standard Workspace and ChromeOS endpoints are registered."""
    service_ids = [s["id"] for s in google_workspace_chromeos_probe.GOOGLE_SERVICES]
    assert "google_identity_sso" in service_ids
    assert "gmail_web" in service_ids
    assert "google_drive" in service_ids
    assert "google_docs" in service_ids
    assert "google_classroom" in service_ids
    assert "chrome_dm_server" in service_ids
    assert "chrome_policy_sync" in service_ids
    assert "chrome_omaha_update" in service_ids
    assert "chrome_dl_cdn" in service_ids
    assert "play_store" in service_ids

def test_google_ssl_bypass_genuine_gts_ca():
    """Verifies genuine Google Trust Services CA passes SSL inspection check."""
    mock_cert = {
        'issuer': [
            (('countryName', 'US'),),
            (('organizationName', 'Google Trust Services LLC'),),
            (('commonName', 'GTS CA 1C3'),)
        ]
    }
    mock_ssock = MagicMock()
    mock_ssock.getpeercert.return_value = mock_cert
    mock_ssock.__enter__.return_value = mock_ssock

    with patch("socket.create_connection"), \
         patch("ssl.create_default_context") as mock_ctx:
        mock_ctx.return_value.wrap_socket.return_value = mock_ssock
        is_bypassed, summary = google_workspace_chromeos_probe.check_ssl_inspection_bypass("accounts.google.com", 443)
        assert is_bypassed is True
        assert "Genuine Google Trust Services" in summary

def test_google_ssl_bypass_mitm_firewall_detected():
    """Verifies firewall MITM decryption proxy on Google accounts is flagged."""
    mock_cert = {
        'issuer': [
            (('countryName', 'US'),),
            (('organizationName', 'Fortinet'),),
            (('commonName', 'FortiGate CA'),)
        ]
    }
    mock_ssock = MagicMock()
    mock_ssock.getpeercert.return_value = mock_cert
    mock_ssock.__enter__.return_value = mock_ssock

    with patch("socket.create_connection"), \
         patch("ssl.create_default_context") as mock_ctx:
        mock_ctx.return_value.wrap_socket.return_value = mock_ssock
        is_bypassed, summary = google_workspace_chromeos_probe.check_ssl_inspection_bypass("accounts.google.com", 443)
        assert is_bypassed is False
        assert "MITM Inspection Detected" in summary

def test_fcm_push_port5228_check():
    """Verifies FCM push notification port checking."""
    with patch("socket.gethostbyname", return_value="142.250.190.10"), \
         patch("socket.create_connection", MagicMock()):
        is_ok, rtt_ms, msg = google_workspace_chromeos_probe.check_tcp_endpoint("fcm.googleapis.com", 5228)
        assert is_ok is True
        assert rtt_ms >= 0.0
        assert "Connected to 142.250.190.10:5228" in msg
