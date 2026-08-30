#!/usr/bin/env python3
"""
Comprehensive Unit Test Suite for Edge Synthetic Probes:
  1. CAASPP & ELPAC State Testing Readiness & SSL Inspection Checker (caaspp_readiness.py)
  2. VoIP / Real-Time Media Quality & MOS Score Calculation (voip_jitter_probe.py)
  3. CIPA Content Filtering & SafeSearch Compliance (cipa_compliance.py)
  4. Multi-Resolver DNS Health & Benchmark (dns_multi_resolver_probe.py)
  5. WYSIWYG EasyBuilder Custom Synthetic Probe Runner (custom_probe_runner.py)
"""

import os
import sys
import tempfile
import json
import pytest
from unittest.mock import patch, MagicMock, mock_open

# Ensure sensor directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import caaspp_readiness
import voip_jitter_probe
import cipa_compliance
import dns_multi_resolver_probe
import custom_probe_runner

# ==========================================
# 1. CAASPP State Testing Probe Unit Tests
# ==========================================

def test_caaspp_ssl_bypass_genuine_ca():
    """Verifies that genuine CA certificates pass CAASPP Secure Browser checks."""
    mock_cert = {
        'issuer': [
            (('countryName', 'US'),),
            (('organizationName', 'DigiCert Inc'),),
            (('commonName', 'DigiCert Global Root CA'),)
        ]
    }
    mock_ssock = MagicMock()
    mock_ssock.getpeercert.return_value = mock_cert
    mock_ssock.__enter__.return_value = mock_ssock

    with patch("socket.create_connection"), \
         patch("ssl.create_default_context") as mock_ctx:
        mock_ctx.return_value.wrap_socket.return_value = mock_ssock
        is_bypassed, summary = caaspp_readiness.check_ssl_inspection_bypass("ca.cambiumtds.com", 443)
        assert is_bypassed is True
        assert "Genuine CA" in summary

def test_caaspp_ssl_mitm_firewall_detected():
    """Verifies that firewall SSL decryption (Fortinet, Palo Alto) is flagged as non-compliant."""
    mock_cert = {
        'issuer': [
            (('countryName', 'US'),),
            (('organizationName', 'Fortinet Inc'),),
            (('commonName', 'FortiGate CA SSL Proxy'),)
        ]
    }
    mock_ssock = MagicMock()
    mock_ssock.getpeercert.return_value = mock_cert
    mock_ssock.__enter__.return_value = mock_ssock

    with patch("socket.create_connection"), \
         patch("ssl.create_default_context") as mock_ctx:
        mock_ctx.return_value.wrap_socket.return_value = mock_ssock
        is_bypassed, summary = caaspp_readiness.check_ssl_inspection_bypass("ca.cambiumtds.com", 443)
        assert is_bypassed is False
        assert "MITM Detected" in summary

def test_caaspp_http_endpoint_success():
    """Verifies successful HTTP 200 response check for Cambium Student interface."""
    target = {"url": "https://ca.cambiumtds.com/student"}
    mock_res = MagicMock()
    mock_res.status = 200
    mock_res.__enter__.return_value = mock_res

    with patch("urllib.request.urlopen", return_value=mock_res):
        is_ok, latency, code, reason = caaspp_readiness.check_http_endpoint(target)
        assert is_ok is True
        assert code == 200
        assert latency >= 0.0

# ==========================================
# 2. VoIP Jitter & MOS Score Unit Tests
# ==========================================

def test_voip_mos_calculation_excellent():
    """Verifies MOS score calculation for pristine network conditions (RTT=15ms, Jitter=1ms, Loss=0%)."""
    mos = voip_jitter_probe.calculate_mos_score(rtt_ms=15.0, jitter_ms=1.0, loss_percent=0.0)
    assert mos >= 4.3
    assert mos <= 4.5

def test_voip_mos_calculation_severe_loss():
    """Verifies MOS score drops significantly under severe packet loss (RTT=120ms, Jitter=30ms, Loss=15%)."""
    mos = voip_jitter_probe.calculate_mos_score(rtt_ms=120.0, jitter_ms=30.0, loss_percent=15.0)
    assert mos <= 2.8

