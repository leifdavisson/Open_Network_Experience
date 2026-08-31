#!/usr/bin/env python3
# License: GNU AGPLv3 (GNU Affero General Public License v3.0)
"""
Unit Test Suite for OpenUX GPS & Precision Location Collector (sensor/gps_location_collector.py).
Tests:
  1. NMEA Latitude / Longitude coordinate conversion (North, South, East, West, invalid inputs)
  2. Hardware GPS serial parsing ($GPGGA, $GNGGA, fixed and non-fixed states, device absence, errors)
  3. Static fallback location configuration loading and dynamic GPS cache updating
  4. Atomic Prometheus metric generation and textfile collector output
  5. Command-Line Interface (main) execution
"""

import os
import sys
import json
import tempfile
import unittest
from unittest.mock import patch, MagicMock

# Ensure sensor directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

def verifies(req_id: str):
    """Requirements verification decorator helper for RTM compliance."""
    def decorator(fn):
        fn.__verifies__ = req_id
        return fn
    return decorator

import gps_location_collector


class TestGPSLocationCollector(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.test_dir.name, "location.json")
        self.prom_file = os.path.join(self.test_dir.name, "location.prom")

    def tearDown(self):
        self.test_dir.cleanup()

    # ====================================================
    # 1. NMEA Coordinate Parsing Tests
    # ====================================================

    @verifies("REQ-PRB-007")
    def test_parse_nmea_lat_long_valid_north(self):
        """Verifies NMEA DDMM.MMMM coordinate parsing for North latitude."""
        # 4807.038, N -> 48 degrees + 07.038/60 minutes = 48.1173
        result = gps_location_collector.parse_nmea_lat_long("4807.038", "N")
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, 48.1173, places=4)

    @verifies("REQ-PRB-007")
    def test_parse_nmea_lat_long_valid_south(self):
        """Verifies NMEA DDMM.MMMM coordinate parsing for South latitude."""
        # 3351.000, S -> -(33 degrees + 51.000/60 minutes) = -33.85
        result = gps_location_collector.parse_nmea_lat_long("3351.000", "S")
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, -33.85, places=4)

    @verifies("REQ-PRB-007")
    def test_parse_nmea_lat_long_valid_east(self):
        """Verifies NMEA DDDMM.MMMM coordinate parsing for East longitude."""
        # 01131.000, E -> 11 degrees + 31.000/60 minutes = 11.516667
        result = gps_location_collector.parse_nmea_lat_long("01131.000", "E")
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, 11.516667, places=5)

    @verifies("REQ-PRB-007")
    def test_parse_nmea_lat_long_valid_west(self):
        """Verifies NMEA DDDMM.MMMM coordinate parsing for West longitude."""
        # 11901.1227, W -> -(119 degrees + 1.1227/60 minutes) = -119.018712
        result = gps_location_collector.parse_nmea_lat_long("11901.1227", "W")
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, -119.018712, places=5)

    @verifies("REQ-PRB-007")
    def test_parse_nmea_lat_long_invalid_inputs(self):
        """Verifies robust error handling and None return for malformed or empty coordinates."""
        self.assertIsNone(gps_location_collector.parse_nmea_lat_long("", "N"))
        self.assertIsNone(gps_location_collector.parse_nmea_lat_long("4807.038", ""))
        self.assertIsNone(gps_location_collector.parse_nmea_lat_long(None, "N"))
        self.assertIsNone(gps_location_collector.parse_nmea_lat_long("4807.038", None))
        self.assertIsNone(gps_location_collector.parse_nmea_lat_long("INVALID_COORDINATE", "N"))
        self.assertIsNone(gps_location_collector.parse_nmea_lat_long("12", "E"))

    # ====================================================
    # 2. Hardware GPS Serial Reading Tests
    # ====================================================

    @verifies("REQ-PRB-007")
    @patch("os.path.exists", return_value=False)
    def test_read_hardware_gps_no_device(self, mock_exists):
        """Verifies hardware GPS detection returns failure when no candidate serial device exists."""
        result = gps_location_collector.read_hardware_gps(timeout_sec=0.1)
        self.assertFalse(result["has_gps"])
        self.assertEqual(result["error"], "No GPS serial device found")

    @verifies("REQ-PRB-007")
    def test_read_hardware_gps_success_gpgga(self):
        """Verifies successful NMEA $GPGGA parsing with 3D satellite fix."""
        mock_serial_instance = MagicMock()
        nmea_sentence = b"$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47\r\n"
        mock_serial_instance.readline.return_value = nmea_sentence

        mock_serial_mod = MagicMock()
        mock_serial_mod.Serial.return_value = mock_serial_instance

        with patch.dict(sys.modules, {"serial": mock_serial_mod}), \
             patch("os.path.exists", side_effect=lambda p: p == "/dev/ttyUSB0"):
            result = gps_location_collector.read_hardware_gps(timeout_sec=1.0)

            self.assertTrue(result["has_gps"])
            self.assertTrue(result["is_fixed"])
            self.assertAlmostEqual(result["latitude"], 48.1173, places=4)
            self.assertAlmostEqual(result["longitude"], 11.516667, places=5)
            self.assertEqual(result["altitude_meters"], 545.4)
            self.assertEqual(result["satellites"], 8)
            self.assertEqual(result["port"], "/dev/ttyUSB0")
            mock_serial_instance.close.assert_called_once()

    @verifies("REQ-PRB-007")
    def test_read_hardware_gps_success_gngga(self):
        """Verifies GNSS multi-constellation $GNGGA sentence parsing."""
        mock_serial_instance = MagicMock()
        nmea_sentence = b"$GNGGA,001043.00,3522.3975,N,11901.1227,W,2,12,0.8,120.5,M,-31.8,M,,*5A\r\n"
        mock_serial_instance.readline.return_value = nmea_sentence

        mock_serial_mod = MagicMock()
        mock_serial_mod.Serial.return_value = mock_serial_instance

        with patch.dict(sys.modules, {"serial": mock_serial_mod}), \
             patch("os.path.exists", side_effect=lambda p: p == "/dev/ttyACM0"):
            result = gps_location_collector.read_hardware_gps(timeout_sec=1.0)

            self.assertTrue(result["has_gps"])
            self.assertTrue(result["is_fixed"])
            self.assertAlmostEqual(result["latitude"], 35.373292, places=4)
            self.assertAlmostEqual(result["longitude"], -119.018712, places=4)
            self.assertEqual(result["altitude_meters"], 120.5)
            self.assertEqual(result["satellites"], 12)
            self.assertEqual(result["port"], "/dev/ttyACM0")

    @verifies("REQ-PRB-007")
    def test_read_hardware_gps_no_fix(self):
        """Verifies GPS reading when sentences indicate fix quality = 0 (searching/no fix)."""
        mock_serial_instance = MagicMock()
        # fix_quality is 0
        nmea_sentence = b"$GPGGA,123519,0000.000,N,00000.000,E,0,00,99.9,0.0,M,0.0,M,,*47\r\n"
        mock_serial_instance.readline.return_value = nmea_sentence

        mock_serial_mod = MagicMock()
        mock_serial_mod.Serial.return_value = mock_serial_instance

        with patch.dict(sys.modules, {"serial": mock_serial_mod}), \
             patch("os.path.exists", side_effect=lambda p: p == "/dev/ttyUSB0"):
            result = gps_location_collector.read_hardware_gps(timeout_sec=0.05)

            self.assertTrue(result["has_gps"])
            self.assertFalse(result["is_fixed"])
            self.assertEqual(result["satellites"], 0)
            self.assertEqual(result["port"], "/dev/ttyUSB0")

    @verifies("REQ-PRB-007")
    def test_read_hardware_gps_serial_exception(self):
        """Verifies graceful handling when serial port communication raises an exception."""
        mock_serial_mod = MagicMock()
        mock_serial_mod.Serial.side_effect = Exception("Serial Port Permission Denied")

        with patch.dict(sys.modules, {"serial": mock_serial_mod}), \
             patch("os.path.exists", side_effect=lambda p: p == "/dev/ttyUSB0"):
            result = gps_location_collector.read_hardware_gps(timeout_sec=0.5)
            self.assertFalse(result["has_gps"])
            self.assertIn("Permission Denied", result["error"])

    # ====================================================
    # 3. Static Location & Dynamic GPS Update Tests
    # ====================================================

    @verifies("REQ-PRB-007")
    def test_load_or_update_location_default_fallback(self):
        """Verifies default static location is loaded when config file does not exist."""
        gps_result = {"has_gps": False, "error": "No device"}
        location = gps_location_collector.load_or_update_location(gps_result, "/nonexistent/path/location.json")

        self.assertEqual(location["district"], "Kern County Superintendent of Schools")
        self.assertEqual(location["site"], "Main Campus")
        self.assertEqual(location["building"], "North Wing")
        self.assertEqual(location["room"], "Room 101")
        self.assertFalse(location["is_gps_auto"])
        self.assertIsNone(location["last_gps_fix"])

    @verifies("REQ-PRB-007")
    def test_load_or_update_location_from_file(self):
        """Verifies reading custom location attributes from existing JSON config."""
        custom_data = {
            "district": "Bakersfield City School District",
            "site": "Sierra Vista Junior High",
            "building": "Science Wing",
            "room": "Lab B-12",
            "notes": "Indoor Edge Probe",
            "latitude": 35.3912,
            "longitude": -119.0345,
            "altitude_meters": 115.0
        }
        with open(self.config_path, "w") as f:
            json.dump(custom_data, f)

        gps_result = {"has_gps": False}
        location = gps_location_collector.load_or_update_location(gps_result, self.config_path)

        self.assertEqual(location["district"], "Bakersfield City School District")
        self.assertEqual(location["site"], "Sierra Vista Junior High")
        self.assertEqual(location["building"], "Science Wing")
        self.assertEqual(location["room"], "Lab B-12")
        self.assertAlmostEqual(location["latitude"], 35.3912)
        self.assertFalse(location["is_gps_auto"])

    @verifies("REQ-PRB-007")
    def test_load_or_update_location_malformed_json(self):
        """Verifies resilient fallback to default configuration when JSON is malformed."""
        with open(self.config_path, "w") as f:
            f.write("{ INVALID JSON CONTENT : ")

        gps_result = {"has_gps": False}
        location = gps_location_collector.load_or_update_location(gps_result, self.config_path)
        self.assertEqual(location["site"], "Main Campus")
        self.assertEqual(location["room"], "Room 101")

    @verifies("REQ-PRB-007")
    def test_load_or_update_location_with_live_gps_fix(self):
        """Verifies dynamic update and atomic persistence when live GPS fix is acquired."""
        gps_result = {
            "has_gps": True,
            "is_fixed": True,
            "latitude": 35.400123,
            "longitude": -119.050456,
            "altitude_meters": 135.2,
            "satellites": 10
        }

        location = gps_location_collector.load_or_update_location(gps_result, self.config_path)

        self.assertTrue(location["is_gps_auto"])
        self.assertIsNotNone(location["last_gps_fix"])
        self.assertAlmostEqual(location["latitude"], 35.400123)
        self.assertAlmostEqual(location["longitude"], -119.050456)
        self.assertAlmostEqual(location["altitude_meters"], 135.2)

        # Verify persisted back to disk
        self.assertTrue(os.path.exists(self.config_path))
        with open(self.config_path, "r") as f:
            saved_json = json.load(f)
            self.assertTrue(saved_json["is_gps_auto"])
            self.assertAlmostEqual(saved_json["latitude"], 35.400123)

    @verifies("REQ-PRB-007")
    def test_load_or_update_location_save_exception(self):
        """Verifies graceful handling when saving dynamic location to disk fails."""
        gps_result = {
            "has_gps": True,
            "is_fixed": True,
            "latitude": 35.400123,
            "longitude": -119.050456,
            "altitude_meters": 135.2,
            "satellites": 10
        }

        with patch("os.replace", side_effect=IOError("Permission denied")):
            location = gps_location_collector.load_or_update_location(gps_result, self.config_path)
            self.assertTrue(location["is_gps_auto"])
            self.assertAlmostEqual(location["latitude"], 35.400123)

    # ====================================================
    # 4. Prometheus Metric Generation Tests
    # ====================================================

    @verifies("REQ-PRB-007")
    def test_write_metrics_to_file(self):
        """Verifies atomic Prometheus metric generation with full location labels."""
        location = {
            "district": "Kern County Supt",
            "site": "Tech Center",
            "building": "Bldg 4",
            "room": "Server Rm 104",
            "latitude": 35.373292,
            "longitude": -119.018712,
            "altitude_meters": 120.0,
            "is_gps_auto": True
        }
        gps_result = {
            "has_gps": True,
            "is_fixed": True,
            "satellites": 9
        }

        gps_location_collector.write_metrics(location, gps_result, self.prom_file)

        self.assertTrue(os.path.exists(self.prom_file))
        with open(self.prom_file, "r") as f:
            content = f.read()

        self.assertIn("openux_sensor_gps_fix_status", content)
        self.assertIn('district="Kern County Supt"', content)
        self.assertIn('site="Tech Center"', content)
        self.assertIn('room="Server Rm 104"', content)
        self.assertIn("openux_sensor_gps_fix_status{", content)
        self.assertIn("openux_sensor_gps_satellites_locked{", content)
        self.assertIn(" 9", content)
        self.assertIn("openux_sensor_location_is_gps_auto{", content)
        self.assertIn("openux_sensor_gps_latitude{", content)
        self.assertIn("35.373292", content)
        self.assertIn("openux_sensor_gps_longitude{", content)
        self.assertIn("-119.018712", content)
        self.assertIn("openux_sensor_gps_altitude_meters{", content)
        self.assertIn("120.0", content)

    @verifies("REQ-PRB-007")
    def test_write_metrics_stdout(self):
        """Verifies metrics output formatting when output_path is None or empty."""
        location = {
            "district": "Kern Supt",
            "site": "Main",
            "building": "North",
            "room": "Rm 1",
            "latitude": 35.0,
            "longitude": -119.0,
            "altitude_meters": 100.0,
            "is_gps_auto": False
        }
        gps_result = {"is_fixed": False, "satellites": 0}

        with patch("builtins.print") as mock_print:
            gps_location_collector.write_metrics(location, gps_result, "")
            mock_print.assert_called()
            printed_arg = mock_print.call_args[0][0]
            self.assertIn("openux_sensor_gps_fix_status", printed_arg)

    # ====================================================
    # 5. CLI Execution Tests
    # ====================================================

    @verifies("REQ-PRB-007")
    @patch("gps_location_collector.read_hardware_gps")
    def test_main_cli_execution(self, mock_read_gps):
        """Verifies CLI main function executes workflow end-to-end."""
        mock_read_gps.return_value = {
            "has_gps": True,
            "is_fixed": True,
            "latitude": 35.373,
            "longitude": -119.018,
            "altitude_meters": 120.0,
            "satellites": 7
        }

        cli_args = [
            "gps_location_collector.py",
            "--config", self.config_path,
            "--output", self.prom_file
        ]

        with patch.object(sys, "argv", cli_args):
            gps_location_collector.main()

        self.assertTrue(os.path.exists(self.prom_file))
        with open(self.prom_file, "r") as f:
            content = f.read()
        self.assertIn("openux_sensor_gps_fix_status", content)


if __name__ == "__main__":
    unittest.main()
