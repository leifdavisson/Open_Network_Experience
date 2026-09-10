import pytest
import asyncio
from hypothesis import given, strategies as st, settings

from server import db
from server.routers.sensor_diagnostics import run_sensor_diagnostics, DiagnosticRunRequest
from server.state import PROBES_DB, get_or_create_sensor

@pytest.fixture(autouse=True)
def setup_mock_probes():
    db.init_db()
    PROBES_DB["taco-bell"] = {
        "id": "taco-bell",
        "name": "Taco Bell Order API",
        "probe_type": "http",
        "target": "https://malformed.taco.bell"
    }
    yield
    if "taco-bell" in PROBES_DB:
        del PROBES_DB["taco-bell"]

@given(test_type=st.text(min_size=1).filter(lambda x: x not in ["speedtest", "iperf3", "canvas", "pcap", "taco-bell", "classroom", "google", "iready", "ringcentral", "rc_voip", "zoom", "voip", "jitter", "client_isolation", "intra_bss", "guest_isolation", "vlan_isolation", "segmentation", "caaspp", "dns", "gateway", "all", "wifi_flapping", "rrm_darrp", "cipa", "content_filter", "dhcp", "lease"]))
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
    assert any("Good DNS Probe" in d["name"] for d in res["details"])
    assert res["status"] in ["PASS", "FAIL"]
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
    assert any("Good TCP Probe" in d["name"] for d in res["details"])
    assert res["status"] in ["PASS", "FAIL"]
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
    assert any("Other Probe" in d["name"] for d in res["details"])
    assert res["status"] in ["PASS", "FAIL"]
    del PROBES_DB["other-probe"]

@pytest.mark.verifies("REQ-DIAG-008")
def test_dynamic_gateway_derivation():
    # Setup sensor with specific subnet IP 10.98.2.141
    sensor = get_or_create_sensor("sensor-141")
    sensor["ip_address"] = "10.98.2.141"

    req = DiagnosticRunRequest(test_type="gateway")
    res = asyncio.run(run_sensor_diagnostics("sensor-141", req))

    gw_detail = next(d for d in res["details"] if "Default" in d["name"])
    assert "10.98.2.1" in gw_detail["target"]
    assert "10.0.0.1" not in gw_detail["target"]

    # Test default/all suite as well
    req_all = DiagnosticRunRequest(test_type="all")
    res_all = asyncio.run(run_sensor_diagnostics("sensor-141", req_all))
    gw_all_detail = next(d for d in res_all["details"] if "Default Gateway" in d["name"])
    assert gw_all_detail["target"] == "10.98.2.1"

@pytest.mark.verifies("REQ-DIAG-009")
def test_wifi_flapping_probe_execution():
    req = DiagnosticRunRequest(test_type="wifi_flapping")
    res = asyncio.run(run_sensor_diagnostics("sensor-123", req))

    assert any("Wi-Fi" in d["name"] or "DARRP" in d["name"] for d in res["details"])
    assert "Default Gateway ICMP Ping" not in [d["name"] for d in res["details"]]

@pytest.mark.verifies("REQ-DIAG-010")
def test_accurate_attribution_string_formatting():
    # Force an unreachable target override on HTTP probe
    req = DiagnosticRunRequest(test_type="all", custom_target="http://10.255.255.1:59999")
    res = asyncio.run(run_sensor_diagnostics("sensor-123", req))

    failed_http = next(d for d in res["details"] if d["type"] == "HTTP 2XX" and not d["passed"])
    assert "valid SSL cert" not in failed_http["info"]
    assert ("Unreachable" in failed_http["info"] or "HTTP" in failed_http["info"] or "failed" in failed_http["info"].lower())

@pytest.mark.verifies("REQ-DIAG-011")
def test_cipa_probe_execution():
    req = DiagnosticRunRequest(test_type="cipa")
    res = asyncio.run(run_sensor_diagnostics("sensor-123", req))
    assert res["status"] in ["PASS", "WARNING"]
    assert any("CSAM" in d["name"] or "IWF" in d["name"] for d in res["details"])
    assert any("CTIRU" in d["name"] for d in res["details"])
    assert any("Adult" in d["name"] for d in res["details"])

@pytest.mark.verifies("REQ-DIAG-012")
def test_dhcp_probe_execution():
    req = DiagnosticRunRequest(test_type="dhcp")
    res = asyncio.run(run_sensor_diagnostics("sensor-123", req))
    assert res["status"] == "PASS"
    assert any("DORA" in d["name"] for d in res["details"])
    assert any("Scope" in d["name"] or "Pool" in d["name"] for d in res["details"])

@pytest.mark.verifies("REQ-DIAG-013")
def test_canvas_probe_execution():
    req = DiagnosticRunRequest(test_type="canvas")
    res = asyncio.run(run_sensor_diagnostics("sensor-123", req))
    assert res["status"] in ["PASS", "WARNING"]
    assert any("Canvas LMS" in d["name"] for d in res["details"])
