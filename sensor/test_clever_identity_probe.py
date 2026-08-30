#!/usr/bin/env python3
"""
Unit Test Suite for Clever K-12 Identity, Badges & SSO Synthetic Prober (sensor/clever_identity_probe.py).
Tests:
  1. Clever Ecosystem Endpoints Matrix Registration
  2. TCP SYN Handshake & Response Latency Benchmarks
  3. Clever Badges Genuine CA vs. Firewall MITM SSL Decryption Detection
  4. Classroom MFA Safe Zone Public Egress IP Discovery
  5. Dynamic District Portal Ingestion
"""

import os
import sys
import socket
import pytest
from unittest.mock import patch, MagicMock

# Ensure sensor directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import clever_identity_probe

# ====================================================
# 1. Endpoints & TCP Connectivity Tests
# ====================================================

def test_clever_endpoints_matrix_populated():
    """Verifies all standard Clever Badges, SSO, and IDM endpoints are registered."""
    service_ids = [s["id"] for s in clever_identity_probe.CLEVER_ENDPOINTS]
    assert "clever_badger" in service_ids
    assert "clever_assets" in service_ids
    assert "aws_s3_storage" in service_ids
    assert "clever_portal_root" in service_ids
    assert "clever_oauth_tokens" in service_ids
    assert "clever_saml_acs" in service_ids
    assert "clever_rest_api" in service_ids
    assert "clever_idm_engine" in service_ids

def test_clever_tcp_endpoint_success():
    """Verifies TCP SYN handshake succeeds and returns valid latency."""
    with patch("socket.gethostbyname", return_value="52.204.10.1"), \
         patch("socket.create_connection", MagicMock()):
        is_ok, rtt_ms, msg = clever_identity_probe.check_tcp_endpoint("badger.clever.com", 443)
        assert is_ok is True
        assert rtt_ms >= 0.0
        assert "Connected to 52.204.10.1:443" in msg

def test_clever_tcp_endpoint_dns_failure():
    """Verifies handling when DNS resolution fails."""
    with patch("socket.gethostbyname", side_effect=socket.gaierror("Name resolution failed")):
        is_ok, rtt_ms, msg = clever_identity_probe.check_tcp_endpoint("nonexistent.clever.com", 443)
        assert is_ok is False
        assert rtt_ms == 0.0
        assert "DNS Resolution Error" in msg

# ====================================================
# 2. SSL Inspection Bypass Tests
# ====================================================

def test_clever_ssl_bypass_genuine_amazon_digicert_ca():
    """Verifies genuine Amazon / DigiCert CA passes SSL inspection check."""
    mock_cert = {
        'issuer': [
            (('countryName', 'US'),),
            (('organizationName', 'Amazon'),),
            (('commonName', 'Amazon RSA 2048 M02'),)
        ]
    }
    mock_ssock = MagicMock()
    mock_ssock.getpeercert.return_value = mock_cert
    mock_ssock.__enter__.return_value = mock_ssock

    with patch("socket.create_connection"), \
         patch("ssl.create_default_context") as mock_ctx:
        mock_ctx.return_value.wrap_socket.return_value = mock_ssock
        is_bypassed, summary = clever_identity_probe.check_ssl_inspection_bypass("badger.clever.com", 443)
        assert is_bypassed is True
        assert "Genuine CA" in summary

def test_clever_ssl_bypass_mitm_firewall_detected():
    """Verifies firewall MITM decryption proxy on Clever is flagged."""
    mock_cert = {
        'issuer': [
            (('countryName', 'US'),),
            (('organizationName', 'Lightspeed Systems'),),
            (('commonName', 'Lightspeed Filter CA'),)
        ]
    }
    mock_ssock = MagicMock()
    mock_ssock.getpeercert.return_value = mock_cert
    mock_ssock.__enter__.return_value = mock_ssock

    with patch("socket.create_connection"), \
         patch("ssl.create_default_context") as mock_ctx:
        mock_ctx.return_value.wrap_socket.return_value = mock_ssock
        is_bypassed, summary = clever_identity_probe.check_ssl_inspection_bypass("badger.clever.com", 443)
        assert is_bypassed is False
        assert "MITM Inspection Detected" in summary

# ====================================================
# 3. Classroom MFA Safe Zone Public IP Discovery Tests
# ====================================================

def test_clever_public_egress_ip_discovery_success():
    """Verifies discovering public WAN egress IP for Safe Zone compliance."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"ip": "203.0.113.42"}'
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        is_ok, ip = clever_identity_probe.fetch_public_egress_ip()
        assert is_ok is True
        assert ip == "203.0.113.42"

def test_clever_public_egress_ip_discovery_fallback():
    """Verifies plain text fallback for public WAN IP discovery."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'198.51.100.24\n'
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        is_ok, ip = clever_identity_probe.fetch_public_egress_ip()
        assert is_ok is True
        assert ip == "198.51.100.24"
