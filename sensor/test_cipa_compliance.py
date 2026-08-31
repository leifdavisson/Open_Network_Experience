#!/usr/bin/env python3
# License: GNU AGPLv3 (GNU Affero General Public License v3.0)
"""
Unit Test Suite for CIPA Filtering Compliance Checker (sensor/cipa_compliance.py).
Tests:
  1. Content filter enforcement verification (Blocked via HTTPError, URLError, Timeout/Handshake, Block Page)
  2. Non-compliance detection when restricted tokens bypass filter (HTTP 200 with matching token)
  3. Control probe baseline internet connectivity validation
  4. Atomic Prometheus metric generation and textfile collector output
  5. CLI execution under online, offline, compliant, and non-compliant conditions
"""

import os
import sys
import tempfile
import unittest
import urllib.error
from unittest.mock import patch, MagicMock

# Ensure sensor directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

def verifies(req_id: str):
    """Requirements verification decorator helper for RTM compliance."""
    def decorator(fn):
        fn.__verifies__ = req_id
        return fn
    return decorator

import cipa_compliance


class TestCIPACompliance(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.prom_file = os.path.join(self.test_dir.name, "cipa.prom")
        self.sample_target = {
            "id": "caic",
            "category": "csam",
            "name": "CSAM Filtering (IWF Standard)",
            "url": "http://iwf.testfiltering.com",
            "token": "SFf84Q2LRDkv02bVB7KYmvF9mPbO27IZnsueXWxeo5KE174T25Y7ybeaof851oyK"
        }

    def tearDown(self):
        self.test_dir.cleanup()

    # ====================================================
    # 1. Target Check & Filter Enforcement Tests
    # ====================================================

    @verifies("REQ-PRB-008")
    @patch("urllib.request.urlopen")
    def test_check_target_blocked_by_http_error(self, mock_urlopen):
        """Verifies compliant classification when network filter returns HTTP 403 Forbidden."""
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url=self.sample_target["url"],
            code=403,
            msg="Forbidden",
            hdrs={},
            fp=None
        )

        is_compliant, reason = cipa_compliance.check_target(self.sample_target)
        self.assertTrue(is_compliant)
        self.assertIn("Blocked (HTTP Error 403)", reason)

    @verifies("REQ-PRB-008")
    @patch("urllib.request.urlopen")
    def test_check_target_blocked_by_network_error(self, mock_urlopen):
        """Verifies compliant classification when DNS drops or connection is reset by firewall."""
        mock_urlopen.side_effect = urllib.error.URLError("Connection reset by peer")

        is_compliant, reason = cipa_compliance.check_target(self.sample_target)
        self.assertTrue(is_compliant)
        self.assertIn("Blocked (Network Error: Connection reset by peer)", reason)

    @verifies("REQ-PRB-008")
    @patch("urllib.request.urlopen")
    def test_check_target_blocked_by_timeout_or_handshake(self, mock_urlopen):
        """Verifies compliant classification when filter silently drops packets causing timeout."""
        mock_urlopen.side_effect = TimeoutError("Connection timed out after 5000ms")

        is_compliant, reason = cipa_compliance.check_target(self.sample_target)
        self.assertTrue(is_compliant)
        self.assertIn("Blocked (Handshake/Timeout:", reason)

    @verifies("REQ-PRB-008")
    @patch("urllib.request.urlopen")
    def test_check_target_blocked_by_block_page_without_token(self, mock_urlopen):
        """Verifies compliant classification when filter serves custom block page (HTTP 200 without token)."""
        mock_response = MagicMock()
        mock_response.read.return_value = b"<html><head><title>Access Denied - School Policy</title></head><body>Category: Prohibited</body></html>"
        mock_response.status = 200
        mock_response.__enter__.return_value = mock_response

        mock_urlopen.return_value = mock_response

        is_compliant, reason = cipa_compliance.check_target(self.sample_target)
        self.assertTrue(is_compliant)
        self.assertIn("Blocked (Response received, but token missing - code 200)", reason)

    @verifies("REQ-PRB-008")
    @patch("urllib.request.urlopen")
    def test_check_target_allowed_non_compliant(self, mock_urlopen):
        """Verifies non-compliant (failed) classification when restricted verification token is returned."""
        mock_response = MagicMock()
        token_html = f"<html><body>Test Page Content {self.sample_target['token']} Verified</body></html>".encode("utf-8")
        mock_response.read.return_value = token_html
        mock_response.status = 200
        mock_response.__enter__.return_value = mock_response

        mock_urlopen.return_value = mock_response

        is_compliant, reason = cipa_compliance.check_target(self.sample_target)
        self.assertFalse(is_compliant)
        self.assertEqual(reason, "Allowed (Verification token matched)")

    # ====================================================
    # 2. Control Probe Baseline Connectivity Tests
    # ====================================================

    @verifies("REQ-PRB-008")
    @patch("urllib.request.urlopen")
    def test_check_internet_connectivity_success_204(self, mock_urlopen):
        """Verifies connectivity probe succeeds on HTTP 204 No Content."""
        mock_response = MagicMock(status=204)
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        self.assertTrue(cipa_compliance.check_internet_connectivity())

    @verifies("REQ-PRB-008")
    @patch("urllib.request.urlopen")
    def test_check_internet_connectivity_success_200(self, mock_urlopen):
        """Verifies connectivity probe succeeds on HTTP 200 OK."""
        mock_response = MagicMock(status=200)
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        self.assertTrue(cipa_compliance.check_internet_connectivity())

    @verifies("REQ-PRB-008")
    @patch("urllib.request.urlopen")
    def test_check_internet_connectivity_failure_status(self, mock_urlopen):
        """Verifies connectivity probe fails on non-200/204 response."""
        mock_response = MagicMock(status=500)
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        self.assertFalse(cipa_compliance.check_internet_connectivity())

    @verifies("REQ-PRB-008")
    @patch("urllib.request.urlopen")
    def test_check_internet_connectivity_failure_exception(self, mock_urlopen):
        """Verifies connectivity probe returns False when offline or probe unreachable."""
        mock_urlopen.side_effect = Exception("No route to host")
        self.assertFalse(cipa_compliance.check_internet_connectivity())

    # ====================================================
    # 3. Prometheus Metric Generation Tests
    # ====================================================

    @verifies("REQ-PRB-008")
    def test_write_metrics_to_file(self):
        """Verifies atomic metric file generation for Node Exporter."""
        prom_lines = [
            "# HELP cipa_compliance_status CIPA internet filtering compliance.",
            "# TYPE cipa_compliance_status gauge",
            'cipa_internet_connectivity 1',
            'cipa_compliance_status{id="caic",category="csam",name="CSAM Filtering",reason="Blocked (HTTP Error 403)",url="http://iwf.testfiltering.com"} 1'
        ]

        cipa_compliance.write_metrics(prom_lines, self.prom_file)

        self.assertTrue(os.path.exists(self.prom_file))
        with open(self.prom_file, "r") as f:
            content = f.read()

        self.assertIn("cipa_internet_connectivity 1", content)
        self.assertIn('cipa_compliance_status{id="caic"', content)

    @verifies("REQ-PRB-008")
    def test_write_metrics_stdout(self):
        """Verifies metrics output formatting when output_file is None."""
        prom_lines = ["cipa_internet_connectivity 1"]
        with patch("builtins.print") as mock_print:
            cipa_compliance.write_metrics(prom_lines, None)
            mock_print.assert_called_with("cipa_internet_connectivity 1\n")

    @verifies("REQ-PRB-008")
    def test_write_metrics_error_handling(self):
        """Verifies sys.exit(1) on invalid unwriteable destination path."""
        prom_lines = ["cipa_internet_connectivity 1"]
        with patch("os.makedirs", side_effect=PermissionError("Permission denied")), \
             self.assertRaises(SystemExit) as cm:
            cipa_compliance.write_metrics(prom_lines, "/root/unauthorized/cipa.prom")
        self.assertEqual(cm.exception.code, 1)

    # ====================================================
    # 4. CLI Execution & Orchestration Tests
    # ====================================================

    @verifies("REQ-PRB-008")
    @patch("cipa_compliance.check_internet_connectivity", return_value=False)
    def test_main_offline_fallback(self, mock_conn):
        """Verifies that offline state reports unknown (-1) for all categories without running false tests."""
        with patch.object(sys, "argv", ["cipa_compliance.py", self.prom_file]):
            cipa_compliance.main()

        self.assertTrue(os.path.exists(self.prom_file))
        with open(self.prom_file, "r") as f:
            content = f.read()

        self.assertIn("cipa_internet_connectivity 0", content)
        for target in cipa_compliance.TEST_TARGETS:
            self.assertIn(f'id="{target["id"]}"', content)
            self.assertIn("} -1", content)

    @verifies("REQ-PRB-008")
    @patch("cipa_compliance.check_target")
    @patch("cipa_compliance.check_internet_connectivity", return_value=True)
    def test_main_online_all_compliant(self, mock_conn, mock_check_target):
        """Verifies normal execution when all target categories are successfully blocked."""
        mock_check_target.return_value = (True, "Blocked (HTTP Error 403)")

        with patch.object(sys, "argv", ["cipa_compliance.py", self.prom_file]):
            cipa_compliance.main()

        self.assertTrue(os.path.exists(self.prom_file))
        with open(self.prom_file, "r") as f:
            content = f.read()

        self.assertIn("cipa_internet_connectivity 1", content)
        self.assertIn("} 1", content)
        self.assertEqual(mock_check_target.call_count, len(cipa_compliance.TEST_TARGETS))

    @verifies("REQ-PRB-008")
    @patch("cipa_compliance.check_target")
    @patch("cipa_compliance.check_internet_connectivity", return_value=True)
    def test_main_online_with_filter_breach(self, mock_conn, mock_check_target):
        """Verifies metrics capture when one category fails filtering (unblocked)."""
        # First target fails (allowed), rest pass
        def side_effect(target):
            if target["id"] == "porn":
                return (False, "Allowed (Verification token matched)")
            return (True, "Blocked (HTTP Error 403)")

        mock_check_target.side_effect = side_effect

        with patch.object(sys, "argv", ["cipa_compliance.py", self.prom_file]):
            cipa_compliance.main()

        self.assertTrue(os.path.exists(self.prom_file))
        with open(self.prom_file, "r") as f:
            content = f.read()

        self.assertIn('id="porn",category="restricted_adult",name="Restricted Adult Content",reason="Allowed (Verification token matched)"', content)
        self.assertIn("} 0", content)


if __name__ == "__main__":
    unittest.main()
