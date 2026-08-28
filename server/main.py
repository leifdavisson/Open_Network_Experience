"""
Central Monitoring Platform (CMP) API Control Plane & Sensor Administration Web UI

Orchestrates configuration, telemetry check-ins, Wi-Fi profiles, remote resets,
and WYSIWYG EasyBuilder synthetic test creation for edge sensors.

Security & Concurrency:
  - Trust-On-First-Use Onboarding: Brand new sensors register via public POST /register.
  - Header Authentication: Reconcile endpoints use dynamic 'X-API-Key' header validation mapped to each sensor, and admin endpoints use `verify_admin_key`.
  - State Safety: Uses `copy.deepcopy` for default configurations and Pydantic `model_copy`
    for non-mutating response injection (e.g. one-shot reset delivery).
  - Redacted Views: Admin status queries return `SensorStatusResponseSafe` to prevent
    exposing sensitive Wi-Fi PSKs and EAP passwords.
  - Built-in Administration Web UI: Responsive browser dashboard at / for 1-click TOFU
    approvals, forensic evidence bundle downloads, and WYSIWYG probe creation.
"""

from fastapi import FastAPI, HTTPException, Depends, Header, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Dict, List, Optional, Any
import time
import copy
import secrets
import json
import os
from schemas import (
    SensorReportRequest,
    SensorRegisterRequest,
    SensorRegisterResponse,
    SensorReconcileResponse,
    SensorConfigUpdate,
    SensorStatusResponse,
    SensorStatusResponseSafe,
    WifiSpec,
    TargetContainerSpec,
    PcapTriggerSpec,
    EvidenceBundleInfo,
    CustomProbeSpec
)

# API Keys — In production, load from environment variables or secrets manager
ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY", "admin-noc-key-change-me")

async def verify_admin_key(x_api_key: str = Header(..., alias="X-API-Key")):
    """Dependency that validates administrative NOC API keys."""
    if x_api_key != ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing admin API key")

app = FastAPI(
    title="Open Network Experience CMP API",
    description="Manages configuration, telemetry reconciliation, forensic evidence, and WYSIWYG probes for edge sensors.",
    version="0.3.0"
)

# In-Memory Databases (In production, backed by SQL Database)
SENSORS_DB: Dict[str, dict] = {}
PROBES_DB: Dict[str, dict] = {}
EVIDENCE_DB: Dict[str, List[dict]] = {}

# Default fallback container configurations for new sensors
DEFAULT_TARGET_CONTAINERS = {
    "blackbox-exporter": TargetContainerSpec(
        image="prom/blackbox-exporter:master",
        ports=["9115:9115"],
        volumes=[]
    ),
    "node-exporter": TargetContainerSpec(
        image="prom/node-exporter:v1.8.2",
        ports=["9100:9100"],
        volumes=["/:/host:ro,rslave"]
    ),
    "browser-transaction-tester": TargetContainerSpec(
        image="open-ux/playwright-runner:latest",
        ports=[],
        volumes=["/var/lib/node_exporter/textfile_collector:/metrics"],
        env={
            "TARGET_URL": "https://portal.your-district.edu",
            "TEST_TYPE": "page",
            "TEST_INTERVAL_SECONDS": "300"
        }
    )
}

DEFAULT_TARGET_WIFI = WifiSpec(
    ssid="District-Testing",
    security="open"
)

def get_or_create_sensor(sensor_id: str) -> dict:
    """Helper to initialize sensor record if new to the platform."""
    if sensor_id not in SENSORS_DB:
        SENSORS_DB[sensor_id] = {
            "sensor_id": sensor_id,
            "last_seen": 0,
            "os": "unknown",
            "hostname": "unknown",
            "mac_address": "unknown",
            "status": "pending",
            "api_key": "",
            "reset_flag": False,
            "reported_containers": {},
            "target_config": SensorReconcileResponse(
                reset=False,
                wifi=copy.deepcopy(DEFAULT_TARGET_WIFI),
                containers=copy.deepcopy(DEFAULT_TARGET_CONTAINERS),
                custom_probes=[]
            )
        }
    return SENSORS_DB[sensor_id]

# --- Edge Sensor API Endpoints ---

