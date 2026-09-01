#!/usr/bin/env python3
import unittest
from unittest.mock import patch, MagicMock
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import ringcentral_probe

def verifies(req_id: str):
    def decorator(fn):
        fn.__verifies__ = req_id
        return fn
    return decorator

class TestRingCentralProbe(unittest.TestCase):
    @verifies("REQ-PROBE-001")
    @patch("ringcentral_probe.socket.socket")
    def test_sip_signaling_success(self, mock_socket_cls):
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock
        res = ringcentral_probe.check_sip_signaling("sip.ringcentral.com", 5060)
        self.assertEqual(res["status"], "ok")
        self.assertIn("latency_ms", res)
        mock_sock.connect.assert_called_once_with(("sip.ringcentral.com", 5060))

    @verifies("REQ-PROBE-001")
    @patch("ringcentral_probe.socket.socket")
    def test_sip_signaling_failure(self, mock_socket_cls):
        mock_sock = MagicMock()
        mock_sock.connect.side_effect = ConnectionRefusedError("Port 5060 closed")
        mock_socket_cls.return_value = mock_sock
        res = ringcentral_probe.check_sip_signaling("sip.ringcentral.com", 5060)
        self.assertEqual(res["status"], "error")
        self.assertIn("Port 5060 closed", res["error"])

    @verifies("REQ-PROBE-001")
    @patch("ringcentral_probe.urllib.request.urlopen")
    def test_api_status_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        res = ringcentral_probe.check_api_status("https://platform.ringcentral.com/restapi/v1.0/status")
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["http_status"], 200)

    @verifies("REQ-PROBE-001")
    def test_itu_mos_calculation(self):
        # Excellent quality
        mos_high = ringcentral_probe.calculate_itu_mos(rtt_ms=20.0, jitter_ms=1.5, packet_loss_pct=0.0)
        self.assertGreaterEqual(mos_high, 4.30)
        self.assertLessEqual(mos_high, 4.50)

        # Poor quality with delay & packet loss
        mos_low = ringcentral_probe.calculate_itu_mos(rtt_ms=250.0, jitter_ms=35.0, packet_loss_pct=8.0)
        self.assertLess(mos_low, 3.0)

    @verifies("REQ-PROBE-001")
    @patch("ringcentral_probe.check_sip_signaling", return_value={"status": "ok", "latency_ms": 12.0})
    @patch("ringcentral_probe.check_api_status", return_value={"status": "ok", "http_status": 200, "latency_ms": 22.0})
    def test_full_ringcentral_probe_run(self, mock_api, mock_sip):
        res = ringcentral_probe.run_ringcentral_probe()
        self.assertTrue(res["passed"])
        self.assertIn("mos_score", res["telemetry"])
        self.assertGreaterEqual(res["telemetry"]["mos_score"], 4.0)

if __name__ == "__main__":
    unittest.main()
