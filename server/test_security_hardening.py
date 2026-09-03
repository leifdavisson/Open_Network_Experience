import os
import sys
import time
import pytest
import subprocess
import shlex
from unittest.mock import patch, MagicMock
from fastapi import Request
from fastapi.testclient import TestClient

# Ensure the server directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from server.security import (
    verify_api_key_constant_time,
    create_session_token,
    verify_session_token,
    verify_dashboard_auth,
    DEFAULT_INSECURE_KEY
)
from server.main import app

verifies = pytest.mark.verifies

@verifies("REQ-SEC-001")
def test_verify_api_key_constant_time():
    """Verify constant-time API key validation logic."""
    assert verify_api_key_constant_time("valid-key", "valid-key") is True
    assert verify_api_key_constant_time("valid-key", "invalid-key") is False
    assert verify_api_key_constant_time("", "valid-key") is False
    assert verify_api_key_constant_time(None, "valid-key") is False
    assert verify_api_key_constant_time("valid-key", None) is False
    assert verify_api_key_constant_time("  valid-key  ", "valid-key") is True
    assert verify_api_key_constant_time("valid-key", "  valid-key  ") is True


@verifies("REQ-SEC-002")
def test_create_session_token():
    """Verify session token structure and HMAC-SHA256 signature."""
    with patch("server.security.SESSION_SECRET", "test-secret"):
        token = create_session_token("admin", 3600)
        parts = token.split(":")
        assert len(parts) == 3
        assert parts[0] == "admin"
        assert int(parts[1]) > time.time()
        assert len(parts[2]) == 64  # SHA256 hex digest length


@verifies("REQ-SEC-002")
def test_verify_session_token():
    """Verify session token validation handles valid, expired, tampered, and malformed tokens."""
    with patch("server.security.SESSION_SECRET", "test-secret"):
        # Valid token
        valid_token = create_session_token("admin", 3600)
        assert verify_session_token(valid_token) is True

        # Expired token
        expired_token = create_session_token("admin", -10)
        assert verify_session_token(expired_token) is False

        # Tampered signature
        parts = valid_token.split(":")
        tampered_token = f"{parts[0]}:{parts[1]}:{'0'*64}"
        assert verify_session_token(tampered_token) is False

        # Malformed (wrong part count)
        assert verify_session_token("admin:1234567890") is False

        # None/empty
        assert verify_session_token(None) is False
        assert verify_session_token("") is False


@verifies("REQ-SEC-001")
def test_verify_dashboard_auth():
    """Verify Dashboard UI authentication across headers, query params, and cookies."""
    import asyncio
    with patch("server.security.ADMIN_API_KEY", "secure-key"), \
         patch("server.security.ENV", "production"):

        # Valid header
        req = MagicMock(spec=Request)
        req.headers.get.side_effect = lambda k: "secure-key" if k == "X-API-Key" else None
        assert asyncio.run(verify_dashboard_auth(req)) is True

        # Valid query param
        req = MagicMock(spec=Request)
        req.headers.get.return_value = None
        req.query_params.get.side_effect = lambda k: "secure-key" if k == "api_key" else None
        assert asyncio.run(verify_dashboard_auth(req)) is True

        # Valid cookie
        req = MagicMock(spec=Request)
        req.headers.get.return_value = None
        req.query_params.get.return_value = None
        with patch("server.security.SESSION_SECRET", "test-secret"):
            token = create_session_token("admin", 3600)
            req.cookies.get.side_effect = lambda k: token if k == "one_session" else None
            assert asyncio.run(verify_dashboard_auth(req)) is True

        # Production rejection (no valid auth)
        req = MagicMock(spec=Request)
        req.headers.get.return_value = None
        req.query_params.get.return_value = None
        req.cookies.get.return_value = None
        assert asyncio.run(verify_dashboard_auth(req)) is False

    with patch("server.security.ADMIN_API_KEY", DEFAULT_INSECURE_KEY), \
         patch("server.security.ENV", "development"):
        # Dev mode bypass
        req = MagicMock(spec=Request)
        req.headers.get.return_value = None
        req.query_params.get.return_value = None
        req.cookies.get.return_value = None
        assert asyncio.run(verify_dashboard_auth(req)) is True


