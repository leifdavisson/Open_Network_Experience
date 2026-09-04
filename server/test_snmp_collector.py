#
# Open Network Experience (ONE) - Firewall & Security Gateway SNMP Collector Unit Tests
#
# Copyright (C) 2026 Open Network Experience Authors.
# Licensed under the GNU Affero General Public License v3.0 (AGPLv3).
# See LICENSE in the project root for full license details.
#

import os
import sys

def verifies(req_id: str):
    def decorator(fn):
        fn.__verifies__ = req_id
        return fn
    return decorator

import subprocess
import pytest
from unittest.mock import patch, MagicMock

# Ensure server directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import snmp_collector

# ============================================================================
# 1. snmp_get_value tests (CLI utility wrapping, output parsing, error handling)
# ============================================================================

def test_snmp_get_value_success_plain_float():
    """Tests successful snmpget call returning a plain float."""
    mock_res = MagicMock()
    mock_res.returncode = 0
    mock_res.stdout = "42.5\n"
    with patch("subprocess.run", return_value=mock_res) as mock_run:
        val = snmp_collector.snmp_get_value("10.0.0.1", "public", "1.3.6.1.4.1.12356.101.4.1.3.0", timeout_sec=2)
        assert val == 42.5  # nosec B101
        mock_run.assert_called_once_with(
            ["snmpget", "-v2c", "-c", "public", "-t", "2", "-Oqv", "10.0.0.1", "1.3.6.1.4.1.12356.101.4.1.3.0"],
            capture_output=True,
            text=True,
            timeout=3
        )

@pytest.mark.parametrize("stdout_val,expected_float", [
    ('Gauge32: 75\n', 75.0),
    ('INTEGER: 1200\n', 1200.0),
    ('Counter32: 987654\n', 987654.0),
    ('"55.8"\n', 55.8),
    (' Gauge32: "88.2" ', 88.2),
])
def test_snmp_get_value_type_prefixes_and_quotes(stdout_val, expected_float):
    """Tests parsing snmpget outputs with various MIB type prefixes and quotation marks."""
    mock_res = MagicMock()
    mock_res.returncode = 0
    mock_res.stdout = stdout_val
    with patch("subprocess.run", return_value=mock_res):
        val = snmp_collector.snmp_get_value("192.168.1.1", "secret", "1.2.3.4")
        assert val == pytest.approx(expected_float)  # nosec B101

def test_snmp_get_value_non_zero_returncode():
    """Tests snmpget returning a non-zero exit code (e.g. No Such Object)."""
    mock_res = MagicMock()
    mock_res.returncode = 1
    mock_res.stdout = ""
    mock_res.stderr = "No Such Instance currently exists at this OID\n"
    with patch("subprocess.run", return_value=mock_res):
        val = snmp_collector.snmp_get_value("10.0.0.1", "public", "1.2.3.4")
        assert val is None  # nosec B101

def test_snmp_get_value_timeout_or_os_exception():
    """Tests subprocess throwing TimeoutExpired or FileNotFoundError."""
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="snmpget", timeout=3)):
        val = snmp_collector.snmp_get_value("10.0.0.1", "public", "1.2.3.4")
        assert val is None  # nosec B101

    with patch("subprocess.run", side_effect=FileNotFoundError("snmpget not found")):
        val = snmp_collector.snmp_get_value("10.0.0.1", "public", "1.2.3.4")
        assert val is None  # nosec B101

def test_snmp_get_value_unparseable_string():
    """Tests handling non-numeric output string from snmpget."""
    mock_res = MagicMock()
    mock_res.returncode = 0
    mock_res.stdout = "STRING: FortiGate-VM64\n"
    with patch("subprocess.run", return_value=mock_res):
        val = snmp_collector.snmp_get_value("10.0.0.1", "public", "1.2.3.4")
        assert val is None  # nosec B101

# ============================================================================
# 2. poll_firewall tests (FortiGate, Generic Host, Conserve Mode, Reachability)
# ============================================================================

