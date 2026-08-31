#!/usr/bin/env python3
# License: GNU AGPLv3 (GNU Affero General Public License v3.0)
"""
High-Assurance Unit Test Suite for Scheduled Bandwidth & Throughput Tester
Target: sensor/iperf3_runner.py

Verifies:
  - Time window calculation for standard business hours, overnight windows, and invalid formats
  - Interface IPv4 retrieval and exception handling
  - iperf3 client execution: TCP, UDP, reverse, bandwidth capping, timeout, and process errors
  - Prometheus metric atomic emission and stdout fallback
  - Comprehensive safety guardrail enforcement and CLI execution:
      * Instructional hours lockout (-1 status)
      * Thermal protection (-2 status)
      * Preflight congestion backoff (-3 status)
      * Parameter clamping (bandwidth / duration limits)
      * Force override bypass
      * Dual-interface execution (wired and wireless) with anti-contention cooldown
      * Missing IP address handling
"""

import os
import sys
import json
import time
import datetime
import tempfile
import unittest
import subprocess
from unittest.mock import patch, MagicMock, call

# Ensure sensor directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

def verifies(req_id: str):
    """Decorator to mark requirements traceability ID."""
    def decorator(fn):
        fn.__verifies__ = req_id
        return fn
    return decorator

import iperf3_runner


