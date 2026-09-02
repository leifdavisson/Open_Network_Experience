"""
Dedicated Test Suite for Active Alert Panel & Alertmanager Webhook Lifecycle Engine.
Tests:
  1. Pydantic Schemas & Data Models
  2. SQLite Database Persistence, Deduplication & CRUD Operations
  3. System Backup & Disaster Recovery Roundtrip with Alerts
  4. Prometheus Alertmanager Webhook Ingestion & Fingerprint Deduplication
  5. Alert Status Transitions (FIRING -> ACKNOWLEDGED -> RESOLVED)
  6. REST API Endpoints, Filters & Summary Aggregation
  7. Telemetry & Wallboard Integration (Live Alarms KPI)
  8. Dashboard Web UI Elements & Modals Validation
  9. Prometheus / VictoriaMetrics Alert Rules YAML Specification Validation
  10. Automated Forensic PCAP Evidence Capture & Drilldown Endpoints
"""

import os
import time
import yaml
import pytest
from fastapi.testclient import TestClient

def verifies(req_id: str):
    def decorator(fn):
        fn.__verifies__ = req_id
        return fn
    return decorator

import server.db as db
import server.main as main
from server.schemas import (
    AlertmanagerAlert,
    AlertmanagerWebhookPayload,
    AlertRecord
)

ADMIN_KEY = "admin-noc-key-change-me"
AUTH_HEADERS = {"X-API-Key": ADMIN_KEY}
client = TestClient(main.app)

@pytest.fixture(autouse=True)
def setup_isolated_db(tmp_path, monkeypatch):
    """Isolates each test in a clean temporary SQLite database."""
    temp_db = str(tmp_path / "test_alerts.db")
    monkeypatch.setenv("DB_PATH", temp_db)
    monkeypatch.setattr(db, "DB_PATH", temp_db)
    db.init_db()
    main.SENSORS_DB.clear()
    main.PROBES_DB.clear()
    main.SCHEDULES_DB.clear()


# --- 1. Schema Validation Tests ---

@verifies("REQ-ALT-SCHEMA-001")
def test_01_alert_schemas_validation():
    """Validates Alertmanager and Alert record Pydantic schemas."""
    alert_item = AlertmanagerAlert(
        status="firing",
        labels={"alertname": "CAASPPUntrustedCertificate", "severity": "critical", "campus_id": "CAMPUS-WEST-HIGH"},
        annotations={"summary": "Untrusted MITM cert detected", "description": "Cambium TDS synthetic probe failed TLS handshake."},
        startsAt="2026-08-30T19:00:00Z"
    )
    assert alert_item.status == "firing"
    assert alert_item.labels["alertname"] == "CAASPPUntrustedCertificate"

    payload = AlertmanagerWebhookPayload(
        receiver="default-receiver",
        status="firing",
        alerts=[alert_item]
    )
    assert len(payload.alerts) == 1

    record = AlertRecord(
        id="alt-test-01",
        fingerprint="fp-test-01",
        status="firing",
        severity="critical",
        title="Test Alert",
        starts_at=int(time.time())
    )
    assert record.status == "firing"
    assert record.severity == "critical"


# --- 2. Database CRUD & Deduplication Tests ---

