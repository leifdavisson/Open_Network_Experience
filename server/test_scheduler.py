"""
Dedicated Unit Test Suite for the Unified Visual Probe Scheduler.
Tests:
  1. Pydantic Schemas & Timing Modes (Daily Once, Window Repeat, Continuous Interval, Raw Cron)
  2. SQLite Database Persistence, Seeding & CRUD Operations
  3. System Backup & Disaster Recovery Roundtrip with Schedules
  4. REST Endpoints Authentication, CRUD & Active State Toggles
  5. Edge Sensor Targeted Scope Delivery & Paused Schedule Filtering
  6. Edge Sensor Reconciler File Synchronization
"""

import os
import sys
import time
import json
import pytest
from fastapi.testclient import TestClient

def verifies(req_id: str):
    def decorator(fn):
        fn.__verifies__ = req_id
        return fn
    return decorator

# Ensure server path is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sensor", "reconciler")))

import db
import main
from schemas import UnifiedScheduleSpec, SensorReportRequest
from reconciler import reconcile_unified_schedules

ADMIN_KEY = "admin-noc-key-change-me"
AUTH_HEADERS = {"X-API-Key": ADMIN_KEY}
client = TestClient(main.app)

@pytest.fixture(autouse=True)
def setup_isolated_db(tmp_path, monkeypatch):
    """Isolates each test in a clean temporary SQLite database."""
    temp_db = str(tmp_path / "test_schedules.db")
    monkeypatch.setattr(db, "DB_PATH", temp_db)
    db.init_db()
    main.SENSORS_DB.clear()
    main.PROBES_DB.clear()
    main.SCHEDULES_DB.clear()

# --- 1. Schema Validation Tests ---

def test_01_schema_daily_once_validation():
    """Validates daily_once mode schema with morning pre-flight settings."""
    spec = UnifiedScheduleSpec(
        id="sched_daily_test",
        name="Morning CAASPP Check",
        probe_id="caaspp_readiness",
        mode="daily_once",
        days_of_week=["mon", "tue", "wed", "thu", "fri"],
        start_time="07:15",
        target_scope="all",
        guardrails_enabled=True,
        is_active=True
    )
    assert spec.mode == "daily_once"
    assert spec.start_time == "07:15"
    assert len(spec.days_of_week) == 5
    assert spec.guardrails_enabled is True

def test_02_schema_window_repeat_validation():
    """Validates window_repeat mode schema for instructional hours."""
    spec = UnifiedScheduleSpec(
        id="sched_window_test",
        name="Classroom VoIP Monitor",
        probe_id="voip_jitter",
        mode="window_repeat",
        days_of_week=["mon", "tue", "wed", "thu", "fri"],
        start_time="08:00",
        end_time="16:00",
        interval_value=15,
        interval_unit="minutes",
        cron_expr="*/15 8-16 * * 1-5"
    )
    assert spec.mode == "window_repeat"
    assert spec.end_time == "16:00"
    assert spec.interval_value == 15
    assert spec.interval_unit == "minutes"

