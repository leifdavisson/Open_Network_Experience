"""
Open Network Experience (ONE) — TSDB SQLite Disk Spool Queue Test Suite
License: GNU AGPLv3

Verifies persistent time-series metrics buffering in SQLite (tsdb_spool_queue),
ensuring zero metric loss during VictoriaMetrics restarts or transient outages.
"""

import sys
import time
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

SERVER_DIR = Path(__file__).resolve().parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))
ROOT_DIR = SERVER_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import server.db as db
from server.routers.sensors import forward_chromebook_metrics_to_tsdb

@pytest.fixture(autouse=True)
def setup_and_teardown_spool_db():
    """Initializes the test database and clears the spool queue before and after tests."""
    db.init_db()
    db.clear_tsdb_spool_queue()
    yield
    db.clear_tsdb_spool_queue()

def test_01_spool_enqueue_and_dequeue_fifo():
    """Verify that payloads are enqueued and dequeued in FIFO order."""
    assert db.get_tsdb_spool_count() == 0

    payload1 = 'chromebook_wifi_connected{sensor_id="cb-01"} 1 1700000000000'
    payload2 = 'chromebook_wifi_connected{sensor_id="cb-02"} 1 1700000001000'

    db.enqueue_tsdb_spool(payload1)
    db.enqueue_tsdb_spool(payload2)

    assert db.get_tsdb_spool_count() == 2

    items = db.dequeue_tsdb_spool(batch_size=10)
    assert len(items) == 2
    assert items[0]["payload"] == payload1
    assert items[1]["payload"] == payload2
    assert items[0]["attempts"] == 0

def test_02_spool_delete_entries():
    """Verify that successfully delivered entries are purged from SQLite."""
    db.enqueue_tsdb_spool("test_metric_1 10 1700000000000")
    db.enqueue_tsdb_spool("test_metric_2 20 1700000000000")
    db.enqueue_tsdb_spool("test_metric_3 30 1700000000000")

    items = db.dequeue_tsdb_spool(batch_size=2)
    assert len(items) == 2
    ids_to_del = [items[0]["id"], items[1]["id"]]

    deleted_count = db.delete_tsdb_spool_entries(ids_to_del)
    assert deleted_count == 2
    assert db.get_tsdb_spool_count() == 1

    remaining = db.dequeue_tsdb_spool(batch_size=10)
    assert len(remaining) == 1
    assert remaining[0]["payload"] == "test_metric_3 30 1700000000000"

def test_03_spool_increment_attempts():
    """Verify that delivery failures increment the attempts counter."""
    db.enqueue_tsdb_spool("failed_metric 5 1700000000000")
    items = db.dequeue_tsdb_spool(batch_size=1)
    assert len(items) == 1
    assert items[0]["attempts"] == 0

    db.increment_tsdb_spool_attempts([items[0]["id"]])
    updated = db.dequeue_tsdb_spool(batch_size=1)
    assert updated[0]["attempts"] == 1

def test_04_spool_backpressure_eviction():
    """Verify FIFO eviction when spool queue exceeds max_records threshold."""
    for i in range(10):
        db.enqueue_tsdb_spool(f"metric_{i} {i}", max_records=5)

    assert db.get_tsdb_spool_count() == 5
    items = db.dequeue_tsdb_spool(batch_size=10)
    assert items[0]["payload"] == "metric_5 5"
    assert items[-1]["payload"] == "metric_9 9"

def test_05_forward_metrics_offline_spool_and_online_flush():
    """Simulate VictoriaMetrics outage, verify SQLite buffering, and verify recovery delivery."""
    report = {
        "sensor_id": "cb-spool-test",
        "timestamp": int(time.time()),
        "wifi": {
            "connected": True,
            "rssi_dbm": -56,
            "ssid": "District-WiFi",
            "bssid": "00:11:22:33:44:55"
        },
        "probes": {
            "webrtc": {
                "success": True,
                "mos": 4.42,
                "rtt_ms": 18.2
            }
        }
    }

    # 1. Outage phase: Mock urllib.request to fail (simulating dead VictoriaMetrics)
    with patch("urllib.request.urlopen", side_effect=Exception("Connection refused (TSDB down)")):
        forward_chromebook_metrics_to_tsdb(report)

    # Metrics MUST be saved to SQLite disk spool queue
    assert db.get_tsdb_spool_count() >= 1
    spooled = db.dequeue_tsdb_spool(batch_size=10)
    assert "chromebook_wifi_rssi_dbm" in spooled[0]["payload"]
    assert "chromebook_webrtc_mos" in spooled[0]["payload"]

    # 2. Recovery phase: Mock urllib.request to succeed (200 OK)
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        # Send a second report while TSDB is back online
        report2 = {
            "sensor_id": "cb-spool-test-2",
            "timestamp": int(time.time()),
            "wifi": {"connected": True, "rssi_dbm": -60}
        }
        forward_chromebook_metrics_to_tsdb(report2)

    # All spooled metrics and current report MUST be delivered and purged from SQLite
    assert db.get_tsdb_spool_count() == 0
