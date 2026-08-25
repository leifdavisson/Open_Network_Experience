#!/usr/bin/env python3
"""
Central Monitoring Platform Integration Test Suite
Executes end-to-end testing of the registration, approval, reconciliation,
and administration endpoints against the running API container.
"""

import unittest
import urllib.request
import urllib.error
import json
import time

CMP_BASE_URL = "http://localhost:8000/api/v1"
ADMIN_KEY = "admin-noc-key-change-me"

class TestCMPFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sensor_id = "test-unit-sensor-99"

    def make_request(self, path, method="GET", headers=None, body=None):
        """Helper to send urllib HTTP requests."""
        url = f"{CMP_BASE_URL}{path}"
        data = json.dumps(body).encode("utf-8") if body else None
        
        req_headers = {"Content-Type": "application/json"}
        if headers:
            req_headers.update(headers)
            
        req = urllib.request.Request(
            url,
            data=data,
            headers=req_headers,
            method=method
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return e.code, None
        except Exception as e:
            self.fail(f"Request failed: {e}")

    def test_01_unauthorized_endpoints(self):
        """Ensures administrative endpoints require a valid API key."""
        # Query sensor list without key -> expecting 422 (FastAPI required header)
        code, _ = self.make_request("/sensors", method="GET")
        self.assertEqual(code, 422)

        # Query sensor list with wrong key -> expecting 401 Unauthorized
        code, _ = self.make_request("/sensors", method="GET", headers={"X-API-Key": "wrong-key"})
        self.assertEqual(code, 401)

    def test_02_sensor_registration_lifecycle(self):
        """Tests the full register-approve-reconcile sensor lifecycle."""
        # 1. Register a new sensor (unauthenticated)
        reg_payload = {
            "sensor_id": self.sensor_id,
            "os": "linux",
            "hostname": "unit-test-mdf",
            "mac_address": "aa:bb:cc:dd:ee:ff",
            "timestamp": int(time.time())
        }
        code, data = self.make_request("/sensors/register", method="POST", body=reg_payload)
        self.assertEqual(code, 200)
        self.assertEqual(data["status"], "pending")
        self.assertIsNone(data["api_key"])

        # 2. Reconcile check-in without key or approval -> expecting 401
        reconcile_payload = {
            "sensor_id": self.sensor_id,
            "os": "linux",
            "timestamp": int(time.time()),
            "containers": {}
        }
        code, _ = self.make_request("/sensors/reconcile", method="POST", body=reconcile_payload, headers={"X-API-Key": "none"})
        self.assertEqual(code, 401)

        # 3. View pending sensor on administrative status board
        code, data = self.make_request("/sensors", method="GET", headers={"X-API-Key": ADMIN_KEY})
        self.assertEqual(code, 200)
        
        # Verify our sensor is in the list and marked pending
        test_sensor = next((s for s in data if s["sensor_id"] == self.sensor_id), None)
        self.assertIsNotNone(test_sensor)
        self.assertEqual(test_sensor["status"], "pending")

        # 4. Approve the pending sensor (admin authorized)
        code, data = self.make_request(f"/sensors/{self.sensor_id}/approve", method="POST", headers={"X-API-Key": ADMIN_KEY})
        self.assertEqual(code, 200)
        self.assertEqual(data["status"], "success")
        api_key = data["api_key"]
        self.assertTrue(api_key.startswith("sensor-key-"))

        # 5. Sensor registers again -> should get approved status and the api_key
        code, data = self.make_request("/sensors/register", method="POST", body=reg_payload)
        self.assertEqual(code, 200)
        self.assertEqual(data["status"], "approved")
        self.assertEqual(data["api_key"], api_key)

        # 6. Reconcile check-in with the generated API key -> should succeed
        code, data = self.make_request("/sensors/reconcile", method="POST", body=reconcile_payload, headers={"X-API-Key": api_key})
        self.assertEqual(code, 200)
        self.assertFalse(data["reset"])
        self.assertIn("blackbox-exporter", data["containers"])

    def test_03_rebuild_and_reset_delivery(self):
        """Tests factory reset signal queuing and delivery."""
        # Get approved api_key from DB
        _, sensors = self.make_request("/sensors", method="GET", headers={"X-API-Key": ADMIN_KEY})
        test_sensor = next((s for s in sensors if s["sensor_id"] == self.sensor_id), None)
        self.assertIsNotNone(test_sensor)
        
        # We can't see the raw key in status (redacted). Let's register again to grab it
        reg_payload = {
            "sensor_id": self.sensor_id,
            "os": "linux",
            "hostname": "unit-test-mdf",
            "mac_address": "aa:bb:cc:dd:ee:ff",
            "timestamp": int(time.time())
        }
        _, reg_data = self.make_request("/sensors/register", method="POST", body=reg_payload)
        api_key = reg_data["api_key"]

        # 1. Trigger sensor reset via admin API
        code, data = self.make_request(f"/sensors/{self.sensor_id}/reset", method="POST", headers={"X-API-Key": ADMIN_KEY})
        self.assertEqual(code, 200)
        self.assertEqual(data["status"], "success")

        # 2. Check-in from sensor -> reset flag should be True
        reconcile_payload = {
            "sensor_id": self.sensor_id,
            "os": "linux",
            "timestamp": int(time.time()),
            "containers": {}
        }
        code, data = self.make_request("/sensors/reconcile", method="POST", body=reconcile_payload, headers={"X-API-Key": api_key})
        self.assertEqual(code, 200)
        self.assertTrue(data["reset"])

        # 3. Check-in a second time -> reset flag should be cleared (one-shot delivery)
        code, data = self.make_request("/sensors/reconcile", method="POST", body=reconcile_payload, headers={"X-API-Key": api_key})
        self.assertEqual(code, 200)
        self.assertFalse(data["reset"])

    def test_04_sensor_revocation(self):
        """Tests rejecting/revoking a sensor and invalidating its key."""
        # 1. Grab api_key
        reg_payload = {
            "sensor_id": self.sensor_id,
            "os": "linux",
            "hostname": "unit-test-mdf",
            "mac_address": "aa:bb:cc:dd:ee:ff",
            "timestamp": int(time.time())
        }
        _, reg_data = self.make_request("/sensors/register", method="POST", body=reg_payload)
        api_key = reg_data["api_key"]

        # 2. Reject/revoke sensor via Admin API
        code, data = self.make_request(f"/sensors/{self.sensor_id}/reject", method="POST", headers={"X-API-Key": ADMIN_KEY})
        self.assertEqual(code, 200)
        self.assertEqual(data["status"], "success")

        # 3. Check-in from sensor using the old key -> should be 401 Unauthorized
        reconcile_payload = {
            "sensor_id": self.sensor_id,
            "os": "linux",
            "timestamp": int(time.time()),
            "containers": {}
        }
        code, _ = self.make_request("/sensors/reconcile", method="POST", body=reconcile_payload, headers={"X-API-Key": api_key})
        self.assertEqual(code, 401)

if __name__ == "__main__":
    unittest.main()
