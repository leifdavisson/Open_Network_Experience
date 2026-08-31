"""
Open Network Experience (ONE) - Security & Authentication Engine
Copyright (C) 2026 Open Network Experience Authors.
Licensed under the GNU Affero General Public License v3.0 (AGPLv3).

Provides:
  - Constant-time administrative API key verification
  - Fail-fast enforcement against insecure default credentials in production
  - HMAC signed session token generation and verification for Dashboard UI
"""

import os
import sys
import secrets
import hmac
import hashlib
import time
from typing import Optional
from fastapi import Header, HTTPException, Request, Depends

ENV = os.environ.get("ENV", os.environ.get("ENVIRONMENT", "development")).lower()
_RAW_ADMIN_KEY = os.environ.get("ADMIN_API_KEY")

DEFAULT_INSECURE_KEY = "admin-noc-key-change-me"

if not _RAW_ADMIN_KEY or _RAW_ADMIN_KEY == DEFAULT_INSECURE_KEY:
    if ENV == "production":
        print(
            "FATAL SECURITY ERROR: ADMIN_API_KEY environment variable is unset or using insecure default in production mode!\n"
            "Open Network Experience refuses to boot in production with default credentials.\n"
            "Please set a strong ADMIN_API_KEY before starting.",
            file=sys.stderr
        )
        sys.exit(1)
    else:
        # Development mode: Generate ephemeral random key or fallback with warning
        if not _RAW_ADMIN_KEY:
            _RAW_ADMIN_KEY = DEFAULT_INSECURE_KEY
            print(f"[SECURITY WARNING] Using default dev key '{DEFAULT_INSECURE_KEY}'. Set ADMIN_API_KEY for production.")
        else:
            print(f"[SECURITY WARNING] Using insecure default ADMIN_API_KEY '{DEFAULT_INSECURE_KEY}' in development mode.")

ADMIN_API_KEY: str = _RAW_ADMIN_KEY
SESSION_SECRET: str = os.environ.get("SESSION_SECRET", secrets.token_hex(32))

def verify_api_key_constant_time(provided_key: str, expected_key: str) -> bool:
    """Performs constant-time comparison to prevent timing attacks."""
    if not provided_key or not expected_key:
        return False
    return secrets.compare_digest(provided_key.strip(), expected_key.strip())

async def verify_admin_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")) -> str:
    """FastAPI dependency that validates administrative NOC API keys in constant time."""
    if not x_api_key or not verify_api_key_constant_time(x_api_key, ADMIN_API_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing admin API key")
    return x_api_key

def create_session_token(username: str = "admin", expires_in_seconds: int = 86400) -> str:
    """Generates an HMAC-SHA256 signed session cookie token."""
    expiry = int(time.time()) + expires_in_seconds
    payload = f"{username}:{expiry}"
    sig = hmac.new(SESSION_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"

def verify_session_token(token: Optional[str]) -> bool:
    """Verifies HMAC signature and expiration of session token."""
    if not token or ":" not in token:
        return False
    try:
        parts = token.split(":")
        if len(parts) != 3:
            return False
        username, expiry_str, sig = parts
        expiry = int(expiry_str)
        if time.time() > expiry:
            return False
        expected_payload = f"{username}:{expiry}"
        expected_sig = hmac.new(SESSION_SECRET.encode(), expected_payload.encode(), hashlib.sha256).hexdigest()
        return secrets.compare_digest(sig, expected_sig)
    except Exception:
        return False

async def verify_dashboard_auth(request: Request) -> bool:
    """
    Validates either session cookie 'one_session', query param 'api_key', or 'X-API-Key' header.
    Allows easy developer access while securing production UI.
    """
    # Check X-API-Key header
    api_key_hdr = request.headers.get("X-API-Key")
    if api_key_hdr and verify_api_key_constant_time(api_key_hdr, ADMIN_API_KEY):
        return True

    # Check query param api_key
    api_key_query = request.query_params.get("api_key")
    if api_key_query and verify_api_key_constant_time(api_key_query, ADMIN_API_KEY):
        return True

    # Check cookie
    session_cookie = request.cookies.get("one_session")
    if session_cookie and verify_session_token(session_cookie):
        return True

    # In dev mode with default insecure key, allow bypass for convenience if no header
    if ENV != "production" and ADMIN_API_KEY == DEFAULT_INSECURE_KEY:
        return True

    return False
