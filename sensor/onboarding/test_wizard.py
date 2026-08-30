#
# Open Network Experience (ONE) - Sensor Onboarding Wizard Unit Tests
#
# Copyright (C) 2026 Open Network Experience Authors.
# Licensed under the GNU Affero General Public License v3.0 (AGPLv3).
# See LICENSE in the project root for full license details.
#

import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock, mock_open
import urllib.error

# Add sensor and onboarding paths
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import wizard

def test_inspect_hardware():
    """Validates hardware and system diagnostic inspection."""
    hw = wizard.inspect_hardware()
    assert "hostname" in hw
    assert "os" in hw
    assert "cpu_cores" in hw
    assert hw["cpu_cores"] >= 1
    assert "memory_gb" in hw
    assert "disk_free_gb" in hw
    assert "interfaces" in hw
    assert isinstance(hw["interfaces"], list)

def test_get_machine_uuid():
    """Validates machine UUID detection from /etc/machine-id or generated fallback."""
    with patch("os.path.exists", side_effect=lambda p: p == "/etc/machine-id"):
        with patch("builtins.open", mock_open(read_data="test-system-machine-id-12345")):
            uuid_val = wizard.get_machine_uuid()
            assert uuid_val == "test-system-machine-id-12345"

def test_get_primary_mac_and_ip():
    """Validates MAC address and IP extraction."""
    mac, ip, iface = wizard.get_primary_mac_and_ip()
    assert isinstance(mac, str)
    assert len(mac.split(":")) == 6
    assert isinstance(ip, str)
    assert isinstance(iface, str)

def test_discover_cmp_endpoints_from_config(tmp_path):
    """Validates discovering CMP endpoint from existing configuration."""
    cfg_file = tmp_path / "reconciler.json"
    cfg_file.write_text(json.dumps({"cmp_url": "http://10.98.2.125:8000/api/v1"}))

    with patch("wizard.CONFIG_PATH", str(cfg_file)):
        candidates = wizard.discover_cmp_endpoints()
        assert len(candidates) >= 1
        assert any(c["url"] == "http://10.98.2.125:8000/api/v1" for c in candidates)

def test_test_cmp_connectivity_success():
    """Validates CMP connectivity testing when server responds OK."""
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        healthy, status_msg, latency = wizard.test_cmp_connectivity("http://cmp.test.local:8000/api/v1")
        assert healthy is True
        assert "HTTP 200 OK" in status_msg
        assert latency >= 0

def test_test_cmp_connectivity_failure():
    """Validates CMP connectivity testing when server is unreachable."""
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
        healthy, status_msg, latency = wizard.test_cmp_connectivity("http://192.0.2.1:8000/api/v1", timeout=0.1)
        assert healthy is False
        assert "refused" in status_msg.lower() or "timed out" in status_msg.lower()

def test_register_sensor_direct_approved():
    """Validates sensor registration handling when CMP returns approved."""
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = json.dumps({
        "status": "approved",
        "api_key": "key_approved_secret_token_123"
    }).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        result = wizard.register_sensor_direct(
            cmp_url="http://cmp.test.local:8000/api/v1",
            sensor_id="sensor-test-01",
            hostname="pi-sensor-01",
            mac_address="b8:27:eb:11:22:33",
            location={"district": "District", "site": "High School", "room": "204"}
        )
        assert result["success"] is True
        assert result["status"] == "approved"
        assert result["api_key"] == "key_approved_secret_token_123"

def test_register_sensor_direct_pending():
    """Validates sensor registration handling when CMP returns pending approval."""
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = json.dumps({
        "status": "pending",
        "api_key": None
    }).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        result = wizard.register_sensor_direct(
            cmp_url="http://cmp.test.local:8000/api/v1",
            sensor_id="sensor-test-02",
            hostname="pi-sensor-02",
            mac_address="b8:27:eb:44:55:66",
            location={"district": "District", "site": "Middle School", "room": "101"}
        )
        assert result["success"] is True
        assert result["status"] == "pending"
        assert result["api_key"] is None

def test_save_sensor_configuration(tmp_path):
    """Validates saving reconciler.json file."""
    test_path = tmp_path / "sensor" / "reconciler.json"
    cfg = {
        "cmp_url": "http://cmp.test:8000/api/v1",
        "sensor_id": "test-sensor-abc",
        "api_key": "key-123",
        "initial_location": {
            "district": "Test District",
            "site": "Test Campus",
            "room": "Room 101"
        }
    }
    assert wizard.save_sensor_configuration(cfg, path=str(test_path)) is True
    assert test_path.exists()
    loaded = json.loads(test_path.read_text())
    assert loaded["sensor_id"] == "test-sensor-abc"
    assert loaded["initial_location"]["room"] == "Room 101"

def test_configure_wpa_supplicant(tmp_path):
    """Validates generating wpa_supplicant.conf file."""
    wpa_path = tmp_path / "wpa_supplicant.conf"
    assert wizard.configure_wpa_supplicant(
        ssid="School-Staff-IoT",
        psk="SecretPassword99!",
        security="psk",
        config_path=str(wpa_path)
    ) is True
    assert wpa_path.exists()
    content = wpa_path.read_text()
    assert 'ssid="School-Staff-IoT"' in content
    assert 'psk="SecretPassword99!"' in content
    assert 'key_mgmt=WPA-PSK' in content

def test_run_non_interactive_batch(tmp_path, capsys):
    """Validates batch non-interactive provisioning via CLI flags."""
    test_cfg_path = tmp_path / "reconciler.json"

    mock_args = MagicMock()
    mock_args.cmp = "http://10.98.2.125:8000/api/v1"
    mock_args.sensor_id = "test-batch-uuid"
    mock_args.site = "Lincoln High School"
    mock_args.building = "Building C"
    mock_args.room = "Library Drop 01"
    mock_args.district = "Unified District"
    mock_args.notes = "Asset #9941"
    mock_args.token = "ztp-secret-token"
    mock_args.wifi_ssid = None
    mock_args.wifi_psk = None
    mock_args.non_interactive = True
    mock_args.check_only = False
    mock_args.json = True

    with patch("wizard.CONFIG_PATH", str(test_cfg_path)):
        with patch("wizard.register_sensor_direct", return_value={"success": True, "status": "approved", "api_key": "key_xyz"}):
            with patch("wizard.is_root", return_value=False):
                wizard.run_non_interactive(mock_args)
                captured = capsys.readouterr()
                out = json.loads(captured.out)
                assert out["sensor_id"] == "test-batch-uuid"
                assert out["location"]["site"] == "Lincoln High School"
                assert out["location"]["room"] == "Library Drop 01"
                assert out["registration"]["status"] == "approved"
                assert test_cfg_path.exists()
