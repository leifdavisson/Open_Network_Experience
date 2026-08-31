#!/usr/bin/env python3
"""
Unit Test Suite for the Edge Sensor Reconciler Daemon (sensor/reconciler/reconciler.py).
Tests:
  1. Hardware UUID & Machine ID Derivation
  2. Zero-Touch Discovery (DHCP Option 43, DNS Search Domain, Config URL, Fallback)
  3. Wi-Fi Configuration Generation (Open, WPA-PSK, WPA-EAP PEAP)
  4. Docker Container Reconciliation & Safety Thresholds
  5. Adaptive Resolution Engine State Machine (GREEN, AMBER, RED, BLACKOUT, ON_DEMAND)
  6. Probe, PCAP, and Unified Schedule Synchronization
"""

import os
import sys
import uuid
from unittest.mock import patch, MagicMock, mock_open

# Ensure reconciler module path is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import reconciler
from reconciler import (
    AdaptiveResolutionEngine,
    get_sensor_uuid,
    load_config,
    save_config,
    reconcile_wifi,
    reconcile_containers,
    reconcile_unified_schedules,
    reconcile_pcap_trigger,
    get_cmp_url,
    discover_cmp_via_dhcp_option43,
    resolve_cmp_via_dns
)

# --- 1. Hardware ID and Config Management Tests ---

def test_01_hardware_uuid_fallback():
    """Verifies that get_sensor_uuid() reads /etc/machine-id if present, or generates UUID."""
    # When /etc/machine-id exists
    with patch("os.path.exists", return_value=True), \
         patch("builtins.open", mock_open(read_data="test-node-99887766\n")):
        sensor_id = get_sensor_uuid()
        assert sensor_id == "test-node-99887766"

    # When /etc/machine-id is missing, falls back to UUID
    with patch("os.path.exists", return_value=False):
        generated = get_sensor_uuid()
        # Validate UUID format
        parsed = uuid.UUID(generated, version=4)
        assert str(parsed) == generated

def test_02_load_and_save_config(tmp_path, monkeypatch):
    """Verifies loading, defaults assignment, and atomic config saving."""
    config_file = str(tmp_path / "reconciler.json")
    monkeypatch.setattr(reconciler, "CONFIG_PATH", config_file)

    # Load with non-existent file -> default created
    cfg = load_config()
    assert cfg["cmp_url"] == reconciler.DEFAULT_CONFIG["cmp_url"]
    assert cfg["sensor_id"] != ""
    assert os.path.exists(config_file)

    # Modify and save
    cfg["api_key"] = "sec-edge-token-123"
    save_config(cfg)

    # Reload
    reloaded = load_config()
    assert reloaded["api_key"] == "sec-edge-token-123"

# --- 2. Zero-Touch Discovery Tests ---

def test_03_dhcp_option43_discovery(tmp_path):
    """Verifies parsing of DHCP Option 43 from lease files."""
    lease_content = 'OPTION_43="http://cmp.example.com:8000/api/v1"\n'

    with patch("os.path.exists", return_value=True), \
         patch("os.walk", return_value=[("/run/systemd/netif/leases", [], ["eth0.lease"])]), \
         patch("builtins.open", mock_open(read_data=lease_content)):
        url = discover_cmp_via_dhcp_option43()
        assert url == "http://cmp.example.com:8000/api/v1"

def test_03b_dhcp_option43_hex_tlv_discovery(tmp_path):
    """Verifies parsing of RFC 2132 Sub-Option TLV hex streams in Option 43."""
    # Sub-option 1 (0x01), length 30 (0x1e) -> http://192.0.2.10:8000/api/v1
    # Sub-option 2 (0x02), length 9 (0x09) -> West High
    hex_payload = "01:1d:68:74:74:70:3a:2f:2f:31:39:32:2e:30:2e:32:2e:31:30:3a:38:30:30:30:2f:61:70:69:2f:76:31:02:09:57:65:73:74:20:48:69:67:68"
    lease_content = f'vendor-encapsulated-options="{hex_payload}"\n'

    with patch("os.path.exists", return_value=True), \
         patch("os.walk", return_value=[("/run/systemd/netif/leases", [], ["eth0.lease"])]), \
         patch("builtins.open", mock_open(read_data=lease_content)):
        url = discover_cmp_via_dhcp_option43()
        assert url == "http://192.0.2.10:8000/api/v1"

    parsed = reconciler.parse_option43_tlv_or_string(hex_payload)
    assert parsed["cmp_url"] == "http://192.0.2.10:8000/api/v1"
    assert parsed["campus"] == "West High"

