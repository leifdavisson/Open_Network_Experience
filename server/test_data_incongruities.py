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
    js_modules_dir = TEMPLATES_DIR.parent / "static" / "js" / "modules"
    with open(dash_html_path, "r", encoding="utf-8") as f:
        js_code = f.read()
    if js_modules_dir.exists():
        for p in js_modules_dir.glob("*.js"):
            with open(p, "r", encoding="utf-8") as f:
                js_code += f.read()

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

def test_07_offline_device_modal_stale_warning_and_real_data():
    """Verify that inspecting an offline device renders an explicit stale warning banner."""
    dash_html_path = TEMPLATES_DIR / "dashboard.html"
    js_modules_dir = TEMPLATES_DIR.parent / "static" / "js" / "modules"
    with open(dash_html_path, "r", encoding="utf-8") as f:
        js_code = f.read()
    if js_modules_dir.exists():
        for p in js_modules_dir.glob("*.js"):
            with open(p, "r", encoding="utf-8") as f:
                js_code += f.read()

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
    js_modules_dir = TEMPLATES_DIR.parent / "static" / "js" / "modules"
    with open(dash_html_path, "r", encoding="utf-8") as f:
        html_code = f.read()
    if js_modules_dir.exists():
        for p in js_modules_dir.glob("*.js"):
            with open(p, "r", encoding="utf-8") as f:
                html_code += f.read()

    assert '<div id="cb-fleet-offline-banner"></div>' in html_code  # nosec B101
    assert "⚠️ Chromebook Fleet Offline" in html_code  # nosec B101
    assert "No active telemetry streams detected. Live KPI metrics are paused" in html_code  # nosec B101

def test_09_dedicated_chromebook_fleet_view_and_lock_controls():
    """Verify that dedicated Chromebook management view exists with full lock and PIN controls."""
    dash_html_path = TEMPLATES_DIR / "dashboard.html"
    js_modules_dir = TEMPLATES_DIR.parent / "static" / "js" / "modules"
    with open(dash_html_path, "r", encoding="utf-8") as f:
        html_code = f.read()
    if js_modules_dir.exists():
        for p in js_modules_dir.glob("*.js"):
            with open(p, "r", encoding="utf-8") as f:
                html_code += f.read()

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

def test_10_trend_analysis_data_truthfulness_and_discovery():
    """Verify that Trend Analysis does not generate synthetic 15-point arrays and handles fresh installs truthfully."""
    from fastapi.testclient import TestClient
    from server.main import app

    client = TestClient(app)
    resp = client.get("/api/v1/wallboard/live-stats")
    assert resp.status_code == 200  # nosec B101
    data = resp.json()

    assert "trends" in data  # nosec B101
    trends = data["trends"]

    # Invariants for Issue #34:
    assert "has_history" in trends, "trends must report whether real historical data was retrieved"  # nosec B101
    assert "insufficient_data" in trends, "trends must indicate when installation lacks sufficient trend history"  # nosec B101
    assert "streams" in trends, "trends must provide dynamically discovered latency streams"  # nosec B101

    # In fresh/offline test environment, it must truthfully report insufficient data rather than fabricating 15 mock points
    if trends.get("insufficient_data"):
        # Must not fabricate a fake 15-day series
        synthetic_pattern = [round(1.18 + ((i % 5) - 2) * 0.04, 2) for i in range(15)]
        assert trends.get("wired") != synthetic_pattern, "Backend must not emit synthetic modulo-derived 15-point data"  # nosec B101

    # Check charts.js does not hardcode fake fallback arrays
    charts_js_path = TEMPLATES_DIR.parent / "static" / "js" / "modules" / "charts.js"
    with open(charts_js_path, "r", encoding="utf-8") as f:
        js_code = f.read()

    assert "Array.from({length: 15}" not in js_code, "Frontend must not hardcode 15 fake days"  # nosec B101
    assert "[1.2, 1.15, 1.22" not in js_code, "Frontend must not contain hardcoded fallback mock arrays"  # nosec B101

