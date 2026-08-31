"""
Open Network Experience (ONE) - Authentication & Session Router
Copyright (C) 2026 Open Network Experience Authors.
Licensed under the GNU Affero General Public License v3.0 (AGPLv3).
"""

from fastapi import APIRouter, HTTPException, Response, Depends, Request
from pydantic import BaseModel
from typing import Optional
from server.security import (
    ADMIN_API_KEY,
    verify_api_key_constant_time,
    create_session_token,
    verify_admin_key
)

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

class LoginRequest(BaseModel):
    api_key: str
    username: Optional[str] = "admin"

class LoginResponse(BaseModel):
    status: str
    session_token: str
    expires_in_seconds: int

@router.post("/login", response_model=LoginResponse, summary="Authenticate to CMP Dashboard")
async def login(req: LoginRequest, response: Response):
    """Authenticates using Admin API Key and issues a secure session cookie."""
    if not verify_api_key_constant_time(req.api_key, ADMIN_API_KEY):
        raise HTTPException(status_code=401, detail="Invalid administrator API key")

    token = create_session_token(username=req.username or "admin", expires_in_seconds=86400)
    response.set_cookie(
        key="one_session",
        value=token,
        max_age=86400,
        httponly=True,
        samesite="lax"
    )
    return LoginResponse(
        status="authenticated",
        session_token=token,
        expires_in_seconds=86400
    )

@router.post("/logout", summary="Logout and Clear Session Cookie")
async def logout(response: Response):
    """Clears the session cookie."""
    response.delete_cookie(key="one_session")
    return {"status": "logged_out"}