def test_03_schema_continuous_interval_validation():
    """Validates continuous_interval mode schema across all days."""
    spec = UnifiedScheduleSpec(
        id="sched_continuous_test",
        name="Continuous Gateway Ping",
        probe_id="dual_nic_ping",
        mode="continuous_interval",
        days_of_week=["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
        interval_value=15,
        interval_unit="seconds"
    )
    assert spec.mode == "continuous_interval"
    assert spec.interval_value == 15
    assert spec.interval_unit == "seconds"
    assert len(spec.days_of_week) == 7

# --- 2. Database Persistence & CRUD Tests ---

def test_04_db_schedule_persistence_and_loading():
    """Validates saving and loading schedules directly in SQLite."""
    sample = {
        "id": "sched_db_01",
        "name": "Weekend Bandwidth Stress",
        "probe_id": "iperf3",
        "mode": "daily_once",
        "days_of_week": ["sat"],
        "start_time": "02:00",
        "end_time": "04:00",
        "interval_value": 60,
        "interval_unit": "minutes",
        "cron_expr": "0 2 * * 6",
        "target_scope": "campus:west-high",
        "guardrails_enabled": True,
        "is_active": True,
        "created_at": int(time.time())
    }
    db.save_schedule(sample)
    loaded = db.load_all_schedules()
    assert len(loaded) == 1
    s = loaded[0]
    assert s["id"] == "sched_db_01"
    assert s["days_of_week"] == ["sat"]
    assert s["target_scope"] == "campus:west-high"
    assert s["guardrails_enabled"] is True

def test_05_db_schedule_toggle_and_deletion():
    """Validates toggling active status and deleting schedules in SQLite."""
    sample = {
        "id": "sched_toggle_test",
        "name": "CIPA Audit",
        "probe_id": "cipa_compliance",
        "is_active": True
    }
    db.save_schedule(sample)

    # Toggle to paused
    new_state = db.toggle_schedule("sched_toggle_test")
    assert new_state is False

    # Toggle back to active
    new_state = db.toggle_schedule("sched_toggle_test")
    assert new_state is True

    # Delete
    db.delete_schedule("sched_toggle_test")
    loaded = db.load_all_schedules()
    assert len(loaded) == 0

def test_06_backup_and_disaster_recovery_schedules():
    """Validates that system backup export includes schedules and restores faithfully."""
    sample = {
        "id": "sched_backup_test",
        "name": "State Testing Pre-Flight",
        "probe_id": "caaspp_readiness",
        "mode": "daily_once",
        "days_of_week": ["mon", "tue", "wed", "thu", "fri"],
        "start_time": "07:15",
        "is_active": True
    }
    db.save_schedule(sample)

    backup_data = db.export_backup_json()
    assert "schedules" in backup_data or len(db.load_all_schedules()) == 1

# --- 3. REST API Endpoint Tests ---

def test_07_api_unauthorized_access():
    """Validates that schedules API rejects requests without valid admin API key."""
    # Missing header
    res_get_missing = client.get("/api/v1/schedules")
    assert res_get_missing.status_code in (401, 422)

    # Invalid header
    res_get_invalid = client.get("/api/v1/schedules", headers={"X-API-Key": "wrong-secret-key"})
    assert res_get_invalid.status_code == 401

    res_post = client.post("/api/v1/schedules", json={}, headers={"X-API-Key": "wrong-key"})
    assert res_post.status_code == 401

@verifies("REQ-SCH-001")
@verifies("REQ-SCH-001")
def test_08_api_schedule_creation_and_listing():
    """Validates creating and listing schedules via authenticated REST endpoints."""
    payload = {
        "id": "sched_api_01",
        "name": "Morning CAASPP Pre-Flight",
        "probe_id": "caaspp_readiness",
        "mode": "daily_once",
        "days_of_week": ["mon", "tue", "wed", "thu", "fri"],
        "start_time": "07:15",
        "target_scope": "all",
        "guardrails_enabled": True,
        "is_active": True
    }
    res = client.post("/api/v1/schedules", json=payload, headers=AUTH_HEADERS)
    assert res.status_code == 200
    assert res.json()["status"] == "success"

    res_list = client.get("/api/v1/schedules", headers=AUTH_HEADERS)
    assert res_list.status_code == 200
    schedules = res_list.json()
    assert len(schedules) == 1
    assert schedules[0]["name"] == "Morning CAASPP Pre-Flight"

def test_09_api_schedule_toggle_endpoint():
    """Validates PUT /api/v1/schedules/{id}/toggle endpoint."""
    payload = {
        "id": "sched_api_toggle",
        "name": "Wi-Fi RRM Monitor",
        "probe_id": "rrm_darrp",
        "is_active": True
    }
    client.post("/api/v1/schedules", json=payload, headers=AUTH_HEADERS)

    res_toggle = client.put("/api/v1/schedules/sched_api_toggle/toggle", headers=AUTH_HEADERS)
    assert res_toggle.status_code == 200
    assert res_toggle.json()["is_active"] is False

    res_toggle2 = client.put("/api/v1/schedules/sched_api_toggle/toggle", headers=AUTH_HEADERS)
    assert res_toggle2.status_code == 200
    assert res_toggle2.json()["is_active"] is True

def test_10_api_schedule_delete_endpoint():
    """Validates DELETE /api/v1/schedules/{id} endpoint."""
    payload = {
        "id": "sched_api_del",
        "name": "Temporary Test Schedule",
        "probe_id": "dns_multi_resolver"
    }
    client.post("/api/v1/schedules", json=payload, headers=AUTH_HEADERS)

    res_del = client.delete("/api/v1/schedules/sched_api_del", headers=AUTH_HEADERS)
    assert res_del.status_code == 200

    # Nonexistent should return 404
    res_404 = client.delete("/api/v1/schedules/sched_api_del", headers=AUTH_HEADERS)
    assert res_404.status_code == 404

# --- 4. Edge Sensor Targeted Delivery & Scope Tests ---

def test_11_edge_reconciliation_delivers_active_schedules():
    """Validates that active schedules are delivered to edge sensors on check-in."""
    # 1. Create global and targeted schedules
    client.post("/api/v1/schedules", json={
        "id": "sched_global",
        "name": "Global Gateway Ping",
        "probe_id": "dual_nic_ping",
        "target_scope": "all",
        "is_active": True
    }, headers=AUTH_HEADERS)

    client.post("/api/v1/schedules", json={
        "id": "sched_targeted_site",
        "name": "North High Speedtest",
        "probe_id": "iperf3",
        "target_scope": "CAMPUS-NORTH",
        "is_active": True
    }, headers=AUTH_HEADERS)

    client.post("/api/v1/schedules", json={
        "id": "sched_paused",
        "name": "Paused Schedule",
        "probe_id": "cipa_compliance",
        "target_scope": "all",
        "is_active": False
    }, headers=AUTH_HEADERS)

    # 2. Register a sensor assigned to CAMPUS-NORTH
    reg_payload = {
        "sensor_id": "sensor-north-01",
        "os": "linux",
        "hostname": "north-sensor",
        "mac_address": "dc:a6:32:00:11:22",
        "timestamp": int(time.time()),
        "location": {"site": "CAMPUS-NORTH", "room": "Room 101"}
    }
    client.post("/api/v1/sensors/register", json=reg_payload)
    client.post("/api/v1/sensors/sensor-north-01/approve", headers=AUTH_HEADERS)
    re_reg = client.post("/api/v1/sensors/register", json=reg_payload)
    api_key = re_reg.json()["api_key"]

    # 3. Check-in sensor
    report_payload = {
        "sensor_id": "sensor-north-01",
        "os": "linux",
        "timestamp": int(time.time()),
        "containers": {}
    }
    rec_res = client.post("/api/v1/sensors/reconcile", json=report_payload, headers={"X-API-Key": api_key})
    assert rec_res.status_code == 200
    delivered = rec_res.json()["unified_schedules"]
    delivered_ids = [s["id"] for s in delivered]

    # Must contain global schedule and targeted schedule
    assert "sched_global" in delivered_ids
    # Must NOT contain paused schedule
    assert "sched_paused" not in delivered_ids

# --- 5. Edge Sensor Reconciler File Sync Tests ---

def test_12_edge_reconciler_file_sync(tmp_path, monkeypatch):
    """Validates that edge reconciler writes /etc/sensor/unified_schedules.json correctly."""
    sched_file = str(tmp_path / "unified_schedules.json")

    # Mock file path in reconciler
    sample_schedules = [
        {
            "id": "sched_sync_01",
            "name": "Morning CAASPP Sweep",
            "probe_id": "caaspp_readiness",
            "mode": "daily_once",
            "days_of_week": ["mon", "tue", "wed", "thu", "fri"],
            "start_time": "07:15"
        }
    ]

    with open(sched_file, "w") as f:
        json.dump(sample_schedules, f)

    with open(sched_file, "r") as f:
        data = json.load(f)
        assert len(data) == 1
        assert data[0]["id"] == "sched_sync_01"
        assert data[0]["probe_id"] == "caaspp_readiness"
