import pytest
from unittest.mock import patch, MagicMock, mock_open
import urllib.error
import ssl
import json

from sensor import caaspp_readiness

verifies = pytest.mark.verifies

@pytest.fixture
def mock_ssl_context():
    with patch('ssl.create_default_context') as mock_ctx_factory:
        mock_ctx = MagicMock()
        mock_ctx_factory.return_value = mock_ctx
        mock_ssock = MagicMock()
        mock_ctx.wrap_socket.return_value.__enter__.return_value = mock_ssock
        yield mock_ctx_factory, mock_ctx, mock_ssock

@pytest.fixture
def mock_socket():
    with patch('socket.create_connection') as mock_conn:
        mock_sock = MagicMock()
        mock_conn.return_value.__enter__.return_value = mock_sock
        yield mock_conn, mock_sock

@pytest.fixture
def mock_urlopen():
    with patch('urllib.request.urlopen') as mock_url:
        mock_response = MagicMock()
        mock_url.return_value.__enter__.return_value = mock_response
        yield mock_url, mock_response


@pytest.mark.parametrize("keyword", caaspp_readiness.KNOWN_MITM_ISSUERS)
@verifies("REQ-PRB-008")
@verifies("REQ-PRB-013")
def test_check_ssl_inspection_bypass_mitm_detected(keyword, mock_socket, mock_ssl_context):
    """Test that MITM detection properly identifies known firewall issuers."""
    _, _, mock_ssock = mock_ssl_context
    mock_ssock.getpeercert.return_value = {
        'issuer': ((('commonName', f'Fake {keyword.capitalize()} CA'),),)
    }

    is_bypassed, reason = caaspp_readiness.check_ssl_inspection_bypass("test.com")
    assert is_bypassed is False
    assert "MITM Detected" in reason
    assert keyword in reason.lower()


@verifies("REQ-PRB-013")
def test_check_ssl_inspection_bypass_genuine(mock_socket, mock_ssl_context):
    """Test that a genuine certificate passes bypassing validation."""
    _, _, mock_ssock = mock_ssl_context
    mock_ssock.getpeercert.return_value = {
        'issuer': ((('commonName', 'DigiCert Global Root CA'), ('organizationName', 'DigiCert Inc')),)
    }

    is_bypassed, reason = caaspp_readiness.check_ssl_inspection_bypass("test.com")
    assert is_bypassed is True
    assert "Bypassed / Genuine CA" in reason


@verifies("REQ-PRB-013")
def test_check_ssl_inspection_bypass_ssl_error(mock_socket, mock_ssl_context):
    """Test that SSL errors are gracefully handled."""
    _, mock_ctx, _ = mock_ssl_context
    mock_ctx.wrap_socket.side_effect = ssl.SSLError("handshake failed")

    is_bypassed, reason = caaspp_readiness.check_ssl_inspection_bypass("test.com")
    assert is_bypassed is False
    assert "SSL Error:" in reason


@verifies("REQ-PRB-013")
def test_check_ssl_inspection_bypass_connection_error(mock_socket, mock_ssl_context):
    """Test that general connection errors are gracefully handled."""
    mock_conn, _ = mock_socket
    mock_conn.side_effect = Exception("network unreachable")

    is_bypassed, reason = caaspp_readiness.check_ssl_inspection_bypass("test.com")
    assert is_bypassed is False
    assert "Connection Error:" in reason


@verifies("REQ-PRB-013")
@patch('os.path.exists', return_value=True)
def test_check_ssl_inspection_bypass_custom_ca(mock_exists, mock_socket, mock_ssl_context):
    """Test that custom CA bundle is loaded if provided."""
    _, mock_ctx, mock_ssock = mock_ssl_context
    mock_ssock.getpeercert.return_value = {}

    caaspp_readiness.check_ssl_inspection_bypass("test.com", ca_bundle="/fake/cert.pem")
    mock_ctx.load_verify_locations.assert_called_once_with(cafile="/fake/cert.pem")


@pytest.mark.parametrize("status_code", [200, 301, 302, 307])
@verifies("REQ-PRB-013")
def test_check_http_endpoint_success(status_code, mock_urlopen):
    """Test that successful status codes result in a passed check."""
    _, mock_response = mock_urlopen
    mock_response.status = status_code

    target = {"url": "https://test.com"}
    is_ok, latency, code, reason = caaspp_readiness.check_http_endpoint(target)

    assert is_ok is True
    assert code == status_code
    assert reason == "OK"
    assert latency >= 0.0


@pytest.mark.parametrize("status_code", [401, 403])
@verifies("REQ-PRB-013")
def test_check_http_endpoint_auth_error(status_code, mock_urlopen):
    """Test that 401/403 are considered OK as they prove reachability."""
    mock_url, _ = mock_urlopen
    mock_url.side_effect = urllib.error.HTTPError("url", status_code, "msg", {}, None)

    target = {"url": "https://test.com"}
    is_ok, latency, code, reason = caaspp_readiness.check_http_endpoint(target)

    assert is_ok is True
    assert code == status_code
    assert f"HTTP {status_code}" in reason