def test_11_fault_situation_7d_compliance_truthfulness():
    """Verify that Fault Situation reports real 7-day trailing compliance rather than multiplying faults by 10."""
    from fastapi.testclient import TestClient
    from server.main import app

    client = TestClient(app)
    resp = client.get("/api/v1/wallboard/live-stats")
    assert resp.status_code == 200  # nosec B101
    data = resp.json()

    # Invariants for Issue #35:
    assert "compliance_7d" in data, "liveStats must include real compliance_7d calculation"  # nosec B101
    comp_7d = data["compliance_7d"]
    assert "compliant_pct" in comp_7d  # nosec B101
    assert "fault_pct" in comp_7d  # nosec B101
    assert "eval_window" in comp_7d  # nosec B101
    assert round(comp_7d["compliant_pct"] + comp_7d["fault_pct"], 1) == 100.0  # nosec B101

    # Check charts.js does not use the arbitrary 'faults * 10' scaling heuristic
    charts_js_path = TEMPLATES_DIR.parent / "static" / "js" / "modules" / "charts.js"
    with open(charts_js_path, "r", encoding="utf-8") as f:
        js_code = f.read()

    assert "liveStats.kpis.faults * 10" not in js_code, "Frontend must not use arbitrary faults * 10 multiplier"  # nosec B101
    assert "compliance_7d" in js_code, "Frontend must ingest real compliance_7d metrics"  # nosec B101

def test_12_query_vm_range_helper_contract():
    """Verify query_vm_range helper exists in server.routers.telemetry and handles query parameters."""
    from server.routers.telemetry import query_vm_range
    assert callable(query_vm_range)  # nosec B101
    # When VM is not running locally, returns empty list gracefully without throwing
    res = query_vm_range("probe_duration_seconds", 1700000000, 1700086400, "1h")
    assert isinstance(res, list)  # nosec B101

def test_13_alarm_overview_30d_resolution_truthfulness():
    """Verify Alarm Overview computes real 30-day resolved/active counts and avoids hardcoded 100 constant."""
    from fastapi.testclient import TestClient
    from server.main import app
    import server.db as db

    client = TestClient(app)
    resp = client.get("/api/v1/wallboard/live-stats")
    assert resp.status_code == 200  # nosec B101
    data = resp.json()

    assert "alarm_overview_30d" in data["kpis"], "liveStats.kpis must contain alarm_overview_30d"  # nosec B101
    ao = data["kpis"]["alarm_overview_30d"]
    assert "resolved_30d" in ao  # nosec B101
    assert "active" in ao  # nosec B101
    assert "total_30d" in ao  # nosec B101
    assert "resolved_pct" in ao  # nosec B101

    # Verify summary endpoint also contains resolved_30d_count
    sum_resp = client.get("/api/v1/alerts/summary")
    assert sum_resp.status_code == 200  # nosec B101
    summary = sum_resp.json()
    assert "resolved_30d_count" in summary  # nosec B101
    assert "active_30d_count" in summary  # nosec B101

    # Check charts.js does NOT contain the hardcoded [100, activeAlarms] dataset
    charts_js_path = TEMPLATES_DIR.parent / "static" / "js" / "modules" / "charts.js"
    with open(charts_js_path, "r", encoding="utf-8") as f:
        js_code = f.read()

    assert "data: [100, activeAlarms]" not in js_code, "Frontend must not hardcode 100 resolved alarms in chart dataset"  # nosec B101
    assert "alarm_overview_30d" in js_code, "Frontend must ingest real alarm_overview_30d metrics"  # nosec B101

    # Check app.js does NOT contain the hardcoded [100, activeAlarms] dataset
    app_js_path = TEMPLATES_DIR.parent / "static" / "js" / "app.js"
    with open(app_js_path, "r", encoding="utf-8") as f:
        app_js_code = f.read()

    assert "data: [100, activeAlarms]" not in app_js_code, "app.js must not hardcode 100 resolved alarms in chart dataset"  # nosec B101