@verifies("REQ-ALT-DB-001")
def test_02_database_crud_operations():
    """Tests saving, retrieving, filtering, and deleting alerts in SQLite."""
    now = int(time.time())
    alt_data = {
        "id": "alt-unit-101",
        "fingerprint": "fp-unit-101",
        "status": "firing",
        "severity": "critical",
        "title": "CAASPP SSL Interception",
        "description": "MITM certificate detected.",
        "sensor_id": "pi5-science-01",
        "campus_id": "CAMPUS-WEST-HIGH",
        "probe_id": "caaspp_readiness",
        "starts_at": now,
        "raw_labels": {"alertname": "CAASPPUntrustedCertificate", "severity": "critical"},
        "raw_annotations": {"summary": "CAASPP SSL Interception"}
    }
    saved_id = db.save_alert(alt_data)
    assert saved_id == "alt-unit-101"

    # Retrieve by ID
    loaded = db.load_alert_by_id("alt-unit-101")
    assert loaded is not None
    assert loaded["title"] == "CAASPP SSL Interception"
    assert loaded["severity"] == "critical"
    assert loaded["status"] == "firing"

    # Retrieve active by fingerprint
    active_fp = db.load_active_alert_by_fingerprint("fp-unit-101")
    assert active_fp is not None
    assert active_fp["id"] == "alt-unit-101"

    # Acknowledge
    acked = db.acknowledge_alert("alt-unit-101", acknowledged_by="NOC Lead")
    assert acked["status"] == "acknowledged"
    assert acked["acknowledged_by"] == "NOC Lead"
    assert acked["acknowledged_at"] is not None

    # Resolve
    resolved = db.resolve_alert("alt-unit-101", resolution_notes="Firewall bypass rule added.")
    assert resolved["status"] == "resolved"
    assert resolved["resolution_notes"] == "Firewall bypass rule added."
    assert resolved["ends_at"] is not None

    # Verify no longer returned by load_active_alert_by_fingerprint
    assert db.load_active_alert_by_fingerprint("fp-unit-101") is None

    # Delete
    deleted = db.delete_alert("alt-unit-101")
    assert deleted is True
    assert db.load_alert_by_id("alt-unit-101") is None


# --- 3. Summary & Filtering Tests ---

@verifies("REQ-ALT-SUMMARY-001")
def test_03_alerts_summary_and_filtering():
    """Tests multi-criteria filtering and summary metrics."""
    now = int(time.time())
    db.save_alert({
        "id": "alt-1",
        "fingerprint": "fp-1",
        "status": "firing",
        "severity": "critical",
        "title": "Critical Alarm 1",
        "campus_id": "CAMPUS-WEST",
        "sensor_id": "sensor-1",
        "starts_at": now
    })
    db.save_alert({
        "id": "alt-2",
        "fingerprint": "fp-2",
        "status": "acknowledged",
        "severity": "warning",
        "title": "Warning Alarm 2",
        "campus_id": "CAMPUS-WEST",
        "sensor_id": "sensor-2",
        "starts_at": now
    })
    db.save_alert({
        "id": "alt-3",
        "fingerprint": "fp-3",
        "status": "resolved",
        "severity": "info",
        "title": "Info Alarm 3",
        "campus_id": "CAMPUS-EAST",
        "sensor_id": "sensor-3",
        "starts_at": now - 3600,
        "ends_at": now - 1800
    })

    summary = db.get_alerts_summary()
    assert summary["total_count"] == 3
    assert summary["open_count"] == 2  # firing + acknowledged
    assert summary["firing_count"] == 1
    assert summary["acknowledged_count"] == 1
    assert summary["critical_count"] == 1
    assert summary["warning_count"] == 1
    assert summary["resolved_24h_count"] == 1

    # Filter tests
    active_alerts = db.load_all_alerts(status="active")
    assert len(active_alerts) == 2

    crit_alerts = db.load_all_alerts(severity="critical")
    assert len(crit_alerts) == 1
    assert crit_alerts[0]["id"] == "alt-1"

    west_alerts = db.load_all_alerts(campus_id="CAMPUS-WEST")
    assert len(west_alerts) == 2


# --- 4. Backup & Disaster Recovery Roundtrip ---

@verifies("REQ-ALT-BACKUP-001")
def test_04_backup_restore_roundtrip():
    """Ensures alerts are persisted and restored during disaster recovery backups."""
    now = int(time.time())
    db.save_alert({
        "id": "alt-backup-test",
        "fingerprint": "fp-backup-test",
        "status": "firing",
        "severity": "critical",
        "title": "Disaster Recovery Test Alarm",
        "starts_at": now
    })

    backup = db.export_backup_json()
    assert "alerts" in backup
    assert any(a["id"] == "alt-backup-test" for a in backup["alerts"])

    # Clear and restore
    db.delete_alert("alt-backup-test")
    assert db.load_alert_by_id("alt-backup-test") is None

    db.restore_backup_json(backup)
    restored = db.load_alert_by_id("alt-backup-test")
    assert restored is not None
    assert restored["title"] == "Disaster Recovery Test Alarm"


