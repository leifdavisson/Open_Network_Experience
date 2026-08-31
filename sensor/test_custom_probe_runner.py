#!/usr/bin/env python3
# License: GNU AGPLv3 (GNU Affero General Public License v3.0)
"""
Comprehensive Unit Test Suite for OpenUX Custom Synthetic Probe Runner
(sensor/custom_probe_runner.py).

Verifies:
  - HTTP probe execution (200 OK, expected status matching, regex matching, HTTPError handling, network failures)
  - DNS probe resolution (successful lookup, socket resolution error)
  - TCP probe connection (successful handshake, connection failure/timeout)
  - Batch probe runner execution (mixed probe types, disabled probes, invalid probe types)
  - Atomic Prometheus metric file generation
  - CLI argument parsing and main execution loop
"""

import os
import sys
import json
import socket
import tempfile
import urllib.error
import unittest
from unittest.mock import patch, MagicMock

# Ensure sensor directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import custom_probe_runner


def verifies(req_id: str):
    """Decorator to attach requirement traceability identifiers to test methods."""
    def decorator(fn):
        fn.__verifies__ = req_id
        return fn
    return decorator


class TestCustomProbeRunner(unittest.TestCase):
    """Test suite for custom_probe_runner module."""

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.output_prom = os.path.join(self.test_dir.name, "custom_probes.prom")

    def tearDown(self):
        self.test_dir.cleanup()

    # ==========================================
    # 1. HTTP Probe Execution Tests
    # ==========================================

    @verifies("REQ-PRB-012")
    @patch("urllib.request.urlopen")
    def test_execute_http_probe_200_ok(self, mock_urlopen):
        """Verifies successful HTTP GET probe with default 200 status."""
        mock_resp = MagicMock()
        mock_resp.getcode.return_value = 200
        mock_resp.read.return_value = b"<html>Welcome to Canvas LMS</html>"
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        success, latency, status_code = custom_probe_runner.execute_http_probe("https://canvas.district.edu", timeout=3.0)
        self.assertEqual(success, 1)
        self.assertEqual(status_code, 200)
        self.assertGreaterEqual(latency, 0.0)

    @verifies("REQ-PRB-012")
    @patch("urllib.request.urlopen")
    def test_execute_http_probe_regex_match_success(self, mock_urlopen):
        """Verifies HTTP probe regex pattern match success."""
        mock_resp = MagicMock()
        mock_resp.getcode.return_value = 200
        mock_resp.read.return_value = b'{"status": "healthy", "service": "sis"}'
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        success, latency, status_code = custom_probe_runner.execute_http_probe(
            "https://sis.district.edu/api/v1/health",
            timeout=3.0,
            expected_status=200,
            match_regex="healthy"
        )
        self.assertEqual(success, 1)
        self.assertEqual(status_code, 200)

    @verifies("REQ-PRB-012")
    @patch("urllib.request.urlopen")
    def test_execute_http_probe_regex_match_failure(self, mock_urlopen):
        """Verifies HTTP probe fails when regex pattern is not in the response body."""
        mock_resp = MagicMock()
        mock_resp.getcode.return_value = 200
        mock_resp.read.return_value = b'{"status": "maintenance_mode"}'
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        success, latency, status_code = custom_probe_runner.execute_http_probe(
            "https://sis.district.edu/api/v1/health",
            timeout=3.0,
            expected_status=200,
            match_regex="healthy"
        )
        self.assertEqual(success, 0)
        self.assertEqual(status_code, 200)

    @verifies("REQ-PRB-012")
    @patch("urllib.request.urlopen")
    def test_execute_http_probe_http_error_unexpected(self, mock_urlopen):
        """Verifies HTTPError handling when status code is unexpected (e.g. 500 vs expected 200)."""
        err = urllib.error.HTTPError("https://portal.district.edu", 500, "Internal Server Error", {}, None)
        mock_urlopen.side_effect = err

        success, latency, status_code = custom_probe_runner.execute_http_probe("https://portal.district.edu")
        self.assertEqual(success, 0)
        self.assertEqual(status_code, 500)
        self.assertGreaterEqual(latency, 0.0)

    @verifies("REQ-PRB-012")
    @patch("urllib.request.urlopen")
    def test_execute_http_probe_http_error_expected(self, mock_urlopen):
        """Verifies HTTPError handling when an error status code is intentionally expected (e.g. 401 Unauthorized)."""
        err = urllib.error.HTTPError("https://secure.district.edu/admin", 401, "Unauthorized", {}, None)
        mock_urlopen.side_effect = err

        success, latency, status_code = custom_probe_runner.execute_http_probe(
            "https://secure.district.edu/admin",
            expected_status=401
        )
        self.assertEqual(success, 1)
        self.assertEqual(status_code, 401)

    @verifies("REQ-PRB-012")
    @patch("urllib.request.urlopen")
    def test_execute_http_probe_network_exception(self, mock_urlopen):
        """Verifies HTTP probe handles low-level network exceptions (URLError, timeout)."""
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

        success, latency, status_code = custom_probe_runner.execute_http_probe("https://unreachable.district.edu")
        self.assertEqual(success, 0)
        self.assertEqual(status_code, -1)
        self.assertGreaterEqual(latency, 0.0)

    # ==========================================
    # 2. DNS Probe Execution Tests
    # ==========================================

    @verifies("REQ-PRB-012")
    @patch("socket.gethostbyname")
    def test_execute_dns_probe_success(self, mock_gethostbyname):
        """Verifies successful DNS resolution probe."""
        mock_gethostbyname.return_value = "10.0.0.53"

        success, latency, status_code = custom_probe_runner.execute_dns_probe("dns.district.edu")
        self.assertEqual(success, 1)
        self.assertEqual(status_code, 0)
        self.assertGreaterEqual(latency, 0.0)
        mock_gethostbyname.assert_called_once_with("dns.district.edu")

    @verifies("REQ-PRB-012")
    @patch("socket.gethostbyname")
    def test_execute_dns_probe_failure(self, mock_gethostbyname):
        """Verifies DNS probe failure on socket resolution error (NXDOMAIN / gaierror)."""
        mock_gethostbyname.side_effect = socket.gaierror(socket.EAI_NONAME, "Name or service not known")

        success, latency, status_code = custom_probe_runner.execute_dns_probe("nonexistent.district.edu")
        self.assertEqual(success, 0)
        self.assertEqual(status_code, -1)
        self.assertGreaterEqual(latency, 0.0)

    # ==========================================
    # 3. TCP Probe Execution Tests
    # ==========================================

    @verifies("REQ-PRB-012")
    @patch("socket.socket")
    def test_execute_tcp_probe_success(self, mock_socket_class):
        """Verifies successful TCP port reachability probe."""
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        success, latency, status_code = custom_probe_runner.execute_tcp_probe("10.0.10.1", 8080, timeout=2.0)
        self.assertEqual(success, 1)
        self.assertEqual(status_code, 200)
        self.assertGreaterEqual(latency, 0.0)
        mock_sock.settimeout.assert_called_once_with(2.0)
        mock_sock.connect.assert_called_once_with(("10.0.10.1", 8080))
        mock_sock.close.assert_called_once()

    @verifies("REQ-PRB-012")
    @patch("socket.socket")
    def test_execute_tcp_probe_failure(self, mock_socket_class):
        """Verifies TCP probe failure when connection is refused or timed out."""
        mock_sock = MagicMock()
        mock_sock.connect.side_effect = socket.timeout("timed out")
        mock_socket_class.return_value = mock_sock

        success, latency, status_code = custom_probe_runner.execute_tcp_probe("10.0.10.2", 443, timeout=2.0)
        self.assertEqual(success, 0)
        self.assertEqual(status_code, -1)
        self.assertGreaterEqual(latency, 0.0)
        mock_sock.close.assert_called_once()

    # ==========================================
    # 4. Batch Probe Runner Tests
    # ==========================================

    @verifies("REQ-PRB-012")
    @patch("custom_probe_runner.execute_http_probe")
    @patch("custom_probe_runner.execute_dns_probe")
    @patch("custom_probe_runner.execute_tcp_probe")
    def test_run_probes_mixed_types_and_disabled(self, mock_tcp, mock_dns, mock_http):
        """Verifies run_probes orchestrates multiple probe types and ignores disabled probes."""
        mock_http.return_value = (1, 0.045, 200)
        mock_dns.return_value = (1, 0.008, 0)
        mock_tcp.return_value = (1, 0.012, 200)

        probes = [
            {
                "id": "canvas-lms",
                "name": "Canvas LMS",
                "probe_type": "http",
                "target": "https://canvas.district.edu",
                "timeout_seconds": 4.0,
                "expected_status_code": 200,
                "match_body_regex": "Canvas",
                "enabled": True
            },
            {
                "id": "sis-api",
                "name": "SIS API",
                "probe_type": "api",
                "target": "https://powerschool.district.edu/api",
                "timeout_seconds": 5.0,
                "expected_status_code": 200,
                "enabled": True
            },
            {
                "id": "internal-dns",
                "name": "DC1 DNS",
                "probe_type": "dns",
                "target": "auth.district.local",
                "timeout_seconds": 2.0,
                "enabled": True
            },
            {
                "id": "door-access",
                "name": "Door Access Controller",
                "probe_type": "tcp",
                "target": "10.0.50.10:4000",
                "timeout_seconds": 2.0,
                "enabled": True
            },
            {
                "id": "tcp-default-port",
                "name": "Web Proxy TCP",
                "probe_type": "tcp",
                "target": "10.0.50.11",
                "timeout_seconds": 2.0,
                "enabled": True
            },
            {
                "id": "disabled-probe",
                "name": "Legacy Lunch POS",
                "probe_type": "http",
                "target": "https://oldpos.district.edu",
                "enabled": False
            },
            {
                "id": "unknown-probe",
                "name": "Custom ICMP",
                "probe_type": "unsupported_proto",
                "target": "10.0.0.1",
                "enabled": True
            }
        ]

        results = custom_probe_runner.run_probes(probes)

        # 6 enabled probes, 1 disabled probe
        self.assertEqual(len(results), 6)
        result_ids = [r["id"] for r in results]
        self.assertNotIn("disabled-probe", result_ids)
        self.assertIn("canvas-lms", result_ids)
        self.assertIn("sis-api", result_ids)
        self.assertIn("internal-dns", result_ids)
        self.assertIn("door-access", result_ids)
        self.assertIn("tcp-default-port", result_ids)
        self.assertIn("unknown-probe", result_ids)

        mock_http.assert_any_call("https://canvas.district.edu", 4.0, 200, "Canvas")
        mock_http.assert_any_call("https://powerschool.district.edu/api", 5.0, 200, None)
        mock_dns.assert_called_once_with("auth.district.local", 2.0)
        mock_tcp.assert_any_call("10.0.50.10", 4000, 2.0)
        mock_tcp.assert_any_call("10.0.50.11", 80, 2.0)

        # Verify unknown probe returns failure
        unknown_res = next(r for r in results if r["id"] == "unknown-probe")
        self.assertEqual(unknown_res["success"], 0)
        self.assertEqual(unknown_res["status_code"], -1)

    # ==========================================
    # 5. Atomic Metrics Writing Tests
    # ==========================================

    @verifies("REQ-PRB-012")
    def test_write_metrics_atomic_file(self):
        """Verifies Prometheus metrics are written to file atomically with proper format."""
        results = [
            {
                "id": "canvas-lms",
                "name": "Canvas LMS",
                "type": "http",
                "target": "https://canvas.district.edu",
                "success": 1,
                "latency": 0.04567,
                "status_code": 200
            },
            {
                "id": "door-access",
                "name": "Door Access",
                "type": "tcp",
                "target": "10.0.50.10:4000",
                "success": 0,
                "latency": 2.0001,
                "status_code": -1
            }
        ]

        custom_probe_runner.write_metrics(results, self.output_prom)

        self.assertTrue(os.path.exists(self.output_prom))
        with open(self.output_prom, "r") as f:
            content = f.read()

        self.assertIn("# HELP openux_custom_probe_status", content)
        self.assertIn("# TYPE openux_custom_probe_status gauge", content)
        self.assertIn("# HELP openux_custom_probe_duration_seconds", content)
        self.assertIn("# HELP openux_custom_probe_http_status", content)
        self.assertIn('openux_custom_probe_status{id="canvas-lms",name="Canvas LMS",type="http",target="https://canvas.district.edu"} 1', content)
        self.assertIn('openux_custom_probe_duration_seconds{id="canvas-lms",name="Canvas LMS",type="http",target="https://canvas.district.edu"} 0.0457', content)
        self.assertIn('openux_custom_probe_http_status{id="canvas-lms",name="Canvas LMS",type="http",target="https://canvas.district.edu"} 200', content)
        self.assertIn('openux_custom_probe_status{id="door-access",name="Door Access",type="tcp",target="10.0.50.10:4000"} 0', content)
        self.assertIn('openux_custom_probe_http_status{id="door-access",name="Door Access",type="tcp",target="10.0.50.10:4000"} -1', content)

    @verifies("REQ-PRB-012")
    @patch("builtins.print")
    def test_write_metrics_stdout_when_output_path_none(self, mock_print):
        """Verifies Prometheus metrics output to stdout when output_path is None or empty."""
        results = [
            {
                "id": "test-probe",
                "name": "Test Probe",
                "type": "dns",
                "target": "dns.district.edu",
                "success": 1,
                "latency": 0.0123,
                "status_code": 0
            }
        ]

        custom_probe_runner.write_metrics(results, "")
        mock_print.assert_called()
        printed_arg = mock_print.call_args[0][0]
        self.assertIn('openux_custom_probe_status{id="test-probe",name="Test Probe",type="dns",target="dns.district.edu"} 1', printed_arg)

    # ==========================================
    # 6. CLI Execution & main() Tests
    # ==========================================

    @verifies("REQ-PRB-012")
    @patch("custom_probe_runner.write_metrics")
    @patch("custom_probe_runner.run_probes")
    def test_main_with_valid_config(self, mock_run_probes, mock_write_metrics):
        """Verifies main() reads config file, runs probes, and writes metrics."""
        mock_run_probes.return_value = [
            {"id": "portal", "name": "Portal", "type": "http", "target": "https://portal.edu", "success": 1, "latency": 0.05, "status_code": 200}
        ]

        config_data = [
            {"id": "portal", "name": "Portal", "probe_type": "http", "target": "https://portal.edu", "enabled": True}
        ]
        config_path = os.path.join(self.test_dir.name, "probes.json")
        with open(config_path, "w") as f:
            json.dump(config_data, f)

        test_args = ["custom_probe_runner.py", "--config", config_path, "--output", self.output_prom]
        with patch.object(sys, "argv", test_args):
            custom_probe_runner.main()

        mock_run_probes.assert_called_once_with(config_data)
        mock_write_metrics.assert_called_once()

    @verifies("REQ-PRB-012")
    @patch("custom_probe_runner.write_metrics")
    @patch("custom_probe_runner.run_probes")
    def test_main_fallback_default_when_no_config(self, mock_run_probes, mock_write_metrics):
        """Verifies main() uses starter test probe when config file does not exist."""
        mock_run_probes.return_value = [
            {"id": "district-gateway", "name": "District Gateway Portal", "type": "http", "target": "https://google.com", "success": 1, "latency": 0.05, "status_code": 200}
        ]

        nonexistent_path = os.path.join(self.test_dir.name, "does_not_exist.json")
        test_args = ["custom_probe_runner.py", "--config", nonexistent_path, "--output", self.output_prom]
        with patch.object(sys, "argv", test_args):
            custom_probe_runner.main()

        mock_run_probes.assert_called_once()
        probes_passed = mock_run_probes.call_args[0][0]
        self.assertEqual(len(probes_passed), 1)
        self.assertEqual(probes_passed[0]["id"], "district-gateway")
        mock_write_metrics.assert_called_once()

    @verifies("REQ-PRB-012")
    @patch("custom_probe_runner.write_metrics")
    @patch("custom_probe_runner.run_probes")
    def test_main_handles_invalid_json_config(self, mock_run_probes, mock_write_metrics):
        """Verifies main() handles invalid JSON gracefully and falls back to default probe."""
        mock_run_probes.return_value = [
            {"id": "district-gateway", "name": "District Gateway Portal", "type": "http", "target": "https://google.com", "success": 1, "latency": 0.05, "status_code": 200}
        ]

        invalid_json_path = os.path.join(self.test_dir.name, "invalid.json")
        with open(invalid_json_path, "w") as f:
            f.write("{invalid-json-content")

        test_args = ["custom_probe_runner.py", "--config", invalid_json_path, "--output", self.output_prom]
        with patch.object(sys, "argv", test_args):
            custom_probe_runner.main()

        mock_run_probes.assert_called_once()
        probes_passed = mock_run_probes.call_args[0][0]
        self.assertEqual(len(probes_passed), 1)
        self.assertEqual(probes_passed[0]["id"], "district-gateway")


if __name__ == "__main__":
    unittest.main()
