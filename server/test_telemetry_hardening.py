import os
import pytest
import json
import time
from unittest.mock import patch, MagicMock
import urllib.error

from fastapi.testclient import TestClient
from server.main import app
from server.routers.telemetry import query_vm_instant
from server.routers.sensor_telemetry import forward_chromebook_metrics_to_tsdb
import server.state as state

verifies = pytest.mark.verifies

client = TestClient(app)

@verifies("REQ-TEL-002")
@patch("urllib.request.urlopen")
def test_query_vm_instant_success(mock_urlopen):
    """Test VictoriaMetrics query fallback and parsing on success."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({
        "status": "success",
        "data": {"result": [{"metric": {}, "value": [1600000000, "0.105"]}]}
    }).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_urlopen.return_value = mock_resp

    res = query_vm_instant('probe_duration_seconds{job="blackbox-saas-apps"}')
    assert len(res) == 1  # nosec B101
    assert res[0]["value"][1] == "0.105"  # nosec B101
    assert mock_urlopen.call_count == 1  # nosec B101

@verifies("REQ-TEL-002")
@patch("urllib.request.urlopen")
def test_query_vm_instant_fallback_and_failure(mock_urlopen):
    """Test VictoriaMetrics query fallback on connection error/timeout."""
    mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

    res = query_vm_instant('probe_duration_seconds')
    assert len(res) == 0  # nosec B101
    assert mock_urlopen.call_count == 3  # nosec B101

@verifies("REQ-TEL-002")
@patch("urllib.request.urlopen")
def test_query_vm_instant_malformed_json(mock_urlopen):
    """Test VictoriaMetrics query fallback on malformed JSON."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = b"{ invalid json "
    mock_resp.__enter__.return_value = mock_resp
    mock_urlopen.return_value = mock_resp

    res = query_vm_instant('probe_duration_seconds')
    assert len(res) == 0  # nosec B101
    assert mock_urlopen.call_count == 3  # nosec B101

@verifies("REQ-TEL-002")
@patch("server.routers.telemetry.query_vm_range", return_value=[])
@patch("server.routers.telemetry.query_vm_instant")
def test_get_wallboard_live_stats_success(mock_query, mock_range):
    """Test wallboard returns SaaS health derived from PromQL."""
    def fake_query(q):
        if "probe_duration_seconds" in q and "saas" in q:
            return [{"metric": {"instance": "canvas.instructure.com"}, "value": [1, "0.080"]}]
        if "probe_success" in q and "saas" in q:
            return [{"metric": {"instance": "canvas.instructure.com"}, "value": [1, "1"]}]
        return []

    mock_query.side_effect = fake_query

    start_time = time.time()
    resp = client.get("/api/v1/wallboard/live-stats")
    assert resp.status_code == 200  # nosec B101
    duration = time.time() - start_time
    assert duration <= 2.0  # nosec B101

    data = resp.json()
    assert "saas" in data  # nosec B101
    assert data["saas"]["canvas"]["rtt_ms"] == 80.0  # nosec B101
    assert data["saas"]["canvas"]["is_up"] is True  # nosec B101

@verifies("REQ-TEL-002")
@patch("server.routers.telemetry.query_vm_range", return_value=[])
@patch("server.routers.telemetry.query_vm_instant")
def test_get_wallboard_live_stats_tsdb_unreachable(mock_query, mock_range):
    """Test wallboard returns defaults when TSDB is unreachable."""
    mock_query.return_value = []

    resp = client.get("/api/v1/wallboard/live-stats")
    assert resp.status_code == 200  # nosec B101
    data = resp.json()

    assert "saas" in data  # nosec B101
    assert data["saas"]["canvas"]["rtt_ms"] == 105.0  # nosec B101
    # When TSDB is unreachable and no edge sensor reports, gateway_wired_ms is truthfully None (unmonitored)
    assert data["slas"]["gateway_wired_ms"] is None  # nosec B101

@verifies("REQ-TEL-002")
def test_health_endpoint():
    """Test health endpoint reports accurate version and sensor counts."""
    state.SENSORS_DB.clear()
    state.SENSORS_DB["s1"] = {"last_seen": int(time.time()) - 10}
    state.SENSORS_DB["s2"] = {"last_seen": int(time.time()) - 10}
    state.SENSORS_DB["s3"] = {"last_seen": int(time.time()) - 10}

    resp = client.get("/api/v1/health")
    assert resp.status_code == 200  # nosec B101
    data = resp.json()

    assert data["status"] == "ok"  # nosec B101
    assert data["active_sensors"] == 3  # nosec B101
    assert data["version"] == "0.7.8"  # nosec B101

@verifies("REQ-SEC-005")
def test_evidence_vault_no_auth():
    """Verify GET /api/v1/evidence now requires auth after security fix."""
    # Unauthenticated request should be rejected
    resp = client.get("/api/v1/evidence")
    assert resp.status_code == 401  # nosec B101

    # Authenticated request should succeed
    resp_auth = client.get("/api/v1/evidence", headers={"X-API-Key": "admin-noc-key-change-me"})
    assert resp_auth.status_code == 200  # nosec B101
    assert isinstance(resp_auth.json(), list)  # nosec B101

@verifies("REQ-DB-001")
@patch("urllib.request.urlopen")
@patch("server.db.enqueue_tsdb_spool")
def test_forward_chromebook_metrics_enqueue_when_unreachable(mock_enqueue, mock_urlopen):
    """Test spooling enqueues metrics when VictoriaMetrics is unreachable."""
    mock_urlopen.side_effect = Exception("Connection refused")

    report = {
        "sensor_id": "cb-test-1",
        "wifi": {"ssid": "TestNet", "connected": True}
    }

    forward_chromebook_metrics_to_tsdb(report)
    mock_enqueue.assert_called_once()
    assert "chromebook_wifi_connected" in mock_enqueue.call_args[0][0]  # nosec B101

@verifies("REQ-DB-001")
@patch("urllib.request.urlopen")
@patch("server.db.dequeue_tsdb_spool")
@patch("server.db.delete_tsdb_spool_entries")
def test_forward_chromebook_metrics_dequeue_when_reachable(mock_delete, mock_dequeue, mock_urlopen):
    """Test spooling dequeues metrics and deletes on success."""
    mock_dequeue.return_value = [{"id": 1, "payload": "spooled_metric 1"}]

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.__enter__.return_value = mock_resp
    mock_urlopen.return_value = mock_resp

    report = {
        "sensor_id": "cb-test-2",
        "wifi": {"ssid": "TestNet2", "connected": True}
    }

    forward_chromebook_metrics_to_tsdb(report)
    mock_delete.assert_called_once_with([1])


@verifies("REQ-PRB-006")
@patch("urllib.request.urlopen")
@patch("server.db.enqueue_tsdb_spool")
def test_forward_chromebook_probe_metrics_all_fields(mock_enqueue, mock_urlopen):
    """Test full metric payload with EdTech, bufferbloat, gateway, and DNS generates expected Prometheus series."""
    mock_urlopen.side_effect = Exception("Spool it")

    report = {
        "sensor_id": "cb-advanced-01",
        "wifi": {"ssid": "District-Secure", "connected": True, "rssi": -65},
        "gateway_probe": {"reachable": True, "rtt_ms": 1.45, "gateway_ip": "10.0.0.1"},
        "dns_benchmark": {
            "doh_google": {"latency_ms": 12.5},
            "doh_cloudflare": {"latency_ms": 14.2},
            "local_dns": {"latency_ms": 5.1}
        },
        "bandwidth_bufferbloat": {
            "success": True,
            "throughput_mbps": 85.2,
            "bufferbloat_delta_ms": 42.0,
            "grade": "B (Good)"
        },
        "edtech_filter": {
            "detected_agents": ["Securly Filter", "Lightspeed Systems Relay"],
            "collision_detected": True,
            "filter_overhead_ms": 115.0,
            "ssl_inspection": {"ssl_valid": False},
            "classroom_whitelist": {"blocked_count": 1}
        }
    }

    forward_chromebook_metrics_to_tsdb(report)
    mock_enqueue.assert_called_once()
    payload = mock_enqueue.call_args[0][0]
    assert 'chromebook_gateway_reachable{sensor_id="cb-advanced-01"' in payload
    assert 'chromebook_gateway_rtt_ms{sensor_id="cb-advanced-01"' in payload
    assert 'chromebook_dns_latency_ms{sensor_id="cb-advanced-01",campus_id="CAMPUS-CHROMEBOOK-FLEET",resolver="google_doh"} 12.5' in payload
    assert 'chromebook_bandwidth_downlink_mbps{sensor_id="cb-advanced-01",campus_id="CAMPUS-CHROMEBOOK-FLEET"} 85.2' in payload
    assert 'chromebook_bufferbloat_delta_ms{sensor_id="cb-advanced-01",campus_id="CAMPUS-CHROMEBOOK-FLEET",grade="B"} 42.0' in payload
    assert 'chromebook_filter_collision{sensor_id="cb-advanced-01",campus_id="CAMPUS-CHROMEBOOK-FLEET"} 1' in payload
    assert 'chromebook_filter_overhead_ms{sensor_id="cb-advanced-01",campus_id="CAMPUS-CHROMEBOOK-FLEET"} 115.0' in payload
    assert 'chromebook_filter_ssl_failed{sensor_id="cb-advanced-01",campus_id="CAMPUS-CHROMEBOOK-FLEET"} 1' in payload
    assert 'chromebook_filter_classroom_blocked_count{sensor_id="cb-advanced-01",campus_id="CAMPUS-CHROMEBOOK-FLEET"} 1' in payload


@verifies("REQ-DB-001")
def test_chromebook_report_and_fleet_listing_integration():
    """Test ingestion of new Chromebook probe metrics and verify they appear in /api/v1/chromebooks."""
    report_payload = {
        "sensor_id": "cb-fleet-test-01",
        "timestamp": int(time.time()),
        "os": "chromeos",
        "battery": {"charging": True, "level": 0.95},
        "wifi": {"ssid": "District-Secure", "connected": True, "signal_strength": -58},
        "gateway_probe": {"reachable": True, "rtt_ms": 2.1},
        "dns_benchmark": {"dns_health": "HEALTHY", "doh_google": {"latency_ms": 18.4}},
        "bandwidth_bufferbloat": {
            "success": True,
            "throughput_mbps": 94.5,
            "bufferbloat_delta_ms": 15.0,
            "grade": "A"
        },
        "edtech_filter": {
            "health_status": "HEALTHY",
            "collision_detected": False,
            "filter_overhead_ms": 35.0,
            "ssl_inspection": {"ssl_valid": True},
            "classroom_whitelist": {"blocked_count": 0}
        }
    }

    # Ingest report
    resp = client.post("/api/v1/sensors/report", json=report_payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "received"

    # Verify presence and enriched fields in fleet endpoint
    admin_key = os.environ.get("ADMIN_API_KEY", "test-admin-key-12345")
    fleet_resp = client.get("/api/v1/chromebooks", headers={"X-API-Key": admin_key})
    assert fleet_resp.status_code == 200
    devices = fleet_resp.json()
    device = next((d for d in devices if d["sensor_id"] == "cb-fleet-test-01"), None)
    assert device is not None
    assert device["gateway_reachable"] is True
    assert device["gateway_rtt_ms"] == 2.1
    assert device["dns_health"] == "HEALTHY"
    assert device["bandwidth_downlink_mbps"] == 94.5
    assert device["bufferbloat_grade"] == "A"
    assert device["bufferbloat_delta_ms"] == 15.0
    assert device["edtech_collision_detected"] is False
    assert device["edtech_filter_overhead_ms"] == 35.0
    assert device["edtech_filter_status"] == "HEALTHY"