# --- 5. Alertmanager Webhook Ingestion & Lifecycle REST Tests ---

@verifies("REQ-ALT-WEBHOOK-001")
def test_05_alertmanager_webhook_lifecycle():
    """Tests Alertmanager webhook ingestion, deduplication, and resolution via REST."""
    webhook_payload = {
        "version": "4",
        "groupKey": "test-group",
        "status": "firing",
        "receiver": "default-receiver",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "CAASPPUntrustedCertificate",
                    "severity": "critical",
                    "campus_id": "CAMPUS-WEST-HIGH",
                    "sensor_id": "pi5-science-01",
                    "probe_id": "caaspp_readiness"
                },
                "annotations": {
                    "summary": "CAASPP Secure Browser SSL Certificate Interception",
                    "description": "Untrusted MITM certificate detected during synthetic pre-flight probe."
                },
                "startsAt": "2026-08-30T19:00:00Z",
                "fingerprint": "fp-caaspp-001"
            }
        ]
    }

    # Ingest webhook
    res = client.post("/api/v1/alerts/webhook", json=webhook_payload)
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["status"] == "success"
    assert res_data["firing_updated"] == 1

    # Check alert in database
    active = db.load_active_alert_by_fingerprint("fp-caaspp-001")
    assert active is not None
    assert active["status"] == "firing"
    assert active["severity"] == "critical"
    assert active["evidence_id"] is not None  # Auto PCAP capture generated!
    alert_id = active["id"]

    # Ingest identical firing alert (Deduplication)
    res2 = client.post("/api/v1/alerts/webhook", json=webhook_payload)
    assert res2.status_code == 200
    all_active = db.load_all_alerts(status="active")
    assert len(all_active) == 1
    assert all_active[0]["id"] == alert_id

    # Acknowledge via REST
    ack_res = client.post(f"/api/v1/alerts/{alert_id}/acknowledge", json={"acknowledged_by": "Senior NOC Engineer"})
    assert ack_res.status_code == 200
    assert ack_res.json()["status"] == "acknowledged"
    assert ack_res.json()["acknowledged_by"] == "Senior NOC Engineer"

    # Ingest resolve webhook for the same fingerprint
    resolve_payload = {
        "status": "resolved",
        "alerts": [
            {
                "status": "resolved",
                "labels": {
                    "alertname": "CAASPPUntrustedCertificate",
                    "severity": "critical",
                    "campus_id": "CAMPUS-WEST-HIGH",
                    "sensor_id": "pi5-science-01"
                },
                "annotations": {
                    "summary": "CAASPP Secure Browser SSL Certificate Interception"
                },
                "startsAt": "2026-08-30T19:00:00Z",
                "endsAt": "2026-08-30T19:15:00Z",
                "fingerprint": "fp-caaspp-001"
            }
        ]
    }
    res_resolve = client.post("/api/v1/alerts/webhook", json=resolve_payload)
    assert res_resolve.status_code == 200
    assert res_resolve.json()["resolved_updated"] == 1

    # Check alert is now resolved
    resolved_alert = db.load_alert_by_id(alert_id)
    assert resolved_alert["status"] == "resolved"


# --- 6. REST API Endpoints & Simulation ---

