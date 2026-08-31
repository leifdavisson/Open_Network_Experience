"""
Open Network Experience (ONE) - Central State & In-Memory Cache Layer
Copyright (C) 2026 Open Network Experience Authors.
Licensed under the GNU Affero General Public License v3.0 (AGPLv3).
"""

import copy
from typing import Dict, List
from server.schemas import (
    WifiSpec,
    TargetContainerSpec,
    LocationSpec,
    SensorReconcileResponse
)

# In-Memory Active Caches (Synchronized with SQLite)
SENSORS_DB: Dict[str, dict] = {}
PROBES_DB: Dict[str, dict] = {}
SCHEDULES_DB: Dict[str, dict] = {}
EVIDENCE_DB: Dict[str, List[dict]] = {}
ROAMING_EVENTS_DB: List[dict] = []

DEFAULT_TARGET_CONTAINERS = {
    "blackbox-exporter": TargetContainerSpec(
        image="prom/blackbox-exporter:master",
        ports=["9115:9115"],
        volumes=[],
        command=None
    ),
    "node-exporter": TargetContainerSpec(
        image="prom/node-exporter:v1.8.2",
        ports=["9100:9100"],
        volumes=[
            "/:/host:ro,rslave",
            "/var/lib/node_exporter/textfile_collector:/var/lib/node_exporter/textfile_collector:ro"
        ],
        command=None
    ),
    "browser-transaction-tester": TargetContainerSpec(
        image="open-ux/playwright-runner:latest",
        ports=[],
        volumes=["/var/lib/node_exporter/textfile_collector:/metrics"],
        command=None,
        env={
            "TARGET_URL": "https://portal.example.edu",
            "TEST_TYPE": "page",
            "TEST_INTERVAL_SECONDS": "300"
        }
    )
}

DEFAULT_TARGET_WIFI = WifiSpec(
    ssid="District-Testing",
    security="open",
    psk=None,
    username=None,
    password=None
)

def get_or_create_sensor(sensor_id: str) -> dict:
    """Helper to load sensor from SQLite or initialize if new to the platform."""
    import server.db as db
    db_sensor = db.load_sensor(sensor_id)
    if db_sensor:
        loc_val = db_sensor.get("location")
        if loc_val:
            if isinstance(loc_val, dict):
                if loc_val.get("latitude") is None:
                    loc_val["latitude"] = 35.37452
                    loc_val["longitude"] = -119.01874
                if not loc_val.get("site"):
                    loc_val["site"] = "City Center"
                if not loc_val.get("building"):
                    loc_val["building"] = "1300 17th St"
                if not loc_val.get("room"):
                    loc_val["room"] = "IT Operations"
            db_sensor["location"] = LocationSpec(**loc_val) if isinstance(loc_val, dict) else loc_val
        if isinstance(db_sensor.get("target_config"), dict):
            db_sensor["target_config"] = SensorReconcileResponse(**db_sensor["target_config"])
        SENSORS_DB[sensor_id] = db_sensor
        return SENSORS_DB[sensor_id]

    if sensor_id not in SENSORS_DB:
        SENSORS_DB[sensor_id] = {
            "sensor_id": sensor_id,
            "last_seen": 0,
            "os": "unknown",
            "hostname": "unknown",
            "mac_address": "unknown",
            "status": "pending",
            "api_key": "",
            "reset_flag": False,
            "probing_state": "GREEN",
            "location": LocationSpec(
                district="Kern County Superintendent of Schools",
                site="City Center",
                building="1300 17th St",
                room="IT Operations",
                notes="1300 17th St, Bakersfield, CA 93301",
                latitude=35.37452,
                longitude=-119.01874,
                is_gps_auto=False
            ),
            "reported_containers": {},
            "target_config": SensorReconcileResponse(
                reset=False,
                wifi=copy.deepcopy(DEFAULT_TARGET_WIFI),
                containers=copy.deepcopy(DEFAULT_TARGET_CONTAINERS),
                custom_probes=[],
                probing_state="GREEN"
            )
        }
        db.save_sensor(SENSORS_DB[sensor_id])
    else:
        s = SENSORS_DB[sensor_id]
        if isinstance(s.get("location"), dict):
            s["location"] = LocationSpec(**s["location"])
        if isinstance(s.get("target_config"), dict):
            s["target_config"] = SensorReconcileResponse(**s["target_config"])
    return SENSORS_DB[sensor_id]
