#!/usr/bin/env python3
"""
Unit tests for Wi-Fi Multi-Band Hardware & Spectrum Generation Diagnostic Suite
Licensed under GNU AGPLv3.
"""

import pytest
from unittest.mock import patch
from sensor.wifi_multiband_probe import (
    freq_to_band_and_channel,
    audit_nic_capabilities,
    get_current_link,
    evaluate_band_and_channel_health
)


def test_freq_to_band_and_channel():
    test_cases = [
        (2412, ("2.4GHz", 1)),
        (2437, ("2.4GHz", 6)),
        (2462, ("2.4GHz", 11)),
        (2484, ("2.4GHz", 14)),
        (5180, ("5GHz", 36)),
        (5220, ("5GHz", 44)),
        (5745, ("5GHz", 149)),
        (5955, ("6GHz", 1)),
        (6115, ("6GHz", 33))
    ]
    for freq, expected in test_cases:
        assert freq_to_band_and_channel(freq) == expected


@patch("sensor.wifi_multiband_probe.run_cmd")
def test_audit_nic_capabilities_parsing(mock_run_cmd):
    mock_output = """
    Wiphy phy0
        Band 1:
            Frequencies:
                * 2412 MHz [1] (20.0 dBm)
                * 2462 MHz [11] (20.0 dBm)
            HT20/HT40
        Band 2:
            Frequencies:
                * 5180 MHz [36] (20.0 dBm)
                * 5745 MHz [149] (20.0 dBm)
            VHT Capabilities (0x03800000):
                Max MPDU length: 3895
                Supported Channel Width: neither 160 nor 80+80
            VHT RX MCS set:
                1 stream: MCS 0-9
                2 streams: MCS 0-9
        Available Antennas: TX 0x3 RX 0x3
    """
    mock_run_cmd.return_value = mock_output
    caps = audit_nic_capabilities("phy0")
    assert "2.4GHz" in caps["bands_supported"]
    assert "5GHz" in caps["bands_supported"]
    assert caps["max_generation"] == "Wi-Fi 5"
    assert caps["max_channel_width_mhz"] == 80
    assert caps["antenna_chains"] == 2


@patch("sensor.wifi_multiband_probe.run_cmd")
def test_get_current_link_parsing(mock_run_cmd):
    mock_output = """
    Connected to 48:3a:02:6c:9a:8a (on wlp1s0)
        SSID: KCSOS
        freq: 2412
        signal: -72 dBm
        tx bitrate: 144.4 MBit/s MCS 15 20MHz short GI
    """
    mock_run_cmd.return_value = mock_output
    link = get_current_link("wlp1s0")
    assert link["connected"] is True
    assert link["bssid"] == "48:3a:02:6c:9a:8a"
    assert link["ssid"] == "KCSOS"
    assert link["freq_mhz"] == 2412
    assert link["band"] == "2.4GHz"
    assert link["channel"] == 1
    assert link["rssi_dbm"] == -72
    assert link["tx_bitrate_mbps"] == 144.4
    assert link["standard_generation"] == "Wi-Fi 4 (HT)"
    assert link["channel_width_mhz"] == 20


def test_band_steering_anomaly_detection():
    nic_caps = {
        "phy": "phy0",
        "bands_supported": ["2.4GHz", "5GHz"],
        "standards_supported": ["Wi-Fi 4 (802.11n / HT)", "Wi-Fi 5 (802.11ac / VHT)"],
        "max_generation": "Wi-Fi 5",
        "max_channel_width_mhz": 80,
        "antenna_chains": 2
    }
    current_link = {
        "connected": True,
        "bssid": "48:3a:02:6c:9a:8a",
        "ssid": "KCSOS",
        "freq_mhz": 2412,
        "band": "2.4GHz",
        "channel": 1,
        "rssi_dbm": -72,
        "tx_bitrate_mbps": 144.4,
        "standard_generation": "Wi-Fi 4 (HT)",
        "channel_width_mhz": 20
    }
    scan_results = {
        "2.4GHz": {
            "total_aps": 1,
            "best_rssi": -72,
            "generation_counts": {"Wi-Fi 4 (HT)": 1},
            "channels": {
                "1": {
                    "channel": 1,
                    "freq_mhz": 2412,
                    "ap_count": 1,
                    "best_rssi": -72,
                    "aps": [
                        {"bssid": "48:3a:02:6c:9a:8a", "ssid": "KCSOS", "rssi_dbm": -72, "standard_generation": "Wi-Fi 4 (HT)"}
                    ]
                }
            }
        },
        "5GHz": {
            "total_aps": 1,
            "best_rssi": -65,
            "generation_counts": {"Wi-Fi 5 (VHT)": 1},
            "channels": {
                "36": {
                    "channel": 36,
                    "freq_mhz": 5180,
                    "ap_count": 1,
                    "best_rssi": -65,
                    "aps": [
                        {"bssid": "48:3a:02:6c:9a:8b", "ssid": "KCSOS", "rssi_dbm": -65, "standard_generation": "Wi-Fi 5 (VHT)"}
                    ]
                }
            }
        },
        "6GHz": {"total_aps": 0, "channels": {}, "best_rssi": -100, "generation_counts": {}}
    }

    report = evaluate_band_and_channel_health(nic_caps, current_link, scan_results)
    assert report["status"] == "WARNING"
    assert len(report["anomalies"]) >= 1
    assert report["anomalies"][0]["type"] == "BAND_STEERING_FAILURE"
    assert "Band Steering Anomaly" in report["anomalies"][0]["description"]
