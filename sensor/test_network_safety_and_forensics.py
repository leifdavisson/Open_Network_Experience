#!/usr/bin/env python3
"""
Unit Test Suite for Network Safety Guardrails, Bandwidth Testing, and Incident Forensics:
  1. Bandwidth Testing Time Windows & Safety Throttling (iperf3_runner.py)
  2. Precision GPS NMEA Coordinate Parsing (gps_location_collector.py)
  3. Incident PCAP Slicing & Evidence Collection (pcap_trigger.py, evidence_collector.py)
"""

import os
import sys
import datetime
import pytest
from unittest.mock import patch, MagicMock

# Ensure sensor directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import iperf3_runner
import gps_location_collector

# ==========================================
# 1. iperf3 Time Windows & Safety Guardrails
# ==========================================

def test_iperf3_allowed_hours_none():
    """Verifies that empty allowed_hours list allows execution anytime."""
    assert iperf3_runner.is_within_allowed_hours(None) is True
    assert iperf3_runner.is_within_allowed_hours([]) is True

def test_iperf3_allowed_hours_daytime_window():
    """Verifies daytime window (e.g. 08:00 - 17:00)."""
    allowed = ["08:00-17:00"]

    # Inside window
    with patch("datetime.datetime") as mock_dt:
        mock_dt.now.return_value.time.return_value = datetime.time(12, 30)
        assert iperf3_runner.is_within_allowed_hours(allowed) is True

    # Outside window (early morning)
    with patch("datetime.datetime") as mock_dt:
        mock_dt.now.return_value.time.return_value = datetime.time(7, 0)
        assert iperf3_runner.is_within_allowed_hours(allowed) is False

def test_iperf3_allowed_hours_overnight_midnight_window():
    """Verifies overnight maintenance window crossing midnight (e.g. 20:00 - 06:00)."""
    allowed = ["20:00-06:00"]

    # Late night (23:30) -> Inside
    with patch("datetime.datetime") as mock_dt:
        mock_dt.now.return_value.time.return_value = datetime.time(23, 30)
        assert iperf3_runner.is_within_allowed_hours(allowed) is True

    # Early morning (03:15) -> Inside
    with patch("datetime.datetime") as mock_dt:
        mock_dt.now.return_value.time.return_value = datetime.time(3, 15)
        assert iperf3_runner.is_within_allowed_hours(allowed) is True

    # School hours (11:00) -> Outside / Blocked
    with patch("datetime.datetime") as mock_dt:
        mock_dt.now.return_value.time.return_value = datetime.time(11, 0)
        assert iperf3_runner.is_within_allowed_hours(allowed) is False

def test_iperf3_get_interface_ip():
    """Verifies parsing of ip addr output to extract IPv4 address."""
    sample_ip_output = (
        "2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP\n"
        "    inet 10.10.40.55/24 brd 10.10.40.255 scope global eth0\n"
        "       valid_lft forever preferred_lft forever\n"
    )
    with patch("subprocess.check_output", return_value=sample_ip_output):
        ip = iperf3_runner.get_interface_ip("eth0")
        assert ip == "10.10.40.55"

# ==========================================
# 2. GPS & NMEA Geolocation Parsing
# ==========================================

def test_gps_nmea_lat_long_north_west():
    """Verifies converting NMEA coordinate degrees to decimal degrees (e.g. California North / West)."""
    # 3522.1234 N -> 35.368723
    lat = gps_location_collector.parse_nmea_lat_long("3522.1234", "N")
    assert lat is not None
    assert round(lat, 4) == 35.3687

    # 11901.5678 W -> -119.02613
    lon = gps_location_collector.parse_nmea_lat_long("11901.5678", "W")
    assert lon is not None
    assert round(lon, 4) == -119.0261

def test_gps_nmea_lat_long_invalid():
    """Verifies invalid or empty NMEA coordinate returns None."""
    assert gps_location_collector.parse_nmea_lat_long("", "N") is None
    assert gps_location_collector.parse_nmea_lat_long("invalid", "N") is None