def test_03c_option224_private_option_discovery(tmp_path):
    """Verifies parsing of site-specific private DHCP Option 224."""
    lease_content = 'OPTION_224="http://192.0.2.10:8000/api/v1"\n'

    with patch("os.path.exists", return_value=True), \
         patch("os.walk", return_value=[("/var/lib/dhcp", [], ["dhclient.leases"])]), \
         patch("builtins.open", mock_open(read_data=lease_content)):
        url = discover_cmp_via_dhcp_option43()
        assert url == "http://192.0.2.10:8000/api/v1"

def test_04_dns_domain_resolution():
    """Verifies resolving openux-cmp via DNS domain suffix."""
    with patch("reconciler.discover_domain", return_value="district.k12.ca.us"):
        with patch("socket.gethostbyname", return_value="10.10.10.5"):
            url = resolve_cmp_via_dns()
            assert url == "http://openux-cmp.district.k12.ca.us:8000/api/v1"

def test_05_get_cmp_url_priority():
    """Verifies priority of explicit URL vs local default discovery fallback."""
    # Explicit custom URL
    cfg_explicit = {"cmp_url": "https://cmp.custom-domain.org/api/v1"}
    assert get_cmp_url(cfg_explicit) == "https://cmp.custom-domain.org/api/v1"

# --- 3. Wi-Fi WPA Supplicant Reconfiguration Tests ---

def test_06_reconcile_wifi_open_network(tmp_path):
    """Verifies wpa_supplicant generation for Open guest Wi-Fi."""
    conf_path = str(tmp_path / "wpa_supplicant.conf")
    spec = {"ssid": "District-Guest", "security": "open"}

    with patch("reconciler.run_cmd", return_value=True):
        reconcile_wifi(spec, "wlan0", conf_path)

    assert os.path.exists(conf_path)
    with open(conf_path, "r") as f:
        content = f.read()
        assert 'ssid="District-Guest"' in content
        assert "key_mgmt=NONE" in content

def test_07_reconcile_wifi_psk_network(tmp_path):
    """Verifies wpa_supplicant generation for WPA2/WPA3-PSK networks."""
    conf_path = str(tmp_path / "wpa_supplicant.conf")
    spec = {"ssid": "District-Staff-WPA", "security": "psk", "psk": "SecretPresharedKey99"}

    with patch("reconciler.run_cmd", return_value=True):
        reconcile_wifi(spec, "wlan0", conf_path)

    assert os.path.exists(conf_path)
    with open(conf_path, "r") as f:
        content = f.read()
        assert 'ssid="District-Staff-WPA"' in content
        assert 'psk="SecretPresharedKey99"' in content
        assert "key_mgmt=WPA-PSK" in content

def test_08_reconcile_wifi_eap_peap_network(tmp_path):
    """Verifies wpa_supplicant generation for 802.1X Enterprise PEAP networks."""
    conf_path = str(tmp_path / "wpa_supplicant.conf")
    spec = {
        "ssid": "District-Secure-EAP",
        "security": "eap-peap",
        "username": "sensor_svc_account",
        "password": "EapRadiusPassword88"
    }

    with patch("reconciler.run_cmd", return_value=True):
        reconcile_wifi(spec, "wlan0", conf_path)

    assert os.path.exists(conf_path)
    with open(conf_path, "r") as f:
        content = f.read()
        assert 'ssid="District-Secure-EAP"' in content
        assert "key_mgmt=WPA-EAP" in content
        assert "eap=PEAP" in content
        assert 'identity="sensor_svc_account"' in content
        assert 'password="EapRadiusPassword88"' in content
        assert 'phase2="auth=MSCHAPV2"' in content

# --- 4. Container Management & Safety Tests ---

def test_09_container_empty_spec_safety_threshold():
    """Verifies safety threshold: empty container spec from CMP must NOT wipe host containers."""
    mock_stop = MagicMock()
    with patch("reconciler.get_running_containers", return_value={"prom-agent": {"image": "prom:v1"}}), \
         patch("reconciler.stop_and_remove_container", mock_stop):
        reconcile_containers({})
        # mock_stop should NOT have been called
        assert mock_stop.call_count == 0

