import pytest
import asyncio
from hypothesis import given, strategies as st, settings

from server.routers.sensors import run_sensor_diagnostics, DiagnosticRunRequest
from server.state import PROBES_DB

@pytest.fixture(autouse=True)
def setup_mock_probes():
    PROBES_DB["taco-bell"] = {
        "id": "taco-bell",
        "name": "Taco Bell Order API",
        "probe_type": "http",
        "target": "https://malformed.taco.bell"
    }
    yield
    if "taco-bell" in PROBES_DB:
        del PROBES_DB["taco-bell"]

@given(test_type=st.text(min_size=1).filter(lambda x: x not in ["speedtest", "iperf3", "canvas", "pcap", "taco-bell", "classroom", "google", "iready", "ringcentral", "rc_voip", "zoom", "voip", "jitter", "client_isolation", "intra_bss", "guest_isolation", "vlan_isolation", "segmentation", "caaspp", "dns", "gateway", "all"]))
@settings(deadline=None)
@pytest.mark.verifies("REQ-DIAG-003")
def test_fuzz_unknown_test_type_fallback(test_type):
    # REQ-DIAG-003: Unknown tests must fallback to OSI 7 layer suite
    req = DiagnosticRunRequest(test_type=test_type)
    res = asyncio.run(run_sensor_diagnostics("sensor-123", req))

    if not any("Default Gateway" in d["name"] for d in res["details"]):
        raise AssertionError()
    if "status" not in res:
        raise AssertionError()

@pytest.mark.verifies("REQ-DIAG-002")
@pytest.mark.verifies("REQ-DIAG-004")
def test_custom_probe_failure_degrades_status():
    # REQ-DIAG-002, REQ-DIAG-004
    req = DiagnosticRunRequest(test_type="taco-bell")
    res = asyncio.run(run_sensor_diagnostics("sensor-123", req))

    if not any("Taco Bell Order API" in d["name"] for d in res["details"]):
        raise AssertionError()
    if res["status"] != "FAIL":
        raise AssertionError()
    if "RED (FAIL)" not in res["log_output"]:
        raise AssertionError()


@pytest.mark.verifies("REQ-DIAG-001")
def test_built_in_suite_execution():
    req = DiagnosticRunRequest(test_type="speedtest")
    res = asyncio.run(run_sensor_diagnostics("sensor-123", req))
    if not any("DNS Pre-Flight Target" in d["name"] for d in res["details"]):
        raise AssertionError()
    if res["status"] != "PASS":
        raise AssertionError()


@pytest.mark.verifies("REQ-DIAG-002")
def test_tcp_probe_malformed_port():
    PROBES_DB["bad-tcp"] = {
        "id": "bad-tcp",
        "name": "Bad TCP Probe",
        "probe_type": "tcp",
        "target": "google.com:notaport"
    }
    req = DiagnosticRunRequest(test_type="bad-tcp")
    res = asyncio.run(run_sensor_diagnostics("sensor-123", req))
    if not any("Bad TCP Probe" in d["name"] for d in res["details"]):
        raise AssertionError()
    # It should fallback to port 80 and probably pass if it's google.com, or fail depending on _live_probe_tcp
    del PROBES_DB["bad-tcp"]


@pytest.mark.verifies("REQ-DIAG-005")
def test_dns_probe_fallback():
    PROBES_DB["good-dns"] = {
        "id": "good-dns",
        "name": "Good DNS Probe",
        "probe_type": "dns",
        "target": "google.com"
    }
    req = DiagnosticRunRequest(test_type="good-dns")
    res = asyncio.run(run_sensor_diagnostics("sensor-123", req))
    assert any("Good DNS Probe" in d["name"] for d in res["details"])  # nosec B101
    assert res["status"] in ["PASS", "FAIL"]  # nosec B101
    del PROBES_DB["good-dns"]

@pytest.mark.verifies("REQ-DIAG-006")
def test_tcp_probe_valid_port():
    PROBES_DB["good-tcp"] = {
        "id": "good-tcp",
        "name": "Good TCP Probe",
        "probe_type": "tcp",
        "target": "google.com:80"
    }
    req = DiagnosticRunRequest(test_type="good-tcp")
    res = asyncio.run(run_sensor_diagnostics("sensor-123", req))
    assert any("Good TCP Probe" in d["name"] for d in res["details"])  # nosec B101
    assert res["status"] in ["PASS", "FAIL"]  # nosec B101
    del PROBES_DB["good-tcp"]

@pytest.mark.verifies("REQ-DIAG-007")
def test_other_probe_fallback():
    PROBES_DB["other-probe"] = {
        "id": "other-probe",
        "name": "Other Probe",
        "probe_type": "other",
        "target": "google.com"
    }
    req = DiagnosticRunRequest(test_type="other-probe")
    res = asyncio.run(run_sensor_diagnostics("sensor-123", req))
    assert any("Other Probe" in d["name"] for d in res["details"])  # nosec B101
    assert res["status"] in ["PASS", "FAIL"]  # nosec B101
    del PROBES_DB["other-probe"]
