#!/usr/bin/env python3
# License: GNU AGPLv3 (GNU Affero General Public License v3.0)
import os
import sys
import unittest
import tempfile
import tarfile
from unittest.mock import patch, MagicMock

def verifies(req_id: str):
    def decorator(fn):
        fn.__verifies__ = req_id
        return fn
    return decorator

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import evidence_collector

class TestEvidenceCollector(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.snap_dir = os.path.join(self.test_dir.name, "snapshots")
        self.bundle_dir = os.path.join(self.test_dir.name, "bundles")

    def tearDown(self):
        self.test_dir.cleanup()

    @verifies("REQ-PRB-003")
    def test_generate_plain_english_summary(self):
        """Verifies plain English translation for various incident reasons."""
        txt, html = evidence_collector.generate_plain_english_summary("sensor-101", "caaspp_failure", "2026-08-30 12:00:00 UTC")
        self.assertIn("State Testing (CAASPP / ELPAC) Connection Failure", txt)
        self.assertIn("sensor-101", txt)
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("State Testing (CAASPP / ELPAC)", html)

        txt_custom, html_custom = evidence_collector.generate_plain_english_summary("sensor-102", "unknown_custom_alert", "2026-08-30 12:00:00 UTC")
        self.assertIn("unknown_custom_alert", txt_custom)

    @patch("subprocess.check_output")
    def test_collect_system_telemetry(self, mock_subproc):
        """Verifies staging of network link, route, DNS, and journal telemetry."""
        staging_dir = os.path.join(self.test_dir.name, "staging")
        os.makedirs(staging_dir, exist_ok=True)

        mock_subproc.return_value = "dummy system output"
        evidence_collector.collect_system_telemetry(staging_dir)

        self.assertTrue(os.path.exists(os.path.join(staging_dir, "wifi_link.txt")))
        self.assertTrue(os.path.exists(os.path.join(staging_dir, "network_ip_route.txt")))
        self.assertTrue(os.path.exists(os.path.join(staging_dir, "journal_recent.log")))

    @verifies("REQ-PRB-003")
    @patch("evidence_collector.SNAPSHOTS_DIR")
    @patch("evidence_collector.EVIDENCE_BUNDLE_DIR")
    @patch("subprocess.check_output")
    def test_package_evidence_bundle(self, mock_subproc, mock_bundle_dir, mock_snap_dir):
        """Verifies creation of .tar.gz bundle with all required evidence artifacts."""
        mock_snap_dir.__str__.return_value = self.snap_dir
        mock_bundle_dir.__str__.return_value = self.bundle_dir
        os.makedirs(self.snap_dir, exist_ok=True)
        os.makedirs(self.bundle_dir, exist_ok=True)

        dummy_pcap = os.path.join(self.snap_dir, "incident_20260830_01.pcap")
        with open(dummy_pcap, "wb") as f:
            f.write(b"DUMMY_PCAP_BYTES")

        mock_subproc.return_value = "dummy output"

        with patch("evidence_collector.SNAPSHOTS_DIR", self.snap_dir), \
             patch("evidence_collector.EVIDENCE_BUNDLE_DIR", self.bundle_dir):
            bundle_path = evidence_collector.package_evidence_bundle("sensor-test-01", reason="wifi_flapping")
            self.assertIsNotNone(bundle_path)
            self.assertTrue(os.path.exists(bundle_path))
            self.assertTrue(bundle_path.endswith(".tar.gz"))

            with tarfile.open(bundle_path, "r:gz") as tar:
                names = tar.getnames()
                self.assertTrue(any("incident_summary.txt" in n for n in names))
                self.assertTrue(any("incident_summary.html" in n for n in names))

if __name__ == "__main__":
    unittest.main()
