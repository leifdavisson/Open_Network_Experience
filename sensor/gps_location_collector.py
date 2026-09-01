#!/usr/bin/env python3
"""
OpenUX GPS & Precision Location Collector
Reads hardware GPS / GNSS receivers (USB / Serial / UART / gpsd) and parses NMEA sentences
($GPGGA, $GPRMC) to provide autonomous outdoor/campus geolocation for edge sensors.

When hardware GPS is not available or indoor satellites are occluded, it loads the
static campus/room profile from /etc/sensor/location.json.

Atomically outputs Prometheus metrics for Grafana mapping and updates local location state.
"""

import os
import time
import json
import argparse
from typing import Dict, Any, Optional

DEFAULT_LOCATION_FILE = "/etc/sensor/location.json"
DEFAULT_PROM_FILE = "/var/lib/node_exporter/textfile_collector/location.prom"

# Serial port candidates for USB/UART GPS dongles and Raspberry Pi HATs
GPS_DEVICE_CANDIDATES = [
    "/dev/ttyUSB0",
    "/dev/ttyUSB1",
    "/dev/ttyACM0",
    "/dev/ttyACM1",
    "/dev/serial0",
    "/dev/ttyAMA0"
]

def parse_nmea_lat_long(raw_val: str, direction: str) -> Optional[float]:
    """Converts NMEA DDMM.MMMM format to decimal degrees."""
    if not raw_val or not direction:
        return None
    try:
        if direction in ('N', 'S'):
            degrees = float(raw_val[:2])
            minutes = float(raw_val[2:])
        else: # E or W
            degrees = float(raw_val[:3])
            minutes = float(raw_val[3:])

        decimal = degrees + (minutes / 60.0)
        if direction in ('S', 'W'):
            decimal = -decimal
        return round(decimal, 6)
    except Exception:
        return None

def read_hardware_gps(timeout_sec: float = 3.0) -> Dict[str, Any]:
    """
    Attempts to connect to available serial GPS device and parse NMEA sentences.
    """
    available_ports = [p for p in GPS_DEVICE_CANDIDATES if os.path.exists(p)]
    if not available_ports:
        return {"has_gps": False, "error": "No GPS serial device found"}

    port_path = available_ports[0]
    try:
        import serial
        ser = serial.Serial(port_path, baudrate=9600, timeout=1.0)
        start = time.time()

        while (time.time() - start) < timeout_sec:
            line = ser.readline().decode('ascii', errors='ignore').strip()
            if line.startswith('$GPGGA') or line.startswith('$GNGGA'):
                # $GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47
                parts = line.split(',')
                if len(parts) >= 10:
                    raw_lat, lat_dir = parts[2], parts[3]
                    raw_lon, lon_dir = parts[4], parts[5]
                    fix_quality = int(parts[6]) if parts[6].isdigit() else 0
                    satellites = int(parts[7]) if parts[7].isdigit() else 0
                    altitude = float(parts[9]) if parts[9] else 0.0

                    lat = parse_nmea_lat_long(raw_lat, lat_dir)
                    lon = parse_nmea_lat_long(raw_lon, lon_dir)

                    if fix_quality > 0 and lat is not None and lon is not None:
                        ser.close()
                        return {
                            "has_gps": True,
                            "is_fixed": True,
                            "latitude": lat,
                            "longitude": lon,
                            "altitude_meters": altitude,
                            "satellites": satellites,
                            "port": port_path
                        }
        ser.close()
        return {"has_gps": True, "is_fixed": False, "satellites": 0, "port": port_path}
    except Exception as e:
        return {"has_gps": False, "error": str(e)}