@verifies("REQ-SNMP-001")
def test_poll_firewall_fortigate_normal():
    """Tests FortiGate polling under normal operating conditions."""
    def mock_get(host, community, oid, timeout_sec=2):
        if oid == snmp_collector.FORTIGATE_OIDS["cpu"]:
            return 18.5
        elif oid == snmp_collector.FORTIGATE_OIDS["memory"]:
            return 45.0
        elif oid == snmp_collector.FORTIGATE_OIDS["sessions"]:
            return 5230.0
        return None

    with patch("snmp_collector.snmp_get_value", side_effect=mock_get):
        res = snmp_collector.poll_firewall(
            host="10.10.1.1",
            community="public",
            device_type="fortigate",
            device_name="border-fg-01"
        )
        assert res["device_name"] == "border-fg-01"  # nosec B101
        assert res["host"] == "10.10.1.1"  # nosec B101
        assert res["device_type"] == "fortigate"  # nosec B101
        assert res["is_reachable"] == 1  # nosec B101
        assert res["cpu_percent"] == 18.5  # nosec B101
        assert res["memory_percent"] == 45.0  # nosec B101
        assert res["active_sessions"] == 5230  # nosec B101
        assert res["conserve_mode"] == 0  # nosec B101

def test_poll_firewall_fortigate_conserve_mode():
    """Tests FortiGate conserve mode trigger threshold (memory >= 88.0%)."""
    def mock_get(host, community, oid, timeout_sec=2):
        if oid == snmp_collector.FORTIGATE_OIDS["cpu"]:
            return 95.0
        elif oid == snmp_collector.FORTIGATE_OIDS["memory"]:
            return 88.0  # Exactly at threshold
        elif oid == snmp_collector.FORTIGATE_OIDS["sessions"]:
            return 120000.0
        return None

    with patch("snmp_collector.snmp_get_value", side_effect=mock_get):
        res = snmp_collector.poll_firewall("10.10.1.1", "public", "fortigate", "border-fg-01")
        assert res["conserve_mode"] == 1  # nosec B101
        assert res["memory_percent"] == 88.0  # nosec B101

def test_poll_firewall_generic_host():
    """Tests Generic Host OID polling (Net-SNMP ssCpuIdle / memAvailReal)."""
    def mock_get(host, community, oid, timeout_sec=2):
        if oid == snmp_collector.GENERIC_HOST_OIDS["cpu"]:
            return 33.3
        elif oid == snmp_collector.GENERIC_HOST_OIDS["memory"]:
            return 72.1
        return None

    with patch("snmp_collector.snmp_get_value", side_effect=mock_get):
        res = snmp_collector.poll_firewall("192.168.10.254", "snmp_ro", "generic", "cisco-router")
        assert res["device_type"] == "generic"  # nosec B101
        assert res["is_reachable"] == 1  # nosec B101
        assert res["cpu_percent"] == 33.3  # nosec B101
        assert res["memory_percent"] == 72.1  # nosec B101
        assert res["active_sessions"] == 0  # nosec B101
        assert res["conserve_mode"] == 0  # nosec B101

def test_poll_firewall_unreachable_switch():
    """Tests behavior when switch or firewall is completely unreachable."""
    with patch("snmp_collector.snmp_get_value", return_value=None):
        res = snmp_collector.poll_firewall("192.0.2.1", "public", "fortigate", "offline-device")
        assert res["is_reachable"] == 0  # nosec B101
        assert res["cpu_percent"] == 0.0  # nosec B101
        assert res["memory_percent"] == 0.0  # nosec B101
        assert res["active_sessions"] == 0  # nosec B101
        assert res["conserve_mode"] == 0  # nosec B101

# ============================================================================
# 3. write_metrics & PromQL generation tests
# ============================================================================

