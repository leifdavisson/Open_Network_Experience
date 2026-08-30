"""
Enterprise Scaling & Adaptive Probing Test Suite for Open Network Experience (ONE) CMP.
Validates:
  1. Multi-Campus Hierarchy CRUD & Aggregation
  2. Zero-Touch Provisioning (ZTP) Subnet CIDR Auto-Approval
  3. Batch Sensor Approval
  4. On-Demand Diagnostic Burst Trigger
  5. Edge Adaptive Resolution State Machine (GREEN -> AMBER -> RED -> BLACKOUT)
"""

import os
import sys
import time
import json
import tempfile
import pytest
from fastapi.testclient import TestClient

# Ensure server path is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sensor", "reconciler")))

import db
import main
from reconciler import AdaptiveResolutionEngine

ADMIN_KEY = "admin-noc-key-change-me"
client = TestClient(main.app)
ADMIN_HEADERS = {"X-API-Key": ADMIN_KEY}

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    """Initializes a temporary database for test isolation."""
    db_file = str(tmp_path / "test_cmp.db")
    monkeypatch.setattr(db, "DB_PATH", db_file)
    db.init_db()
    main.SENSORS_DB.clear()
    main.PROBES_DB.clear()
    main.SCHEDULES_DB.clear()

def test_campus_hierarchy_crud():
    """Validates adding, listing, and rolling up campus statistics."""
    campus_payload = {
        "campus_id": "CAMPUS-WEST-HIGH",
        "name": "West High School",
        "category": "High School",
        "district": "Kern High School District",
        "latitude": 35.3582,
        "longitude": -119.0471,
        "address": "1200 New St, Bakersfield, CA",
        "contact_email": "tech@westhigh.edu"
    }
    res = client.post("/api/v1/campuses", json=campus_payload, headers=ADMIN_HEADERS)
    assert res.status_code == 200
    assert res.json()["status"] == "success"

    res = client.get("/api/v1/campuses", headers=ADMIN_HEADERS)
    assert res.status_code == 200
    campuses = res.json()
    assert len(campuses) == 1
    assert campuses[0]["campus_id"] == "CAMPUS-WEST-HIGH"
    assert campuses[0]["sensor_count"] == 0

