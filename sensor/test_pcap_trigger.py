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
import pcap_trigger

class TestPcapTrigger(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.ram_dir = os.path.join(self.test_dir.name, "shm")
        self.snap_dir = os.path.join(self.test_dir.name, "snapshots")
        self.prom_file = os.path.join(self.test_dir.name, "pcap.prom")

    def tearDown(self):
        self.test_dir.cleanup()

    @patch("pcap_trigger.RAM_BUFFER_DIR")
    @patch("pcap_trigger.SNAPSHOT_DIR")
    def test_ensure_directories(self, mock_snap, mock_ram):
        mock_ram.__str__.return_value = self.ram_dir
        mock_snap.__str__.return_value = self.snap_dir
        with patch("os.makedirs") as mock_mkdirs:
            pcap_trigger.ensure_directories()
            self.assertEqual(mock_mkdirs.call_count, 2)

    @verifies("REQ-PRB-002")
    @patch("subprocess.Popen")
    @patch("pcap_trigger.ensure_directories")
    def test_start_rolling_capture(self, mock_ensure, mock_popen):
        mock_proc = MagicMock()
        mock_popen.return_value = mock_proc
        proc = pcap_trigger.start_rolling_capture(interface="eth0", snaplen=128)
        self.assertEqual(proc, mock_proc)
        mock_popen.assert_called_once()

        mock_popen.side_effect = Exception("tcpdump not installed")
        proc_fail = pcap_trigger.start_rolling_capture()
        self.assertIsNone(proc_fail)

    @verifies("REQ-PRB-002")
    @patch("pcap_trigger.SNAPSHOT_DIR")
    @patch("pcap_trigger.RAM_BUFFER_DIR")
    @patch("pcap_trigger.DEFAULT_PROM_FILE")
    @patch("subprocess.run")
    def test_trigger_pcap_snapshot(self, mock_run, mock_prom, mock_ram, mock_snap):
        os.makedirs(self.ram_dir, exist_ok=True)
        os.makedirs(self.snap_dir, exist_ok=True)

        chunk1 = os.path.join(self.ram_dir, "ring.pcap")
        with open(chunk1, "wb") as f:
            f.write(b"PCAP_DUMMY_DATA_1")

        with patch("pcap_trigger.RAM_BUFFER_DIR", self.ram_dir), \
             patch("pcap_trigger.SNAPSHOT_DIR", self.snap_dir), \
             patch("pcap_trigger.DEFAULT_PROM_FILE", self.prom_file):

            mock_run.return_value = MagicMock(returncode=0)
            snapshot_path = pcap_trigger.trigger_pcap_snapshot(reason="synthetic_failure", details={"test": "ok"})
            self.assertIsNotNone(snapshot_path)
            self.assertTrue(snapshot_path.endswith(".pcap"))
            self.assertTrue(os.path.exists(snapshot_path + ".json"))

    def test_prune_old_snapshots(self):
        os.makedirs(self.snap_dir, exist_ok=True)
        with patch("pcap_trigger.SNAPSHOT_DIR", self.snap_dir), \
             patch("pcap_trigger.MAX_SNAPSHOTS_RETAINED", 2):
            for i in range(4):
                fpath = os.path.join(self.snap_dir, f"incident_{i}.pcap")
                with open(fpath, "w") as f:
                    f.write(f"snap {i}")
                with open(fpath + ".json", "w") as f:
                    f.write("{}")

            pcap_trigger.prune_old_snapshots()
            remaining = [f for f in os.listdir(self.snap_dir) if f.endswith(".pcap")]
            self.assertLessEqual(len(remaining), 2)

    def test_emit_pcap_metrics(self):
        with patch("pcap_trigger.SNAPSHOT_DIR", self.snap_dir), \
             patch("pcap_trigger.DEFAULT_PROM_FILE", self.prom_file):
            pcap_trigger.emit_pcap_metrics("dns_failure")
            self.assertTrue(os.path.exists(self.prom_file))
            with open(self.prom_file, "r") as f:
                content = f.read()
                self.assertIn("openux_pcap_snapshots_total", content)
                self.assertIn('reason="dns_failure"', content)

if __name__ == "__main__":
    unittest.main()