@verifies("REQ-ALT-REST-001")
def test_06_alerts_rest_endpoints():
    """Tests simulation, get, summary, acknowledge, and resolve REST endpoints."""
    # Simulate an alert
    sim_payload = {
        "alertname": "WiFiFlappingDetected",
        "severity": "warning",
        "title": "Wi-Fi AP Channel Hopping",
        "description": "High flapping observed on wlp1s0.",
        "campus_id": "CAMPUS-WEST-HIGH",
        "sensor_id": "pi5-science-01",
        "probe_id": "rrm_darrp"
    }
    sim_res = client.post("/api/v1/alerts/simulate", json=sim_payload)
    assert sim_res.status_code == 200
    alert_obj = sim_res.json()
    alert_id = alert_obj["id"]
    assert alert_obj["status"] == "firing"
    assert alert_obj["severity"] == "warning"
    assert alert_obj["evidence_id"] is not None

    # GET /api/v1/alerts
    list_res = client.get("/api/v1/alerts?status=active")
    assert list_res.status_code == 200
    alerts = list_res.json()
    assert len(alerts) >= 1
    assert any(a["id"] == alert_id for a in alerts)

    # GET /api/v1/alerts/summary
    sum_res = client.get("/api/v1/alerts/summary")
    assert sum_res.status_code == 200
    summary = sum_res.json()
    assert summary["open_count"] >= 1
    assert summary["warning_count"] >= 1

    # GET single alert
    get_res = client.get(f"/api/v1/alerts/{alert_id}")
    assert get_res.status_code == 200
    assert get_res.json()["title"] == "Wi-Fi AP Channel Hopping"

    # Ack via alias
    ack_res = client.post(f"/api/v1/alerts/{alert_id}/ack", json={"acknowledged_by": "Operator 42"})
    assert ack_res.status_code == 200
    assert ack_res.json()["status"] == "acknowledged"

    # Resolve via REST
    res_res = client.post(f"/api/v1/alerts/{alert_id}/resolve", json={"resolution_notes": "RF channel plan locked."})
    assert res_res.status_code == 200
    assert res_res.json()["status"] == "resolved"
    assert res_res.json()["resolution_notes"] == "RF channel plan locked."

    # Delete
    del_res = client.delete(f"/api/v1/alerts/{alert_id}")
    assert del_res.status_code == 200


# --- 7. Telemetry Wallboard Live Alarms Integration ---

@verifies("REQ-ALT-WALLBOARD-001")
def test_07_telemetry_wallboard_integration():
    """Verifies that live wallboard telemetry aggregates real active alarms count."""
    db.save_alert({
        "id": "alt-wallboard-test",
        "fingerprint": "fp-wallboard-test",
        "status": "firing",
        "severity": "critical",
        "title": "Wallboard Live Alarm Test",
        "campus_id": "CAMPUS-WEST-HIGH",
        "starts_at": int(time.time())
    })

    res = client.get("/api/v1/wallboard/live-stats")
    assert res.status_code == 200
    data = res.json()
    assert data["kpis"]["alarms"] >= 1
    assert any("Wallboard Live Alarm Test" in inc["title"] for inc in data["incidents"])


# --- 8. Web UI HTML Validation & DOM Balance ---

@verifies("REQ-ALT-UI-001")
def test_08_dashboard_ui_elements():
    """Validates that the Alert Center DOM elements, modals, PCAP inspection, and balanced DOM exist in dashboard.html."""
    res = client.get("/")
    assert res.status_code == 200
    html = res.text

    assert "id=\"nav-monitor-alerts\"" in html
    assert "id=\"view-monitor-alerts\"" in html
    assert "id=\"noc-alarms-banner\"" in html
    assert "id=\"alerts-table-body\"" in html
    assert "id=\"simulate-alert-modal\"" in html
    assert "id=\"resolve-alert-modal\"" in html
    assert "id=\"alert-detail-modal\"" in html
    assert "id=\"maintenance-modal\"" in html
    assert "id=\"view-configure-maintenance\"" in html
    assert "id=\"evidence-modal\"" in html
    assert "id=\"btn-download-pcap\"" in html
    assert "loadAlertCenterData()" in html
    assert "openEvidenceModal(" in html
    assert "renderEvidenceTable(" in html

    # Strict HTML Tag Balance & Well-Formedness Check
    from html.parser import HTMLParser
    class TagChecker(HTMLParser):
        def __init__(self):
            super().__init__()
            self.stack = []
            self.void_tags = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
            self.errors = []

        def handle_starttag(self, tag, attrs):
            if tag.lower() not in self.void_tags:
                self.stack.append((tag.lower(), self.getpos()))

        def handle_endtag(self, tag):
            tag_lower = tag.lower()
            if tag_lower in self.void_tags:
                return
            if not self.stack:
                self.errors.append(f"Unexpected end tag </{tag_lower}> at {self.getpos()}")
                return
            last_tag, last_pos = self.stack.pop()
            if last_tag != tag_lower:
                self.errors.append(f"Mismatched tag: expected </{last_tag}> (opened at {last_pos}), got </{tag_lower}> at {self.getpos()}")

    checker = TagChecker()
    checker.feed(html)
    assert len(checker.errors) == 0, f"HTML parser errors encountered: {checker.errors}"
    assert len(checker.stack) == 0, f"Unclosed tags on stack: {checker.stack}"