def test_10_container_reconciliation_image_upgrade():
    """Verifies that an image tag mismatch triggers stop, pull, and recreate."""
    mock_stop = MagicMock()
    mock_pull = MagicMock()
    mock_start = MagicMock()

    running = {"blackbox-exporter": {"image": "prom/blackbox-exporter:v0.24.0", "id": "abc123"}}
    target = {"blackbox-exporter": {"image": "prom/blackbox-exporter:v0.25.0"}}

    with patch("reconciler.get_running_containers", return_value=running), \
         patch("reconciler.get_all_container_names", return_value={"blackbox-exporter"}), \
         patch("reconciler.stop_and_remove_container", mock_stop), \
         patch("reconciler.pull_image", mock_pull), \
         patch("reconciler.start_container", mock_start), \
         patch("reconciler.run_cmd", return_value=True):
        reconcile_containers(target)
        assert mock_stop.call_count == 1
        assert mock_pull.call_count == 1
        assert mock_start.call_count == 1

# --- 5. Adaptive Resolution State Machine Tests ---

def test_11_adaptive_resolution_engine_transitions():
    """Verifies dynamic state transitions: GREEN -> AMBER -> RED -> BLACKOUT -> ON_DEMAND."""
    cfg = {"check_interval_seconds": 15}
    engine = AdaptiveResolutionEngine(cfg)

    # 1. Healthy gateway (low latency <80ms) -> GREEN (15s interval)
    with patch.object(engine, "check_gateway_reachability", return_value=(True, 12.5)):
        state = engine.evaluate_state()
        assert state == "GREEN"
        assert engine.get_sleep_interval() == 15

    # 2. High gateway latency (>80ms) -> AMBER (5s interval)
    with patch.object(engine, "check_gateway_reachability", return_value=(True, 125.0)):
        state = engine.evaluate_state()
        assert state == "AMBER"
        assert engine.get_sleep_interval() == 5

    # 3. Gateway unreachable (1 failure) -> RED (1s burst)
    with patch.object(engine, "check_gateway_reachability", return_value=(False, 0.0)):
        state = engine.evaluate_state()
        assert state == "RED"
        assert engine.get_sleep_interval() == 1

    # 4. Gateway unreachable (3 consecutive failures) -> BLACKOUT (300s dampened interval)
    with patch.object(engine, "check_gateway_reachability", return_value=(False, 0.0)):
        engine.evaluate_state() # 2nd fail
        state = engine.evaluate_state() # 3rd fail
        assert state == "BLACKOUT"
        assert engine.get_sleep_interval() == 300

    # 5. Remote ON_DEMAND command override
    state = engine.evaluate_state(commanded_state="ON_DEMAND")
    assert state == "ON_DEMAND"
    assert engine.get_sleep_interval() == 1

# --- 6. Unified Schedules & PCAP Synchronization Tests ---

def test_12_reconcile_unified_schedules_atomic_write(tmp_path):
    """Verifies that reconcile_unified_schedules writes json config properly."""
    sched_list = [
        {
            "id": "sched_1",
            "name": "CAASPP Morning Sweep",
            "probe_id": "caaspp_readiness",
            "mode": "daily_once",
            "days_of_week": ["mon", "tue", "wed", "thu", "fri"],
            "start_time": "07:15"
        }
    ]

    with patch("os.makedirs"), \
         patch("builtins.open", mock_open()) as mock_f, \
         patch("os.replace") as mock_replace:
        reconcile_unified_schedules(sched_list, {})
        assert mock_f.call_count >= 1
        assert mock_replace.call_count == 1

def test_13_reconcile_pcap_trigger_dispatch():
    """Verifies that reconcile_pcap_trigger spawns pcap_trigger.py subprocess."""
    mock_popen = MagicMock()
    with patch("subprocess.Popen", mock_popen), \
         patch("os.path.exists", return_value=True):
        reconcile_pcap_trigger({"trigger_now": True, "reason": "voip_packet_loss_spike"}, {})
        assert mock_popen.call_count == 1
        args = mock_popen.call_args[0][0]
        assert "--trigger" in args
        assert "voip_packet_loss_spike" in args
