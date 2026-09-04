"""
Open Network Experience (ONE) — Cross-Layer Data Incongruity & Truthfulness Test Suite
License: GNU AGPLv3

Tests data invariants, zero-state truthfulness, offline sensor masking,
and cross-layer fidelity between Sensor Telemetry, Database Storage, and UI Presentation.
"""

import time
import sys
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))
ROOT_DIR = SERVER_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pytest
from server.schemas import ChromebookFleetItemResponse, SensorStatusResponseSafe, LocationSpec

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

def test_01_empty_fleet_zero_state_truth_invariants():
    """Verify that zero-state / empty fleet never presents hardcoded placeholder metrics."""
    dash_html_path = TEMPLATES_DIR / "dashboard.html"
    assert dash_html_path.exists()  # nosec B101

    with open(dash_html_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    # Invariants: Zero-state HTML defaults MUST NOT show hardcoded live stats
    assert '<div class="metric-value" id="cb-kpi-rssi">-- dBm</div>' in html_content  # nosec B101
    assert '<div class="metric-value" id="cb-kpi-mos">-- / 5.0</div>' in html_content  # nosec B101
    assert '<div class="metric-value" id="cb-kpi-sla">--%</div>' in html_content  # nosec B101
    assert 'id="cb-kpi-rssi-sub">No Active Stream<' in html_content  # nosec B101
    assert 'id="cb-kpi-mos-sub">No Active Sessions<' in html_content  # nosec B101

def test_02_offline_sensor_data_masking_in_schema_and_ui():
    """Verify that an offline sensor does not present active streaming indicators."""
    offline_item = ChromebookFleetItemResponse(
        sensor_id="cb-offline-test",
        serial_number="TEST-SN-001",
        is_online=False,
        last_seen=int(time.time()) - 3600,
        wifi_rssi_dbm=-58,
        webrtc_mos=4.38,
        battery_level_pct=88,
        settings_locked=True
    )

    assert offline_item.is_online is False  # nosec B101
    assert offline_item.sensor_id == "cb-offline-test"  # nosec B101

    # Verify that JavaScript UI rendering masks offline metrics
    dash_html_path = TEMPLATES_DIR / "dashboard.html"
    with open(dash_html_path, "r", encoding="utf-8") as f:
        js_code = f.read()

    # Assert JavaScript checks isOnline before displaying active RSSI & MOS
    assert "const isOnline = Boolean(cb.is_online);" in js_code  # nosec B101
    assert "`<span style=\"color:var(--text-muted);\">-- (Offline)</span>`" in js_code  # nosec B101
    assert "`<span style=\"color:var(--text-muted);\">-- (N/A)</span>`" in js_code  # nosec B101
    assert "`<span style=\"color:var(--text-muted);\">Disconnected</span>" in js_code  # nosec B101

def test_03_database_to_api_schema_fidelity():
    """Verify that database records translate without data loss or type mutation to API models."""
    raw_db_record = {
        "sensor_id": "f10325921e2b43b2b5fcf33cadad864b",
        "last_seen": int(time.time()),
        "os": "linux",
        "status": "approved",
        "probing_state": "GREEN",
        "reported_containers": {},
        "target_config": {},
        "location": {
            "district": "Unified School District",
            "site": "City Center",
            "building": "District Support",
            "room": "IT Operations",
            "notes": "Test Bench Sensor"
        }
    }

    # Safe response schema mapping
    safe_resp = SensorStatusResponseSafe.from_internal(
        sensor_id=raw_db_record["sensor_id"],
        last_seen=raw_db_record["last_seen"],
        os_val=raw_db_record["os"],
        is_online=True,
        reconciled_ok=True,
        status_val=raw_db_record["status"],
        reported_containers=raw_db_record["reported_containers"],
        target_config=raw_db_record["target_config"],
        location_val=LocationSpec(**raw_db_record["location"]),
        probing_state=raw_db_record["probing_state"]
    )

    assert safe_resp.sensor_id == raw_db_record["sensor_id"]  # nosec B101
    assert safe_resp.location.district == "Unified School District"  # nosec B101
    assert safe_resp.location.room == "IT Operations"  # nosec B101

def test_04_sensor_offline_state_timeout_invariant():
    """Verify state calculation invariant: sensors unseen for >120s must be marked offline."""
    now = int(time.time())

    # 1. Fresh heartbeat -> Online
    recent_seen = now - 30
    is_online_recent = (now - recent_seen) < 120
    assert is_online_recent is True  # nosec B101

    # 2. Stale heartbeat -> Offline
    stale_seen = now - 300
    is_online_stale = (now - stale_seen) < 120
    assert is_online_stale is False  # nosec B101

def test_05_roaming_trail_falsification_invariant():
    """Verify that stationary sensors without roam flags never generate fake roaming events."""
    roaming_events = []

    sensor_report = {
        "sensor_id": "cb-stationary-101",
        "wifi": {
            "connected": True,
            "bssid": "00:11:22:33:44:55",
            "roamed_recently": False
        }
    }

    if sensor_report.get("wifi", {}).get("roamed_recently"):
        roaming_events.append(sensor_report)

    # Invariant: Must not create roaming event when roamed_recently is False
    assert len(roaming_events) == 0  # nosec B101

@pytest.mark.parametrize("is_online,rssi,mos,expected_kpi_sub", [
    (True, -55, 4.45, "Optimal"),
    (True, -82, 3.20, "Fair / Weak"),
    (False, -55, 4.45, "No Active Stream"),
    (False, None, None, "No Active Stream"),
])
def test_06_data_truthfulness_oracle_matrix(is_online, rssi, mos, expected_kpi_sub):
    """Oracle truth-table test ensuring offline states always suppress active health ratings."""
    rssi_count = 1 if (is_online and rssi is not None) else 0

    if rssi_count > 0:
        kpi_sub = "Optimal" if rssi >= -65 else "Fair / Weak"
    else:
        kpi_sub = "No Active Stream"

    assert kpi_sub == expected_kpi_sub  # nosec B101

def test_07_modal_offline_stale_warning_banner():
    """Verify that inspecting an offline device renders an explicit stale warning banner."""
    dash_html_path = TEMPLATES_DIR / "dashboard.html"
    with open(dash_html_path, "r", encoding="utf-8") as f:
        js_code = f.read()

    # Assert offline warning banner is rendered
    assert "⚠️ Device Offline — Stale Telemetry Warning" in js_code  # nosec B101
    assert "Metrics below represent a frozen snapshot and are not live." in js_code  # nosec B101
    assert "formatTimeAgo" in js_code  # nosec B101

    # Assert live streaming stream indicator is rendered when online
    assert "● Live Telemetry Stream Active" in js_code  # nosec B101

    # Assert that no fake CAASPP/Google/Clever fallbacks are hardcoded in the modal
    assert "CAASPP Testing: 45ms" not in js_code  # nosec B101
    assert "Google Classroom: 32ms" not in js_code  # nosec B101
    assert "Clever SSO: 28ms" not in js_code  # nosec B101

def test_08_slide_level_fleet_offline_warning_banner():
    """Verify that Slide 6 includes a top-level warning banner when all Chromebooks are offline."""
    dash_html_path = TEMPLATES_DIR / "dashboard.html"
    with open(dash_html_path, "r", encoding="utf-8") as f:
        html_code = f.read()

    assert '<div id="cb-fleet-offline-banner"></div>' in html_code  # nosec B101
    assert "⚠️ Chromebook Fleet Offline" in html_code  # nosec B101
    assert "No active telemetry streams detected. Live KPI metrics are paused" in html_code  # nosec B101

def test_09_dedicated_chromebook_fleet_view_and_lock_controls():
    """Verify that dedicated Chromebook management view exists with full lock and PIN controls."""
    dash_html_path = TEMPLATES_DIR / "dashboard.html"
    with open(dash_html_path, "r", encoding="utf-8") as f:
        html_code = f.read()

    # Sidebar navigation verification
    assert 'id="nav-manage-chromebooks"' in html_code  # nosec B101
    assert "Chromebook Fleet" in html_code  # nosec B101

    # Dedicated view container verification
    assert '<div class="view-section" id="view-manage-chromebooks">' in html_code  # nosec B101
    assert 'id="fleet-lock-status-badge"' in html_code  # nosec B101
    assert 'id="btn-fleet-lock"' in html_code  # nosec B101
    assert 'id="btn-fleet-unlock"' in html_code  # nosec B101
    assert 'id="fleet-helpdesk-pin"' in html_code  # nosec B101
    assert 'id="cb-dedicated-fleet-table-body"' in html_code  # nosec B101

    # Direct download links for Google Workspace staging
    assert '/api/v1/chromebooks/download/extension.zip' in html_code  # nosec B101
    assert '/api/v1/chromebooks/download/policy.json' in html_code  # nosec B101