class TestIperf3Runner(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.prom_file = os.path.join(self.test_dir.name, "iperf3.prom")

    def tearDown(self):
        self.test_dir.cleanup()

    # =========================================================================
    # 1. Allowed Hours Window Verification Tests
    # =========================================================================

    @verifies("REQ-PRB-011")
    def test_is_within_allowed_hours_none_or_empty(self):
        """Verifies that empty or None allowed_hours implies unconstrained maintenance."""
        self.assertTrue(iperf3_runner.is_within_allowed_hours(None))
        self.assertTrue(iperf3_runner.is_within_allowed_hours([]))

    @verifies("REQ-PRB-011")
    def test_is_within_allowed_hours_normal_window(self):
        """Verifies standard intraday window evaluation (e.g. 08:00 to 17:00)."""
        windows = ["08:00-17:00"]

        # Inside window
        with patch("datetime.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = datetime.time(12, 0)
            self.assertTrue(iperf3_runner.is_within_allowed_hours(windows))

        # At start boundary
        with patch("datetime.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = datetime.time(8, 0)
            self.assertTrue(iperf3_runner.is_within_allowed_hours(windows))

        # At end boundary
        with patch("datetime.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = datetime.time(17, 0)
            self.assertTrue(iperf3_runner.is_within_allowed_hours(windows))

        # Before start
        with patch("datetime.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = datetime.time(7, 59)
            self.assertFalse(iperf3_runner.is_within_allowed_hours(windows))

        # After end
        with patch("datetime.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = datetime.time(17, 1)
            self.assertFalse(iperf3_runner.is_within_allowed_hours(windows))

    @verifies("REQ-PRB-011")
    def test_is_within_allowed_hours_overnight_window(self):
        """Verifies overnight maintenance window crossing midnight (e.g. 20:00 to 06:00)."""
        windows = ["20:00-06:00"]

        # Late night (22:00)
        with patch("datetime.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = datetime.time(22, 0)
            self.assertTrue(iperf3_runner.is_within_allowed_hours(windows))

        # Early morning (04:00)
        with patch("datetime.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = datetime.time(4, 0)
            self.assertTrue(iperf3_runner.is_within_allowed_hours(windows))

        # At start boundary (20:00)
        with patch("datetime.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = datetime.time(20, 0)
            self.assertTrue(iperf3_runner.is_within_allowed_hours(windows))

        # At end boundary (06:00)
        with patch("datetime.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = datetime.time(6, 0)
            self.assertTrue(iperf3_runner.is_within_allowed_hours(windows))

        # Daytime outside window (12:00)
        with patch("datetime.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = datetime.time(12, 0)
            self.assertFalse(iperf3_runner.is_within_allowed_hours(windows))

        # Just before start (19:59)
        with patch("datetime.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = datetime.time(19, 59)
            self.assertFalse(iperf3_runner.is_within_allowed_hours(windows))

        # Just after end (06:01)
        with patch("datetime.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = datetime.time(6, 1)
            self.assertFalse(iperf3_runner.is_within_allowed_hours(windows))

    @verifies("REQ-PRB-011")
    def test_is_within_allowed_hours_multiple_and_malformed(self):
        """Verifies multi-window matching and graceful handling of malformed window strings."""
        # Multiple windows
        multi_windows = ["08:00-10:00", "20:00-22:00"]
        with patch("datetime.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = datetime.time(9, 0)
            self.assertTrue(iperf3_runner.is_within_allowed_hours(multi_windows))
        with patch("datetime.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = datetime.time(21, 0)
            self.assertTrue(iperf3_runner.is_within_allowed_hours(multi_windows))
        with patch("datetime.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = datetime.time(14, 0)
            self.assertFalse(iperf3_runner.is_within_allowed_hours(multi_windows))

        # Malformed strings
        with patch("datetime.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = datetime.time(12, 0)
            self.assertFalse(iperf3_runner.is_within_allowed_hours(["invalid-window", "99:99-88:88", "12:00"]))

    # =========================================================================
    # 2. Interface IP Discovery Tests
    # =========================================================================

    @verifies("REQ-PRB-011")
    @patch("subprocess.check_output")
    def test_get_interface_ip_success(self, mock_check_output):
        """Verifies IPv4 address parsing from `ip -4 addr show <interface>` output."""
        sample_output = (
            "2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP group default qlen 1000\n"
            "    inet 10.142.10.45/24 brd 10.142.10.255 scope global dynamic eth0\n"
            "       valid_lft 86321sec preferred_lft 86321sec\n"
        )
        mock_check_output.return_value = sample_output

        ip = iperf3_runner.get_interface_ip("eth0")
        self.assertEqual(ip, "10.142.10.45")
        mock_check_output.assert_called_once_with(
            ["ip", "-4", "addr", "show", "eth0"],
            stderr=subprocess.DEVNULL,
            text=True
        )

    @verifies("REQ-PRB-011")
    @patch("subprocess.check_output")
    def test_get_interface_ip_no_inet_line(self, mock_check_output):
        """Verifies None returned when interface has no IPv4 assigned."""
        sample_output = "3: wlan0: <NO-CARRIER,BROADCAST,MULTICAST,UP> mtu 1500 qdisc noqueue state DOWN group default\n"
        mock_check_output.return_value = sample_output

        ip = iperf3_runner.get_interface_ip("wlan0")
        self.assertIsNone(ip)

    @verifies("REQ-PRB-011")
    @patch("subprocess.check_output", side_effect=subprocess.CalledProcessError(1, "ip"))
    def test_get_interface_ip_subprocess_error(self, mock_check_output):
        """Verifies graceful None handling when ip command raises CalledProcessError or OSError."""
        ip = iperf3_runner.get_interface_ip("nonexistent0")
        self.assertIsNone(ip)

    # =========================================================================
    # 3. iperf3 Test Execution Tests
    # =========================================================================

    @verifies("REQ-PRB-011")
    @patch("subprocess.run")
    def test_run_iperf3_test_tcp_success(self, mock_run):
        """Verifies standard TCP throughput test execution and metric calculations."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "end": {
                "sum_sent": {
                    "bits_per_second": 95400000.0,
                    "retransmits": 4
                },
                "sum_received": {
                    "bits_per_second": 94800000.0
                }
            }
        })
        mock_run.return_value = mock_result

        res = iperf3_runner.run_iperf3_test(
            server="192.168.1.1",
            port=5201,
            duration=10,
            bandwidth_cap_mbps=100,
            bind_ip="10.142.10.45",
            protocol="tcp",
            reverse=False
        )

        expected_cmd = [
            "iperf3", "-c", "192.168.1.1", "-p", "5201", "-t", "10", "-J",
            "-B", "10.142.10.45", "-b", "100M"
        ]
        mock_run.assert_called_once_with(expected_cmd, capture_output=True, text=True, timeout=25)

        self.assertTrue(res["success"])
        self.assertEqual(res["tx_mbps"], 95.4)
        self.assertEqual(res["rx_mbps"], 94.8)
        self.assertEqual(res["retransmits"], 4)
        self.assertEqual(res["protocol"], "tcp")

    @verifies("REQ-PRB-011")
    @patch("subprocess.run")
    def test_run_iperf3_test_udp_success(self, mock_run):
        """Verifies UDP throughput test with jitter and packet loss capture."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "end": {
                "sum_sent": {
                    "bits_per_second": 50000000.0
                },
                "sum_received": {
                    "bits_per_second": 49950000.0
                },
                "sum": {
                    "jitter_ms": 1.236,
                    "lost_percent": 0.052
                }
            }
        })
        mock_run.return_value = mock_result

        res = iperf3_runner.run_iperf3_test(
            server="10.0.0.1",
            protocol="udp",
            reverse=True
        )

        # Check that -u and -R are in the command
        called_cmd = mock_run.call_args[0][0]
        self.assertIn("-u", called_cmd)
        self.assertIn("-R", called_cmd)

        self.assertTrue(res["success"])
        self.assertEqual(res["tx_mbps"], 50.0)
        self.assertEqual(res["rx_mbps"], 49.95)
        self.assertEqual(res["jitter_ms"], 1.236)
        self.assertEqual(res["lost_percent"], 0.05)
        self.assertEqual(res["protocol"], "udp")

    @verifies("REQ-PRB-011")
    @patch("subprocess.run")
    def test_run_iperf3_test_unlimited_bandwidth(self, mock_run):
        """Verifies that bandwidth cap flag is omitted when bandwidth_cap_mbps is 0 or None."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"end": {}})
        mock_run.return_value = mock_result

        iperf3_runner.run_iperf3_test(server="10.0.0.1", bandwidth_cap_mbps=0)
        called_cmd = mock_run.call_args[0][0]
        self.assertNotIn("-b", called_cmd)

    @verifies("REQ-PRB-011")
    @patch("subprocess.run")
    def test_run_iperf3_test_process_failure(self, mock_run):
        """Verifies error result when iperf3 exits with non-zero returncode."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "error - unable to connect to server: Connection refused\n"
        mock_run.return_value = mock_result

        res = iperf3_runner.run_iperf3_test(server="10.0.0.1")
        self.assertFalse(res["success"])
        self.assertIn("Connection refused", res["error"])

        # Stderr empty fallback
        mock_result.stderr = ""
        res_empty_err = iperf3_runner.run_iperf3_test(server="10.0.0.1")
        self.assertFalse(res_empty_err["success"])
        self.assertEqual(res_empty_err["error"], "iperf3 execution failed")

    @verifies("REQ-PRB-011")
    @patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="iperf3", timeout=25))
    def test_run_iperf3_test_timeout_expired(self, mock_run):
        """Verifies timeout handling when iperf3 hangs."""
        res = iperf3_runner.run_iperf3_test(server="10.0.0.1")
        self.assertFalse(res["success"])
        self.assertEqual(res["error"], "Test timed out")

    @verifies("REQ-PRB-011")
    @patch("subprocess.run")
    def test_run_iperf3_test_malformed_json_exception(self, mock_run):
        """Verifies generic exception handling when iperf3 outputs malformed JSON."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Malformed non-JSON output"
        mock_run.return_value = mock_result

        res = iperf3_runner.run_iperf3_test(server="10.0.0.1")
        self.assertFalse(res["success"])
        self.assertIn("Expecting value", res["error"])

    # =========================================================================
    # 4. Metrics Output Tests
    # =========================================================================

    @verifies("REQ-PRB-011")
    def test_write_metrics_atomic_file(self):
        """Verifies atomic Prometheus file writing."""
        lines = [
            "# HELP openux_iperf3_throughput_tx_mbps Outbound bandwidth",
            "# TYPE openux_iperf3_throughput_tx_mbps gauge",
            'openux_iperf3_throughput_tx_mbps{interface="eth0",server="10.0.0.1"} 95.4'
        ]
        iperf3_runner.write_metrics(lines, self.prom_file)

        self.assertTrue(os.path.exists(self.prom_file))
        with open(self.prom_file, "r") as f:
            content = f.read()
        self.assertIn("openux_iperf3_throughput_tx_mbps", content)
        self.assertIn('interface="eth0"', content)

    @verifies("REQ-PRB-011")
    def test_write_metrics_stdout_fallback(self):
        """Verifies stdout printing when output_file is empty."""
        lines = ['openux_iperf3_test_status{interface="eth0"} 1']
        with patch("builtins.print") as mock_print:
            iperf3_runner.write_metrics(lines, output_file="")
            mock_print.assert_called_once()
            self.assertIn("openux_iperf3_test_status", mock_print.call_args[0][0])

    # =========================================================================
    # 5. CLI Execution & Guardrail Enforcement Tests
    # =========================================================================

    @verifies("REQ-PRB-011")
    @patch("iperf3_runner.NetworkSafetyGuardrails")
    @patch("iperf3_runner.write_metrics")
    def test_cli_instructional_lockout_guardrail(self, mock_write, mock_guardrails):
        """Verifies CLI aborts with status -1 when instructional lockout is active."""
        mock_guardrails.check_instructional_lockout.return_value = (False, "Classroom session active")
        test_args = ["iperf3_runner.py", "--server", "10.0.0.1", "--interfaces", "eth0", "wlan0"]

        with patch.object(sys, "argv", test_args):
            iperf3_runner.main()

        mock_write.assert_called_once()
        prom_lines = mock_write.call_args[0][0]
        self.assertTrue(any('openux_iperf3_test_status{interface="eth0",server="10.0.0.1"} -1' in line for line in prom_lines))
        self.assertTrue(any('openux_iperf3_test_status{interface="wlan0",server="10.0.0.1"} -1' in line for line in prom_lines))

    @verifies("REQ-PRB-011")
    @patch("iperf3_runner.NetworkSafetyGuardrails")
    @patch("iperf3_runner.write_metrics")
    def test_cli_thermal_safety_guardrail(self, mock_write, mock_guardrails):
        """Verifies CLI aborts with status -2 when device temperature exceeds safe limit."""
        mock_guardrails.check_instructional_lockout.return_value = (True, "OK")
        mock_guardrails.check_thermal_safety.return_value = (False, 88.5, "Overheating threshold exceeded")
        test_args = ["iperf3_runner.py", "--server", "10.0.0.1", "--interfaces", "eth0"]

        with patch.object(sys, "argv", test_args):
            iperf3_runner.main()

        mock_write.assert_called_once()
        prom_lines = mock_write.call_args[0][0]
        self.assertTrue(any('openux_iperf3_test_status{interface="eth0",server="10.0.0.1"} -2' in line for line in prom_lines))

    @verifies("REQ-PRB-011")
    @patch("iperf3_runner.NetworkSafetyGuardrails")
    @patch("iperf3_runner.write_metrics")
    def test_cli_preflight_congestion_guardrail(self, mock_write, mock_guardrails):
        """Verifies CLI aborts with status -3 when upstream congestion is detected."""
        mock_guardrails.check_instructional_lockout.return_value = (True, "OK")
        mock_guardrails.check_thermal_safety.return_value = (True, 45.0, "OK")
        mock_guardrails.check_preflight_congestion.return_value = (False, "High link latency detected", 250.0, 15.0)
        test_args = ["iperf3_runner.py", "--server", "10.0.0.1", "--interfaces", "eth0"]

        with patch.object(sys, "argv", test_args):
            iperf3_runner.main()

        mock_write.assert_called_once()
        prom_lines = mock_write.call_args[0][0]
        self.assertTrue(any('openux_iperf3_test_status{interface="eth0",server="10.0.0.1"} -3' in line for line in prom_lines))

    @verifies("REQ-PRB-011")
    @patch("iperf3_runner.is_within_allowed_hours", return_value=False)
    @patch("iperf3_runner.NetworkSafetyGuardrails")
    @patch("iperf3_runner.write_metrics")
    def test_cli_outside_allowed_hours(self, mock_write, mock_guardrails, mock_allowed):
        """Verifies CLI aborts with status -1 when current time is outside allowed maintenance window."""
        mock_guardrails.check_instructional_lockout.return_value = (True, "OK")
        mock_guardrails.check_thermal_safety.return_value = (True, 45.0, "OK")
        mock_guardrails.check_preflight_congestion.return_value = (True, "OK", 10.0, 0.0)
        mock_guardrails.clamp_parameters.return_value = (100, 10)
        test_args = ["iperf3_runner.py", "--server", "10.0.0.1", "--allowed-hours", "22:00-05:00", "--interfaces", "eth0"]

        with patch.object(sys, "argv", test_args):
            iperf3_runner.main()

        mock_write.assert_called_once()
        prom_lines = mock_write.call_args[0][0]
        self.assertTrue(any('openux_iperf3_test_status{interface="eth0",server="10.0.0.1"} -1' in line for line in prom_lines))

    @verifies("REQ-PRB-011")
    @patch("iperf3_runner.time.sleep")
    @patch("iperf3_runner.run_iperf3_test")
    @patch("iperf3_runner.get_interface_ip")
    @patch("iperf3_runner.NetworkSafetyGuardrails")
    @patch("iperf3_runner.write_metrics")
    def test_cli_full_dual_nic_success(self, mock_write, mock_guardrails, mock_get_ip, mock_run_test, mock_sleep):
        """Verifies full execution across wired and wireless NICs with parameter clamping and sleep cooldown."""
        mock_guardrails.check_instructional_lockout.return_value = (True, "OK")
        mock_guardrails.check_thermal_safety.return_value = (True, 45.0, "OK")
        mock_guardrails.check_preflight_congestion.return_value = (True, "OK", 10.0, 0.0)
        mock_guardrails.clamp_parameters.return_value = (80, 10)  # Clamped

        mock_get_ip.side_effect = lambda iface: "10.0.0.10" if iface == "eth0" else "10.0.0.20"
        mock_run_test.side_effect = [
            {"success": True, "tx_mbps": 79.5, "rx_mbps": 78.9, "retransmits": 0, "protocol": "tcp"},
            {"success": True, "tx_mbps": 45.0, "rx_mbps": 42.1, "retransmits": 5, "protocol": "tcp"}
        ]

        test_args = [
            "iperf3_runner.py",
            "--server", "10.0.0.1",
            "--bandwidth-cap", "500",
            "--duration", "30",
            "--interfaces", "eth0", "wlan0",
            "--output", self.prom_file
        ]

        with patch.object(sys, "argv", test_args):
            iperf3_runner.main()

        # Cooldown called once between eth0 and wlan0
        mock_sleep.assert_called_once_with(5)

        self.assertEqual(mock_run_test.call_count, 2)
        mock_write.assert_called_once()
        prom_lines = mock_write.call_args[0][0]

        # Verify wired metrics
        self.assertTrue(any('openux_iperf3_test_status{interface="eth0",medium="wired",server="10.0.0.1"} 1' in l for l in prom_lines))
        self.assertTrue(any('openux_iperf3_throughput_tx_mbps{interface="eth0",medium="wired",server="10.0.0.1"} 79.5' in l for l in prom_lines))

        # Verify wireless metrics
        self.assertTrue(any('openux_iperf3_test_status{interface="wlan0",medium="wireless",server="10.0.0.1"} 1' in l for l in prom_lines))
        self.assertTrue(any('openux_iperf3_throughput_tx_mbps{interface="wlan0",medium="wireless",server="10.0.0.1"} 45.0' in l for l in prom_lines))

    @verifies("REQ-PRB-011")
    @patch("iperf3_runner.time.sleep")
    @patch("iperf3_runner.run_iperf3_test")
    @patch("iperf3_runner.get_interface_ip")
    @patch("iperf3_runner.NetworkSafetyGuardrails")
    @patch("iperf3_runner.write_metrics")
    def test_cli_interface_without_ip_or_failed_test(self, mock_write, mock_guardrails, mock_get_ip, mock_run_test, mock_sleep):
        """Verifies status 0 recorded when an interface lacks an IP or iperf3 test fails."""
        mock_guardrails.check_instructional_lockout.return_value = (True, "OK")
        mock_guardrails.check_thermal_safety.return_value = (True, 45.0, "OK")
        mock_guardrails.check_preflight_congestion.return_value = (True, "OK", 10.0, 0.0)
        mock_guardrails.clamp_parameters.return_value = (100, 10)

        # eth0 has no IP; wlan0 has IP but iperf3 fails
        mock_get_ip.side_effect = lambda iface: None if iface == "eth0" else "192.168.1.50"
        mock_run_test.return_value = {"success": False, "error": "Server unreachable"}

        test_args = ["iperf3_runner.py", "--server", "10.0.0.1", "--interfaces", "eth0", "wlan0"]

        with patch.object(sys, "argv", test_args):
            iperf3_runner.main()

        mock_write.assert_called_once()
        prom_lines = mock_write.call_args[0][0]

        self.assertTrue(any('openux_iperf3_test_status{interface="eth0",server="10.0.0.1"} 0' in l for l in prom_lines))
        self.assertTrue(any('openux_iperf3_test_status{interface="wlan0",medium="wireless",server="10.0.0.1"} 0' in l for l in prom_lines))

    @verifies("REQ-PRB-011")
    @patch("iperf3_runner.run_iperf3_test")
    @patch("iperf3_runner.get_interface_ip", return_value="10.0.0.5")
    @patch("iperf3_runner.NetworkSafetyGuardrails")
    @patch("iperf3_runner.write_metrics")
    def test_cli_force_flag_bypasses_all_lockouts(self, mock_write, mock_guardrails, mock_get_ip, mock_run_test):
        """Verifies --force flag bypasses instructional, thermal, congestion, and maintenance windows."""
        mock_guardrails.check_instructional_lockout.return_value = (True, "Overridden")
        mock_guardrails.check_thermal_safety.return_value = (False, 90.0, "Overheating")  # Dangerous but bypassed with --force
        mock_guardrails.check_preflight_congestion.return_value = (False, "Congested", 300.0, 20.0)
        mock_guardrails.clamp_parameters.return_value = (100, 10)
        mock_run_test.return_value = {"success": True, "tx_mbps": 90.0, "rx_mbps": 90.0, "retransmits": 0, "protocol": "tcp"}

        test_args = ["iperf3_runner.py", "--server", "10.0.0.1", "--interfaces", "eth0", "--force"]

        with patch.object(sys, "argv", test_args):
            iperf3_runner.main()

        mock_guardrails.check_instructional_lockout.assert_called_once_with(allow_override=True)
        # Verify run_iperf3_test was called because --force bypassed the guardrails
        mock_run_test.assert_called_once()
        mock_write.assert_called_once()
        prom_lines = mock_write.call_args[0][0]
        self.assertTrue(any('openux_iperf3_test_status{interface="eth0",medium="wired",server="10.0.0.1"} 1' in l for l in prom_lines))


if __name__ == "__main__":
    unittest.main()
