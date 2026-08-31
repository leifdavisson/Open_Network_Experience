#!/usr/bin/env python3
# License: GNU AGPLv3 (GNU Affero General Public License v3.0)
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

def verifies(req_id: str):
    def decorator(fn):
        fn.__verifies__ = req_id
        return fn
    return decorator

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import wifi_dhcp_exporter

class TestWifiDhcpExporter(unittest.TestCase):
    def setUp(self):
        self.sample_logs = [
            "2026-08-30T10:00:00-0700 host wpa_supplicant[123]: wlan0: Trying to associate with SSID 'District-Secure'",
            "2026-08-30T10:00:01-0700 host wpa_supplicant[123]: wlan0: Associated with 00:11:22:33:44:55",
            "2026-08-30T10:00:02-0700 host wpa_supplicant[123]: wlan0: CTRL-EVENT-CONNECTED - Connection to 00:11:22:33:44:55 completed",
            "2026-08-30T10:00:03-0700 host dhclient[456]: DHCPDISCOVER on wlan0 to 255.255.255.255 port 67 interval 3",
            "2026-08-30T10:00:05-0700 host dhclient[456]: bound to 10.142.10.45 -- renewal in 1800 seconds."
        ]

    @verifies("REQ-PRB-001")
    def test_regex_patterns(self):
        """Verifies pattern matching on wpa_supplicant and dhclient logs."""
        m_start = wifi_dhcp_exporter.PATTERNS["wifi_assoc_start"].search("wpa_supplicant: Trying to associate with SSID 'District-Staff'")
        self.assertIsNotNone(m_start)
        self.assertEqual(m_start.group("ssid"), "District-Staff")

        m_end = wifi_dhcp_exporter.PATTERNS["wifi_assoc_end"].search("wpa_supplicant: Associated with aa:bb:cc:dd:ee:ff")
        self.assertIsNotNone(m_end)
        self.assertEqual(m_end.group("bssid"), "aa:bb:cc:dd:ee:ff")

        m_conn = wifi_dhcp_exporter.PATTERNS["wifi_auth_complete"].search("wpa_supplicant: CTRL-EVENT-CONNECTED")
        self.assertIsNotNone(m_conn)

        m_dhcp_start = wifi_dhcp_exporter.PATTERNS["dhcp_start"].search("dhclient[12]: DHCPDISCOVER on wlan0")
        self.assertIsNotNone(m_dhcp_start)

        m_dhcp_ack = wifi_dhcp_exporter.PATTERNS["dhcp_ack"].search("dhclient[12]: bound to 192.168.1.50")
        self.assertIsNotNone(m_dhcp_ack)

    @verifies("REQ-PRB-001")
    def test_calculate_timings_success(self):
        """Verifies correct calculation of onboarding lifecycle durations."""
        metrics = wifi_dhcp_exporter.calculate_timings(self.sample_logs)
        self.assertEqual(metrics["ssid"], "District-Secure")
        self.assertEqual(metrics["bssid"], "00:11:22:33:44:55")
        self.assertAlmostEqual(metrics["wifi_association_seconds"], 1.0, places=1)
        self.assertAlmostEqual(metrics["wifi_authentication_seconds"], 1.0, places=1)
        self.assertAlmostEqual(metrics["dhcp_lease_seconds"], 2.0, places=1)
        self.assertEqual(metrics["onboarding_success"], 1)

    def test_calculate_timings_empty_or_malformed(self):
        """Verifies graceful handling of empty or unparseable log streams."""
        metrics = wifi_dhcp_exporter.calculate_timings([])
        self.assertEqual(metrics["wifi_association_seconds"], -1.0)
        self.assertEqual(metrics["onboarding_success"], 0)

        metrics_garbage = wifi_dhcp_exporter.calculate_timings(["invalid line without timestamp", "some random log"])
        self.assertEqual(metrics_garbage["wifi_association_seconds"], -1.0)

    @patch("subprocess.check_output")
    def test_parse_journal(self, mock_subproc):
        """Verifies journalctl output extraction and error handling."""
        mock_subproc.return_value = "line 1\nline 2\nline 3\n"
        lines = wifi_dhcp_exporter.parse_journal()
        self.assertEqual(len(lines), 3)

        mock_subproc.side_effect = Exception("Journalctl binary missing")
        lines_err = wifi_dhcp_exporter.parse_journal()
        self.assertEqual(lines_err, [])

    @patch("wifi_dhcp_exporter.parse_journal")
    @patch("builtins.open", create=True)
    @patch("os.replace")
    @patch("os.makedirs")
    def test_main_execution(self, mock_dirs, mock_replace, mock_open, mock_journal):
        """Verifies main() generates and atomically writes Prometheus metrics."""
        mock_journal.return_value = self.sample_logs
        with patch.object(sys, "argv", ["wifi_dhcp_exporter.py", "/tmp/test_wifi.prom"]):
            wifi_dhcp_exporter.main()
        mock_replace.assert_called_once()

if __name__ == "__main__":
    unittest.main()