@app.post(
    "/api/v1/sensors/register",
    response_model=SensorRegisterResponse,
    summary="Register new Edge Sensor",
    description="Allows a new edge sensor to register its hardware details. Puts the device in a pending state until approved by an administrator."
)
async def register_sensor(request: SensorRegisterRequest):
    """
    Register endpoint for new edge sensors.
    Allows unauthenticated registration. Saves hardware profiles and queues the sensor
    for administrative approval.
    """
    sensor = get_or_create_sensor(request.sensor_id)
    sensor["hostname"] = request.hostname
    sensor["mac_address"] = request.mac_address
    sensor["os"] = request.os

    # If already approved, return active key
    if sensor["status"] == "approved":
        return SensorRegisterResponse(status="approved", api_key=sensor["api_key"])

    return SensorRegisterResponse(status="pending", api_key=None)

@app.post(
    "/api/v1/sensors/reconcile",
    response_model=SensorReconcileResponse,
    summary="Sensor Registration and State Reconciliation",
    description="Endpoint for edge sensors to check-in, report metrics, and receive configurations."
)
async def reconcile_sensor(report: SensorReportRequest, x_api_key: str = Header(..., alias="X-API-Key")):
    """
    Edge sensor check-in and reconciliation endpoint.
    Requires edge API key authentication (X-API-Key) that matches this specific sensor.
    """
    sensor = SENSORS_DB.get(report.sensor_id)
    if not sensor or sensor["status"] != "approved" or sensor["api_key"] != x_api_key:
        raise HTTPException(status_code=401, detail="Unauthorized or unapproved sensor check-in")

    sensor["last_seen"] = int(time.time())
    sensor["os"] = report.os
    sensor["reported_containers"] = {k: v.model_dump() for k, v in report.containers.items()}

    # Deliver reset flag safely via deep copy
    reset_value = sensor["reset_flag"]
    response = sensor["target_config"].model_copy(update={"reset": reset_value}, deep=True)

    if sensor["reset_flag"]:
        sensor["reset_flag"] = False

    if sensor["target_config"].schedules.bandwidth.run_now:
        sensor["target_config"].schedules.bandwidth.run_now = False

    if getattr(sensor["target_config"], "pcap_trigger", None) and sensor["target_config"].pcap_trigger.trigger_now:
        sensor["target_config"].pcap_trigger.trigger_now = False

    # Inject all active custom probes applicable to this sensor
    active_probes = [
        p for p in PROBES_DB.values()
        if p.get("enabled", True) and ("all" in p.get("target_sensors", ["all"]) or report.sensor_id in p.get("target_sensors", []))
    ]
    response.custom_probes = [CustomProbeSpec(**p) for p in active_probes]

    return response

# --- Administrative & Sensor Management Endpoints ---

@app.get(
    "/api/v1/sensors",
    response_model=List[SensorStatusResponseSafe],
    summary="List Active Sensors",
    description="Returns registration details, online state, and configuration drift checks for all sensors. Wi-Fi credentials are redacted.",
    dependencies=[Depends(verify_admin_key)]
)
async def list_sensors():
    """Administrative endpoint to list all registered sensors and status details."""
    now = int(time.time())
    response_list = []

    for s_id, data in SENSORS_DB.items():
        is_online = (now - data["last_seen"]) < 120 and data["last_seen"] > 0
        reported = data["reported_containers"]
        target = data["target_config"].containers
        reconciled_ok = is_online and (set(reported.keys()) == set(target.keys()))

        response_list.append(
            SensorStatusResponseSafe.from_internal(
                sensor_id=s_id,
                last_seen=data["last_seen"],
                os_val=data["os"],
                is_online=is_online,
                reconciled_ok=reconciled_ok,
                status_val=data["status"],
                reported_containers=data["reported_containers"],
                target_config=data["target_config"]
            )
        )
    return response_list

@app.post(
    "/api/v1/sensors/{sensor_id}/approve",
    summary="Approve Pending Sensor",
    description="Approves a pending edge sensor and generates its unique API key.",
    dependencies=[Depends(verify_admin_key)]
)
async def approve_sensor(sensor_id: str):
    """Approves a pending sensor, generates secret API key, and marks status as approved."""
    sensor = get_or_create_sensor(sensor_id)
    if sensor["status"] == "approved":
        return {"status": "success", "message": "Sensor already approved.", "api_key": sensor["api_key"]}

    sensor["api_key"] = f"sensor-key-{secrets.token_hex(16)}"
    sensor["status"] = "approved"
    return {
        "status": "success",
        "message": "Sensor approved and key generated.",
        "api_key": sensor["api_key"]
    }