def load_or_update_location(gps_result: Dict[str, Any], config_path: str) -> Dict[str, Any]:
    """Loads location config and merges live GPS data if available."""
    location = {
        "district": "Unified School District",
        "site": "Main Campus",
        "building": "North Wing",
        "room": "Room 101",
        "notes": "Edge Diagnostic Sensor",
        "latitude": 35.373292,
        "longitude": -119.018712,
        "altitude_meters": 120.0,
        "is_gps_auto": False,
        "last_gps_fix": None
    }

    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                saved = json.load(f)
                location.update(saved)
        except Exception:
            pass

    # If live GPS has a 3D satellite fix, update coordinate fields
    if gps_result.get("is_fixed"):
        location["latitude"] = gps_result["latitude"]
        location["longitude"] = gps_result["longitude"]
        location["altitude_meters"] = gps_result["altitude_meters"]
        location["is_gps_auto"] = True
        location["last_gps_fix"] = int(time.time())

        # Save back to file
        os.makedirs(os.path.dirname(os.path.abspath(config_path)), exist_ok=True)
        try:
            with open(config_path + ".tmp", "w") as f:
                json.dump(location, f, indent=2)
            os.replace(config_path + ".tmp", config_path)
        except Exception:
            pass

    return location

def write_metrics(location: Dict[str, Any], gps_result: Dict[str, Any], output_path: str):
    """Atomically writes Prometheus metrics for sensor geolocation."""
    is_fixed = 1 if gps_result.get("is_fixed") else 0
    satellites = gps_result.get("satellites", 0)
    is_auto = 1 if location.get("is_gps_auto") else 0
    lat = location.get("latitude", 0.0)
    lon = location.get("longitude", 0.0)
    alt = location.get("altitude_meters", 0.0)

    labels = f'district="{location["district"]}",site="{location["site"]}",building="{location["building"]}",room="{location["room"]}"'

    prom_lines = [
        '# HELP openux_sensor_gps_fix_status Whether the onboard GPS has an active 3D satellite fix (1=Fix, 0=No Fix)',
        '# TYPE openux_sensor_gps_fix_status gauge',
        f'openux_sensor_gps_fix_status{{{labels}}} {is_fixed}',

        '# HELP openux_sensor_gps_satellites_locked Number of GPS/GNSS satellites in lock',
        '# TYPE openux_sensor_gps_satellites_locked gauge',
        f'openux_sensor_gps_satellites_locked{{{labels}}} {satellites}',

        '# HELP openux_sensor_location_is_gps_auto Whether location is dynamically updated by GPS (1=GPS Auto, 0=Static)',
        '# TYPE openux_sensor_location_is_gps_auto gauge',
        f'openux_sensor_location_is_gps_auto{{{labels}}} {is_auto}',

        '# HELP openux_sensor_gps_latitude Current GPS latitude in decimal degrees',
        '# TYPE openux_sensor_gps_latitude gauge',
        f'openux_sensor_gps_latitude{{{labels}}} {lat:.6f}',

        '# HELP openux_sensor_gps_longitude Current GPS longitude in decimal degrees',
        '# TYPE openux_sensor_gps_longitude gauge',
        f'openux_sensor_gps_longitude{{{labels}}} {lon:.6f}',

        '# HELP openux_sensor_gps_altitude_meters Current GPS altitude in meters',
        '# TYPE openux_sensor_gps_altitude_meters gauge',
        f'openux_sensor_gps_altitude_meters{{{labels}}} {alt:.1f}'
    ]

    content = "\n".join(prom_lines) + "\n"
    if output_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        tmp = output_path + ".tmp"
        with open(tmp, "w") as f:
            f.write(content)
        os.replace(tmp, output_path)
        print(f"Location & GPS metrics written to: {output_path}")
    else:
        print(content)

def main():
    parser = argparse.ArgumentParser(description="OpenUX GPS & Precision Location Collector")
    parser.add_argument("--config", default=DEFAULT_LOCATION_FILE, help="Path to location.json")
    parser.add_argument("--output", default=DEFAULT_PROM_FILE, help="Prometheus metric file output path")

    args = parser.parse_args()

    print("Querying Sensor Geolocation & GPS Hardware...")
    gps_result = read_hardware_gps(timeout_sec=1.5)
    location = load_or_update_location(gps_result, args.config)

    status_str = "\033[92m3D GPS FIX\033[0m" if gps_result.get("is_fixed") else "\033[93mSTATIC / NO SATELLITE FIX\033[0m"
    print(f"Location: {location['site']} - {location['building']} ({location['room']})")
    print(f"Coordinates: {location['latitude']}, {location['longitude']} | Status: {status_str}")

    write_metrics(location, gps_result, args.output)

if __name__ == "__main__":
    main()
