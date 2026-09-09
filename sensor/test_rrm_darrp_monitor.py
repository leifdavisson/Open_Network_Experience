#!/usr/bin/env python3
# License: GNU AGPLv3 (GNU Affero General Public License v3.0)
import os
import sys
import unittest
import tempfile
import json
from unittest.mock import patch, MagicMock

def verifies(req_id: str):
    def decorator(fn):
        fn.__verifies__ = req_id
        return fn
    return decorator

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import rrm_darrp_monitor

class TestRrmDarrpMonitor(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.state_file = os.path.join(self.test_dir.name, "rrm_state.json")
        self.prom_file = os.path.join(self.test_dir.name, "wifi_rrm.prom")

    def tearDown(self):
        self.test_dir.cleanup()

    def test_freq_to_channel(self):
        """Verifies 2.4 GHz, 5 GHz, and 6 GHz channel mappings."""
        self.assertEqual(rrm_darrp_monitor.freq_to_channel(2412), 1)
        self.assertEqual(rrm_darrp_monitor.freq_to_channel(2437), 6)
        self.assertEqual(rrm_darrp_monitor.freq_to_channel(2462), 11)
        self.assertEqual(rrm_darrp_monitor.freq_to_channel(2484), 14)
        self.assertEqual(rrm_darrp_monitor.freq_to_channel(5180), 36)
        self.assertEqual(rrm_darrp_monitor.freq_to_channel(5745), 149)
        self.assertEqual(rrm_darrp_monitor.freq_to_channel(5955), 1)
        self.assertEqual(rrm_darrp_monitor.freq_to_channel(9999), 0)

    def test_load_and_save_state(self):
        """Verifies state persistence and recovery."""
        with patch("rrm_darrp_monitor.STATE_FILE", self.state_file):
            initial_state = rrm_darrp_monitor.load_state()
            self.assertEqual(initial_state["total_switches"], 0)

            initial_state["total_switches"] = 5
            initial_state["current_channel"] = 36
            rrm_darrp_monitor.save_state(initial_state)

            loaded_state = rrm_darrp_monitor.load_state()
            self.assertEqual(loaded_state["total_switches"], 5)
            self.assertEqual(loaded_state["current_channel"], 36)

    @verifies("REQ-PRB-004")
    @patch("subprocess.check_output")
    def test_get_connected_wifi_info(self, mock_subproc):
        """Verifies parsing of iw dev link output."""
        mock_subproc.return_value = """
Connected to 00:11:22:33:44:55 (on wlan0)
\tSSID: District-WLAN
\tfreq: 5240
\tsignal: -58 dBm
\ttx bitrate: 866.7 MBit/s 80MHz
\trx bitrate: 780.0 MBit/s
"""
        info = rrm_darrp_monitor.get_connected_wifi_info("wlan0")
        self.assertTrue(info["connected"])
        self.assertEqual(info["ssid"], "District-WLAN")
        self.assertEqual(info["bssid"], "00:11:22:33:44:55")
        self.assertEqual(info["freq_mhz"], 5240)
        self.assertEqual(info["channel"], 48)
        self.assertEqual(info["rssi_dbm"], -58)
        self.assertEqual(info["channel_width_mhz"], 80)

    @verifies("REQ-PRB-004")
    @patch("subprocess.check_output")
    def test_scan_cochannel_interference(self, mock_subproc):
        """Verifies neighbor BSS scan and CCI calculation."""
        mock_subproc.return_value = """
BSS 00:11:22:33:44:55(on wlan0)
\tfreq: 5240
\tsignal: -58 dBm
\tSSID: District-WLAN
BSS aa:bb:cc:dd:ee:ff(on wlan0)
\tfreq: 5240
\tsignal: -75 dBm
\tSSID: Competing-AP
BSS 11:22:33:44:55:66(on wlan0)
\tfreq: 5180
\tsignal: -70 dBm
\tSSID: Other-Channel-AP
"""
        cci_count, neighbors = rrm_darrp_monitor.scan_cochannel_interference("wlan0", 5240, "00:11:22:33:44:55")
        self.assertEqual(cci_count, 1)
        self.assertEqual(len(neighbors), 1)
        self.assertEqual(neighbors[0]["bssid"], "aa:bb:cc:dd:ee:ff")

    def test_write_metrics(self):
        """Verifies metric file emission."""
        lines = ["test_metric 1.0"]
        rrm_darrp_monitor.write_metrics(lines, self.prom_file)
        self.assertTrue(os.path.exists(self.prom_file))
        with open(self.prom_file, "r") as f:
            content = f.read()
            self.assertIn("test_metric 1.0", content)

    @verifies("REQ-PRB-005")
    @patch("rrm_darrp_monitor.write_metrics")
    @patch("rrm_darrp_monitor.scan_cochannel_interference")
    @patch("rrm_darrp_monitor.get_connected_wifi_info")
    def test_rrm_switch_vs_roam(self, mock_wifi, mock_scan, mock_write):
        """Verifies that identical BSSID frequency changes count as RRM switches while BSSID changes count as roams."""
        mock_scan.return_value = (0, [])
        with patch("rrm_darrp_monitor.STATE_FILE", self.state_file):
            # 1. First connection: BSSID-A, Ch 36
            mock_wifi.return_value = {
                "connected": True, "ssid": "District-WLAN", "bssid": "00:11:22:33:44:01",
                "freq_mhz": 5180, "channel": 36, "rssi_dbm": -60, "channel_width_mhz": 80
            }
            with patch("sys.argv", ["rrm_darrp_monitor.py", self.prom_file, "wlan0"]):
                rrm_darrp_monitor.main()
            state = rrm_darrp_monitor.load_state()
            self.assertEqual(state["current_channel"], 36)
            self.assertEqual(state["current_bssid"], "00:11:22:33:44:01")
            self.assertEqual(state["total_switches"], 0)
            self.assertEqual(state["total_roams"], 0)

            # 2. RRM Event: Same BSSID-A jumps to Ch 48
            mock_wifi.return_value = {
                "connected": True, "ssid": "District-WLAN", "bssid": "00:11:22:33:44:01",
                "freq_mhz": 5240, "channel": 48, "rssi_dbm": -62, "channel_width_mhz": 80
            }
            with patch("sys.argv", ["rrm_darrp_monitor.py", self.prom_file, "wlan0"]):
                rrm_darrp_monitor.main()
            state = rrm_darrp_monitor.load_state()
            self.assertEqual(state["current_channel"], 48)
            self.assertEqual(state["current_bssid"], "00:11:22:33:44:01")
            self.assertEqual(state["total_switches"], 1)
            self.assertEqual(state["total_roams"], 0)

            # 3. Roam Event: Client roams to BSSID-B on Ch 36 (channel changes, but BSSID is different)
            mock_wifi.return_value = {
                "connected": True, "ssid": "District-WLAN", "bssid": "00:11:22:33:44:02",
                "freq_mhz": 5180, "channel": 36, "rssi_dbm": -55, "channel_width_mhz": 80
            }
            with patch("sys.argv", ["rrm_darrp_monitor.py", self.prom_file, "wlan0"]):
                rrm_darrp_monitor.main()
            state = rrm_darrp_monitor.load_state()
            self.assertEqual(state["current_channel"], 36)
            self.assertEqual(state["current_bssid"], "00:11:22:33:44:02")
            # total_switches must remain 1 (NOT 2)
            self.assertEqual(state["total_switches"], 1)
            # total_roams must now be 1
            self.assertEqual(state["total_roams"], 1)

            # Check that write_metrics was called with both metrics
            last_prom_lines = mock_write.call_args[0][0]
            switches_line = next(line for line in last_prom_lines if line.startswith("wifi_rrm_channel_switches_total"))
            roams_line = next(line for line in last_prom_lines if line.startswith("wifi_client_roams_total"))
            self.assertTrue(switches_line.endswith(" 1"))
            self.assertTrue(roams_line.endswith(" 1"))

if __name__ == "__main__":
    unittest.main()

