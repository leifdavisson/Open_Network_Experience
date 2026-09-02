"""
Open Network Experience (ONE) - Central Monitoring Platform (CMP)
Copyright (C) 2026 Open Network Experience Authors.
Licensed under the GNU Affero General Public License v3.0 (AGPLv3).
"""

import os
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from server.schemas import (
    LocationSpec,
    SensorReconcileResponse
)
from server.state import (
    SENSORS_DB,
    PROBES_DB,
    SCHEDULES_DB,
    EVIDENCE_DB
)
import server.db as db

# Initialize SQLite tables on module import to ensure test harness readiness
db.init_db()

# Import Modular Routers
from server.routers import (
    auth,
    onboarding,
    sensors,
    campuses,
    probes,
    schedules,
    telemetry,
    alerts,
    ui
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager that initializes SQLite tables and loads persisted state on boot."""
    db.init_db()

    loaded_sensors = db.load_all_sensors()
    for s_id, s_data in loaded_sensors.items():
        if s_data.get("location"):
            loc_dict = s_data["location"]
            if isinstance(loc_dict, dict):
                if loc_dict.get("latitude") is None:
                    loc_dict["latitude"] = 35.37452
                    loc_dict["longitude"] = -119.01874
                if not loc_dict.get("site"):
                    loc_dict["site"] = "City Center"
                if not loc_dict.get("building"):
                    loc_dict["building"] = "1300 17th St"
                if not loc_dict.get("room"):
                    loc_dict["room"] = "IT Operations"
                s_data["location"] = LocationSpec(**loc_dict)
        if s_data.get("target_config"):
            s_data["target_config"] = SensorReconcileResponse(**s_data["target_config"])
        SENSORS_DB[s_id] = s_data

    loaded_probes = db.load_all_probes()
    PROBES_DB.update(loaded_probes)

    loaded_schedules = db.load_all_schedules()
    for sch in loaded_schedules:
        SCHEDULES_DB[sch["id"]] = sch

    # Seed initial default schedules if database is fresh
    if not SCHEDULES_DB:
        default_schedules = [
            {
                "id": "sched_caaspp_morning",
                "name": "Morning State Testing (CAASPP) Pre-Flight",
                "probe_id": "caaspp_readiness",
                "mode": "daily_once",
                "days_of_week": ["mon", "tue", "wed", "thu", "fri"],
                "start_time": "07:15",
                "end_time": "16:00",
                "interval_value": 15,
                "interval_unit": "minutes",
                "cron_expr": "15 7 * * 1-5",
                "target_scope": "all",
                "guardrails_enabled": True,
                "is_active": True,
                "created_at": int(time.time())
            },
            {
                "id": "sched_classroom_voip",
                "name": "Classroom VoIP & Zoom Stream Monitor",
                "probe_id": "voip_jitter",
                "mode": "window_repeat",
                "days_of_week": ["mon", "tue", "wed", "thu", "fri"],
                "start_time": "08:00",
                "end_time": "16:00",
                "interval_value": 1,
                "interval_unit": "minutes",
                "cron_expr": "*/1 8-16 * * 1-5",
                "target_scope": "all",
                "guardrails_enabled": True,
                "is_active": True,
                "created_at": int(time.time())
            },
            {
                "id": "sched_continuous_gw_ping",
                "name": "Continuous Dual-NIC Gateway Latency Ping",
                "probe_id": "dual_nic_ping",
                "mode": "continuous_interval",
                "days_of_week": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
                "start_time": "00:00",
                "end_time": "23:59",
                "interval_value": 15,
                "interval_unit": "seconds",
                "cron_expr": None,
                "target_scope": "all",
                "guardrails_enabled": True,
                "is_active": True,
                "created_at": int(time.time())
            },
            {
                "id": "sched_weekend_speedtest",
                "name": "Off-Peak iperf3 Bandwidth Capacity Test",
                "probe_id": "iperf3",
                "mode": "daily_once",
                "days_of_week": ["sat"],
                "start_time": "02:00",
                "end_time": "04:00",
                "interval_value": 60,
                "interval_unit": "minutes",
                "cron_expr": "0 2 * * 6",
                "target_scope": "all",
                "guardrails_enabled": True,
                "is_active": True,
                "created_at": int(time.time())
            },
            {
                "id": "sched_cipa_audit",
                "name": "CIPA Safety & Content Filter Audit",
                "probe_id": "cipa_compliance",
                "mode": "continuous_interval",
                "days_of_week": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
                "start_time": "00:00",
                "end_time": "23:59",
                "interval_value": 4,
                "interval_unit": "hours",
                "cron_expr": None,
                "target_scope": "all",
                "guardrails_enabled": True,
                "is_active": True,
                "created_at": int(time.time())
            },
            {
                "id": "sched_m365_health",
                "name": "Microsoft 365 & Teams Media Health Sweep",
                "probe_id": "m365_connectivity",
                "mode": "continuous_interval",
                "days_of_week": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
                "start_time": "00:00",
                "end_time": "23:59",
                "interval_value": 15,
                "interval_unit": "minutes",
                "cron_expr": None,
                "target_scope": "all",
                "guardrails_enabled": True,
                "is_active": True,
                "created_at": int(time.time())
            },
            {
                "id": "sched_windows_update_do",
                "name": "Windows Update & Delivery Optimization Peer Audit",
                "probe_id": "windows_update_do",
                "mode": "continuous_interval",
                "days_of_week": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
                "start_time": "00:00",
                "end_time": "23:59",
                "interval_value": 4,
                "interval_unit": "hours",
                "cron_expr": None,
                "target_scope": "all",
                "guardrails_enabled": True,
                "is_active": True,
                "created_at": int(time.time())
            },
            {
                "id": "sched_google_workspace",
                "name": "Google Workspace & ChromeOS Health Sweep",
                "probe_id": "google_workspace",
                "mode": "continuous_interval",
                "days_of_week": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
                "start_time": "00:00",
                "end_time": "23:59",
                "interval_value": 15,
                "interval_unit": "minutes",
                "cron_expr": None,
                "target_scope": "all",
                "guardrails_enabled": True,
                "is_active": True,
                "created_at": int(time.time())
            },
            {
                "id": "sched_clever_identity",
                "name": "Clever K-12 Identity, Badges & SSO Health Sweep",
                "probe_id": "clever_identity",
                "mode": "continuous_interval",
                "days_of_week": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
                "start_time": "00:00",
                "end_time": "23:59",
                "interval_value": 15,
                "interval_unit": "minutes",
                "cron_expr": None,
                "target_scope": "all",
                "guardrails_enabled": True,
                "is_active": True,
                "created_at": int(time.time())
            },
            {
                "id": "sched_lightspeed_filter",
                "name": "Lightspeed Systems Filter & Classroom Sweep",
                "probe_id": "lightspeed_filter",
                "mode": "continuous_interval",
                "days_of_week": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
                "start_time": "00:00",
                "end_time": "23:59",
                "interval_value": 15,
                "interval_unit": "minutes",
                "cron_expr": None,
                "target_scope": "all",
                "guardrails_enabled": True,
                "is_active": True,
                "created_at": int(time.time())
            }
        ]
        for ds in default_schedules:
            ds_key: str = str(ds["id"])
            SCHEDULES_DB[ds_key] = ds
            db.save_schedule(ds)

    loaded_evidence = db.load_all_evidence()
    EVIDENCE_DB.update(loaded_evidence)

    db.export_backup_json()
    yield

app = FastAPI(
    title="Open Network Experience (ONE) — Central Monitoring Platform API",
    description="Zero-Trust High-Assurance Control Plane for Edge Sensors & Chromebook Fleet",
    version="0.6.0",
    lifespan=lifespan
)

# CORS Configuration (REQ-SEC-004): Wildcard origins must not be combined with credentials
_cors_origins_env = os.environ.get("CORS_ORIGINS", "")
_env_mode = os.environ.get("ENV", os.environ.get("ENVIRONMENT", "development")).lower()

if _cors_origins_env:
    _cors_origins = [o.strip() for o in _cors_origins_env.split(",") if o.strip()]
    _cors_credentials = True
elif _env_mode == "production":
    # Production without explicit CORS_ORIGINS: restrict to same-origin only
    _cors_origins = []
    _cors_credentials = False
else:
    # Development: allow all origins but disable credentials (CORS spec compliance)
    _cors_origins = ["*"]
    _cors_credentials = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_credentials,
    allow_methods=["*"],
    allow_headers=["*"]
)

static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "static"))
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/favicon.ico", include_in_schema=False)
async def favicon_endpoint() -> Response:
    fav_path = os.path.join(static_dir, "favicon.svg")
    if os.path.exists(fav_path):
        return FileResponse(fav_path, media_type="image/svg+xml")
    return Response(status_code=204)

app.include_router(auth.router)
app.include_router(onboarding.router)
app.include_router(sensors.router)
app.include_router(campuses.router)
app.include_router(probes.router)
app.include_router(schedules.router)
app.include_router(telemetry.router)
app.include_router(alerts.router)
app.include_router(ui.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server.main:app", host="0.0.0.0", port=8000, reload=True)