@app.put(
    "/api/v1/sensors/{sensor_id}/config",
    summary="Update Sensor Configuration",
    description="Allows updating target Wi-Fi credentials, containers, test schedules, and custom probes for a specific sensor.",
    dependencies=[Depends(verify_admin_key)]
)
async def update_sensor_config(sensor_id: str, update: SensorConfigUpdate):
    """Updates target desired state for an edge sensor."""
    sensor = get_or_create_sensor(sensor_id)
    if update.wifi is not None:
        sensor["target_config"].wifi = update.wifi
    if update.containers is not None:
        sensor["target_config"].containers = update.containers
    if update.schedules is not None:
        sensor["target_config"].schedules = update.schedules
    if update.custom_probes is not None:
        sensor["target_config"].custom_probes = update.custom_probes
    return {"status": "success", "message": f"Configuration updated for sensor {sensor_id}."}

@app.post(
    "/api/v1/sensors/{sensor_id}/reset",
    summary="Trigger Edge Rebuild",
    description="Flags the sensor to execute a clean factory wipe of local container states on its next check-in.",
    dependencies=[Depends(verify_admin_key)]
)
async def trigger_sensor_reset(sensor_id: str):
    """Administrative endpoint to queue a factory reset for a sensor."""
    sensor = get_or_create_sensor(sensor_id)
    sensor["reset_flag"] = True
    return {"status": "success", "message": "Reset flag queued for next reconcile call."}

@app.post(
    "/api/v1/sensors/{sensor_id}/reject",
    summary="Reject/Revoke Sensor",
    description="Rejects a pending sensor request or revokes an approved sensor's access key.",
    dependencies=[Depends(verify_admin_key)]
)
async def reject_sensor(sensor_id: str):
    """Rejects or removes a sensor from the active registration database."""
    if sensor_id in SENSORS_DB:
        del SENSORS_DB[sensor_id]
        return {"status": "success", "message": "Sensor rejected/removed from registration DB."}
    raise HTTPException(status_code=404, detail="Sensor not found")

@app.post(
    "/api/v1/sensors/{sensor_id}/pcap/trigger",
    summary="Trigger Incident PCAP Capture",
    description="Instructs the edge sensor to slice and package an incident PCAP snapshot on its next check-in.",
    dependencies=[Depends(verify_admin_key)]
)
async def trigger_pcap_capture(sensor_id: str, reason: str = "manual_noc_trigger"):
    """Queues a remote PCAP snapshot capture on the targeted sensor."""
    sensor = get_or_create_sensor(sensor_id)
    sensor["target_config"].pcap_trigger.trigger_now = True
    sensor["target_config"].pcap_trigger.reason = reason
    return {"status": "success", "message": f"PCAP snapshot trigger '{reason}' queued for next sensor check-in."}

@app.post(
    "/api/v1/sensors/{sensor_id}/bandwidth/trigger",
    summary="Trigger On-Demand Bandwidth Test",
    description="Instructs the edge sensor to execute an immediate throughput test on its next check-in.",
    dependencies=[Depends(verify_admin_key)]
)
@app.post(
    "/api/v1/sensors/{sensor_id}/tests/bandwidth/trigger",
    summary="Trigger On-Demand Bandwidth Test (Alias)",
    dependencies=[Depends(verify_admin_key)]
)
async def trigger_bandwidth_test(sensor_id: str):
    """Queues an on-demand bandwidth test for the targeted sensor."""
    sensor = get_or_create_sensor(sensor_id)
    sensor["target_config"].schedules.bandwidth.run_now = True
    return {"status": "success", "message": "On-demand bandwidth test queued for next sensor check-in."}

@app.post(
    "/api/v1/sensors/{sensor_id}/evidence",
    summary="Register Diagnostic Evidence Bundle",
    description="Registers an incident evidence package (.tar.gz) from an edge sensor.",
    dependencies=[Depends(verify_admin_key)]
)
async def register_evidence_bundle(sensor_id: str, evidence: EvidenceBundleInfo):
    """Registers an incident evidence bundle."""
    if sensor_id not in EVIDENCE_DB:
        EVIDENCE_DB[sensor_id] = []
    EVIDENCE_DB[sensor_id].append(evidence.model_dump())
    return {"status": "success", "message": "Evidence bundle registered successfully."}

