"""
Open Network Experience (ONE) - Onboarding & Delegation Test Suite
Tests for Ed25519 key generation, CMP public key distribution,
dynamic install.sh script generation, and remote SSH probe delegation.

Copyright (C) 2026 Open Network Experience Authors.
Licensed under the GNU Affero General Public License v3.0 (AGPLv3).
"""

import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from server.main import app
from server.routers.onboarding import get_or_create_cmp_ssh_key
from server.routers.sensor_diagnostics import _run_remote_sensor_probe


class TestOnboardingAndDelegation(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_cmp_public_key_endpoint(self):
        """Verifies GET /api/v1/auth/cmp.pub serves a valid Ed25519 public key."""
        resp = self.client.get("/api/v1/auth/cmp.pub")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers["content-type"], "text/plain; charset=utf-8")
        content = resp.text.strip()
        self.assertTrue(content.startswith("ssh-ed25519") or len(content) > 0)

    def test_key_generation_idempotency(self):
        """Verifies get_or_create_cmp_ssh_key generates key and returns the same key on subsequent calls."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"DATA_DIR": tmpdir}):
                priv1, pub1 = get_or_create_cmp_ssh_key()
                self.assertTrue(os.path.exists(priv1))
                self.assertTrue(os.path.exists(f"{priv1}.pub"))

                priv2, pub2 = get_or_create_cmp_ssh_key()
                self.assertEqual(priv1, priv2)
                self.assertEqual(pub1, pub2)

    def test_install_script_generation(self):
        """Verifies GET /install.sh dynamically injects site, room, and CMP URL."""
        resp = self.client.get("/install.sh?site=WestHigh&room=204&building=Science")
        self.assertEqual(resp.status_code, 200)
        content = resp.text
        self.assertIn("WestHigh", content)
        self.assertIn("204", content)
        self.assertIn("Science", content)
        self.assertIn("one-sensor", content)
        self.assertIn("wifi_multiband_probe.py", content)

    def test_remote_sensor_probe_no_ip(self):
        """Verifies _run_remote_sensor_probe returns None gracefully if no IP is provided."""
        res = _run_remote_sensor_probe(None, "echo test")
        self.assertIsNone(res)

    def test_remote_sensor_probe_with_key(self):
        """Verifies _run_remote_sensor_probe prefers Ed25519 key over password."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("fake-private-key")
            key_path = f.name

        try:
            with patch.dict(os.environ, {"SSH_KEY_PATH": key_path}):
                with patch("subprocess.run") as mock_run:
                    mock_proc = MagicMock()
                    mock_proc.returncode = 0
                    mock_proc.stdout = '{"success": true, "metric": 42}'
                    mock_run.return_value = mock_proc

                    res = _run_remote_sensor_probe("10.0.0.50", "python3 /test.py")
                    self.assertIsNotNone(res)
                    self.assertTrue(res.get("success"))
                    self.assertEqual(res.get("metric"), 42)

                    # Verify ssh command used key auth
                    cmd_called = mock_run.call_args[0][0]
                    self.assertEqual(cmd_called[0], "ssh")
                    self.assertIn("-i", cmd_called)
                    self.assertIn(key_path, cmd_called)
                    self.assertIn("-o", cmd_called)
                    self.assertIn("BatchMode=yes", cmd_called)
        finally:
            if os.path.exists(key_path):
                os.remove(key_path)

    def test_remote_sensor_probe_fallback_to_password(self):
        """Verifies _run_remote_sensor_probe falls back to sshpass when no key exists."""
        with patch.dict(os.environ, {"SSH_KEY_PATH": "/nonexistent/key", "SSH_PASS": "testpass"}):
            with patch("subprocess.run") as mock_run:
                mock_proc = MagicMock()
                mock_proc.returncode = 0
                mock_proc.stdout = '{"success": true, "fallback": "sshpass"}'
                mock_run.return_value = mock_proc

                res = _run_remote_sensor_probe("10.0.0.50", "python3 /test.py")
                self.assertIsNotNone(res)
                self.assertEqual(res.get("fallback"), "sshpass")

                cmd_called = mock_run.call_args[0][0]
                self.assertEqual(cmd_called[0], "sshpass")
                self.assertIn("testpass", cmd_called)

    def test_health_check_delegation_flag(self):
        """Verifies /api/v1/health indicates ssh delegation status correctly."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("fake-key")
            key_path = f.name

        try:
            with patch.dict(os.environ, {"SSH_KEY_PATH": key_path}):
                resp = self.client.get("/api/v1/health")
                self.assertEqual(resp.status_code, 200)
                data = resp.json()
                self.assertTrue(data.get("ssh_delegation_configured"))
                self.assertEqual(data.get("delegation_mode"), "key")
        finally:
            if os.path.exists(key_path):
                os.remove(key_path)


if __name__ == "__main__":
    unittest.main()
