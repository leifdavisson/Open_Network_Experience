#!/usr/bin/env python3
# License: GNU AGPLv3 (GNU Affero General Public License v3.0)
import os
import sys
import unittest
import tempfile
from unittest.mock import patch, MagicMock

def verifies(req_id: str):
    def decorator(fn):
        fn.__verifies__ = req_id
        return fn
    return decorator

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

if "playwright" not in sys.modules:
    mock_pw = MagicMock()
    sys.modules["playwright"] = mock_pw
    sys.modules["playwright.sync_api"] = mock_pw

import browser_transaction

class TestBrowserTransaction(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.prom_file = os.path.join(self.test_dir.name, "browser.prom")

    def tearDown(self):
        self.test_dir.cleanup()

    @verifies("REQ-PRB-006")
    @patch("browser_transaction.sync_playwright")
    def test_run_api_test_success(self, mock_playwright):
        """Verifies API testing performance calculation when successful."""
        mock_p = MagicMock()
        mock_playwright.return_value.__enter__.return_value = mock_p
        mock_req_ctx = MagicMock()
        mock_p.request.new_context.return_value = mock_req_ctx

        mock_response = MagicMock(status=200, ok=True)
        mock_req_ctx.get.return_value = mock_response

        res = browser_transaction.run_api_test("https://api.district.edu/health", method="GET")
        self.assertEqual(res["success"], 1)
        self.assertEqual(res["status_code"], 200)

    @verifies("REQ-PRB-006")
    @patch("browser_transaction.sync_playwright")
    def test_run_api_test_failure(self, mock_playwright):
        """Verifies API testing handling of exceptions."""
        mock_p = MagicMock()
        mock_playwright.return_value.__enter__.return_value = mock_p
        mock_req_ctx = MagicMock()
        mock_p.request.new_context.return_value = mock_req_ctx
        mock_req_ctx.get.side_effect = Exception("Connection Refused")

        res = browser_transaction.run_api_test("https://broken.district.edu", method="GET")
        self.assertEqual(res["success"], 0)
        self.assertEqual(res["status_code"], -1)

    @verifies("REQ-PRB-006")
    @patch("browser_transaction.sync_playwright")
    @patch("browser_transaction.SNAPSHOTS_DIR")
    def test_run_page_test_success(self, mock_snap_dir, mock_playwright):
        """Verifies page test timing evaluation with mocked performance metrics."""
        mock_snap_dir.__str__.return_value = self.test_dir.name
        mock_p = MagicMock()
        mock_playwright.return_value.__enter__.return_value = mock_p

        mock_browser = MagicMock()
        mock_p.chromium.launch.return_value = mock_browser
        mock_context = MagicMock()
        mock_browser.new_context.return_value = mock_context
        mock_page = MagicMock()
        mock_context.new_page.return_value = mock_page

        mock_page.goto.return_value = MagicMock(status=200)
        mock_page.evaluate.return_value = '{"navigationStart": 1000, "domContentLoadedEventEnd": 1500, "loadEventEnd": 2000}'

        res = browser_transaction.run_page_test("https://portal.district.edu")
        self.assertEqual(res["success"], 1)
        self.assertEqual(res["status_code"], 200)
        self.assertAlmostEqual(res["dcl_seconds"], 0.5, places=2)
        self.assertAlmostEqual(res["load_seconds"], 1.0, places=2)

    @patch("browser_transaction.run_api_test")
    def test_main_cli_api(self, mock_api_test):
        """Verifies CLI execution for API testing mode."""
        mock_api_test.return_value = {
            "success": 1,
            "duration_seconds": 0.123,
            "status_code": 200,
            "failed_requests": {}
        }
        with patch.object(sys, "argv", ["browser_transaction.py", "https://api.edu", "api", self.prom_file]):
            browser_transaction.main()
        self.assertTrue(os.path.exists(self.prom_file))
        with open(self.prom_file, "r") as f:
            content = f.read()
            self.assertIn("browser_transaction_success", content)
            self.assertIn("200", content)

if __name__ == "__main__":
    unittest.main()
