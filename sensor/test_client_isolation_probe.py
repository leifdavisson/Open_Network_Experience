#!/usr/bin/env python3
import unittest
from unittest.mock import patch, MagicMock
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import client_isolation_probe

def verifies(req_id: str):
    def decorator(fn):
        fn.__verifies__ = req_id
        return fn
    return decorator

class TestClientIsolationProbe(unittest.TestCase):
    @verifies("REQ-SEC-001")
    @patch("client_isolation_probe.subprocess.run")
    def test_gateway_reachability_pass(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        res = client_isolation_probe.probe_gateway_reachability("10.98.2.1")
        self.assertTrue(res)

    @verifies("REQ-SEC-001")
    @patch("client_isolation_probe.socket.socket")
    @patch("client_isolation_probe.subprocess.run")
    def test_lateral_peers_isolated_nominal(self, mock_run, mock_sock_cls):
        # All peer connects fail (Strict client isolation)
        mock_sock = MagicMock()
        mock_sock.connect.side_effect = ConnectionRefusedError("Dropped by AP")
        mock_sock_cls.return_value = mock_sock
        mock_run.return_value = MagicMock(returncode=1)  # Ping fails

        res = client_isolation_probe.probe_lateral_peers("10.98.2.105", "10.98.2.1")
        self.assertEqual(res["peer_count"], 0)
        self.assertEqual(len(res["leaked_peers_discovered"]), 0)

    @verifies("REQ-SEC-001")
    @patch("client_isolation_probe.socket.socket")
    @patch("client_isolation_probe.subprocess.run")
    def test_lateral_peers_breach_detected(self, mock_run, mock_sock_cls):
        # Peer connect succeeds (Client isolation breach)
        mock_sock = MagicMock()
        mock_sock_cls.return_value = mock_sock
        mock_run.return_value = MagicMock(returncode=0)  # Ping succeeds

        res = client_isolation_probe.probe_lateral_peers("10.98.2.105", "10.98.2.1")
        self.assertGreater(res["peer_count"], 0)

    @verifies("REQ-SEC-001")
    @patch("client_isolation_probe.get_default_gateway_and_ip", return_value={"gateway_ip": "10.98.2.1", "interface": "wlp1s0", "local_ip": "10.98.2.105"})
    @patch("client_isolation_probe.probe_gateway_reachability", return_value=True)
    @patch("client_isolation_probe.probe_lateral_peers", return_value={"candidate_peers_scanned": ["10.98.2.102"], "leaked_peers_discovered": [], "peer_count": 0})
    def test_full_client_isolation_run_pass(self, mock_peers, mock_gw, mock_net):
        res = client_isolation_probe.run_client_isolation_probe()
        self.assertTrue(res["isolation_enforced"])
        self.assertIn("PASS", res["summary"])

    @verifies("REQ-SEC-001")
    @patch("client_isolation_probe.get_default_gateway_and_ip", return_value={"gateway_ip": "10.98.2.1", "interface": "wlp1s0", "local_ip": "10.98.2.105"})
    @patch("client_isolation_probe.probe_gateway_reachability", return_value=True)
    @patch("client_isolation_probe.probe_lateral_peers", return_value={"candidate_peers_scanned": ["10.98.2.102"], "leaked_peers_discovered": ["10.98.2.102"], "peer_count": 1})
    def test_full_client_isolation_run_breach(self, mock_peers, mock_gw, mock_net):
        res = client_isolation_probe.run_client_isolation_probe()
        self.assertFalse(res["isolation_enforced"])
        self.assertIn("BREACH", res["summary"])

if __name__ == "__main__":
    unittest.main()