# --- 9. PromQL Alert Rules YAML Specification Validation ---

@verifies("REQ-ALT-RULES-001")
def test_09_alert_rules_yaml_validation():
    """Ensures alerts.rules.yml is well-formed YAML and defines all critical probe rules."""
    rules_path = os.path.join(os.path.dirname(__file__), "deploy", "alerts.rules.yml")
    assert os.path.exists(rules_path), f"Rules file not found at {rules_path}"

    with open(rules_path, "r") as f:
        rules_data = yaml.safe_load(f)

    assert "groups" in rules_data
    assert len(rules_data["groups"]) >= 1

    rule_names = []
    for grp in rules_data["groups"]:
        for r in grp.get("rules", []):
            rule_names.append(r.get("alert"))
            assert "expr" in r
            assert "labels" in r
            assert "severity" in r["labels"]
            assert "annotations" in r
            assert "summary" in r["annotations"]

    expected_rules = [
        "CAASPPUntrustedCertificate",
        "CampusGatewayDown",
        "DNSResolutionFailure",
        "WiFiFlappingDetected",
        "SaaSAppUnreachable",
        "SaaSAppHighLatency",
        "VoIPJitterDegraded",
        "SensorAgentOffline",
        "CIPABypassDetected",
        "ChromebookFleetRssiCritical"
    ]
    for exp in expected_rules:
        assert exp in rule_names, f"Expected alert rule '{exp}' missing from alerts.rules.yml"


# --- 10. Automated Forensic PCAP Evidence Capture & Endpoints ---

@verifies("REQ-ALT-PCAP-001")
def test_10_pcap_evidence_automatic_freeze_and_endpoints():
    """Verifies automatic PCAP evidence generation, on-demand capture, and retrieval endpoints."""
    # 1. Simulate alert without evidence_id -> system auto-captures PCAP evidence bundle
    sim_res = client.post("/api/v1/alerts/simulate", json={
        "alertname": "CAASPPUntrustedCertificate",
        "severity": "critical",
        "title": "CAASPP SSL Interception Test",
        "sensor_id": "pi5-science-01",
        "probe_id": "caaspp_readiness"
    })
    assert sim_res.status_code == 200
    alert_obj = sim_res.json()
    alert_id = alert_obj["id"]
    evidence_id = alert_obj.get("evidence_id")
    assert evidence_id is not None
    assert evidence_id.startswith("ev-pcap-")

    # 2. Retrieve evidence directly for the alert
    ev_res = client.get(f"/api/v1/alerts/{alert_id}/evidence")
    assert ev_res.status_code == 200
    ev_data = ev_res.json()
    assert ev_data["id"] == evidence_id
    assert ev_data["sensor_id"] == "pi5-science-01"
    assert "dissection" in ev_data
    assert "protocols" in ev_data["dissection"]

    # 3. Trigger manual PCAP freeze on existing alert
    cap_res = client.post(f"/api/v1/alerts/{alert_id}/capture-pcap")
    assert cap_res.status_code == 200
    new_ev_id = cap_res.json()["evidence_id"]
    assert new_ev_id is not None

    # Verify updated alert has new evidence_id
    alert_updated = client.get(f"/api/v1/alerts/{alert_id}").json()
    assert alert_updated["evidence_id"] == new_ev_id

    # 4. List all evidence bundles across the system
    all_ev_res = client.get("/api/v1/evidence", headers={"X-API-Key": "admin-noc-key-change-me"})
    assert all_ev_res.status_code == 200
    all_ev_list = all_ev_res.json()
    assert len(all_ev_list) >= 1
    assert any(e["id"] == new_ev_id for e in all_ev_list)


# --- 11. Custom Alert Rules Configuration & Toggle API Tests ---