@app.get(
    "/api/v1/sensors/{sensor_id}/evidence",
    response_model=List[EvidenceBundleInfo],
    summary="List Evidence Bundles",
    description="Lists all recorded diagnostic evidence packages for a specific sensor.",
    dependencies=[Depends(verify_admin_key)]
)
async def list_evidence_bundles(sensor_id: str):
    """Lists diagnostic forensic bundles available for the sensor."""
    return EVIDENCE_DB.get(sensor_id, [])

# --- WYSIWYG EasyBuilder Custom Probes Endpoints ---

@app.get(
    "/api/v1/probes",
    response_model=List[CustomProbeSpec],
    summary="List Custom Synthetic Probes",
    dependencies=[Depends(verify_admin_key)]
)
async def list_custom_probes():
    """Lists all synthetic probes created via WYSIWYG EasyBuilder Studio."""
    return list(PROBES_DB.values())

@app.post(
    "/api/v1/probes",
    summary="Create/Update Custom Synthetic Probe",
    dependencies=[Depends(verify_admin_key)]
)
async def save_custom_probe(probe: CustomProbeSpec):
    """Creates or updates a custom synthetic probe via WYSIWYG Studio."""
    PROBES_DB[probe.id] = probe.model_dump()
    return {"status": "success", "message": f"Custom probe '{probe.name}' saved and ready for distribution."}

@app.delete(
    "/api/v1/probes/{probe_id}",
    summary="Delete Custom Synthetic Probe",
    dependencies=[Depends(verify_admin_key)]
)
async def delete_custom_probe(probe_id: str):
    """Deletes a custom synthetic probe."""
    if probe_id in PROBES_DB:
        del PROBES_DB[probe_id]
        return {"status": "success", "message": f"Probe '{probe_id}' deleted."}
    raise HTTPException(status_code=404, detail="Probe not found")

# --- Central Management Web UI Dashboard ---