@verifies("REQ-SEC-001")
def test_production_fail_fast():
    """Verify that the security module aborts if loaded with insecure keys in production."""
    env = os.environ.copy()
    env["ENV"] = "production"
    env["ADMIN_API_KEY"] = DEFAULT_INSECURE_KEY

    cmd = [sys.executable, "-c", "import server.security"]
    result = subprocess.run(cmd, env=env, capture_output=True, text=True, cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

    assert result.returncode != 0
    assert "FATAL SECURITY ERROR" in result.stderr


@verifies("REQ-SEC-003")
def test_onboarding_shell_injection():
    """Verify shell injection prevention in install script generation."""
    payloads = ["; rm -rf /; echo ", "$(whoami)", "`whoami`", "test\ncmd", "a|b&c"]

    with TestClient(app) as client:
        for payload in payloads:
            params = {
                "site": payload,
                "building": payload,
                "room": payload,
                "district": payload,
                "notes": payload,
                "token": payload,
                "wifi_ssid": payload,
                "wifi_psk": payload
            }
            response = client.get("/install.sh", params=params)
            assert response.status_code == 200
            content = response.text

            # The payload should appear, but wrapped securely.
            # Using shlex.quote() ensures no shell execution
            expected_quoted = shlex.quote(payload)

            # Check site substitution as example (should be SITE_NAME=...)
            # It should look like SITE_NAME='...'
            assert f"SITE_NAME={expected_quoted}" in content
            assert f"BUILDING_NAME={expected_quoted}" in content
            assert f"ROOM_NAME={expected_quoted}" in content
            assert f"DISTRICT_NAME={expected_quoted}" in content
            assert f"LOCATION_NOTES={expected_quoted}" in content
            assert f"ENROLL_TOKEN={expected_quoted}" in content
            assert f"WIFI_SSID={expected_quoted}" in content
            assert f"WIFI_PSK={expected_quoted}" in content

            # Ensure the raw payload doesn't appear unescaped in variable assignments
            assert f'SITE_NAME="{payload}"' not in content


@verifies("REQ-SEC-003")
def test_usb_kit_zip_generation():
    """Verify USB kit zip contains expected files."""
    with TestClient(app) as client:
        response = client.get("/api/v1/onboarding/usb-kit.zip")
        assert response.status_code == 200
        assert response.headers["Content-Type"] == "application/zip"
        assert response.content.startswith(b"PK")


@verifies("REQ-SEC-003")
def test_install_script_404(tmp_path):
    """Verify 404 response when install.sh is missing."""
    with patch("server.routers.onboarding.os.path.exists", return_value=False):
        with TestClient(app) as client:
            response = client.get("/install.sh")
            assert response.status_code == 404


@verifies("REQ-SEC-002")
def test_auth_login_sets_cookie():
    """Verify successful login sets a secure session cookie."""
    with patch("server.routers.auth.verify_api_key_constant_time", return_value=True), \
         patch("server.routers.auth.create_session_token", return_value="dummy_token"):

        with TestClient(app) as client:
            response = client.post("/api/v1/auth/login", json={"api_key": "valid_key", "username": "admin"})
            assert response.status_code == 200
            assert "one_session" in response.cookies
            assert response.cookies["one_session"] == "dummy_token"


@verifies("REQ-SEC-002")
def test_auth_logout_clears_cookie():
    """Verify logout clears the session cookie."""
    with TestClient(app) as client:
        # Create a client with a pre-existing cookie to ensure it gets cleared
        client.cookies.set("one_session", "dummy_token")
        response = client.post("/api/v1/auth/logout")
        assert response.status_code == 200

        # Check that the cookie is instructed to be deleted (max-age=0 or expires in past)
        set_cookie = response.headers.get("set-cookie", "")
        assert "one_session=" in set_cookie
        assert "Max-Age=0" in set_cookie or "expires=" in set_cookie


# --- CORS Security (REQ-SEC-004) ---

@verifies("REQ-SEC-004")
def test_cors_no_wildcard_with_credentials():
    """Verify CORS does not combine allow_origins=['*'] with allow_credentials=True.

    Per the CORS specification and REQ-SEC-004, wildcard origins must not be
    combined with credentials. After the security fix, dev mode uses wildcard
    origins with credentials=False.
    """
    from server.main import app
    from starlette.middleware.cors import CORSMiddleware

    for middleware in app.user_middleware:
        if middleware.cls is CORSMiddleware:
            kwargs = middleware.kwargs
            origins = kwargs.get("allow_origins", [])
            credentials = kwargs.get("allow_credentials", False)
            # If wildcard is in origins, credentials MUST be False
            if "*" in origins:
                assert credentials is False, (
                    f"CORS violation: allow_origins={origins} with allow_credentials={credentials}. "
                    "Wildcard origins must not be combined with credentials=True."
                )
            break

# --- Validation Gate Tests ---

@verifies("REQ-SEC-005")
def test_custom_probe_spec_validation():
    from pydantic import ValidationError
    from server.schemas import CustomProbeSpec

    # Valid
    CustomProbeSpec(id="1", name="http_test", probe_type="http", target="https://example.com")
    CustomProbeSpec(id="2", name="dns_test", probe_type="dns", target="example.com")
    CustomProbeSpec(id="3", name="tcp_test", probe_type="tcp", target="example.com:80")

    # Invalid HTTP
    with pytest.raises(ValidationError) as exc:
        CustomProbeSpec(id="4", name="http_invalid", probe_type="http", target="example.com")
    assert "target must be a valid HTTP/HTTPS URL" in str(exc.value)

    # Invalid DNS
    with pytest.raises(ValidationError) as exc:
        CustomProbeSpec(id="5", name="dns_invalid", probe_type="dns", target="https://example.com")
    assert "target must be a valid domain name or IP address" in str(exc.value)

    # Invalid TCP - no port
    with pytest.raises(ValidationError) as exc:
        CustomProbeSpec(id="6", name="tcp_invalid1", probe_type="tcp", target="example.com")
    assert "target must be formatted as host:port" in str(exc.value)

    # Invalid TCP - port out of bounds
    with pytest.raises(ValidationError) as exc:
        CustomProbeSpec(id="7", name="tcp_invalid2", probe_type="tcp", target="example.com:70000")
    assert "port must be between 1 and 65535" in str(exc.value)

@verifies("REQ-SEC-005")
def test_wifi_spec_validation():
    from pydantic import ValidationError
    from server.schemas import WifiSpec

    # Valid open
    WifiSpec(ssid="guest", security="open")

    # Valid psk
    WifiSpec(ssid="secure", security="psk", psk="supersecret123")

    # Valid eap
    WifiSpec(ssid="enterprise", security="eap-peap", username="user", password="pwd")

    # Invalid psk (missing)
    with pytest.raises(ValidationError) as exc:
        WifiSpec(ssid="secure", security="psk")
    assert "psk is required when security is psk" in str(exc.value)

    # Invalid psk (too short)
    with pytest.raises(ValidationError) as exc:
        WifiSpec(ssid="secure", security="psk", psk="short")
    assert "psk must be between 8 and 63 characters" in str(exc.value)

    # Invalid eap (missing username/pwd)
    with pytest.raises(ValidationError) as exc:
        WifiSpec(ssid="enterprise", security="eap-peap", username="user")
    assert "username and password are required when security is eap-peap" in str(exc.value)

    # Invalid security type
    with pytest.raises(ValidationError) as exc:
        WifiSpec(ssid="guest", security="wep")
    assert "security must be open, psk, or eap-peap" in str(exc.value)

@verifies("REQ-SEC-005")
def test_unified_schedule_spec_validation():
    from pydantic import ValidationError
    from server.schemas import UnifiedScheduleSpec

    # Valid
    UnifiedScheduleSpec(id="1", name="test1", probe_id="p1", mode="daily_once")
    UnifiedScheduleSpec(id="2", name="test2", probe_id="p2", mode="raw_cron", cron_expr="* * * * *")
    UnifiedScheduleSpec(id="3", name="test3", probe_id="p3", mode="raw_cron", cron_expr="*/15 8-16 * * 1-5")

    # Invalid raw_cron (missing expr)
    with pytest.raises(ValidationError) as exc:
        UnifiedScheduleSpec(id="4", name="test4", probe_id="p4", mode="raw_cron")
    assert "cron_expr is required when mode is raw_cron" in str(exc.value)

    # Invalid raw_cron (wrong fields)
    with pytest.raises(ValidationError) as exc:
        UnifiedScheduleSpec(id="5", name="test5", probe_id="p5", mode="raw_cron", cron_expr="* * * *")
    assert "cron_expr must be a standard 5-field cron syntax" in str(exc.value)

    # Invalid raw_cron (bad characters)
    with pytest.raises(ValidationError) as exc:
        UnifiedScheduleSpec(id="6", name="test6", probe_id="p6", mode="raw_cron", cron_expr="a b c d e")
    assert "invalid cron field" in str(exc.value)