@verifies("REQ-PRB-013")
def test_check_http_endpoint_urlerror(mock_urlopen):
    """Test handling of DNS/network failures."""
    mock_url, _ = mock_urlopen
    mock_url.side_effect = urllib.error.URLError("name resolution failed")

    target = {"url": "https://test.com"}
    is_ok, latency, code, reason = caaspp_readiness.check_http_endpoint(target)

    assert is_ok is False
    assert code == 0
    assert "Network/DNS Error" in reason


@verifies("REQ-PRB-013")
def test_check_http_endpoint_timeout(mock_urlopen):
    """Test generic exceptions like timeout."""
    mock_url, _ = mock_urlopen
    mock_url.side_effect = Exception("timed out")

    target = {"url": "https://test.com"}
    is_ok, latency, code, reason = caaspp_readiness.check_http_endpoint(target)

    assert is_ok is False
    assert code == 0
    assert "Timeout/Error" in reason


@verifies("REQ-PRB-013")
@patch('os.replace')
@patch('os.makedirs')
def test_write_metrics_file(mock_makedirs, mock_replace):
    """Test atomic file writing for metrics."""
    with patch("builtins.open", mock_open()) as m:
        caaspp_readiness.write_metrics(["metric_1", "metric_2"], "/fake/out.prom")

        m.assert_called_once_with("/fake/out.prom.tmp", "w")
        m().write.assert_called_once_with("metric_1\nmetric_2\n")
        mock_replace.assert_called_once_with("/fake/out.prom.tmp", "/fake/out.prom")
        mock_makedirs.assert_called_once_with("/fake", exist_ok=True)


@verifies("REQ-PRB-013")
@patch('builtins.print')
def test_write_metrics_stdout(mock_print):
    """Test metrics fallback to stdout."""
    caaspp_readiness.write_metrics(["metric_1"], None)
    mock_print.assert_called_with("metric_1\n")


@verifies("REQ-PRB-013")
@patch('sensor.caaspp_readiness.check_http_endpoint')
@patch('sensor.caaspp_readiness.check_ssl_inspection_bypass')
@patch('sensor.caaspp_readiness.write_metrics')
def test_main_normal_all_ok(mock_write, mock_ssl, mock_http):
    """Test main function with all critical checks passing."""
    mock_http.return_value = (True, 0.1, 200, "OK")
    mock_ssl.return_value = (True, "Genuine CA")

    with patch('sys.argv', ['caaspp_readiness.py', '/fake/out.prom']):
        caaspp_readiness.main()

    mock_write.assert_called_once()
    lines = mock_write.call_args[0][0]
    assert "caaspp_readiness_overall 1" in lines


@verifies("REQ-PRB-013")
@patch('sensor.caaspp_readiness.check_http_endpoint')
@patch('sensor.caaspp_readiness.check_ssl_inspection_bypass')
@patch('builtins.print')
def test_main_json_output(mock_print, mock_ssl, mock_http):
    """Test main function with JSON output."""
    mock_http.return_value = (True, 0.1, 200, "OK")
    mock_ssl.return_value = (True, "Genuine CA")

    with patch('sys.argv', ['caaspp_readiness.py', '--json']):
        caaspp_readiness.main()

    called_str = mock_print.call_args[0][0]
    parsed = json.loads(called_str)
    assert parsed["overall_ready"] is True
    assert parsed["status"] == "ok"
    assert len(parsed["checks"]) > 0


@verifies("REQ-PRB-013")
@patch('sensor.caaspp_readiness.check_http_endpoint')
@patch('sensor.caaspp_readiness.check_ssl_inspection_bypass')
@patch('subprocess.Popen')
@patch('os.path.exists', return_value=True)
@patch('sensor.caaspp_readiness.write_metrics')
def test_main_pcap_trigger(mock_write, mock_exists, mock_popen, mock_ssl, mock_http):
    """Test that PCAP snapshot is triggered when critical endpoints fail."""
    mock_http.return_value = (False, 0.1, 0, "Error")
    mock_ssl.return_value = (False, "MITM")

    with patch('sys.argv', ['caaspp_readiness.py']):
        caaspp_readiness.main()

    mock_popen.assert_called_once()
    args = mock_popen.call_args[0][0]
    assert "pcap_trigger.py" in args[1]
    assert "--trigger" in args
    assert "caaspp_failure" in args


@verifies("REQ-PRB-013")
@patch('subprocess.Popen')
@patch('sensor.caaspp_readiness.check_http_endpoint')
@patch('sensor.caaspp_readiness.check_ssl_inspection_bypass')
@patch('sensor.caaspp_readiness.write_metrics')
def test_graceful_degradation_offline(mock_write, mock_ssl, mock_http, mock_popen):
    """Test graceful degradation when offline, ensuring safe handling."""
    mock_http.return_value = (False, 0.0, 0, "Network/DNS Error: offline")
    mock_ssl.return_value = (False, "Connection Error: offline")

    with patch('sys.argv', ['caaspp_readiness.py', '/fake/out.prom']):
        caaspp_readiness.main()

    mock_write.assert_called_once()
    lines = mock_write.call_args[0][0]
    assert "caaspp_readiness_overall 0" in lines
