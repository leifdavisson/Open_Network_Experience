import unittest
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE_URL = "http://localhost:8000"

def verifies(req_id: str):
    def decorator(fn):
        fn.__verifies__ = req_id
        return fn
    return decorator

class TestDashboardUIGherkinCoverage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from server import main as server_main
        client = TestClient(server_main.app)
        try:
            resp = client.get("/")
            cls.html_content = resp.text
            for mod in ["main.js", "sensors.js", "modals.js", "alerts.js", "charts.js"]:
                js_resp = client.get(f"/static/js/modules/{mod}")
                if js_resp.status_code == 200:
                    cls.html_content += js_resp.text
        except Exception as e:
            cls.html_content = ""
            print(f"Failed to fetch dashboard content: {e}")

    @verifies("REQ-UI-001")
    def test_live_diagnostics_dropdown_population(self):
        """
        Scenario: Populating Live Diagnostics Dropdowns
        Validates that both Live Diagnostics and Schedule Builder dropdowns map custom probes.
        """
        self.assertIn("diag-custom-probes-optgroup", self.html_content)
        self.assertIn("sch-custom-probes-optgroup", self.html_content)
        # Verify the JS actually injects them
        self.assertIn("diagOptGroup.innerHTML = html", self.html_content)
        self.assertIn("customOptGroup.innerHTML = html", self.html_content)

    @verifies("REQ-UI-002")
    def test_easybuilder_validation_alert(self):
        """
        Scenario: EasyBuilder Probe Validation Error
        Validates that handleSaveProbe explicitly calls alert(res.statusText) or alert(res.detail) on HTTP 422.
        """
        self.assertTrue(
            re.search(r"if\s*\(!res\.ok\).*?alert\(", self.html_content, re.DOTALL),
            "handleSaveProbe must trigger an alert() if the API rejects the payload (e.g. 422 Unprocessable Entity)"
        )

    @verifies("REQ-UI-003")
    def test_chromebook_fleet_lock_toggle(self):
        """
        Scenario: Chromebook Fleet Lock Toggle
        Validates that the Chromebook Fleet table uses a dynamic ternary to render the Unlock/Lock button,
        preventing the 'PNG' visual glitch where it was hardcoded.
        """
        self.assertTrue(
            re.search(r"cb\.settings_locked\s*\?\s*['\"]🔓\s*Unlock['\"]\s*:\s*['\"]🔒\s*Lock['\"]", self.html_content),
            "Chromebook rendering loop must dynamically toggle '🔓 Unlock' and '🔒 Lock' text based on cb.settings_locked"
        )

    @verifies("REQ-UI-004")
    def test_chromebook_fleet_dynamic_identity(self):
        """
        Scenario: Chromebook Fleet Identity Binding
        Validates that the dashboard properly binds the true cb.hostname and cb.mac_address in the UI loop,
        instead of hardcoding DEV-SIM-SERIAL placeholders.
        """
        self.assertIn("${cb.hostname || 'Unknown Host'}", self.html_content)
        self.assertIn("${cb.mac_address", self.html_content)

if __name__ == '__main__':
    unittest.main()