@verifies("REQ-ALT-RULES-001")
def test_11_custom_alert_rules_crud_and_toggle():
    """Tests CRUD lifecycle and toggle state for custom metric threshold detection rules."""
    # 1. List seeded default alert rules
    rules_res = client.get("/api/v1/alerts/rules")
    assert rules_res.status_code == 200
    rules = rules_res.json()
    assert len(rules) >= 6

    # 2. Create a new custom threshold rule
    new_rule_payload = {
        "id": "rule_ci_test_dns",
        "name": "CI Test DNS Latency Threshold",
        "probe_id": "dns_multi_resolver",
        "metric": "rtt_ms",
        "operator": "gt",
        "threshold_value": 750.0,
        "unit": "ms",
        "duration_seconds": 45,
        "severity": "critical",
        "campus_id": "CAMPUS-WEST-HIGH",
        "sensor_id": "pi5-science-01",
        "channels": ["chan_slack_noc"],
        "autocapture_pcap": True,
        "is_active": True
    }
    create_res = client.post("/api/v1/alerts/rules", json=new_rule_payload)
    assert create_res.status_code == 200
    created = create_res.json()
    assert created["id"] == "rule_ci_test_dns"
    assert created["threshold_value"] == 750.0

    # 3. Retrieve rule by ID
    get_res = client.get("/api/v1/alerts/rules/rule_ci_test_dns")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "CI Test DNS Latency Threshold"

    # 4. Toggle rule active state
    toggle_res = client.post("/api/v1/alerts/rules/rule_ci_test_dns/toggle")
    assert toggle_res.status_code == 200
    assert toggle_res.json()["is_active"] is False

    # 5. Delete rule
    del_res = client.delete("/api/v1/alerts/rules/rule_ci_test_dns")
    assert del_res.status_code == 200
    assert client.get("/api/v1/alerts/rules/rule_ci_test_dns").status_code == 404


# --- 12. Notification Channels Webhook Dispatch & Test API Tests ---

@verifies("REQ-ALT-CHANNELS-001")
def test_12_notification_channels_crud_and_test_dispatch():
    """Tests CRUD operations and test dispatch connectivity for outbound webhook destinations."""
    # 1. List default notification channels
    chans_res = client.get("/api/v1/alerts/channels")
    assert chans_res.status_code == 200
    channels = chans_res.json()
    assert len(channels) >= 3

    # 2. Create new PagerDuty channel
    new_chan_payload = {
        "id": "chan_ci_test_pd",
        "name": "CI PagerDuty Escalation",
        "channel_type": "pagerduty",
        "endpoint_url": "https://events.pagerduty.com/v2/enqueue",
        "auth_headers": {"Authorization": "Token mock_key"},
        "min_severity": "critical",
        "is_active": True
    }
    create_res = client.post("/api/v1/alerts/channels", json=new_chan_payload)
    assert create_res.status_code == 200
    created = create_res.json()
    assert created["id"] == "chan_ci_test_pd"
    assert created["channel_type"] == "pagerduty"

    # 3. Send test notification to channel
    test_res = client.post("/api/v1/alerts/channels/chan_ci_test_pd/test", json={
        "sample_title": "Automated CI Test Alarm",
        "sample_severity": "critical",
        "sample_message": "Verifying delivery engine."
    })
    assert test_res.status_code == 200
    assert "status" in test_res.json()

    # 4. Delete channel
    del_res = client.delete("/api/v1/alerts/channels/chan_ci_test_pd")
    assert del_res.status_code == 200
    assert client.get("/api/v1/alerts/channels/chan_ci_test_pd").status_code == 404


# --- 13. District K-12 Email (SMTP) Channel & Dispatch Tests ---

