"""
Open Network Experience (ONE) - Dashboard & Wallboard UI Router
Copyright (C) 2026 Open Network Experience Authors.
Licensed under the GNU Affero General Public License v3.0 (AGPLv3).
"""

import os
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["User Interface"])

template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "templates"))
templates = Jinja2Templates(directory=template_dir)

@router.get("/", response_class=HTMLResponse, summary="Sensor Administration Dashboard")
@router.get("/ui", response_class=HTMLResponse, summary="Sensor Administration Dashboard")
async def serve_admin_ui(request: Request) -> HTMLResponse:
    """Serves modern, responsive single-pane-of-glass administration dashboard via Jinja2."""
    response = templates.TemplateResponse(request=request, name="dashboard.html", context={})
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response
