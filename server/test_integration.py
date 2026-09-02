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

def verifies(req_id: str):
    def decorator(fn):
        fn.__verifies__ = req_id
        return fn
    return decorator

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

    @verifies("REQ-SEC-001")
    def test_01_unauthorized_endpoints(self):
        """Ensures administrative endpoints require a valid API key."""
        # Query sensor list without key -> expecting 401 Unauthorized (or 422 validation error)
        code, _ = self.make_request("/sensors", method="GET")
        self.assertIn(code, (401, 422))

        # Query sensor list with wrong key -> expecting 401 Unauthorized
        code, _ = self.make_request("/sensors", method="GET", headers={"X-API-Key": "wrong-key"})
        self.assertEqual(code, 401)

    @verifies("REQ-DB-001")
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

    def test_05_test_schedules_and_bandwidth_trigger(self):
        """Tests updating test schedules and queuing on-demand bandwidth testing."""
        # 1. Register and approve a fresh sensor
        s_id = "sched-test-sensor-01"
        reg_payload = {
            "sensor_id": s_id,
            "os": "linux",
            "hostname": "bandwidth-test-node",
            "mac_address": "11:22:33:44:55:66",
            "timestamp": int(time.time())
        }
        self.make_request("/sensors/register", method="POST", body=reg_payload)
        _, app_data = self.make_request(f"/sensors/{s_id}/approve", method="POST", headers={"X-API-Key": ADMIN_KEY})
        api_key = app_data["api_key"]

        # 2. Update sensor config with custom bandwidth test schedule
        config_update = {
            "schedules": {
                "bandwidth": {
                    "enabled": True,
                    "server": "speedtest.example.com",
                    "port": 5201,
                    "duration_seconds": 15,
                    "bandwidth_cap_mbps": 250,
                    "interfaces": ["eth0", "wlan0"],
                    "allowed_hours": ["22:00-05:00"],
                    "interval_seconds": 7200,
                    "run_now": False
                },
                "cipa": {"enabled": True, "interval_seconds": 300},
                "browser": {"enabled": True, "interval_seconds": 300, "targets": ["https://google.com"]}
            }
        }
        code, data = self.make_request(f"/sensors/{s_id}/config", method="PUT", body=config_update, headers={"X-API-Key": ADMIN_KEY})
        self.assertEqual(code, 200)

        # 3. Check-in from sensor -> verify schedules are received
        reconcile_payload = {
            "sensor_id": s_id,
            "os": "linux",
            "timestamp": int(time.time()),
            "containers": {}
        }
        code, data = self.make_request("/sensors/reconcile", method="POST", body=reconcile_payload, headers={"X-API-Key": api_key})
        self.assertEqual(code, 200)
        self.assertIn("schedules", data)
        self.assertEqual(data["schedules"]["bandwidth"]["server"], "speedtest.example.com")
        self.assertEqual(data["schedules"]["bandwidth"]["bandwidth_cap_mbps"], 250)
        self.assertFalse(data["schedules"]["bandwidth"]["run_now"])

        # 4. Trigger on-demand bandwidth test via admin API
        code, data = self.make_request(f"/sensors/{s_id}/tests/bandwidth/trigger", method="POST", headers={"X-API-Key": ADMIN_KEY})
        self.assertEqual(code, 200)
        self.assertEqual(data["status"], "success")

        # 5. Check-in -> run_now should be True
        code, data = self.make_request("/sensors/reconcile", method="POST", body=reconcile_payload, headers={"X-API-Key": api_key})
        self.assertEqual(code, 200)
        self.assertTrue(data["schedules"]["bandwidth"]["run_now"])

        # 6. Next check-in -> run_now should be cleared (one-shot delivery)
        code, data = self.make_request("/sensors/reconcile", method="POST", body=reconcile_payload, headers={"X-API-Key": api_key})
        self.assertEqual(code, 200)
        self.assertFalse(data["schedules"]["bandwidth"]["run_now"])

    def test_06_pcap_trigger_and_evidence_bundle(self):
        """Tests triggering on-demand PCAP snapshot and registering evidence bundles."""
        s_id = f"pcap-test-sensor-{int(time.time())}"
        reg_payload = {
            "sensor_id": s_id,
            "os": "linux",
            "hostname": "pcap-node",
            "mac_address": "22:33:44:55:66:77",
            "timestamp": int(time.time())
        }
        self.make_request("/sensors/register", method="POST", body=reg_payload)
        _, app_data = self.make_request(f"/sensors/{s_id}/approve", method="POST", headers={"X-API-Key": ADMIN_KEY})
        api_key = app_data["api_key"]

        reconcile_payload = {
            "sensor_id": s_id,
            "os": "linux",
            "timestamp": int(time.time()),
            "containers": {}
        }

        # 1. Initial check-in -> pcap_trigger should not be active
        code, data = self.make_request("/sensors/reconcile", method="POST", body=reconcile_payload, headers={"X-API-Key": api_key})
        self.assertEqual(code, 200)
        self.assertIn("pcap_trigger", data)
        self.assertFalse(data["pcap_trigger"]["trigger_now"])

        # 2. Trigger PCAP capture via Admin API
        code, data = self.make_request(f"/sensors/{s_id}/pcap/trigger?reason=high_latency_spike", method="POST", headers={"X-API-Key": ADMIN_KEY})
        self.assertEqual(code, 200)
        self.assertEqual(data["status"], "success")

        # 3. Check-in from sensor -> trigger_now should be True with reason
        code, data = self.make_request("/sensors/reconcile", method="POST", body=reconcile_payload, headers={"X-API-Key": api_key})
        self.assertEqual(code, 200)
        self.assertTrue(data["pcap_trigger"]["trigger_now"])
        self.assertEqual(data["pcap_trigger"]["reason"], "high_latency_spike")

        # 4. Next check-in -> trigger_now should be cleared (one-shot delivery)
        code, data = self.make_request("/sensors/reconcile", method="POST", body=reconcile_payload, headers={"X-API-Key": api_key})
        self.assertEqual(code, 200)
        self.assertFalse(data["pcap_trigger"]["trigger_now"])

        # 5. Register an evidence bundle
        bundle_payload = {
            "bundle_id": "bundle-001",
            "sensor_id": s_id,
            "timestamp": int(time.time()),
            "reason": "high_latency_spike",
            "filename": "evidence_pcap-node_20260827_high_latency_spike.tar.gz",
            "size_bytes": 1048576
        }
        code, data = self.make_request(f"/sensors/{s_id}/evidence", method="POST", body=bundle_payload, headers={"X-API-Key": ADMIN_KEY})
        self.assertEqual(code, 200)
        self.assertEqual(data["status"], "success")

        # 6. List evidence bundles
        code, data = self.make_request(f"/sensors/{s_id}/evidence", method="GET", headers={"X-API-Key": ADMIN_KEY})
        self.assertEqual(code, 200)
        self.assertEqual(len(data), 2)
        bundle_ids = [d["bundle_id"] for d in data]
        self.assertIn("bundle-001", bundle_ids)
        b = next(d for d in data if d["bundle_id"] == "bundle-001")
        self.assertEqual(b["size_bytes"], 1048576)

    def test_07_web_ui_and_easybuilder_studio(self):
        """Tests the Web UI dashboard, 1-click TOFU approval, and WYSIWYG EasyBuilder probes."""
        # 1. Test Web UI Dashboard HTML serving
        url = "http://localhost:8000/"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            html = resp.read().decode('utf-8')
            self.assertIn("Open Network Experience (ONE)", html)
            self.assertIn("WYSIWYG EasyBuilder", html)

        # 2. Register a new sensor and approve it via 1-click endpoint
        s_id = f"easybuilder-node-{int(time.time())}"
        reg_payload = {
            "sensor_id": s_id,
            "os": "linux",
            "hostname": "stem-lab",
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "timestamp": int(time.time())
        }
        code, data = self.make_request("/sensors/register", method="POST", body=reg_payload)
        self.assertEqual(code, 200)
        self.assertEqual(data["status"], "pending")

        # Approve via 1-click administrative endpoint
        code, data = self.make_request(f"/sensors/{s_id}/approve", method="POST", headers={"X-API-Key": ADMIN_KEY})
        self.assertEqual(code, 200)
        self.assertEqual(data["status"], "success")
        sensor_key = data["api_key"]
        self.assertTrue(sensor_key.startswith("sensor-key-"))

        # 3. Create a custom synthetic probe via WYSIWYG EasyBuilder Studio
        probe_payload = {
            "id": "canvas-lms",
            "name": "Canvas LMS Login Portal",
            "probe_type": "http",
            "target": "https://canvas.example.edu",
            "cadence_minutes": 5,
            "timeout_seconds": 3.0,
            "expected_status_code": 200,
            "target_sensors": ["all"],
            "enabled": True
        }
        code, data = self.make_request("/probes", method="POST", body=probe_payload, headers={"X-API-Key": ADMIN_KEY})
        self.assertEqual(code, 200)
        self.assertEqual(data["status"], "success")

        # 4. List probes
        code, data = self.make_request("/probes", method="GET", headers={"X-API-Key": ADMIN_KEY})
        self.assertEqual(code, 200)
        self.assertTrue(any(p["id"] == "canvas-lms" for p in data))

        # 5. Reconcile sensor and verify custom probe is delivered
        rec_payload = {
            "sensor_id": s_id,
            "os": "linux",
            "timestamp": int(time.time()),
            "containers": {}
        }
        code, data = self.make_request("/sensors/reconcile", method="POST", body=rec_payload, headers={"X-API-Key": sensor_key})
        self.assertEqual(code, 200)
        self.assertIn("custom_probes", data)
        self.assertTrue(any(p["id"] == "canvas-lms" for p in data["custom_probes"]))

        # 6. Clean up probe
        code, data = self.make_request("/probes/canvas-lms", method="DELETE", headers={"X-API-Key": ADMIN_KEY})
        self.assertEqual(code, 200)

    def test_08_sensor_location_and_gps_mapping(self):
        """Tests updating physical campus location and GPS coordinates."""
        s_id = f"location-test-{int(time.time())}"
        # 1. Register with initial GPS fix
        reg_payload = {
            "sensor_id": s_id,
            "os": "linux",
            "hostname": "outdoor-quad-sensor",
            "mac_address": "CC:DD:EE:11:22:33",
            "timestamp": int(time.time()),
            "location": {
                "district": "Unified School District",
                "site": "North High Campus",
                "building": "Quad Area",
                "room": "Courtyard Pole 4",
                "latitude": 35.3733,
                "longitude": -119.0187,
                "is_gps_auto": True
            }
        }
        code, data = self.make_request("/sensors/register", method="POST", body=reg_payload)
        self.assertEqual(code, 200)

        # 2. Approve sensor
        code, data = self.make_request(f"/sensors/{s_id}/approve", method="POST", headers={"X-API-Key": ADMIN_KEY})
        self.assertEqual(code, 200)

        # 3. Update location via administrative location API
        new_loc = {
            "district": "Unified School District",
            "site": "North High Campus",
            "building": "Library Wing",
            "room": "Room 204",
            "notes": "Mounted on ceiling grid",
            "latitude": 35.3745,
            "longitude": -119.0192,
            "is_gps_auto": False
        }
        code, data = self.make_request(f"/sensors/{s_id}/location", method="PUT", body=new_loc, headers={"X-API-Key": ADMIN_KEY})
        self.assertEqual(code, 200)
        self.assertEqual(data["status"], "success")

        # 4. List sensors and verify updated location in safe status response
        code, data = self.make_request("/sensors", method="GET", headers={"X-API-Key": ADMIN_KEY})
        self.assertEqual(code, 200)
        sensor_entry = next((s for s in data if s["sensor_id"] == s_id), None)
        self.assertIsNotNone(sensor_entry)
        self.assertEqual(sensor_entry["location"]["building"], "Library Wing")
        self.assertEqual(sensor_entry["location"]["room"], "Room 204")
        self.assertEqual(sensor_entry["location"]["latitude"], 35.3745)

    def test_09_backup_and_disaster_recovery(self):
        """Tests 1-click JSON backup export and restore disaster recovery endpoints."""
        # 1. Export backup
        code, backup_data = self.make_request("/system/backup", method="GET", headers={"X-API-Key": ADMIN_KEY})
        self.assertEqual(code, 200)
        self.assertIn("sensors", backup_data)
        self.assertIn("probes", backup_data)
        self.assertIn("version", backup_data)
        self.assertEqual(backup_data["version"], "0.4.0")

        # 2. Restore backup
        code, restore_res = self.make_request("/system/restore", method="POST", body=backup_data, headers={"X-API-Key": ADMIN_KEY})
        self.assertEqual(code, 200)
        self.assertEqual(restore_res["status"], "success")
        self.assertIn("restored successfully", restore_res["message"].lower())

    def test_10_on_demand_live_diagnostics_runner(self):
        """Tests executing on-demand live diagnostic probes on a sensor."""
        # 1. Register and approve a test sensor
        s_id = f"diag-test-sensor-{int(time.time())}"
        reg_payload = {
            "sensor_id": s_id,
            "os": "linux",
            "hostname": "diag-runner-node",
            "mac_address": "00:11:22:33:44:55",
            "timestamp": int(time.time()),
            "location": {
                "district": "Unified School District",
                "site": "City Center",
                "building": "1300 17th St",
                "room": "IT Operations"
            }
        }
        self.make_request("/sensors/register", method="POST", body=reg_payload)
        self.make_request(f"/sensors/{s_id}/approve", method="POST", headers={"X-API-Key": ADMIN_KEY})

        # 2. Run on-demand diagnostics
        diag_payload = {"test_type": "all", "custom_target": ""}
        code, data = self.make_request(f"/sensors/{s_id}/diagnostics/run", method="POST", body=diag_payload, headers={"X-API-Key": ADMIN_KEY})
        self.assertEqual(code, 200)
        self.assertIn("status", data)
        self.assertIn("details", data)
        self.assertIn("log_output", data)
        self.assertTrue(len(data["details"]) > 0)
        self.assertTrue(any("Gateway" in d.get("name", "") for d in data["details"]))

    def test_11_chromebook_sensor_telemetry_report(self):
        """Tests Chromebook extension telemetry ingestion at /sensors/report and /chromebook/metrics."""
        cb_id = f"chromebook-sn-test{int(time.time())}"
        report_payload = {
            "sensor_id": cb_id,
            "sensor_type": "chromebook",
            "os": "ChromeOS",
            "timestamp": int(time.time()),
            "campus_id": "CAMPUS-WEST-HIGH",
            "device_info": {
                "serial_number": "5CD9440ABC",
                "asset_id": "ASSET-CB-90210",
                "annotated_location": "West High Room 204",
                "hostname": "cb-student-204-01",
                "is_managed": True,
                "user_agent": "Mozilla/5.0 (X11; CrOS x86_64 14542.0.0)"
            },
            "wifi": {
                "connected": True,
                "ssid": "District-Secure-WiFi",
                "bssid": "00:1A:2B:3C:4D:5E",
                "rssi_dbm": -58,
                "signal_strength_pct": 85,
                "frequency_mhz": 5240,
                "channel": 48,
                "band": "5GHz",
                "security": "WPA-Enterprise",
                "roamed_recently": False
            },
            "hardware": {
                "battery": {
                    "level_percent": 94,
                    "charging": True
                },
                "cpu": {
                    "usage_percent": 18.5
                },
                "memory": {
                    "usage_percent": 50.0
                }
            },
            "probes": {
                "synthetic_http": [
                    {"name": "Google Classroom", "url": "https://classroom.google.com", "latency_ms": 32, "success": True},
                    {"name": "CAASPP Testing", "url": "https://caaspp.org", "latency_ms": 55, "success": True}
                ],
                "webrtc": {
                    "success": True,
                    "rtt_ms": 22.4,
                    "jitter_ms": 1.8,
                    "mos": 4.39,
                    "mos_grade": "Excellent"
                }
            }
        }

        # 1. Ingest via /sensors/report
        code, data = self.make_request("/sensors/report", method="POST", body=report_payload)
        self.assertEqual(code, 200)
        self.assertEqual(data["status"], "received")
        self.assertEqual(data["sensor_id"], cb_id)

        # 2. Ingest via /chromebook/metrics
        code2, data2 = self.make_request("/chromebook/metrics", method="POST", body=report_payload)
        self.assertEqual(code2, 200)
        self.assertEqual(data2["status"], "received")

        # 3. Verify sensor is in active fleet list
        code3, sensors_list = self.make_request("/sensors", method="GET", headers={"X-API-Key": ADMIN_KEY})
        self.assertEqual(code3, 200)
        matching = [s for s in sensors_list if s["sensor_id"] == cb_id]
        self.assertTrue(len(matching) > 0)
        self.assertEqual(matching[0]["os"], "ChromeOS")

        # 4. Verify /chromebooks endpoint returns formatted fleet item
        code4, cb_fleet = self.make_request("/chromebooks", method="GET")
        self.assertEqual(code4, 200)
        cb_item = next((c for c in cb_fleet if c["sensor_id"] == cb_id), None)
        self.assertIsNotNone(cb_item)
        self.assertEqual(cb_item["serial_number"], "5CD9440ABC")
        self.assertEqual(cb_item["asset_id"], "ASSET-CB-90210")
        self.assertEqual(cb_item["wifi_bssid"], "00:1A:2B:3C:4D:5E")
        self.assertEqual(cb_item["battery_level_pct"], 94)

        # 5. Verify /chromebooks/{sensor_id} detailed inspection
        code5, cb_detail = self.make_request(f"/chromebooks/{cb_id}", method="GET")
        self.assertEqual(code5, 200)
        self.assertEqual(cb_detail["sensor_id"], cb_id)
        self.assertEqual(cb_detail["serial_number"], "5CD9440ABC")

        # 6. Ingest roaming event and verify /chromebooks/roaming-trail
        roam_payload = dict(report_payload)
        roam_payload["wifi"] = dict(report_payload["wifi"])
        roam_payload["wifi"]["roamed_recently"] = True
        roam_payload["wifi"]["old_bssid"] = "00:1A:2B:3C:4D:5E"
        roam_payload["wifi"]["bssid"] = "00:1A:2B:99:88:77"
        self.make_request("/sensors/report", method="POST", body=roam_payload)

        code6, roam_trail = self.make_request("/chromebooks/roaming-trail", method="GET")
        self.assertEqual(code6, 200)
        self.assertTrue(len(roam_trail) > 0)
        self.assertEqual(roam_trail[-1]["new_bssid"], "00:1A:2B:99:88:77")

        # 7. Verify /chromebooks/{sensor_id}/lock endpoint
        code7, lock_res = self.make_request(
            f"/chromebooks/{cb_id}/lock",
            method="POST",
            body={"locked": True, "helpdesk_pin": "9988"},
            headers={"X-API-Key": ADMIN_KEY}
        )
        self.assertEqual(code7, 200)
        self.assertEqual(lock_res["status"], "success")
        self.assertEqual(lock_res["settings_locked"], True)

if __name__ == "__main__":
    unittest.main()