def test_voip_stun_binding_request():
    """Verifies RFC 5389 STUN Binding Request packet construction."""
    tx_id = b"\x01" * 12
    packet = voip_jitter_probe.build_stun_binding_request(tx_id)
    assert len(packet) == 20
    assert packet[:2] == b"\x00\x01"  # Binding Request
    assert packet[4:8] == b"\x21\x12\xa4\x42"  # Magic Cookie
    assert packet[8:] == tx_id

# ==========================================
# 3. CIPA Compliance Filter Unit Tests
# ==========================================

def test_cipa_content_blocked_success():
    """Verifies compliant behavior when restricted content is blocked (token not in page)."""
    target = {
        "url": "https://testfiltering.pornhub.com/",
        "token": "5468v9o44huX499v91e9X35ki0mmlwv21449076I7VMI2LA53200Qd9859S2E4aF"
    }
    # Mock block page returned by content filter
    mock_res = MagicMock()
    mock_res.read.return_value = b"<html><body>Access Denied: School Content Filter Blocked This Site</body></html>"
    mock_res.status = 200
    mock_res.__enter__.return_value = mock_res

    with patch("urllib.request.urlopen", return_value=mock_res):
        is_compliant, reason = cipa_compliance.check_target(target)
        assert is_compliant is True
        assert "Blocked" in reason

def test_cipa_content_allowed_failure():
    """Verifies non-compliant alert when restricted content loads successfully with matching token."""
    token = "5468v9o44huX499v91e9X35ki0mmlwv21449076I7VMI2LA53200Qd9859S2E4aF"
    target = {
        "url": "https://testfiltering.pornhub.com/",
        "token": token
    }
    # Mock raw unblocked page with verification token
    mock_res = MagicMock()
    mock_res.read.return_value = f"<html><body>Unfiltered Content Test: {token}</body></html>".encode("utf-8")
    mock_res.status = 200
    mock_res.__enter__.return_value = mock_res

    with patch("urllib.request.urlopen", return_value=mock_res):
        is_compliant, reason = cipa_compliance.check_target(target)
        assert is_compliant is False
        assert "Allowed" in reason

# ==========================================
# 4. Multi-Resolver DNS Health Unit Tests
# ==========================================

def test_dns_discover_local_resolvers(tmp_path):
    """Verifies parsing nameserver entries from /etc/resolv.conf."""
    resolv_content = "search district.k12.ca.us\nnameserver 10.10.1.1\nnameserver 10.10.1.2\n"

    with patch("os.path.exists", return_value=True), \
         patch("builtins.open", mock_open(read_data=resolv_content)):
        resolvers = dns_multi_resolver_probe.discover_local_resolvers()
        assert len(resolvers) == 2
        assert resolvers[0]["ip"] == "10.10.1.1"
        assert resolvers[1]["ip"] == "10.10.1.2"
        assert resolvers[0]["is_public"] is False

# ==========================================
# 5. Custom Probe Runner Unit Tests
# ==========================================

def test_custom_probe_runner_http_match():
    """Verifies WYSIWYG custom probe execution with body regex validation."""
    probe_spec = {
        "id": "canvas_lms",
        "name": "Canvas LMS Health",
        "probe_type": "http",
        "target": "https://canvas.district.edu/health",
        "timeout_seconds": 5.0,
        "expected_status_code": 200,
        "match_body_regex": r"\"status\":\s*\"ok\""
    }

    mock_res = MagicMock()
    mock_res.getcode.return_value = 200
    mock_res.read.return_value = b'{"status": "ok", "version": "1.4.2"}'
    mock_res.__enter__.return_value = mock_res

    with patch("urllib.request.urlopen", return_value=mock_res):
        is_success, latency, status_code = custom_probe_runner.execute_http_probe(
            target="https://canvas.district.edu/health",
            timeout=5.0,
            expected_status=200,
            match_regex="status"
        )
        assert is_success == 1
        assert status_code == 200
        assert latency >= 0.0