def test_write_metrics_to_file(tmp_path):
    """Tests writing PromQL / Prometheus textfile collector metrics atomically to disk."""
    prom_file = tmp_path / "subdir" / "firewall_snmp.prom"
    metrics_data = {
        "device_name": "edge-core-gw",
        "host": "10.0.0.254",
        "device_type": "fortigate",
        "is_reachable": 1,
        "cpu_percent": 45.2,
        "memory_percent": 68.7,
        "active_sessions": 3410,
        "conserve_mode": 0
    }

    snmp_collector.write_metrics(metrics_data, str(prom_file))
    assert prom_file.exists()  # nosec B101
    content = prom_file.read_text()

    # Verify PromQL metrics format, headers, labels, and values
    assert '# HELP openux_firewall_reachable Whether the Security Gateway responds to SNMP queries (1=Up, 0=Down)' in content  # nosec B101
    assert '# TYPE openux_firewall_reachable gauge' in content  # nosec B101
    assert 'openux_firewall_reachable{device="edge-core-gw",host="10.0.0.254",type="fortigate"} 1' in content  # nosec B101
    assert 'openux_firewall_cpu_utilization_percent{device="edge-core-gw",host="10.0.0.254"} 45.2' in content  # nosec B101
    assert 'openux_firewall_memory_utilization_percent{device="edge-core-gw",host="10.0.0.254"} 68.7' in content  # nosec B101
    assert 'openux_firewall_active_sessions{device="edge-core-gw",host="10.0.0.254"} 3410' in content  # nosec B101
    assert 'openux_firewall_conserve_mode{device="edge-core-gw",host="10.0.0.254"} 0' in content  # nosec B101

def test_write_metrics_to_stdout(capsys):
    """Tests write_metrics when output_path is empty, verifying stdout emission."""
    metrics_data = {
        "device_name": "stdout-gw",
        "host": "10.1.1.1",
        "device_type": "generic",
        "is_reachable": 0,
        "cpu_percent": 0.0,
        "memory_percent": 0.0,
        "active_sessions": 0,
        "conserve_mode": 0
    }
    snmp_collector.write_metrics(metrics_data, "")
    captured = capsys.readouterr()
    assert 'openux_firewall_reachable{device="stdout-gw",host="10.1.1.1",type="generic"} 0' in captured.out  # nosec B101
    assert 'openux_firewall_cpu_utilization_percent{device="stdout-gw",host="10.1.1.1"} 0.0' in captured.out  # nosec B101

# ============================================================================
# 4. main() CLI entrypoint execution tests
# ============================================================================

def test_main_cli_online(tmp_path, capsys):
    """Tests executing main() CLI with custom arguments when target is online."""
    out_file = tmp_path / "firewall.prom"
    test_args = [
        "snmp_collector.py",
        "--host", "10.200.1.1",
        "--community", "secret-comm",
        "--device-name", "noc-firewall-01",
        "--device-type", "fortigate",
        "--output", str(out_file)
    ]

    mock_metrics = {
        "device_name": "noc-firewall-01",
        "host": "10.200.1.1",
        "device_type": "fortigate",
        "is_reachable": 1,
        "cpu_percent": 15.0,
        "memory_percent": 42.0,
        "active_sessions": 2048,
        "conserve_mode": 0
    }

    with patch("sys.argv", test_args):
        with patch("snmp_collector.poll_firewall", return_value=mock_metrics) as mock_poll:
            snmp_collector.main()
            mock_poll.assert_called_once_with(
                host="10.200.1.1",
                community="secret-comm",
                device_type="fortigate",
                device_name="noc-firewall-01"
            )
            assert out_file.exists()  # nosec B101
            captured = capsys.readouterr()
            assert "ONLINE" in captured.out  # nosec B101
            assert "CPU: 15.0%" in captured.out  # nosec B101

def test_main_cli_unreachable(tmp_path, capsys):
    """Tests executing main() CLI when target device is unreachable."""
    out_file = tmp_path / "firewall_down.prom"
    test_args = [
        "snmp_collector.py",
        "--host", "192.0.2.55",
        "--device-name", "dead-firewall",
        "--output", str(out_file)
    ]

    mock_metrics = {
        "device_name": "dead-firewall",
        "host": "192.0.2.55",
        "device_type": "fortigate",
        "is_reachable": 0,
        "cpu_percent": 0.0,
        "memory_percent": 0.0,
        "active_sessions": 0,
        "conserve_mode": 0
    }

    with patch("sys.argv", test_args):
        with patch("snmp_collector.poll_firewall", return_value=mock_metrics):
            snmp_collector.main()
            captured = capsys.readouterr()
            assert "UNREACHABLE" in captured.out  # nosec B101
            assert out_file.exists()  # nosec B101
