"""
Central Monitoring Platform (CMP) API Control Plane

Orchestrates configuration, telemetry check-ins, Wi-Fi profiles, and remote resets
for edge sensors.

Security & Concurrency:
  - Trust-On-First-Use Onboarding: Brand new sensors register via public POST /register.
  - Header Authentication: Reconcile endpoints use dynamic 'X-API-Key' header validation mapped to each sensor, and admin endpoints use `verify_admin_key`.
  - State Safety: Uses `copy.deepcopy` for default configurations and Pydantic `model_copy`
    for non-mutating response injection (e.g. one-shot reset delivery).
  - Redacted Views: Admin status queries return `SensorStatusResponseSafe` to prevent
    exposing sensitive Wi-Fi PSKs and EAP passwords.
"""

from fastapi import FastAPI, HTTPException, Depends, Header
from typing import Dict, List, Optional
import time
import copy
import secrets
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
    EvidenceBundleInfo
)

# API Keys — In production, load from environment variables or secrets manager
ADMIN_API_KEY = "admin-noc-key-change-me"

async def verify_admin_key(x_api_key: str = Header(..., alias="X-API-Key")):
    """Dependency that validates administrative NOC API keys."""
    if x_api_key != ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing admin API key")

app = FastAPI(
    title="Open Network Experience CMP API",
    description="Manages configuration, telemetry reconciliation, and forensic evidence for edge sensors.",
    version="0.2.0"
)

# In-Memory DB mock (stores dynamic configs, reset signals, and sensor statuses)
# In production, this would map to a SQL Database.
SENSORS_DB: Dict[str, dict] = {}