def test_subnet_auto_enroll_ztp():
    """Validates Zero-Touch Provisioning via DHCP Subnet Matching."""
    subnet_payload = {
        "subnet_cidr": "10.142.10.0/24",
        "campus_id": "CAMPUS-WEST-HIGH",
        "campus_name": "West High School",
        "building_default": "Science Wing A",
        "auto_approve": True
    }
    res = client.post("/api/v1/subnets", json=subnet_payload, headers=ADMIN_HEADERS)
    assert res.status_code == 200

    reg_payload = {
        "sensor_id": "sensor-ztp-01",
        "os": "linux",
        "hostname": "pi5-whs-101",
        "mac_address": "b8:27:eb:aa:bb:cc",
        "timestamp": 1700000000
    }
    res = client.post(
        "/api/v1/sensors/register",
        json=reg_payload,
        headers={"X-Forwarded-For": "10.142.10.55"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "approved"
    assert data["api_key"] is not None
    assert data["api_key"].startswith("key_")

    sensor = main.SENSORS_DB.get("sensor-ztp-01")
    assert sensor is not None
    assert sensor["campus_id"] == "CAMPUS-WEST-HIGH"
    assert sensor["location"].site == "West High School"
    assert sensor["location"].building == "Science Wing A"

def test_batch_sensor_approval():
    """Validates bulk approval of pending sensors."""
    for i in range(1, 4):
        s_id = f"pending-sensor-{i}"
        client.post("/api/v1/sensors/register", json={
            "sensor_id": s_id,
            "os": "linux",
            "hostname": f"sensor-{i}",
            "mac_address": f"00:11:22:33:44:0{i}",
            "timestamp": 1700000000
        })

    batch_payload = {
        "sensor_ids": ["pending-sensor-1", "pending-sensor-2", "pending-sensor-3"],
        "campus_id": "CAMPUS-RIDGEVIEW",
        "building": "Main Hall"
    }
    res = client.post("/api/v1/sensors/batch-approve", json=batch_payload, headers=ADMIN_HEADERS)
    assert res.status_code == 200
    assert res.json()["approved_count"] == 3

    for i in range(1, 4):
        s = main.SENSORS_DB[f"pending-sensor-{i}"]
        assert s["status"] == "approved"
        assert s["campus_id"] == "CAMPUS-RIDGEVIEW"

def test_on_demand_burst_trigger():
    """Validates triggering 1-second high-resolution burst on sensors."""
    s_id = "sensor-burst-01"
    client.post("/api/v1/sensors/register", json={
        "sensor_id": s_id,
        "os": "linux",
        "hostname": "test-sensor",
        "mac_address": "00:11:22:33:44:55",
        "timestamp": 1700000000
    })
    client.post("/api/v1/sensors/batch-approve", json={"sensor_ids": [s_id]}, headers=ADMIN_HEADERS)

    burst_payload = {
        "sensor_ids": [s_id],
        "duration_seconds": 60,
        "reason": "packet_loss_investigation"
    }
    res = client.post("/api/v1/sensors/burst", json=burst_payload, headers=ADMIN_HEADERS)
    assert res.status_code == 200

    assert main.SENSORS_DB[s_id]["probing_state"] == "ON_DEMAND"

def test_adaptive_resolution_state_machine():
    """Validates the edge AdaptiveResolutionEngine state transitions and intervals."""
    engine = AdaptiveResolutionEngine(config={"check_interval_seconds": 15})

    # Mock gateway reachability healthy
    engine.check_gateway_reachability = lambda: (True, 12.0)
    state = engine.evaluate_state()
    assert state == "GREEN"
    assert engine.get_sleep_interval() == 15

    # Mock high latency (>80ms) -> AMBER
    engine.check_gateway_reachability = lambda: (True, 95.0)
    state = engine.evaluate_state()
    assert state == "AMBER"
    assert engine.get_sleep_interval() == 5

    # Mock gateway unreachable 1x -> RED
    engine.check_gateway_reachability = lambda: (False, 0.0)
    state = engine.evaluate_state()
    assert state == "RED"
    assert engine.get_sleep_interval() == 1

    # Mock gateway unreachable 3x -> BLACKOUT (Backoff state)
    engine.evaluate_state()
    state = engine.evaluate_state()
    assert state == "BLACKOUT"
    assert engine.get_sleep_interval() == 300 # 5 min dampened interval

    # Mock ON_DEMAND command
    state = engine.evaluate_state(commanded_state="ON_DEMAND")
    assert state == "ON_DEMAND"
    assert engine.get_sleep_interval() == 1

def test_install_script_endpoint():
    """Validates that CMP serves the 1-line curl installer script."""
    res = client.get("/install.sh")
    assert res.status_code == 200
    assert "Open Network Experience (ONE) Edge Sensor Installer" in res.text
    assert "--cmp" in res.text
    assert "--site" in res.text
    assert "--wizard" in res.text

def test_install_script_with_query_params():
    """Validates dynamic substitution of campus, room, and wizard flags via query parameters."""
    res = client.get("/install.sh?site=West+High+School&room=Room+204&building=Science+Wing&wizard=true")
    assert res.status_code == 200
    assert 'SITE_NAME="West High School"' in res.text
    assert 'ROOM_NAME="Room 204"' in res.text
    assert 'BUILDING_NAME="Science Wing"' in res.text
    assert 'LAUNCH_WIZARD=1' in res.text

def test_health_check_endpoint():
    """Validates platform health and readiness endpoint."""
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "active_sensors" in data
    assert "version" in data

def test_sensor_script_distribution():
    """Validates that CMP serves edge synthetic probe scripts for remote curl bootstrap."""
    res = client.get("/sensor/scripts/reconciler.py")
    assert res.status_code == 200
    assert "AdaptiveResolutionEngine" in res.text

    res = client.get("/sensor/scripts/wizard.py")
    assert res.status_code == 200
    assert "one-wizard" in res.text

    res = client.get("/sensor/scripts/usb_provisioner.py")
    assert res.status_code == 200
    assert "USB AUTO-PROVISIONER" in res.text

    res = client.get("/sensor/scripts/cipa_compliance.py")
    assert res.status_code == 200

def test_download_usb_staging_kit():
    """Validates dynamic generation of in-memory USB Staging Kit zip file."""
    import zipfile
    import io

    res = client.get("/api/v1/onboarding/usb-kit.zip?site=West+High&room=Room+204&wifi_ssid=School-Staff&wifi_psk=Secret88")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/zip"
    assert "attachment; filename=one_usb_staging_kit.zip" in res.headers.get("content-disposition", "")

    # Inspect zip contents in memory
    zip_bytes = io.BytesIO(res.content)
    with zipfile.ZipFile(zip_bytes, "r") as zf:
        file_list = zf.namelist()
        assert "one-bootstrap.json" in file_list
        assert "setup.sh" in file_list
        assert "usb_provisioner.py" in file_list
        assert "wizard.py" in file_list
        assert "reconciler.py" in file_list
        assert "README_USB_STAGING.txt" in file_list

        # Validate bootstrap json content
        bootstrap_raw = zf.read("one-bootstrap.json").decode("utf-8")
        bootstrap_cfg = json.loads(bootstrap_raw)
        assert bootstrap_cfg["location"]["site"] == "West High"
        assert bootstrap_cfg["location"]["room"] == "Room 204"
        assert bootstrap_cfg["wifi"]["ssid"] == "School-Staff"
        assert bootstrap_cfg["wifi"]["psk"] == "Secret88"

def test_visual_schedule_crud_and_toggle():
    """Validates Visual Probe Schedule CRUD, timing modes, and toggle endpoints."""
    sch_payload = {
        "id": "sched_test_unit",
        "name": "State Testing Pre-Flight Sweep",
        "probe_id": "caaspp_readiness",
        "mode": "daily_once",
        "days_of_week": ["mon", "tue", "wed", "thu", "fri"],
        "start_time": "07:15",
        "end_time": "16:00",
        "interval_value": 15,
        "interval_unit": "minutes",
        "cron_expr": "15 7 * * 1-5",
        "target_scope": "all",
        "guardrails_enabled": True,
        "is_active": True
    }

    # 1. Create Schedule
    res = client.post("/api/v1/schedules", json=sch_payload, headers={"X-API-Key": ADMIN_KEY})
    assert res.status_code == 200

    # 2. List Schedules
    res = client.get("/api/v1/schedules", headers={"X-API-Key": ADMIN_KEY})
    assert res.status_code == 200
    schedules = res.json()
    assert any(s["id"] == "sched_test_unit" for s in schedules)

    # 3. Toggle Active State
    res = client.put("/api/v1/schedules/sched_test_unit/toggle", headers={"X-API-Key": ADMIN_KEY})
    assert res.status_code == 200
    assert res.json()["is_active"] is False

    # 4. Re-enable
    res = client.put("/api/v1/schedules/sched_test_unit/toggle", headers={"X-API-Key": ADMIN_KEY})
    assert res.status_code == 200
    assert res.json()["is_active"] is True

    # 5. Delete Schedule
    res = client.delete("/api/v1/schedules/sched_test_unit", headers={"X-API-Key": ADMIN_KEY})
    assert res.status_code == 200

def test_edge_reconciliation_unified_schedules():
    """Validates that edge sensor reconciliation receives active unified visual schedules."""
    # Create an active schedule
    sch_payload = {
        "id": "sched_reconcile_check",
        "name": "CAASPP Testing Check",
        "probe_id": "caaspp_readiness",
        "mode": "daily_once",
        "days_of_week": ["mon", "tue", "wed", "thu", "fri"],
        "start_time": "07:15",
        "target_scope": "all",
        "guardrails_enabled": True,
        "is_active": True
    }
    client.post("/api/v1/schedules", json=sch_payload, headers={"X-API-Key": ADMIN_KEY})

    # Register & approve a test sensor
    reg_payload = {
        "sensor_id": "sensor-sched-test-01",
        "os": "linux",
        "hostname": "sched-sensor",
        "mac_address": "dc:a6:32:ee:ff:01",
        "timestamp": int(time.time()),
        "location": {"site": "Bakersfield High", "room": "Room 101"}
    }
    reg_res = client.post("/api/v1/sensors/register", json=reg_payload)
    client.post("/api/v1/sensors/sensor-sched-test-01/approve", headers={"X-API-Key": ADMIN_KEY})
    re_reg = client.post("/api/v1/sensors/register", json=reg_payload)
    api_key = re_reg.json()["api_key"]

    # Check-in and reconcile
    report_payload = {
        "sensor_id": "sensor-sched-test-01",
        "os": "linux",
        "timestamp": int(time.time()),
        "containers": {}
    }
    rec_res = client.post("/api/v1/sensors/reconcile", json=report_payload, headers={"X-API-Key": api_key})
    assert rec_res.status_code == 200
    target_config = rec_res.json()
    assert "unified_schedules" in target_config
    assert len(target_config["unified_schedules"]) > 0
    assert any(s["probe_id"] == "caaspp_readiness" for s in target_config["unified_schedules"])