@verifies("REQ-ALT-EMAIL-001")
def test_13_district_email_smtp_dispatch():
    """Verifies Google Workspace, Microsoft 365, and on-prem SMTP email channel configurations & delivery."""
    # 1. Create Google Workspace SMTP relay channel
    g_relay_payload = {
        "id": "chan_google_workspace",
        "name": "District NOC Google Workspace Relay",
        "channel_type": "email",
        "endpoint_url": "smtp-relay.gmail.com:587",
        "auth_headers": {
            "smtp_host": "smtp-relay.gmail.com",
            "smtp_port": 587,
            "security_mode": "starttls",
            "from_email": "noc-alerts@district.edu",
            "from_name": "ONE Platform Network Monitor",
            "recipients": "noc@district.edu, helpdesk@district.edu",
            "username": "",
            "password": ""
        },
        "min_severity": "critical",
        "is_active": True
    }
    g_res = client.post("/api/v1/alerts/channels", json=g_relay_payload)
    assert g_res.status_code == 200
    assert g_res.json()["channel_type"] == "email"

    # 2. Create Microsoft 365 Exchange Online channel
    m365_payload = {
        "id": "chan_m365_exchange",
        "name": "District Operations M365 Email",
        "channel_type": "email",
        "endpoint_url": "smtp.office365.com:587",
        "auth_headers": {
            "smtp_host": "smtp.office365.com",
            "smtp_port": 587,
            "security_mode": "starttls",
            "from_email": "noc-alerts@district.k12.ca.us",
            "from_name": "ONE Platform NOC",
            "recipients": "sysadmin@district.k12.ca.us",
            "username": "noc-service@district.k12.ca.us",
            "password": "mock-app-password"
        },
        "min_severity": "warning",
        "is_active": True
    }
    m_res = client.post("/api/v1/alerts/channels", json=m365_payload)
    assert m_res.status_code == 200

    # 3. Trigger test email dispatch
    test_res = client.post("/api/v1/alerts/channels/chan_google_workspace/test", json={
        "sample_title": "CAASPP SSL Inspection Failure Alert",
        "sample_severity": "critical",
        "sample_message": "Cambium TDS pre-flight synthetic probe failed TLS handshake on science wing sensor."
    })
    assert test_res.status_code == 200
    test_data = test_res.json()
    assert test_data["delivered"] is True
    assert "Simulated Email" in test_data["channel"]["last_status"]

    # 4. Clean up test channels
    client.delete("/api/v1/alerts/channels/chan_google_workspace")
    client.delete("/api/v1/alerts/channels/chan_m365_exchange")


# --- 14. Maintenance Windows & Alert Muting Lifecycle Tests ---