# Default fallback container configurations for new sensors (Phase 1 Baseline)
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
    """Helper to initialize sensor record if new to the platform.
    Uses deep copies of defaults to prevent global mutation."""
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
                containers=copy.deepcopy(DEFAULT_TARGET_CONTAINERS)
            )
        }
    return SENSORS_DB[sensor_id]

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

    # Update registration metadata
    sensor["hostname"] = request.hostname
    sensor["mac_address"] = request.mac_address
    sensor["os"] = request.os
    sensor["last_seen"] = int(time.time())

    if sensor["status"] == "approved":
        return SensorRegisterResponse(status="approved", api_key=sensor["api_key"])

    return SensorRegisterResponse(status="pending")

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
    Updates last-seen timestamp and running containers, and returns the target state
    using model_copy() to deliver one-shot reset flags safely.
    """
    sensor = SENSORS_DB.get(report.sensor_id)
    if not sensor or sensor["status"] != "approved" or sensor["api_key"] != x_api_key:
        raise HTTPException(status_code=401, detail="Unauthorized or unapproved sensor check-in")

    # Update check-in timestamps and system details
    sensor["last_seen"] = int(time.time())
    sensor["os"] = report.os
    sensor["reported_containers"] = {k: v.model_dump() for k, v in report.containers.items()}

    # Return a deep COPY with reset flag injected — never mutate target_config directly
    reset_value = sensor["reset_flag"]
    response = sensor["target_config"].model_copy(update={"reset": reset_value}, deep=True)

    # Reset flag is one-shot: clear it once successfully delivered
    if sensor["reset_flag"]:
        sensor["reset_flag"] = False

    # If on-demand bandwidth test was queued, clear the run_now flag for future check-ins
    if sensor["target_config"].schedules.bandwidth.run_now:
        sensor["target_config"].schedules.bandwidth.run_now = False

    # If on-demand PCAP capture was queued, clear the trigger_now flag for future check-ins
    if getattr(sensor["target_config"], "pcap_trigger", None) and sensor["target_config"].pcap_trigger.trigger_now:
        sensor["target_config"].pcap_trigger.trigger_now = False

    return response

# --- Administrative / Dashboard Management Endpoints ---

@app.get(
    "/api/v1/sensors",
    response_model=List[SensorStatusResponseSafe],
    summary="List Active Sensors",
    description="Returns registration details, online state, and configuration drift checks for all sensors. Wi-Fi credentials are redacted.",
    dependencies=[Depends(verify_admin_key)]
)
async def list_sensors():
    """
    Administrative endpoint to list all registered sensors and status details.
    Requires admin API key authentication (X-API-Key). Returns a safe, redacted list
    where sensitive Wi-Fi PSKs and passwords are removed from public display.
    """
    now = int(time.time())
    response_list = []

    for s_id, data in SENSORS_DB.items():
        # Online threshold: checked in within the last 3 intervals (e.g. 3 minutes)
        is_online = (now - data["last_seen"]) < 180

        # Check if the sensor running containers match target containers configuration
        target_keys = set(data["target_config"].containers.keys())
        reported_keys = set(data["reported_containers"].keys())
        reconciled = (target_keys == reported_keys)

        # Check if images match
        if reconciled:
            for c_name in target_keys:
                target_img = data["target_config"].containers[c_name].image
                reported_img = data["reported_containers"].get(c_name, {}).get("image", "")
                if target_img != reported_img:
                    reconciled = False
                    break

        response_list.append(
            SensorStatusResponseSafe.from_internal(
                sensor_id=s_id,
                last_seen=data["last_seen"],
                os_val=data["os"],
                is_online=is_online,
                reconciled_ok=reconciled,
                status_val=data["status"],
                reported_containers=data["reported_containers"],
                target_config=data["target_config"]
            )
        )
    return response_list

@app.put(
    "/api/v1/sensors/{sensor_id}/config",
    summary="Update Sensor Configuration Target",
    description="Updates the Wi-Fi, container, and test schedules profiles that the sensor will pull during its next loop.",
    dependencies=[Depends(verify_admin_key)]
)
async def update_sensor_config(sensor_id: str, config: SensorConfigUpdate):
    """
    Administrative endpoint to update a sensor's target profile (Wi-Fi/containers/schedules).
    Requires admin API key authentication (X-API-Key). Detects partial updates
    by examining model_fields_set.
    """
    sensor = get_or_create_sensor(sensor_id)

    if "wifi" in config.model_fields_set:
        sensor["target_config"].wifi = config.wifi
    if "containers" in config.model_fields_set:
        sensor["target_config"].containers = config.containers
    if "schedules" in config.model_fields_set and config.schedules is not None:
        sensor["target_config"].schedules = config.schedules

    return {"status": "success", "message": "Sensor target configuration updated."}

@app.post(
    "/api/v1/sensors/{sensor_id}/tests/bandwidth/trigger",
    summary="Trigger On-Demand Bandwidth Test",
    description="Instructs the sensor to execute an immediate iperf3 throughput test on its next reconcile check-in.",
    dependencies=[Depends(verify_admin_key)]
)
async def trigger_bandwidth_test(sensor_id: str):
    """
    Administrative endpoint to queue an immediate on-demand bandwidth test.
    Requires admin API key authentication (X-API-Key). Sets run_now flag to True.
    """
    sensor = get_or_create_sensor(sensor_id)
    sensor["target_config"].schedules.bandwidth.run_now = True
    return {"status": "success", "message": "On-demand bandwidth test queued for next sensor check-in."}

@app.post(
    "/api/v1/sensors/{sensor_id}/pcap/trigger",
    summary="Trigger Incident PCAP Capture",
    description="Instructs the edge sensor to slice and package an incident PCAP snapshot on its next check-in.",
    dependencies=[Depends(verify_admin_key)]
)
async def trigger_pcap_capture(sensor_id: str, reason: str = "manual_noc_trigger"):
    """
    Administrative endpoint to queue an immediate PCAP snapshot on the edge sensor.
    Requires admin API key authentication (X-API-Key). Sets trigger_now flag to True.
    """
    sensor = get_or_create_sensor(sensor_id)
    sensor["target_config"].pcap_trigger.trigger_now = True
    sensor["target_config"].pcap_trigger.reason = reason
    return {"status": "success", "message": f"PCAP snapshot trigger '{reason}' queued for next sensor check-in."}

# In-Memory Evidence DB (maps sensor_id to list of evidence bundles)
EVIDENCE_DB: Dict[str, List[dict]] = {}

@app.post(
    "/api/v1/sensors/{sensor_id}/evidence",
    summary="Register Diagnostic Evidence Bundle",
    description="Registers or records an incident evidence package (.tar.gz) from an edge sensor.",
    dependencies=[Depends(verify_admin_key)]
)
async def register_evidence_bundle(sensor_id: str, evidence: EvidenceBundleInfo):
    """
    Registers an incident evidence package manifest uploaded by or stored on an edge sensor.
    """
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
    """
    Lists diagnostic forensic bundles available for the sensor.
    """
    return EVIDENCE_DB.get(sensor_id, [])

@app.post(
    "/api/v1/sensors/{sensor_id}/reset",
    summary="Trigger Edge Rebuild",
    description="Flags the sensor to execute a clean factory wipe of local container states on its next check-in.",
    dependencies=[Depends(verify_admin_key)]
)
async def trigger_sensor_reset(sensor_id: str):
    """
    Administrative endpoint to queue a factory reset for a sensor.
    Requires admin API key authentication (X-API-Key). Sets reset_flag to True
    which is delivered on next check-in.
    """
    sensor = get_or_create_sensor(sensor_id)
    sensor["reset_flag"] = True
    return {"status": "success", "message": "Reset flag queued for next reconcile call."}

@app.post(
    "/api/v1/sensors/{sensor_id}/approve",
    summary="Approve Pending Sensor",
    description="Approves a pending edge sensor and generates its unique API key.",
    dependencies=[Depends(verify_admin_key)]
)
async def approve_sensor(sensor_id: str):
    """
    Administrative endpoint to approve a pending sensor.
    Generates a unique secret API key for the sensor and changes status to 'approved'.
    """
    sensor = get_or_create_sensor(sensor_id)
    if sensor["status"] == "approved":
        return {"status": "success", "message": "Sensor already approved.", "api_key": sensor["api_key"]}

    # Generate unique key for this sensor
    sensor["api_key"] = f"sensor-key-{secrets.token_hex(16)}"
    sensor["status"] = "approved"

    return {
        "status": "success",
        "message": "Sensor approved and key generated.",
        "api_key": sensor["api_key"]
    }

@app.post(
    "/api/v1/sensors/{sensor_id}/reject",
    summary="Reject/Revoke Sensor",
    description="Rejects a pending sensor request or revokes an approved sensor's access key.",
    dependencies=[Depends(verify_admin_key)]
)
async def reject_sensor(sensor_id: str):
    """
    Administrative endpoint to reject or revoke a sensor.
    Removes the sensor from the registry completely.
    """
    if sensor_id in SENSORS_DB:
        del SENSORS_DB[sensor_id]
        return {"status": "success", "message": "Sensor rejected/removed from registration DB."}
    raise HTTPException(status_code=404, detail="Sensor not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
