#
# Open Network Experience (ONE) - USB Auto-Provisioner Unit Tests
#
# Copyright (C) 2026 Open Network Experience Authors.
# Licensed under the GNU Affero General Public License v3.0 (AGPLv3).
# See LICENSE in the project root for full license details.
#

import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock

# Add sensor and onboarding paths
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import usb_provisioner

def test_find_usb_bootstrap_config(tmp_path):
    """Validates locating one-bootstrap.json in a directory."""
    usb_dir = tmp_path / "fake_usb"
    usb_dir.mkdir()
    cfg_file = usb_dir / "one-bootstrap.json"
    cfg_file.write_text(json.dumps({"cmp_url": "http://10.98.2.125:8000/api/v1"}))

    found = usb_provisioner.find_usb_bootstrap_config(str(usb_dir))
    assert found is not None
    assert found[0] == str(cfg_file)
    assert found[1] == str(usb_dir)

def test_parse_bootstrap_file(tmp_path):
    """Validates parsing bootstrap config and applying schema defaults."""
    cfg_file = tmp_path / "one-bootstrap.json"
    cfg_file.write_text(json.dumps({
        "cmp_url": "http://cmp.school.edu:8000/api/v1",
        "location": {
            "site": "East High",
            "room": "Room 301"
        },
        "wifi": {
            "ssid": "School-Staff-IoT",
            "psk": "Pass123"
        }
    }))

    parsed = usb_provisioner.parse_bootstrap_file(str(cfg_file))
    assert parsed["cmp_url"] == "http://cmp.school.edu:8000/api/v1"
    assert parsed["location"]["site"] == "East High"
    assert parsed["location"]["room"] == "Room 301"
    assert parsed["location"]["district"] == "Kern County Superintendent of Schools"
    assert parsed["wifi"]["ssid"] == "School-Staff-IoT"

def test_pop_next_room_from_pool(tmp_path):
    """Validates sequential room pool popping and updating JSON on the USB drive."""
    cfg_file = tmp_path / "one-bootstrap.json"
    initial_data = {
        "cmp_url": "http://cmp:8000/api/v1",
        "location": {"site": "West High", "room": "Default"},
        "room_pool": ["Room 101", "Room 102", "Room 103"]
    }
    cfg_file.write_text(json.dumps(initial_data, indent=4))

    parsed = usb_provisioner.parse_bootstrap_file(str(cfg_file))

    # 1st run -> Room 101
    assigned_1 = usb_provisioner.pop_next_room_from_pool(str(cfg_file), parsed)
    assert assigned_1 == "Room 101"

    # Verify file updated on disk
    updated_1 = json.loads(cfg_file.read_text())
    assert updated_1["room_pool"] == ["Room 102", "Room 103"]

    # 2nd run -> Room 102
    parsed_2 = usb_provisioner.parse_bootstrap_file(str(cfg_file))
    assigned_2 = usb_provisioner.pop_next_room_from_pool(str(cfg_file), parsed_2)
    assert assigned_2 == "Room 102"

    updated_2 = json.loads(cfg_file.read_text())
    assert updated_2["room_pool"] == ["Room 103"]

def test_configure_wifi_wpa(tmp_path):
    """Validates writing wpa_supplicant.conf from USB Wi-Fi spec."""
    wpa_path = tmp_path / "wpa_supplicant.conf"
    wifi_spec = {
        "ssid": "District-IoT-Corp",
        "security": "psk",
        "psk": "PresharedSecretKey88"
    }

    assert usb_provisioner.configure_wifi_wpa(wifi_spec, config_path=str(wpa_path)) is True
    assert wpa_path.exists()
    content = wpa_path.read_text()
    assert 'ssid="District-IoT-Corp"' in content
    assert 'psk="PresharedSecretKey88"' in content
    assert 'key_mgmt=WPA-PSK' in content

def test_deploy_bundled_probe_scripts(tmp_path):
    """Validates copying bundled probe scripts from USB directory."""
    usb_dir = tmp_path / "usb"
    usb_dir.mkdir()
    target_bin = tmp_path / "bin"
    target_bin.mkdir()

    # Create dummy probe scripts on fake USB
    (usb_dir / "reconciler.py").write_text("#!/usr/bin/env python3\n# Reconciler")
    (usb_dir / "wizard.py").write_text("#!/usr/bin/env python3\n# Wizard")

    count = usb_provisioner.deploy_bundled_probe_scripts(str(usb_dir), target_bin_dir=str(target_bin))
    assert count == 2
    assert (target_bin / "reconciler.py").exists()
    assert (target_bin / "wizard.py").exists()
    assert (target_bin / "one-wizard").exists() # Symlink

def test_append_usb_inventory_receipt(tmp_path):
    """Validates logging provisioning receipt to CSV and log file."""
    usb_dir = tmp_path / "usb"
    usb_dir.mkdir()

    loc = {
        "district": "Test District",
        "site": "Lincoln High",
        "building": "Main",
        "room": "Room 204",
        "notes": "Assembly Staging"
    }

    assert usb_provisioner.append_usb_inventory_receipt(
        usb_root=str(usb_dir),
        sensor_id="sensor-uuid-12345",
        hostname="pi5-lincoln-01",
        mac_address="b8:27:eb:aa:bb:cc",
        ip_address="10.200.4.88",
        location=loc,
        cmp_status="APPROVED_ZTP",
        log_msg="All 12 probes deployed."
    ) is True

    csv_file = usb_dir / "provisioned_sensors.csv"
    log_file = usb_dir / "one-provision-status.log"

    assert csv_file.exists()
    assert log_file.exists()

    csv_text = csv_file.read_text()
    assert "Sensor_UUID,Hostname,Primary_MAC" in csv_text
    assert "sensor-uuid-12345" in csv_text
    assert "b8:27:eb:aa:bb:cc" in csv_text
    assert "Lincoln High" in csv_text
    assert "Room 204" in csv_text
    assert "APPROVED_ZTP" in csv_text

    log_text = log_file.read_text()
    assert "sensor-uuid-12345" in log_text
    assert "APPROVED_ZTP" in log_text

def test_run_usb_provisioning_full_flow(tmp_path):
    """Validates full end-to-end flow of run_usb_provisioning."""
    usb_dir = tmp_path / "usb"
    usb_dir.mkdir()
    cfg_file = usb_dir / "one-bootstrap.json"
    cfg_file.write_text(json.dumps({
        "cmp_url": "http://10.98.2.125:8000/api/v1",
        "location": {"site": "Oak High School", "room": "Room 101"},
        "auto_eject_and_sync": False
    }))

    mock_reg = {"success": True, "status": "approved", "api_key": "key_secret_abc"}

    with patch("usb_provisioner.register_sensor_with_cmp", return_value=mock_reg):
        with patch("usb_provisioner.is_root", return_value=False):
            with patch("usb_provisioner.CONFIG_PATH", str(tmp_path / "reconciler.json")):
                res = usb_provisioner.run_usb_provisioning(search_dir=str(usb_dir), check_only=False, json_output=False)
                assert res["success"] is True
                assert res["location"]["site"] == "Oak High School"
                assert res["cmp_status"] == "APPROVED_ZTP"
                assert (usb_dir / "provisioned_sensors.csv").exists()
