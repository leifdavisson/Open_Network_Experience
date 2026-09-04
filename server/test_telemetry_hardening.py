import pytest
import json
import time
from unittest.mock import patch, MagicMock
import urllib.error

from fastapi.testclient import TestClient
from server.main import app
from server.routers.telemetry import query_vm_instant
from server.routers.sensors import forward_chromebook_metrics_to_tsdb
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
@patch("server.routers.telemetry.query_vm_instant")
def test_get_wallboard_live_stats_success(mock_query):
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
@patch("server.routers.telemetry.query_vm_instant")
def test_get_wallboard_live_stats_tsdb_unreachable(mock_query):
    """Test wallboard returns defaults when TSDB is unreachable."""
    mock_query.return_value = []

    resp = client.get("/api/v1/wallboard/live-stats")
    assert resp.status_code == 200  # nosec B101
    data = resp.json()

    assert "saas" in data  # nosec B101
    assert data["saas"]["canvas"]["rtt_ms"] == 105.0  # nosec B101
    assert data["slas"]["gateway_wired_ms"] == 1.18  # nosec B101

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
    assert data["version"] == "0.6.0"  # nosec B101

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
