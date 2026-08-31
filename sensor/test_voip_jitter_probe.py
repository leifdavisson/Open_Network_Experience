#!/usr/bin/env python3
# License: GNU AGPLv3 (GNU Affero General Public License v3.0)
"""
Comprehensive Unit Test Suite for OpenUX Real-Time Voice & Video (VoIP / Zoom) Jitter Prober
(sensor/voip_jitter_probe.py).

Verifies:
  - STUN Binding Request packet encoding (RFC 5389 magic cookie, transaction ID, packet length)
  - ITU-T G.107 E-model Mean Opinion Score (MOS) calculation and boundary clamping (1.0 - 4.5)
  - UDP jitter probing (DNS resolution failure, successful STUN responses, partial packet loss, all packets dropped, device binding)
  - Atomic Prometheus metric file generation
  - CLI argument parsing and main execution loop
"""

import os
import sys
import socket
import tempfile
import unittest
from unittest.mock import patch, MagicMock, call

# Ensure sensor directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import voip_jitter_probe


def verifies(req_id: str):
    """Decorator to attach requirement traceability identifiers to test methods."""
    def decorator(fn):
        fn.__verifies__ = req_id
        return fn
    return decorator


class TestVoipJitterProbe(unittest.TestCase):
    """Test suite for voip_jitter_probe module."""

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.output_prom = os.path.join(self.test_dir.name, "voip_jitter.prom")

    def tearDown(self):
        self.test_dir.cleanup()

    # ==========================================
    # 1. STUN Packet Encoding Tests
    # ==========================================

    @verifies("REQ-PRB-009")
    def test_build_stun_binding_request_format(self):
        """Verifies STUN Binding Request packet length, magic cookie, and transaction ID encoding."""
        tx_id = b"123456789012"  # 12-byte transaction ID
        pkt = voip_jitter_probe.build_stun_binding_request(tx_id)

        # RFC 5389 Header: 20 bytes total
        # 0-2: Message Type (0x0001 = Binding Request)
        # 2-4: Message Length (0x0000)
        # 4-8: Magic Cookie (0x2112A442)
        # 8-20: Transaction ID (12 bytes)
        self.assertEqual(len(pkt), 20)
        self.assertEqual(pkt[0:2], b"\x00\x01")
        self.assertEqual(pkt[2:4], b"\x00\x00")
        self.assertEqual(pkt[4:8], b"\x21\x12\xa4\x42")
        self.assertEqual(pkt[8:20], tx_id)

    @verifies("REQ-PRB-009")
    def test_build_stun_binding_request_random_tx_id(self):
        """Verifies STUN Binding Request with arbitrary random 12-byte transaction ID."""
        random_tx = os.urandom(12)
        pkt = voip_jitter_probe.build_stun_binding_request(random_tx)
        self.assertEqual(len(pkt), 20)
        self.assertEqual(pkt[8:20], random_tx)

    # ==========================================
    # 2. MOS Score Calculation Tests
    # ==========================================

    @verifies("REQ-PRB-009")
    def test_calculate_mos_score_crystal_clear(self):
        """Verifies MOS score under ideal low latency, minimal jitter, and zero packet loss (~4.4 MOS)."""
        mos = voip_jitter_probe.calculate_mos_score(rtt_ms=20.0, jitter_ms=2.0, loss_percent=0.0)
        self.assertGreaterEqual(mos, 4.3)
        self.assertLessEqual(mos, 4.5)

    @verifies("REQ-PRB-009")
    def test_calculate_mos_score_high_latency_jitter_loss(self):
        """Verifies MOS score degrades severely (< 3.0 MOS) with high latency, jitter, and loss."""
        mos = voip_jitter_probe.calculate_mos_score(rtt_ms=250.0, jitter_ms=60.0, loss_percent=15.0)
        self.assertLess(mos, 3.0)
        self.assertGreaterEqual(mos, 1.0)

    @verifies("REQ-PRB-009")
    def test_calculate_mos_score_clamped_boundaries(self):
        """Verifies MOS score is strictly clamped between 1.0 and 4.5."""
        # Extreme bad conditions
        worst_mos = voip_jitter_probe.calculate_mos_score(rtt_ms=1000.0, jitter_ms=500.0, loss_percent=100.0)
        self.assertEqual(worst_mos, 1.0)

        # Extreme theoretical zero latency
        best_mos = voip_jitter_probe.calculate_mos_score(rtt_ms=0.0, jitter_ms=0.0, loss_percent=0.0)
        self.assertLessEqual(best_mos, 4.5)
        self.assertGreaterEqual(best_mos, 4.3)

    @verifies("REQ-PRB-009")
    def test_calculate_mos_score_intermediate_bounds(self):
        """Verifies MOS score under moderate corporate network conditions (effective_latency >= 160ms)."""
        # Effective latency: 150 + 20*2 + 10 = 200ms (> 160ms branch)
        mos = voip_jitter_probe.calculate_mos_score(rtt_ms=150.0, jitter_ms=20.0, loss_percent=2.0)
        self.assertGreaterEqual(mos, 3.5)
        self.assertLess(mos, 4.3)

    # ==========================================
    # 3. UDP Jitter Prober Tests (probe_udp_jitter)
    # ==========================================

    @verifies("REQ-PRB-009")
    @patch("socket.gethostbyname")
    def test_probe_udp_jitter_dns_failure(self, mock_gethostbyname):
        """Verifies probe_udp_jitter handles DNS resolution failure gracefully."""
        mock_gethostbyname.side_effect = socket.gaierror(socket.EAI_NONAME, "Name or service not known")

        res = voip_jitter_probe.probe_udp_jitter("stun.invalid.example")
        self.assertEqual(res["status"], 0)
        self.assertEqual(res["loss_percent"], 100.0)
        self.assertEqual(res["mos_score"], 1.0)
        self.assertIn("DNS resolution failed", res["error"])

    @verifies("REQ-PRB-009")
    @patch("time.sleep")
    @patch("socket.socket")
    @patch("socket.gethostbyname")
    def test_probe_udp_jitter_success(self, mock_gethostbyname, mock_socket_class, mock_sleep):
        """Verifies probe_udp_jitter measures RTT, jitter, and MOS score with successful STUN responses."""
        mock_gethostbyname.return_value = "74.125.250.129"
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        # Mock sendto and recvfrom to return valid matching STUN echo packets
        def mock_sendto(pkt, dest):
            # Extract tx_id from the outgoing packet
            tx_id = pkt[8:20]
            # Construct a valid STUN response echo matching magic cookie and tx_id
            resp = b"\x01\x01\x00\x00\x21\x12\xa4\x42" + tx_id
            mock_sock.recvfrom.return_value = (resp, dest)
            return len(pkt)

        mock_sock.sendto.side_effect = mock_sendto

        res = voip_jitter_probe.probe_udp_jitter(
            host="stun.l.google.com",
            port=19302,
            packet_count=5,
            interval_sec=0.001,
            timeout_sec=0.5
        )

        self.assertEqual(res["status"], 1)
        self.assertEqual(res["loss_percent"], 0.0)
        self.assertGreaterEqual(res["rtt_ms"], 0.0)
        self.assertGreaterEqual(res["jitter_ms"], 0.0)
        self.assertGreaterEqual(res["mos_score"], 4.0)
        self.assertEqual(res["error"], "OK")
        mock_sock.close.assert_called_once()

    @verifies("REQ-PRB-009")
    @patch("time.sleep")
    @patch("socket.socket")
    @patch("socket.gethostbyname")
    def test_probe_udp_jitter_partial_packet_loss_and_invalid_response(self, mock_gethostbyname, mock_socket_class, mock_sleep):
        """Verifies probe_udp_jitter handles timeouts and corrupted/mismatched STUN responses."""
        mock_gethostbyname.return_value = "74.125.250.129"
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        call_count = [0]

        def mock_sendto(pkt, dest):
            call_count[0] += 1
            if call_count[0] == 1:
                # 1st packet: valid response
                tx_id = pkt[8:20]
                resp = b"\x01\x01\x00\x00\x21\x12\xa4\x42" + tx_id
                mock_sock.recvfrom.return_value = (resp, dest)
            elif call_count[0] == 2:
                # 2nd packet: timeout
                mock_sock.recvfrom.side_effect = socket.timeout("timed out")
            elif call_count[0] == 3:
                # 3rd packet: invalid magic cookie
                mock_sock.recvfrom.side_effect = None
                resp = b"\x01\x01\x00\x00\x00\x00\x00\x00" + os.urandom(12)
                mock_sock.recvfrom.return_value = (resp, dest)
            elif call_count[0] == 4:
                # 4th packet: mismatched transaction ID
                mock_sock.recvfrom.side_effect = None
                resp = b"\x01\x01\x00\x00\x21\x12\xa4\x42" + os.urandom(12)
                mock_sock.recvfrom.return_value = (resp, dest)
            else:
                # 5th packet: valid response
                mock_sock.recvfrom.side_effect = None
                tx_id = pkt[8:20]
                resp = b"\x01\x01\x00\x00\x21\x12\xa4\x42" + tx_id
                mock_sock.recvfrom.return_value = (resp, dest)
            return len(pkt)

        mock_sock.sendto.side_effect = mock_sendto

        res = voip_jitter_probe.probe_udp_jitter(
            host="stun.l.google.com",
            port=19302,
            packet_count=5,
            interval_sec=0.001,
            timeout_sec=0.5
        )

        # 2 out of 5 received -> 60% loss
        self.assertEqual(res["loss_percent"], 60.0)
        self.assertEqual(res["status"], 0)  # > 20% loss results in status 0
        self.assertEqual(res["error"], "OK")

    @verifies("REQ-PRB-009")
    @patch("time.sleep")
    @patch("socket.socket")
    @patch("socket.gethostbyname")
    def test_probe_udp_jitter_all_packets_dropped(self, mock_gethostbyname, mock_socket_class, mock_sleep):
        """Verifies probe_udp_jitter returns 100% loss and status 0 when all UDP packets are dropped."""
        mock_gethostbyname.return_value = "74.125.250.129"
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.recvfrom.side_effect = socket.timeout("timed out")

        res = voip_jitter_probe.probe_udp_jitter(
            host="stun.l.google.com",
            port=19302,
            packet_count=3,
            interval_sec=0.001,
            timeout_sec=0.5
        )

        self.assertEqual(res["status"], 0)
        self.assertEqual(res["loss_percent"], 100.0)
        self.assertEqual(res["mos_score"], 1.0)
        self.assertEqual(res["error"], "All UDP probe packets dropped")

    @verifies("REQ-PRB-009")
    @patch("time.sleep")
    @patch("socket.socket")
    @patch("socket.gethostbyname")
    def test_probe_udp_jitter_interface_binding(self, mock_gethostbyname, mock_socket_class, mock_sleep):
        """Verifies probe_udp_jitter binds to specific network interface when provided."""
        mock_gethostbyname.return_value = "74.125.250.129"
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        def mock_sendto(pkt, dest):
            tx_id = pkt[8:20]
            resp = b"\x01\x01\x00\x00\x21\x12\xa4\x42" + tx_id
            mock_sock.recvfrom.return_value = (resp, dest)
            return len(pkt)

        mock_sock.sendto.side_effect = mock_sendto

        with patch.object(socket, "SO_BINDTODEVICE", 25, create=True):
            res = voip_jitter_probe.probe_udp_jitter(
                host="stun.l.google.com",
                port=19302,
                packet_count=1,
                interface="wlan0"
            )
            mock_sock.setsockopt.assert_called_with(socket.SOL_SOCKET, 25, b"wlan0")

    @verifies("REQ-PRB-009")
    @patch("time.sleep")
    @patch("socket.socket")
    @patch("socket.gethostbyname")
    def test_probe_udp_jitter_generic_exception_handling(self, mock_gethostbyname, mock_socket_class, mock_sleep):
        """Verifies probe_udp_jitter catches generic unexpected socket exceptions during send/recv."""
        mock_gethostbyname.return_value = "74.125.250.129"
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.sendto.side_effect = RuntimeError("Kernel socket error")

        res = voip_jitter_probe.probe_udp_jitter(
            host="stun.l.google.com",
            port=19302,
            packet_count=2,
            interval_sec=0.001,
            timeout_sec=0.5
        )
        self.assertEqual(res["status"], 0)
        self.assertEqual(res["loss_percent"], 100.0)

    @verifies("REQ-PRB-009")
    @patch("time.sleep")
    @patch("socket.socket")
    @patch("socket.gethostbyname")
    def test_probe_udp_jitter_bind_device_exception(self, mock_gethostbyname, mock_socket_class, mock_sleep):
        """Verifies probe_udp_jitter handles PermissionError gracefully when setting SO_BINDTODEVICE."""
        mock_gethostbyname.return_value = "74.125.250.129"
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.setsockopt.side_effect = PermissionError("Operation not permitted")

        def mock_sendto(pkt, dest):
            tx_id = pkt[8:20]
            resp = b"\x01\x01\x00\x00\x21\x12\xa4\x42" + tx_id
            mock_sock.recvfrom.return_value = (resp, dest)
            return len(pkt)

        mock_sock.sendto.side_effect = mock_sendto

        with patch.object(socket, "SO_BINDTODEVICE", 25, create=True):
            res = voip_jitter_probe.probe_udp_jitter(
                host="stun.l.google.com",
                port=19302,
                packet_count=1,
                interface="eth0"
            )
            self.assertEqual(res["status"], 1)

    # ==========================================
    # 4. Atomic Metrics Writing Tests
    # ==========================================

    @verifies("REQ-PRB-009")
    def test_write_metrics_atomic_file(self):
        """Verifies Prometheus metrics are written to file atomically with proper format."""
        results = [
            {
                "target_name": "Google-STUN-Primary",
                "host": "stun.l.google.com",
                "status": 1,
                "rtt_ms": 25.4,
                "jitter_ms": 3.2,
                "loss_percent": 0.0,
                "mos_score": 4.41
            },
            {
                "target_name": "Google-STUN-Backup",
                "host": "stun1.l.google.com",
                "status": 0,
                "rtt_ms": 120.0,
                "jitter_ms": 45.0,
                "loss_percent": 25.0,
                "mos_score": 2.15
            }
        ]

        voip_jitter_probe.write_metrics(results, self.output_prom)

        self.assertTrue(os.path.exists(self.output_prom))
        with open(self.output_prom, "r") as f:
            content = f.read()

        self.assertIn("# HELP openux_voip_status", content)
        self.assertIn("# TYPE openux_voip_status gauge", content)
        self.assertIn("# HELP openux_voip_mos_score", content)
        self.assertIn("# HELP openux_voip_rtt_seconds", content)
        self.assertIn("# HELP openux_voip_jitter_seconds", content)
        self.assertIn("# HELP openux_voip_packet_loss_ratio", content)

        self.assertIn('openux_voip_status{target="Google-STUN-Primary",host="stun.l.google.com"} 1', content)
        self.assertIn('openux_voip_mos_score{target="Google-STUN-Primary",host="stun.l.google.com"} 4.41', content)
        self.assertIn('openux_voip_rtt_seconds{target="Google-STUN-Primary",host="stun.l.google.com"} 0.0254', content)
        self.assertIn('openux_voip_jitter_seconds{target="Google-STUN-Primary",host="stun.l.google.com"} 0.0032', content)
        self.assertIn('openux_voip_packet_loss_ratio{target="Google-STUN-Primary",host="stun.l.google.com"} 0.0000', content)

        self.assertIn('openux_voip_status{target="Google-STUN-Backup",host="stun1.l.google.com"} 0', content)
        self.assertIn('openux_voip_mos_score{target="Google-STUN-Backup",host="stun1.l.google.com"} 2.15', content)
        self.assertIn('openux_voip_packet_loss_ratio{target="Google-STUN-Backup",host="stun1.l.google.com"} 0.2500', content)

    @verifies("REQ-PRB-009")
    @patch("builtins.print")
    def test_write_metrics_stdout_when_output_path_none(self, mock_print):
        """Verifies Prometheus metrics output to stdout when output_path is None or empty."""
        results = [
            {
                "target_name": "Test-STUN",
                "host": "stun.test.local",
                "status": 1,
                "rtt_ms": 15.0,
                "jitter_ms": 1.0,
                "loss_percent": 0.0,
                "mos_score": 4.45
            }
        ]

        voip_jitter_probe.write_metrics(results, "")
        mock_print.assert_called()
        printed_arg = mock_print.call_args[0][0]
        self.assertIn('openux_voip_status{target="Test-STUN",host="stun.test.local"} 1', printed_arg)

    # ==========================================
    # 5. CLI Execution & main() Tests
    # ==========================================

    @verifies("REQ-PRB-009")
    @patch("voip_jitter_probe.write_metrics")
    @patch("voip_jitter_probe.probe_udp_jitter")
    def test_main_execution(self, mock_probe_udp_jitter, mock_write_metrics):
        """Verifies main() iterates across targets and generates metrics."""
        mock_probe_udp_jitter.side_effect = [
            {
                "status": 1,
                "rtt_ms": 20.0,
                "jitter_ms": 2.5,
                "loss_percent": 0.0,
                "mos_score": 4.4,
                "error": "OK"
            },
            {
                "status": 1,
                "rtt_ms": 120.0,
                "jitter_ms": 20.0,
                "loss_percent": 5.0,
                "mos_score": 3.7,
                "error": "OK"
            }
        ]

        test_args = ["voip_jitter_probe.py", "--interface", "eth0", "--output", self.output_prom]
        with patch.object(sys, "argv", test_args):
            voip_jitter_probe.main()

        # Check probe_udp_jitter called for each target in DEFAULT_TARGETS
        self.assertEqual(mock_probe_udp_jitter.call_count, len(voip_jitter_probe.DEFAULT_TARGETS))
        for t in voip_jitter_probe.DEFAULT_TARGETS:
            mock_probe_udp_jitter.assert_any_call(t["host"], t["port"], packet_count=20, interface="eth0")

        mock_write_metrics.assert_called_once()
        results_passed = mock_write_metrics.call_args[0][0]
        self.assertEqual(len(results_passed), len(voip_jitter_probe.DEFAULT_TARGETS))
        self.assertEqual(mock_write_metrics.call_args[0][1], self.output_prom)

    @verifies("REQ-PRB-009")
    @patch("voip_jitter_probe.write_metrics")
    @patch("voip_jitter_probe.probe_udp_jitter")
    def test_main_execution_poor_mos_branch(self, mock_probe_udp_jitter, mock_write_metrics):
        """Verifies main() color output formatting for degraded/poor VoIP quality (< 3.5 MOS)."""
        mock_probe_udp_jitter.return_value = {
            "status": 0,
            "rtt_ms": 300.0,
            "jitter_ms": 80.0,
            "loss_percent": 30.0,
            "mos_score": 1.5,
            "error": "Degraded connection"
        }

        test_args = ["voip_jitter_probe.py", "--output", self.output_prom]
        with patch.object(sys, "argv", test_args):
            voip_jitter_probe.main()

        self.assertEqual(mock_probe_udp_jitter.call_count, len(voip_jitter_probe.DEFAULT_TARGETS))


if __name__ == "__main__":
    unittest.main()
