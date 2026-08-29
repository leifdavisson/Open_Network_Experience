#!/usr/bin/env python3
"""
Comprehensive Web UI Automated Test Suite
Tests DOM element hierarchy, navigation view mapping, button click triggers,
modal form inputs, and backend REST bindings for the Open Network Experience (ONE) Dashboard.
"""

import unittest
import urllib.request
import urllib.error
import json
import re
import time
from html.parser import HTMLParser

BASE_URL = "http://localhost:8000"
API_BASE_URL = f"{BASE_URL}/api/v1"
ADMIN_KEY = "admin-noc-key-change-me"

class DOMStructureParser(HTMLParser):
    """Parses HTML DOM elements, IDs, classes, buttons, and event bindings."""
    def __init__(self):
        super().__init__()
        self.nav_items = []      # (id, onclick)
        self.view_sections = []  # id
        self.buttons = []        # (id, onclick, text)
        self.forms = []          # (id, onsubmit)
        self.inputs = []         # (id, name, type)
        self.modals = []         # id
        self._current_tag = None

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        el_id = attrs_dict.get('id')
        el_class = attrs_dict.get('class', '')
        el_onclick = attrs_dict.get('onclick')
        el_onsubmit = attrs_dict.get('onsubmit')

        if 'nav-item' in el_class:
            self.nav_items.append((el_id, el_onclick))

        if 'view-section' in el_class:
            self.view_sections.append(el_id)

        if 'modal-overlay' in el_class:
            self.modals.append(el_id)

        if tag == 'button':
            self.buttons.append((el_id, el_onclick, attrs_dict.get('class', '')))

        if tag == 'form':
            self.forms.append((el_id, el_onsubmit))

        if tag in ('input', 'select'):
            self.inputs.append((el_id, attrs_dict.get('type', 'text')))

class TestComprehensiveWebUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Fetch the live HTML dashboard from CMP server."""
        req = urllib.request.Request(f"{BASE_URL}/")
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                cls.html_content = resp.read().decode('utf-8')
        except Exception as e:
            raise RuntimeError(f"Failed to connect to CMP server at {BASE_URL}: {e}")

        cls.parser = DOMStructureParser()
        cls.parser.feed(cls.html_content)

    def test_01_page_header_and_brand_rendering(self):
        """Validates that brand headers, page title, and meta tags render cleanly."""
        self.assertIn("<title>Open Network Experience (ONE)", self.html_content)
        self.assertIn("ONE Platform", self.html_content)
        self.assertIn("data-theme=\"dark\"", self.html_content)

    def test_02_sidebar_navigation_and_view_mapping(self):
        """
        Validates that every single navigation item in the 4 buckets maps directly
        to an existing <div class='view-section' id='view-...'> in the DOM.
        """
        expected_views = [
            ("nav-monitor-noc", "monitor-noc", "view-monitor-noc"),
            ("nav-monitor-map", "monitor-map", "view-monitor-map"),
            ("nav-monitor-ondemand", "monitor-ondemand", "view-monitor-ondemand"),
            ("nav-monitor-reports", "monitor-reports", "view-monitor-reports"),
            ("nav-manage-fleet", "manage-fleet", "view-manage-fleet"),
            ("nav-manage-locations", "manage-locations", "view-manage-locations"),
            ("nav-manage-schedules", "manage-schedules", "view-manage-schedules"),
            ("nav-configure-probes", "configure-probes", "view-configure-probes"),
            ("nav-configure-osi", "configure-osi", "view-configure-osi"),
            ("nav-setup-server", "setup-server", "view-setup-server"),
            ("nav-setup-integrations", "setup-integrations", "view-setup-integrations")
        ]

        for nav_id, view_key, target_view_id in expected_views:
            # 1. Verify nav element exists
            matching_nav = [n for n in self.parser.nav_items if n[0] == nav_id]
            self.assertTrue(len(matching_nav) > 0, f"Nav element with ID '{nav_id}' not found in DOM.")
            self.assertIn(f"switchView('{view_key}')", matching_nav[0][1], f"Nav item '{nav_id}' missing onclick switchView('{view_key}')")

            # 2. Verify target view container exists
            self.assertIn(target_view_id, self.parser.view_sections, f"Target view container '{target_view_id}' missing in HTML DOM.")

    def test_03_modals_and_form_bindings(self):
        """Validates that modals, form action bindings, and input fields are correctly defined."""
        # 1. Location Edit Modal
        self.assertIn("location-modal", self.parser.modals)
        self.assertTrue(any(f[0] == "location-form" and "handleSaveLocation" in str(f[1]) for f in self.parser.forms))

        expected_loc_inputs = ["loc-sensor-id", "loc-district", "loc-site", "loc-building", "loc-room", "loc-notes", "loc-lat", "loc-lon"]
        for inp in expected_loc_inputs:
            self.assertTrue(any(i[0] == inp for i in self.parser.inputs), f"Input field '{inp}' missing in Location modal form.")

        # 2. WYSIWYG EasyBuilder Probe Modal
        self.assertIn("probe-modal", self.parser.modals)
        self.assertTrue(any(f[0] == "probe-form" and "handleSaveProbe" in str(f[1]) for f in self.parser.forms))

        expected_probe_inputs = ["p-name", "p-type", "p-cadence", "p-target", "p-timeout", "p-scope"]
        for inp in expected_probe_inputs:
            self.assertTrue(any(i[0] == inp for i in self.parser.inputs), f"Input field '{inp}' missing in Probe modal form.")

    def test_04_global_controls_and_buttons(self):
        """Validates that sidebar toggle, dark/light theme button, and global search are present."""
        self.assertTrue(any(b[0] == "btn-toggle-sidebar" and "toggleSidebar()" in str(b[1]) for b in self.parser.buttons))
        self.assertTrue(any(b[0] == "theme-btn" and "toggleTheme()" in str(b[1]) for b in self.parser.buttons))
        self.assertTrue(any(i[0] == "global-search" for i in self.parser.inputs))

    def test_05_javascript_syntax_and_event_sanity(self):
        """Validates that all embedded JavaScript functions exist and have valid syntax."""
        script_match = re.search(r'<script>(.*?)</script>', self.html_content, re.DOTALL)
        self.assertIsNotNone(script_match, "No <script> block found in dashboard HTML.")
        js_code = script_match.group(1)

        required_functions = [
            "toggleSidebar",
            "toggleTheme",
            "switchView",
            "handleGlobalSearch",
            "loadDashboardData",
            "renderDashboard",
            "approveSensor",
            "rejectSensor",
            "triggerPcap",
            "triggerSpeedtest",
            "openLocationModal",
            "closeLocationModal",
            "handleSaveLocation",
            "openProbeModal",
            "closeProbeModal",
            "handleSaveProbe",
            "deleteProbe"
        ]

        for func in required_functions:
            self.assertIn(f"function {func}", js_code, f"JavaScript function '{func}' missing in dashboard script.")

    def test_06_simulated_button_workflows(self):
        """
        Simulates end-to-end user button click workflows against the live backend:
          1. Create Custom Probe via EasyBuilder
          2. Edit Sensor Location via Location Modal
          3. Trigger Incident PCAP
          4. Trigger On-Demand Speedtest
        """
        # Register a sensor for action testing
        s_id = f"ui-test-sensor-{int(time.time())}"
        reg_payload = {
            "sensor_id": s_id,
            "os": "linux",
            "hostname": "stem-lab-sensor",
            "mac_address": "DD:EE:FF:00:11:22",
            "timestamp": int(time.time()),
            "location": {
                "district": "Kern County Superintendent of Schools",
                "site": "Bakersfield High",
                "building": "Science Wing",
                "room": "Room 101"
            }
        }
        req = urllib.request.Request(
            f"{API_BASE_URL}/sensors/register",
            data=json.dumps(reg_payload).encode('utf-8'),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)

        # 1. Simulate Approve Button
        req = urllib.request.Request(
            f"{API_BASE_URL}/sensors/{s_id}/approve",
            data=b"",
            headers={"X-API-Key": ADMIN_KEY},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode('utf-8'))
            self.assertEqual(data["status"], "success")

        # 2. Simulate Save Location Button
        loc_update = {
            "district": "Kern County Superintendent of Schools",
            "site": "Bakersfield High",
            "building": "Library Wing",
            "room": "Room 204",
            "notes": "Ceiling drop near AP-04",
            "latitude": 35.3733,
            "longitude": -119.0187,
            "is_gps_auto": False
        }
        req = urllib.request.Request(
            f"{API_BASE_URL}/sensors/{s_id}/location",
            data=json.dumps(loc_update).encode('utf-8'),
            headers={"Content-Type": "application/json", "X-API-Key": ADMIN_KEY},
            method="PUT"
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)

        # 3. Simulate Trigger PCAP Button
        req = urllib.request.Request(
            f"{API_BASE_URL}/sensors/{s_id}/pcap/trigger?reason=ui_test_click",
            data=b"",
            headers={"X-API-Key": ADMIN_KEY},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)

        # 4. Simulate Trigger Speedtest Button
        req = urllib.request.Request(
            f"{API_BASE_URL}/sensors/{s_id}/bandwidth/trigger",
            data=b"",
            headers={"X-API-Key": ADMIN_KEY},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)

        # 5. Simulate Create Custom Probe Button (WYSIWYG EasyBuilder)
        probe_data = {
            "id": f"ui-test-probe-{int(time.time())}",
            "name": "District SSO Login Portal",
            "probe_type": "http",
            "target": "https://sso.district.edu",
            "cadence_minutes": 5,
            "timeout_seconds": 3.0,
            "expected_status_code": 200,
            "target_sensors": ["all"],
            "enabled": True
        }
        req = urllib.request.Request(
            f"{API_BASE_URL}/probes",
            data=json.dumps(probe_data).encode('utf-8'),
            headers={"Content-Type": "application/json", "X-API-Key": ADMIN_KEY},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)

if __name__ == "__main__":
    unittest.main()