@app.get("/", response_class=HTMLResponse, summary="Sensor Administration Dashboard")
@app.get("/ui", response_class=HTMLResponse, summary="Sensor Administration Dashboard")
async def serve_admin_ui():
    """Serves modern, responsive single-pane-of-glass administration dashboard."""
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Open Network Experience (ONE) — Sensor Administration</title>
    <style>
        :root {
            --bg-main: #0f172a;
            --bg-card: #1e293b;
            --bg-hover: #334155;
            --accent: #38bdf8;
            --accent-hover: #0284c7;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --border: #334155;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        body { background: var(--bg-main); color: var(--text-main); padding: 24px; }
        .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); padding-bottom: 20px; margin-bottom: 24px; }
        .header h1 { font-size: 22px; font-weight: 700; color: var(--text-main); display: flex; align-items: center; gap: 10px; }
        .badge { background: #0284c7; color: white; padding: 3px 8px; border-radius: 6px; font-size: 12px; }
        .nav-links a { color: var(--accent); text-decoration: none; font-weight: 500; font-size: 14px; margin-left: 20px; }
        .nav-links a:hover { text-decoration: underline; }

        .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 24px; }
        .metric-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 10px; padding: 18px; }
        .metric-title { font-size: 13px; color: var(--text-muted); text-transform: uppercase; font-weight: 600; margin-bottom: 6px; }
        .metric-value { font-size: 28px; font-weight: 700; color: var(--text-main); }

        .section { background: var(--bg-card); border: 1px solid var(--border); border-radius: 10px; padding: 20px; margin-bottom: 24px; }
        .section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
        .section-title { font-size: 16px; font-weight: 700; }

        table { width: 100%; border-collapse: collapse; font-size: 14px; }
        th { text-align: left; padding: 12px; color: var(--text-muted); border-bottom: 1px solid var(--border); font-weight: 600; }
        td { padding: 12px; border-bottom: 1px solid var(--border); }
        tr:hover { background: rgba(51, 65, 85, 0.4); }

        .status-pill { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 9999px; font-size: 12px; font-weight: 600; }
        .status-online { background: rgba(16, 185, 129, 0.15); color: #34d399; }
        .status-pending { background: rgba(245, 158, 11, 0.15); color: #fbbf24; }
        .status-offline { background: rgba(239, 68, 68, 0.15); color: #f87171; }

        .btn { background: var(--accent); color: #0f172a; border: none; border-radius: 6px; padding: 8px 14px; font-weight: 600; font-size: 13px; cursor: pointer; transition: background 0.15s; }
        .btn:hover { background: var(--accent-hover); }
        .btn-danger { background: var(--danger); color: white; }
        .btn-success { background: var(--success); color: white; }
        .btn-outline { background: transparent; border: 1px solid var(--border); color: var(--text-main); }
        .btn-outline:hover { background: var(--bg-hover); }
        .btn-sm { padding: 4px 8px; font-size: 12px; margin-right: 4px; }

        .form-group { margin-bottom: 14px; }
        .form-group label { display: block; font-size: 13px; font-weight: 600; color: var(--text-muted); margin-bottom: 6px; }
        .form-group input, .form-group select { width: 100%; padding: 10px; background: #0f172a; border: 1px solid var(--border); border-radius: 6px; color: white; font-size: 14px; }
        .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }

        .modal-overlay { display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.7); z-index: 100; justify-content: center; align-items: center; }
        .modal { background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; width: 550px; max-width: 90%; padding: 24px; }
    </style>
</head>
<body>

    <div class="header">
        <h1>🌐 Open Network Experience (ONE) <span class="badge">CMP v0.3.0</span></h1>
        <div class="nav-links">
            <a href="http://localhost:3000" target="_blank">📊 Grafana NOC Dashboards ↗</a>
            <a href="/docs" target="_blank">📖 Swagger API Docs ↗</a>
        </div>
    </div>

    <!-- Quick Stat Cards -->
    <div class="metrics-grid">
        <div class="metric-card">
            <div class="metric-title">Total Registered Sensors</div>
            <div class="metric-value" id="stat-total">-</div>
        </div>
        <div class="metric-card">
            <div class="metric-title">Online & Active (2m)</div>
            <div class="metric-value" style="color: #34d399;" id="stat-online">-</div>
        </div>
        <div class="metric-card">
            <div class="metric-title">Pending TOFU Approvals</div>
            <div class="metric-value" style="color: #fbbf24;" id="stat-pending">-</div>
        </div>
        <div class="metric-card">
            <div class="metric-title">Custom Synthetic Probes</div>
            <div class="metric-value" style="color: var(--accent);" id="stat-probes">-</div>
        </div>
    </div>

    <!-- Pending Approval Queue -->
    <div class="section" id="pending-section" style="display: none; border-left: 4px solid var(--warning);">
        <div class="section-header">
            <div class="section-title">⚠️ Pending Approval Queue (Trust-On-First-Use)</div>
        </div>
        <table>
            <thead>
                <tr>
                    <th>Sensor ID</th>
                    <th>Hostname</th>
                    <th>MAC Address</th>
                    <th>OS</th>
                    <th>Action</th>
                </tr>
            </thead>
            <tbody id="pending-table-body"></tbody>
        </table>
    </div>

    <!-- Active Sensor Fleet Table -->
    <div class="section">
        <div class="section-header">
            <div class="section-title">📡 Active Edge Sensors Fleet</div>
            <button class="btn btn-outline" onclick="loadDashboardData()">🔄 Refresh</button>
        </div>
        <table>
            <thead>
                <tr>
                    <th>Sensor ID</th>
                    <th>Status</th>
                    <th>Target SSID</th>
                    <th>Last Seen</th>
                    <th>Quick Actions</th>
                </tr>
            </thead>
            <tbody id="sensors-table-body">
                <tr><td colspan="5" style="text-align:center; color:var(--text-muted);">Loading fleet status...</td></tr>
            </tbody>
        </table>
    </div>

    <!-- WYSIWYG EasyBuilder Studio Section -->
    <div class="section">
        <div class="section-header">
            <div class="section-title">🛠️ WYSIWYG EasyBuilder — Custom Synthetic Probes</div>
            <button class="btn" onclick="openProbeModal()">+ Create Custom Test</button>
        </div>
        <table>
            <thead>
                <tr>
                    <th>Probe Name</th>
                    <th>Type</th>
                    <th>Target URL / Host</th>
                    <th>Cadence</th>
                    <th>Scope</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody id="probes-table-body">
                <tr><td colspan="6" style="text-align:center; color:var(--text-muted);">No custom synthetic probes configured yet.</td></tr>
            </tbody>
        </table>
    </div>

    <!-- WYSIWYG EasyBuilder Modal -->
    <div class="modal-overlay" id="probe-modal">
        <div class="modal">
            <h2 style="font-size: 18px; margin-bottom: 16px;">Create Custom Synthetic Probe</h2>
            <form id="probe-form" onsubmit="handleSaveProbe(event)">
                <div class="form-group">
                    <label>Test Name</label>
                    <input type="text" id="p-name" placeholder="e.g. Canvas LMS Portal" required>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>Probe Type</label>
                        <select id="p-type">
                            <option value="http">Web Application (HTTP/S)</option>
                            <option value="api">API Endpoint (JSON)</option>
                            <option value="dns">DNS Resolution</option>
                            <option value="tcp">TCP Port Check</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Cadence (Interval)</label>
                        <select id="p-cadence">
                            <option value="1">Every 1 Minute</option>
                            <option value="5" selected>Every 5 Minutes</option>
                            <option value="15">Every 15 Minutes</option>
                            <option value="60">Hourly</option>
                        </select>
                    </div>
                </div>
                <div class="form-group">
                    <label>Target URL or Hostname</label>
                    <input type="text" id="p-target" placeholder="https://district.instructure.com" required>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>Max Allowed Latency (ms)</label>
                        <input type="number" id="p-timeout" value="5000">
                    </div>
                    <div class="form-group">
                        <label>Target Scope</label>
                        <select id="p-scope">
                            <option value="all">All Fleet Sensors</option>
                        </select>
                    </div>
                </div>
                <div style="display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px;">
                    <button type="button" class="btn btn-outline" onclick="closeProbeModal()">Cancel</button>
                    <button type="submit" class="btn">Deploy to Fleet</button>
                </div>
            </form>
        </div>
    </div>

    <script>
        const ADMIN_KEY = "admin-noc-key-change-me";

        async function loadDashboardData() {
            try {
                // 1. Fetch Sensors
                const resSensors = await fetch('/api/v1/sensors', { headers: { 'X-API-Key': ADMIN_KEY } });
                const sensors = await resSensors.json();

                // 2. Fetch Probes
                const resProbes = await fetch('/api/v1/probes', { headers: { 'X-API-Key': ADMIN_KEY } });
                const probes = await resProbes.json();

                renderDashboard(sensors, probes);
            } catch (err) {
                console.error("Failed to load dashboard:", err);
            }
        }

        function renderDashboard(sensors, probes) {
            let onlineCount = 0;
            let pendingCount = 0;
            const activeRows = [];
            const pendingRows = [];

            sensors.forEach(s => {
                if (s.status === 'pending') {
                    pendingCount++;
                    pendingRows.push(`
                        <tr>
                            <td><strong>${s.sensor_id}</strong></td>
                            <td>${s.hostname || 'Unknown'}</td>
                            <td>${s.mac_address || 'Unknown'}</td>
                            <td>${s.os || 'Linux'}</td>
                            <td>
                                <button class="btn btn-success btn-sm" onclick="approveSensor('${s.sensor_id}')">✓ Approve</button>
                                <button class="btn btn-danger btn-sm" onclick="rejectSensor('${s.sensor_id}')">✗ Reject</button>
                            </td>
                        </tr>
                    `);
                } else {
                    if (s.is_online) onlineCount++;
                    const statusBadge = s.is_online ?
                        '<span class="status-pill status-online">● Online</span>' :
                        '<span class="status-pill status-offline">○ Offline</span>';

                    activeRows.push(`
                        <tr>
                            <td><strong>${s.sensor_id}</strong></td>
                            <td>${statusBadge}</td>
                            <td>${s.target_config.wifi ? s.target_config.wifi.ssid : 'None'}</td>
                            <td>${s.last_seen > 0 ? new Date(s.last_seen * 1000).toLocaleTimeString() : 'Never'}</td>
                            <td>
                                <button class="btn btn-outline btn-sm" onclick="triggerPcap('${s.sensor_id}')">⚡ PCAP</button>
                                <button class="btn btn-outline btn-sm" onclick="triggerSpeedtest('${s.sensor_id}')">📊 Speedtest</button>
                                <button class="btn btn-danger btn-sm" onclick="rejectSensor('${s.sensor_id}')">Revoke</button>
                            </td>
                        </tr>
                    `);
                }
            });

            document.getElementById('stat-total').innerText = sensors.length;
            document.getElementById('stat-online').innerText = onlineCount;
            document.getElementById('stat-pending').innerText = pendingCount;
            document.getElementById('stat-probes').innerText = probes.length;

            // Pending table visibility
            if (pendingCount > 0) {
                document.getElementById('pending-section').style.display = 'block';
                document.getElementById('pending-table-body').innerHTML = pendingRows.join('');
            } else {
                document.getElementById('pending-section').style.display = 'none';
            }

            // Active sensors table
            document.getElementById('sensors-table-body').innerHTML = activeRows.length > 0 ?
                activeRows.join('') : '<tr><td colspan="5" style="text-align:center;">No active approved sensors found.</td></tr>';

            // Custom Probes Table
            const probeRows = probes.map(p => `
                <tr>
                    <td><strong>${p.name}</strong></td>
                    <td><span class="badge" style="background:#475569;">${p.probe_type.toUpperCase()}</span></td>
                    <td><code>${p.target}</code></td>
                    <td>Every ${p.cadence_minutes}m</td>
                    <td>${p.target_sensors.join(', ')}</td>
                    <td><button class="btn btn-danger btn-sm" onclick="deleteProbe('${p.id}')">Delete</button></td>
                </tr>
            `);
            document.getElementById('probes-table-body').innerHTML = probeRows.length > 0 ?
                probeRows.join('') : '<tr><td colspan="6" style="text-align:center; color:var(--text-muted);">No custom synthetic probes configured yet.</td></tr>';
        }

        async function approveSensor(sensorId) {
            await fetch(`/api/v1/sensors/${sensorId}/approve`, { method: 'POST', headers: { 'X-API-Key': ADMIN_KEY } });
            loadDashboardData();
        }

        async function rejectSensor(sensorId) {
            if (confirm(`Are you sure you want to revoke/reject sensor ${sensorId}?`)) {
                await fetch(`/api/v1/sensors/${sensorId}/reject`, { method: 'POST', headers: { 'X-API-Key': ADMIN_KEY } });
                loadDashboardData();
            }
        }

        async function triggerPcap(sensorId) {
            await fetch(`/api/v1/sensors/${sensorId}/pcap/trigger?reason=manual_web_ui`, { method: 'POST', headers: { 'X-API-Key': ADMIN_KEY } });
            alert(`Incident PCAP capture queued for ${sensorId}.`);
        }

        async function triggerSpeedtest(sensorId) {
            await fetch(`/api/v1/sensors/${sensorId}/bandwidth/trigger`, { method: 'POST', headers: { 'X-API-Key': ADMIN_KEY } });
            alert(`On-demand speedtest queued for ${sensorId}.`);
        }

        function openProbeModal() { document.getElementById('probe-modal').style.display = 'flex'; }
        function closeProbeModal() { document.getElementById('probe-modal').style.display = 'none'; }

        async function handleSaveProbe(e) {
            e.preventDefault();
            const name = document.getElementById('p-name').value;
            const id = name.toLowerCase().replace(/[^a-z0-9]/g, '-');
            const probe = {
                id: id,
                name: name,
                probe_type: document.getElementById('p-type').value,
                target: document.getElementById('p-target').value,
                cadence_minutes: parseInt(document.getElementById('p-cadence').value),
                timeout_seconds: parseFloat(document.getElementById('p-timeout').value) / 1000.0,
                target_sensors: ["all"],
                enabled: true
            };

            await fetch('/api/v1/probes', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-API-Key': ADMIN_KEY },
                body: JSON.stringify(probe)
            });
            closeProbeModal();
            loadDashboardData();
        }

        async function deleteProbe(probeId) {
            if (confirm(`Delete probe ${probeId}?`)) {
                await fetch(`/api/v1/probes/${probeId}`, { method: 'DELETE', headers: { 'X-API-Key': ADMIN_KEY } });
                loadDashboardData();
            }
        }

        // Initial Load
        loadDashboardData();
        setInterval(loadDashboardData, 10000); // Auto-refresh every 10s
    </script>
</body>
</html>
"""
    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