@verifies("REQ-ALT-MAINTENANCE-001")
def test_14_maintenance_windows_muting_lifecycle():
    """Verifies scheduled IT maintenance windows, active muting scope matching, and notification suppression."""
    now = int(time.time())

    # 1. List maintenance windows
    list_res = client.get("/api/v1/alerts/maintenance-windows")
    assert list_res.status_code == 200
    assert isinstance(list_res.json(), list)

    # 2. Create an active maintenance window for West Campus
    maint_payload = {
        "id": "maint_ci_west_switch",
        "name": "West Campus Core Switch Firmware Upgrade",
        "description": "ServiceNow CHG0098124 - Core aggregate switch upgrade",
        "campus_id": "CAMPUS-MAINT-WEST",
        "sensor_id": None,
        "probe_id": "caaspp_readiness",
        "alertname_pattern": "*Certificate*",
        "starts_at": now - 120,
        "ends_at": now + 3600,
        "is_active": True,
        "created_by": "District NOC Engineer"
    }
    create_res = client.post("/api/v1/alerts/maintenance-windows", json=maint_payload)
    assert create_res.status_code == 200
    created = create_res.json()
    assert created["id"] == "maint_ci_west_switch"
    assert created["is_active"] is True

    # 3. Verify window is returned in active-now endpoint
    active_res = client.get("/api/v1/alerts/maintenance-windows/active-now")
    assert active_res.status_code == 200
    active_list = active_res.json()
    assert any(w["id"] == "maint_ci_west_switch" for w in active_list)

    # 4. Trigger alert that MATCHES maintenance window scope
    matched_alert_res = client.post("/api/v1/alerts/simulate", json={
        "alertname": "CAASPPUntrustedCertificate",
        "severity": "critical",
        "title": "CAASPP Testing SSL Interception",
        "description": "MITM certificate error during maintenance window.",
        "campus_id": "CAMPUS-MAINT-WEST",
        "sensor_id": "sensor-west-01",
        "probe_id": "caaspp_readiness"
    })
    assert matched_alert_res.status_code == 200
    matched_alert = matched_alert_res.json()
    assert matched_alert["is_muted"] is True
    assert matched_alert["muted_by_window_id"] == "maint_ci_west_switch"
    assert matched_alert["muted_by_window_name"] == "West Campus Core Switch Firmware Upgrade"

    # 5. Trigger alert that DOES NOT MATCH maintenance window scope (different campus)
    unmatched_alert_res = client.post("/api/v1/alerts/simulate", json={
        "alertname": "CAASPPUntrustedCertificate",
        "severity": "critical",
        "title": "CAASPP Testing SSL Interception East",
        "description": "Production alarm outside maintenance window.",
        "campus_id": "CAMPUS-EAST-ELEMENTARY",
        "sensor_id": "sensor-east-01",
        "probe_id": "caaspp_readiness"
    })
    assert unmatched_alert_res.status_code == 200
    unmatched_alert = unmatched_alert_res.json()
    assert unmatched_alert["is_muted"] is False
    assert unmatched_alert["muted_by_window_id"] is None

    # 6. Toggle maintenance window to disabled
    toggle_res = client.post("/api/v1/alerts/maintenance-windows/maint_ci_west_switch/toggle")
    assert toggle_res.status_code == 200
    assert toggle_res.json()["is_active"] is False

    # 7. Trigger alert on West Campus now that window is disabled -> should NOT be muted
    after_toggle_res = client.post("/api/v1/alerts/simulate", json={
        "alertname": "CAASPPUntrustedCertificate",
        "severity": "critical",
        "title": "CAASPP Testing SSL Interception After Window Disabled",
        "description": "Alarm firing when window is disabled.",
        "campus_id": "CAMPUS-MAINT-WEST",
        "sensor_id": "sensor-west-01",
        "probe_id": "caaspp_readiness"
    })
    assert after_toggle_res.status_code == 200
    assert after_toggle_res.json()["is_muted"] is False

    # 8. Clean up maintenance window
    del_res = client.delete("/api/v1/alerts/maintenance-windows/maint_ci_west_switch")
    assert del_res.status_code == 200
    assert client.get("/api/v1/alerts/maintenance-windows/maint_ci_west_switch").status_code == 404

    # 9. Test Multi-Day Construction Window (e.g. 7-Day Campus Rewiring & AP Replacement)
    const_payload = {
        "id": "maint_ci_const_7day",
        "name": "Science Wing 7-Day Rewiring & Construction",
        "description": "District Bond Project #2026-B - Fiber recabling & ceiling conduit work",
        "window_type": "construction",
        "campus_id": "CAMPUS-WEST-HIGH",
        "sensor_id": None,
        "probe_id": None,
        "alertname_pattern": None,
        "starts_at": now - 3600,
        "ends_at": now + (7 * 86400), # 7 full days
        "is_active": True,
        "created_by": "Facilities & NOC Project Manager"
    }
    const_res = client.post("/api/v1/alerts/maintenance-windows", json=const_payload)
    assert const_res.status_code == 200
    const_data = const_res.json()
    assert const_data["window_type"] == "construction"
    assert const_data["ends_at"] - const_data["starts_at"] == (7 * 86400 + 3600)

    # 10. Test Expiration Reminder Warnings (24h warning trigger)
    # Create an expiring construction window ending in 1 hour (less than 24h & 2h)
    expiring_payload = {
        "id": "maint_ci_expiring_soon",
        "name": "Expiring Construction Window",
        "description": "Final phase of switchboard installation",
        "window_type": "construction",
        "starts_at": now - 7200,
        "ends_at": now + 3000, # Ends in 50 minutes
        "is_active": True,
        "reminded_24h": False,
        "reminded_2h": False,
        "created_by": "NOC Admin"
    }
    client.post("/api/v1/alerts/maintenance-windows", json=expiring_payload)

    rem_res = client.post("/api/v1/alerts/maintenance-windows/check-reminders")
    assert rem_res.status_code == 200
    rem_data = rem_res.json()
    assert rem_data["status"] == "success"
    assert rem_data["reminders_dispatched"] >= 1

    # Cleanup
    client.delete("/api/v1/alerts/maintenance-windows/maint_ci_const_7day")
    client.delete("/api/v1/alerts/maintenance-windows/maint_ci_expiring_soon")