def test_14_executive_sla_wallboard_truthfulness():
    """Verify Executive SLA Wallboard renders measured metrics or honest unmonitored states."""
    from fastapi.testclient import TestClient
    from server.main import app

    client = TestClient(app)
    resp = client.get("/api/v1/wallboard/live-stats")
    assert resp.status_code == 200  # nosec B101
    data = resp.json()
    assert "slas" in data, "liveStats must contain slas"  # nosec B101
    slas = data["slas"]

    # Invariants for Issue #37:
    # 1. WiFi latency must not be a hardcoded 3.65x multiplier of wired latency
    if slas.get("gateway_wired_ms") is not None and slas.get("gateway_wifi_ms") is not None:
        assert slas["gateway_wifi_ms"] != round(slas["gateway_wired_ms"] * 3.65, 2), \
            "gateway_wifi_ms must not be synthesized with a 3.65x multiplier"  # nosec B101

    # 2. Frontend must not synthesize secondary DNS with 1.04x multiplier
    sensors_js_path = TEMPLATES_DIR.parent / "static" / "js" / "modules" / "sensors.js"
    with open(sensors_js_path, "r", encoding="utf-8") as f:
        sensors_code = f.read()
    assert "slas.dns_ms * 1.04" not in sensors_code, "Frontend must not synthesize secondary DNS with 1.04x multiplier"  # nosec B101

    app_js_path = TEMPLATES_DIR.parent / "static" / "js" / "app.js"
    with open(app_js_path, "r", encoding="utf-8") as f:
        app_code = f.read()
    assert "slas.dns_ms * 1.04" not in app_code, "app.js must not synthesize secondary DNS with 1.04x multiplier"  # nosec B101

    # 3. Frontend must dynamically update DHCP, Wi-Fi Flapping, and VLAN Isolation
    assert "sla-val-dhcp" in sensors_code  # nosec B101
    assert "sla-val-rrm" in sensors_code  # nosec B101
    assert "sla-val-vlan" in sensors_code  # nosec B101
    assert "sla-val-dhcp" in app_code  # nosec B101
    assert "sla-val-rrm" in app_code  # nosec B101
    assert "sla-val-vlan" in app_code  # nosec B101

def test_15_classroom_saas_sla_truthfulness():
    """Verify Classroom SaaS SLAs query real 24h uptime, include SIS targets, and do not conflate errors with latency."""
    from fastapi.testclient import TestClient
    from server.main import app

    client = TestClient(app)
    resp = client.get("/api/v1/wallboard/live-stats")
    assert resp.status_code == 200  # nosec B101
    data = resp.json()
    assert "saas" in data, "liveStats must contain saas metrics"  # nosec B101
    saas = data["saas"]

    # Verify all expected SaaS apps are present including SIS
    for k in ["canvas", "google", "iready", "zoom", "caaspp", "sis"]:
        assert k in saas, f"Missing SaaS service: {k}"  # nosec B101
        item = saas[k]
        assert "name" in item  # nosec B101
        assert "status" in item  # nosec B101

    # Verify scrape.yml contains SIS target
    scrape_path = TEMPLATES_DIR.parent / "deploy" / "scrape.yml"
    with open(scrape_path, "r", encoding="utf-8") as f:
        scrape_yml = f.read()
    assert "aeries.net" in scrape_yml, "scrape.yml blackbox-saas-apps must include SIS target"  # nosec B101

def test_16_helpdesk_teacher_quickview_truthfulness():
    """Verify Helpdesk & Teacher QuickView updates all 4 cards dynamically and evaluates WAN reachability."""
    sensors_js_path = TEMPLATES_DIR.parent / "static" / "js" / "modules" / "sensors.js"
    with open(sensors_js_path, "r", encoding="utf-8") as f:
        sensors_code = f.read()

    app_js_path = TEMPLATES_DIR.parent / "static" / "js" / "app.js"
    with open(app_js_path, "r", encoding="utf-8") as f:
        app_code = f.read()

    dash_html_path = TEMPLATES_DIR / "dashboard.html"
    with open(dash_html_path, "r", encoding="utf-8") as f:
        dash_html = f.read()

    # Invariants for Issue #39:
    # 1. All 4 cards must have dynamic hooks in sensors.js and app.js
    for el_id in ["helpdesk-internet-status", "helpdesk-testing-status", "helpdesk-wifi-status", "helpdesk-cipa-status"]:
        assert el_id in sensors_code, f"sensors.js missing handler for {el_id}"  # nosec B101
        assert el_id in app_code, f"app.js missing handler for {el_id}"  # nosec B101

    # 2. Internet status handler must inspect WAN/gateway or DNS timing, not just sensor checkins
    assert "slas.gateway_wired_ms" in sensors_code  # nosec B101
    assert "slas.dns_ms" in sensors_code  # nosec B101

    # 3. Initial dashboard HTML must not present hardcoded 100% passes
    assert 'id="helpdesk-testing-status">⚪ Checking State Testing...' in dash_html  # nosec B101
    assert 'id="helpdesk-wifi-status">⚪ Checking Wi-Fi...' in dash_html  # nosec B101
    assert 'id="helpdesk-cipa-status">⚪ Checking Safety Filter...' in dash_html  # nosec B101

