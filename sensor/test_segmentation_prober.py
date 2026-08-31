#!/usr/bin/env python3
# License: GNU AGPLv3 (GNU Affero General Public License v3.0)
import os
import sys
import unittest
import socket
import tempfile
from unittest.mock import patch, MagicMock

def verifies(req_id: str):
    def decorator(fn):
        fn.__verifies__ = req_id
        return fn
    return decorator

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import segmentation_prober

class TestSegmentationProber(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.prom_file = os.path.join(self.test_dir.name, "segmentation.prom")

    def tearDown(self):
        self.test_dir.cleanup()

    @verifies("REQ-PRB-005")
    @patch("socket.socket")
    def test_probe_target_blocked_compliant(self, mock_socket_cls):
        """Verifies compliant behavior when a restricted port is blocked."""
        mock_sock = MagicMock()
        mock_sock.connect.side_effect = socket.timeout("Connection timed out")
        mock_socket_cls.return_value = mock_sock

        target = {
            "id": "switch_ssh",
            "name": "Switch SSH",
            "host": "10.0.0.1",
            "port": 22,
            "expected_state": "blocked",
            "timeout_sec": 1
        }
        reachable, latency, compliant = segmentation_prober.probe_target(target)
        self.assertEqual(reachable, 0)
        self.assertTrue(compliant)

    @verifies("REQ-PRB-005")
    @patch("socket.socket")
    def test_probe_target_blocked_breached(self, mock_socket_cls):
        """Verifies policy breach detected when a restricted port is accessible."""
        mock_sock = MagicMock()
        mock_sock.connect.return_value = None  # Connection successful
        mock_socket_cls.return_value = mock_sock

        target = {
            "id": "switch_ssh",
            "name": "Switch SSH",
            "host": "10.0.0.1",
            "port": 22,
            "expected_state": "blocked",
            "timeout_sec": 1
        }
        reachable, latency, compliant = segmentation_prober.probe_target(target)
        self.assertEqual(reachable, 1)
        self.assertFalse(compliant)

    @verifies("REQ-PRB-005")
    @patch("socket.socket")
    def test_probe_target_allowed_compliant(self, mock_socket_cls):
        """Verifies compliant behavior when an allowed service is reachable."""
        mock_sock = MagicMock()
        mock_sock.connect.return_value = None
        mock_socket_cls.return_value = mock_sock

        target = {
            "id": "district_dns",
            "name": "District DNS",
            "host": "10.0.0.2",
            "port": 53,
            "expected_state": "allowed",
            "timeout_sec": 1
        }
        reachable, latency, compliant = segmentation_prober.probe_target(target)
        self.assertEqual(reachable, 1)
        self.assertTrue(compliant)

    def test_write_metrics(self):
        """Verifies emission of prometheus compliance metrics."""
        sample_results = [
            {"id": "t1", "name": "Target 1", "expected_state": "blocked", "reachable": 0, "latency": 0.05, "compliant": True},
            {"id": "t2", "name": "Target 2", "expected_state": "allowed", "reachable": 1, "latency": 0.01, "compliant": True}
        ]
        segmentation_prober.write_metrics(sample_results, self.prom_file)
        self.assertTrue(os.path.exists(self.prom_file))
        with open(self.prom_file, "r") as f:
            content = f.read()
            self.assertIn("openux_segmentation_overall_compliant 1", content)
            self.assertIn('id="t1"', content)

if __name__ == "__main__":
    unittest.main()
