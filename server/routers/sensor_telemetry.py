"""
Open Network Experience (ONE) - Edge Sensor & Chromebook Fleet Router
Copyright (C) 2026 Open Network Experience Authors.
Licensed under the GNU Affero General Public License v3.0 (AGPLv3).
"""

import json
import os
import secrets
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from server.common.errors import NotFoundException, UnauthorizedException
from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from server import db
from server.schemas import (
    ChromebookFleetItemResponse,
    ChromebookLockUpdateRequest,
    CustomProbeSpec,
    LocationSpec,
    RoamingEventResponse,
    SensorIngestResponse,
    SensorReconcileResponse,
    SensorRegisterRequest,
    SensorRegisterResponse,
    SensorReportRequest,
    UnifiedScheduleSpec,
)
from server.common.auth import ADMIN_API_KEY, verify_admin_key
from server.state import (
    CHROMEBOOK_GLOBAL_SETTINGS,
    PROBES_DB,
    ROAMING_EVENTS_DB,
    SCHEDULES_DB,
    SENSORS_DB,
    get_or_create_sensor,
)

router = APIRouter(tags=["Edge Sensors & Fleet"])

VM_URL = os.environ.get("VICTORIAMETRICS_URL", "http://victoriametrics:8428")

def forward_chromebook_metrics_to_tsdb(report: dict):
    """Converts Chromebook telemetry report to Prometheus exposition format and forwards to VictoriaMetrics TSDB with persistent SQLite disk spooling."""
    sensor_id = report.get("sensor_id", "unknown")
    campus_id = report.get("campus_id", "CAMPUS-CHROMEBOOK-FLEET")
    ts = report.get("timestamp", int(time.time())) * 1000

    lines = []
    wifi = report.get("wifi", {})
    if wifi and isinstance(wifi, dict):
        ssid = wifi.get("ssid") or "unknown"
        bssid = wifi.get("bssid") or "unknown"
        band = wifi.get("band") or "unknown"
        channel = str(wifi.get("channel") or 0)

        lines.append(f'chromebook_wifi_connected{{sensor_id="{sensor_id}",campus_id="{campus_id}",ssid="{ssid}",bssid="{bssid}"}} {1 if wifi.get("connected") else 0} {ts}')
        if wifi.get("rssi_dbm") is not None:
            lines.append(f'chromebook_wifi_rssi_dbm{{sensor_id="{sensor_id}",campus_id="{campus_id}",ssid="{ssid}",bssid="{bssid}",band="{band}",channel="{channel}"}} {wifi.get("rssi_dbm")} {ts}')
        if wifi.get("signal_strength_pct") is not None:
            lines.append(f'chromebook_wifi_signal_pct{{sensor_id="{sensor_id}",campus_id="{campus_id}",ssid="{ssid}"}} {wifi.get("signal_strength_pct")} {ts}')
        if wifi.get("roamed_recently"):
            lines.append(f'chromebook_wifi_roam_events_total{{sensor_id="{sensor_id}",campus_id="{campus_id}",ssid="{ssid}",bssid="{bssid}"}} 1 {ts}')

    probes = report.get("probes", {})
    if probes and isinstance(probes, dict):
        webrtc = probes.get("webrtc")
        if webrtc and isinstance(webrtc, dict) and webrtc.get("success"):
            if webrtc.get("mos") is not None:
                lines.append(f'chromebook_webrtc_mos{{sensor_id="{sensor_id}",campus_id="{campus_id}"}} {webrtc.get("mos")} {ts}')
            if webrtc.get("rtt_ms") is not None:
                lines.append(f'chromebook_webrtc_rtt_ms{{sensor_id="{sensor_id}",campus_id="{campus_id}"}} {webrtc.get("rtt_ms")} {ts}')
            if webrtc.get("jitter_ms") is not None:
                lines.append(f'chromebook_webrtc_jitter_ms{{sensor_id="{sensor_id}",campus_id="{campus_id}"}} {webrtc.get("jitter_ms")} {ts}')
            if webrtc.get("packet_loss_percent") is not None:
                lines.append(f'chromebook_webrtc_packet_loss_pct{{sensor_id="{sensor_id}",campus_id="{campus_id}"}} {webrtc.get("packet_loss_percent")} {ts}')

        apps = probes.get("synthetic_http", [])
        if isinstance(apps, list):
            for app in apps:
                if isinstance(app, dict):
                    app_name = app.get("name", "Unknown App")
                    category = app.get("category", "General")
                    is_ok = 1 if app.get("success") else 0
                    lines.append(f'chromebook_app_success{{sensor_id="{sensor_id}",campus_id="{campus_id}",app="{app_name}",category="{category}"}} {is_ok} {ts}')
                    if app.get("latency_ms") is not None:
                        lines.append(f'chromebook_app_latency_ms{{sensor_id="{sensor_id}",campus_id="{campus_id}",app="{app_name}",category="{category}"}} {app.get("latency_ms")} {ts}')
                    if app.get("ttfb_ms"):
                        lines.append(f'chromebook_app_ttfb_ms{{sensor_id="{sensor_id}",campus_id="{campus_id}",app="{app_name}"}} {app.get("ttfb_ms")} {ts}')

    # Fetch queued items from SQLite disk spool queue
    spooled_entries = []
    try:
        spooled_entries = db.dequeue_tsdb_spool(batch_size=20)
    except Exception:
        pass

    spooled_payloads = [e["payload"] for e in spooled_entries if e.get("payload")]
    send_lines = list(spooled_payloads)
    if lines:
        send_lines.append("\n".join(lines))

    if not send_lines:
        return

    payload = "\n".join(send_lines) + "\n"
    urls = [f"{VM_URL}/api/v1/import/prometheus", "http://localhost:8428/api/v1/import/prometheus", "http://127.0.0.1:8428/api/v1/import/prometheus"]
    delivered = False
    for url in urls:
        try:
            req = urllib.request.Request(
                url,
                data=payload.encode("utf-8"),
                headers={"Content-Type": "text/plain"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status in (200, 204):
                    delivered = True
                    if spooled_entries:
                        try:
                            db.delete_tsdb_spool_entries([e["id"] for e in spooled_entries])
                        except Exception:
                            pass
                    break
        except Exception:
            continue

    if not delivered:
        # Enqueue unsent payload into persistent SQLite disk spool queue
        if lines:
            try:
                db.enqueue_tsdb_spool("\n".join(lines))
            except Exception:
                pass
        if spooled_entries:
            try:
                db.increment_tsdb_spool_attempts([e["id"] for e in spooled_entries])
            except Exception:
                pass

@router.post(
    "/api/v1/sensors/register",
    response_model=SensorRegisterResponse,
    summary="Register new Edge Sensor"
)
@router.post(
    "/sensors/register",
    response_model=SensorRegisterResponse,
    include_in_schema=False
)
async def register_sensor(request: SensorRegisterRequest, req: Request):
    """Register endpoint for new edge sensors with Zero-Touch Subnet Auto-Approval."""
    client_ip = req.headers.get("X-Forwarded-For", req.client.host if req.client else "unknown").split(",")[0].strip()

    sensor = get_or_create_sensor(request.sensor_id)
    sensor["hostname"] = request.hostname
    sensor["mac_address"] = request.mac_address
    sensor["os"] = request.os
    sensor["ip_address"] = client_ip
    if request.location:
        sensor["location"] = request.location

    if sensor["status"] != "approved":
        matched_rule = db.match_subnet_auto_enroll(client_ip)
        if matched_rule and matched_rule.get("auto_approve"):
            sensor["status"] = "approved"
            sensor["api_key"] = f"key_{secrets.token_hex(16)}"
            sensor["campus_id"] = matched_rule.get("campus_id")
            campus_name = matched_rule.get("campus_name", "Auto Campus")
            building_name = matched_rule.get("building_default", "Main Building")
            sensor["location"] = LocationSpec(
                district="Default District",
                site=campus_name,
                building=building_name,
                room="Auto-Discovered",
                notes=f"Auto-enrolled via subnet {matched_rule.get('subnet_cidr', '')}",
                latitude=35.37452,
                longitude=-119.01874,
                is_gps_auto=False
            )

    SENSORS_DB[sensor["sensor_id"]] = sensor
    db.save_sensor(sensor)

    if sensor["status"] == "approved":
        return SensorRegisterResponse(status="approved", api_key=sensor["api_key"])

    return SensorRegisterResponse(status="pending", api_key=None)

@router.post(
    "/api/v1/sensors/reconcile",
    response_model=SensorReconcileResponse,
    summary="Sensor Registration and State Reconciliation"
)
@router.post(
    "/sensors/reconcile",
    response_model=SensorReconcileResponse,
    include_in_schema=False
)
async def reconcile_sensor(report: SensorReportRequest, req: Request, x_api_key: str = Header(..., alias="X-API-Key")):
    """Edge sensor check-in and reconciliation endpoint."""
    sensor = SENSORS_DB.get(report.sensor_id)
    if not sensor or sensor["status"] != "approved" or sensor["api_key"] != x_api_key:
        raise UnauthorizedException(detail="Unauthorized or unapproved sensor check-in")

    client_ip = req.headers.get("X-Forwarded-For", req.client.host if req.client else "unknown").split(",")[0].strip()
    sensor["last_seen"] = int(time.time())
    sensor["os"] = report.os
    if client_ip and client_ip != "unknown":
        sensor["ip_address"] = client_ip
    sensor["reported_containers"] = {k: v.model_dump() for k, v in report.containers.items()}
    if report.location:
        sensor["location"] = report.location

    reset_value = sensor["reset_flag"]
    response = sensor["target_config"].model_copy(update={"reset": reset_value}, deep=True)
    response.probing_state = sensor.get("probing_state", "GREEN")

    if sensor["reset_flag"]:
        sensor["reset_flag"] = False

    if sensor["target_config"].schedules.bandwidth.run_now:
        sensor["target_config"].schedules.bandwidth.run_now = False

    if getattr(sensor["target_config"], "pcap_trigger", None) and sensor["target_config"].pcap_trigger.trigger_now:
        sensor["target_config"].pcap_trigger.trigger_now = False

    active_probes = []
    for p_dict in PROBES_DB.values():
        p = CustomProbeSpec(**p_dict)
        if p.enabled and ("all" in p.target_sensors or report.sensor_id in p.target_sensors):
            active_probes.append(p)
    response.custom_probes = active_probes

    active_schedules = [
        s for s in SCHEDULES_DB.values()
        if s.get("is_active", True) and (s.get("target_scope") == "all" or report.sensor_id in s.get("target_scope", "") or (sensor.get("campus_id") and sensor.get("campus_id") in s.get("target_scope", "")))
    ]
    response.unified_schedules = [UnifiedScheduleSpec(**s) for s in active_schedules]

    db.save_sensor(sensor)
    return response

@router.post(
    "/api/v1/sensors/report",
    response_model=SensorIngestResponse,
    summary="Universal Sensor & Chromebook Telemetry Report Ingestion"
)
@router.post(
    "/api/v1/chromebook/metrics",
    response_model=SensorIngestResponse,
    summary="Chromebook Fleet Telemetry Ingestion"
)
async def ingest_sensor_report(
    report: dict[str, Any],
    req: Request,
    x_api_key: str | None = Header(None, alias="X-API-Key")
):
    """Ingestion endpoint for Chromebook Fleet extensions and Edge Sensor telemetry."""
    sensor_id = report.get("sensor_id", f"cb-anon-{int(time.time())}")
    client_ip = req.headers.get("X-Forwarded-For", req.client.host if req.client else "unknown").split(",")[0].strip()

    sensor = get_or_create_sensor(sensor_id)
    sensor["last_seen"] = int(time.time())
    sensor["os"] = report.get("os", "ChromeOS")
    sensor["ip_address"] = client_ip

    device_info = report.get("device_info", {})
    if device_info:
        for field in ["hostname", "serial_number", "asset_id", "annotated_user", "directory_device_id", "mac_address", "version", "is_managed", "user_agent"]:
            if device_info.get(field):
                sensor[field] = device_info.get(field)
    if report.get("version"):
        sensor["version"] = report.get("version")

    loc = report.get("location")
    if loc and isinstance(loc, dict):
        if not sensor.get("location"):
            sensor["location"] = LocationSpec(**loc)
        else:
            for k, v in loc.items():
                if v is not None and hasattr(sensor["location"], k):
                    setattr(sensor["location"], k, v)

    sensor["wifi_telemetry"] = report.get("wifi", {})
    sensor["probe_telemetry"] = report.get("probes", {})
    sensor["hardware_telemetry"] = report.get("hardware", {})

    if sensor["status"] != "approved":
        matched_rule = db.match_subnet_auto_enroll(client_ip)
        if matched_rule and matched_rule.get("auto_approve"):
            sensor["status"] = "approved"
            sensor["campus_id"] = matched_rule.get("campus_id")
        elif x_api_key and x_api_key == ADMIN_API_KEY:
            sensor["status"] = "approved"
        else:
            sensor["status"] = "approved"

    db.save_sensor(sensor)

    try:
        forward_chromebook_metrics_to_tsdb(report)
    except Exception:
        pass

    if report.get("wifi", {}).get("roamed_recently"):
        ROAMING_EVENTS_DB.append({
            "sensor_id": sensor_id,
            "serial_number": sensor.get("serial_number"),
            "old_bssid": report.get("wifi", {}).get("old_bssid") or "Previous-AP",
            "new_bssid": report.get("wifi", {}).get("bssid"),
            "ssid": report.get("wifi", {}).get("ssid"),
            "timestamp": int(time.time()),
            "campus_id": sensor.get("campus_id")
        })
        if len(ROAMING_EVENTS_DB) > 500:
            ROAMING_EVENTS_DB.pop(0)

    active_probes = []
    for p_dict in PROBES_DB.values():
        p = CustomProbeSpec(**p_dict)
        if p.enabled and ("all" in p.target_sensors or sensor_id in p.target_sensors):
            active_probes.append(p)
    custom_probe_specs = active_probes

    return SensorIngestResponse(
        status="received",
        sensor_id=sensor_id,
        timestamp=int(time.time()),
        probing_state=sensor.get("probing_state", "GREEN"),
        settings_locked=sensor.get("settings_locked", True),
        helpdesk_pin_required=sensor.get("helpdesk_pin_required", True),
        helpdesk_pin=sensor.get("helpdesk_pin"),
        custom_probes=custom_probe_specs
    )







class DiagnosticRunRequest(BaseModel):
    test_type: str = "all"
    custom_target: str | None = ""


@router.get(
    "/api/v1/chromebooks",
    response_model=list[ChromebookFleetItemResponse],
    summary="List Active Chromebook Fleet Devices"
)
async def list_chromebook_fleet(campus: str | None = None):
    """Returns a list of all reporting Chromebook fleet sensors with Wi-Fi RF and hardware vitals."""
    now = int(time.time())
    result = []
    for s_id, s in SENSORS_DB.items():
        if s.get("os", "").lower() == "chromeos" or s_id.startswith("chromebook-") or s.get("sensor_type") == "chromebook":
            if campus and s.get("campus_id") != campus:
                continue
            is_online = (now - s.get("last_seen", 0)) < 180 and s.get("last_seen", 0) > 0
            wifi = s.get("wifi_telemetry", {})
            probes = s.get("probe_telemetry", {})
            hw = s.get("hardware_telemetry", {})
            webrtc = probes.get("webrtc", {})
            apps = probes.get("synthetic_http", [])
            app_success_count = sum(1 for a in apps if a.get("success"))
            app_sla = round((app_success_count / len(apps)) * 100, 1) if apps else 100.0

            result.append(ChromebookFleetItemResponse(
                sensor_id=s_id,
                serial_number=s.get("serial_number") or "UNTAGGED",
                asset_id=s.get("asset_id") or "UNTAGGED",
                directory_device_id=s.get("directory_device_id"),
                is_managed=s.get("is_managed", False),
                user_agent=s.get("user_agent"),
                annotated_location=str(getattr(s.get("location"), "room", "Mobile Fleet") or "Mobile Fleet"),
                annotated_user=s.get("annotated_user"),
                hostname=s.get("hostname"),
                ip_address=s.get("ip_address"),
                mac_address=s.get("mac_address"),
                is_online=is_online,
                last_seen=s.get("last_seen", 0),
                campus_id=s.get("campus_id") or "CAMPUS-CHROMEBOOK-FLEET",
                wifi_ssid=wifi.get("ssid"),
                wifi_bssid=wifi.get("bssid"),
                wifi_rssi_dbm=wifi.get("rssi_dbm"),
                wifi_signal_pct=wifi.get("signal_strength_pct"),
                wifi_channel=wifi.get("channel"),
                wifi_band=wifi.get("band"),
                battery_level_pct=hw.get("battery", {}).get("level_percent") if isinstance(hw.get("battery"), dict) else None,
                battery_charging=hw.get("battery", {}).get("charging") if isinstance(hw.get("battery"), dict) else None,
                cpu_usage_pct=hw.get("cpu", {}).get("usage_percent") if isinstance(hw.get("cpu"), dict) else None,
                memory_usage_pct=hw.get("memory", {}).get("usage_percent") if isinstance(hw.get("memory"), dict) else None,
                webrtc_mos=webrtc.get("mos"),
                webrtc_mos_grade=webrtc.get("mos_grade"),
                app_sla_pct=app_sla,
                roamed_recently=wifi.get("roamed_recently", False),
                location=s.get("location"),
                settings_locked=s.get("settings_locked", True),
                version=s.get("version") or "1.0.0",
                is_latest_version=(s.get("version", "1.0.0") == "1.0.0"),
                target_version="1.0.0"
            ))
    return result

@router.post(
    "/api/v1/chromebooks/{sensor_id}/lock",
    summary="Update Chromebook Settings Lock State & Helpdesk Override PIN"
)
@router.post(
    "/chromebooks/{sensor_id}/lock",
    include_in_schema=False
)
async def update_chromebook_lock_state(
    sensor_id: str,
    lock_req: ChromebookLockUpdateRequest,
    admin_key: str = Depends(verify_admin_key)
):
    """Allows CMP administrator to centrally lock or unlock the Chromebook sensor options panel and configure helpdesk PIN."""
    sensor = SENSORS_DB.get(sensor_id)
    if not sensor:
        sensor = get_or_create_sensor(sensor_id)

    sensor["settings_locked"] = lock_req.locked
    if lock_req.helpdesk_pin:
        sensor["helpdesk_pin"] = lock_req.helpdesk_pin

    SENSORS_DB[sensor_id] = sensor
    db.save_sensor(sensor)
    return {
        "status": "success",
        "sensor_id": sensor_id,
        "settings_locked": sensor["settings_locked"],
        "message": "Chromebook sensor lock state updated successfully"
    }

@router.get(
    "/api/v1/chromebooks/fleet-settings",
    summary="Get Fleet-Wide Chromebook Security & Lock Settings"
)
async def get_chromebook_fleet_settings():
    """Returns global default lock state and active helpdesk PIN for Chromebook fleet."""
    return {
        "settings_locked": CHROMEBOOK_GLOBAL_SETTINGS["settings_locked"],
        "helpdesk_pin": CHROMEBOOK_GLOBAL_SETTINGS["helpdesk_pin"],
        "target_version": "1.0.0"
    }

@router.post(
    "/api/v1/chromebooks/fleet-settings",
    summary="Update Fleet-Wide Chromebook Security & Lock Settings"
)
async def update_chromebook_fleet_settings(
    settings_req: ChromebookLockUpdateRequest,
    admin_key: str = Depends(verify_admin_key)
):
    """Centrally locks or unlocks all Chromebook sensors and updates the active helpdesk PIN."""
    CHROMEBOOK_GLOBAL_SETTINGS["settings_locked"] = settings_req.locked
    if settings_req.helpdesk_pin:
        CHROMEBOOK_GLOBAL_SETTINGS["helpdesk_pin"] = settings_req.helpdesk_pin

    updated_count = 0
    for s_id, s in SENSORS_DB.items():
        if s.get("os") == "chromeos" or str(s_id).startswith("chromebook-"):
            s["settings_locked"] = settings_req.locked
            if settings_req.helpdesk_pin:
                s["helpdesk_pin"] = settings_req.helpdesk_pin
            db.save_sensor(s)
            updated_count += 1
    return {
        "status": "success",
        "updated_sensors": updated_count,
        "settings_locked": CHROMEBOOK_GLOBAL_SETTINGS["settings_locked"],
        "helpdesk_pin": CHROMEBOOK_GLOBAL_SETTINGS["helpdesk_pin"],
        "message": f"Updated security settings for {updated_count} Chromebook sensors"
    }

@router.get(
    "/api/v1/chromebooks/download/extension.zip",
    summary="Download Packaged ChromeOS Extension (.zip)"
)
async def download_chromebook_extension_zip(request: Request, cmp_url: str | None = None):
    """Serves the zipped Chromebook sensor extension with an auto-incremented version number and injected CMP URL."""
    import io
    import zipfile

    from fastapi.responses import StreamingResponse

    # Fallback to server's own base URL if not provided by query param
    if not cmp_url:
        cmp_url = str(request.base_url).rstrip("/")

    cb_dir = Path(__file__).resolve().parent.parent.parent / "chromebook-sensor"
    if not cb_dir.exists():
        raise NotFoundException(detail="Chromebook source not found on server.")

    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(str(cb_dir)):
            # Exclude dev artifacts and build directories
            dirs[:] = [d for d in dirs if d not in ['.git', 'node_modules', 'test', '.coverage', 'dist']]
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, str(cb_dir))

                # Intercept and modify manifest.json to auto-bump the version for OTA compliance
                if arcname == "manifest.json":
                    with open(file_path, 'r') as f:
                        manifest = json.load(f)

                    # Chrome limits version integers to 65535. We use 1.YYYY.MMDD.HHMM for monotonic uniqueness
                    import datetime
                    now = datetime.datetime.now()
                    manifest["version"] = f"1.{now.year}.{now.month:02}{now.day:02}.{now.hour:02}{now.minute:02}"

                    zf.writestr(arcname, json.dumps(manifest, indent=2))
                # Intercept config_manager.js to dynamically inject the CMP URL so it works zero-config out of the box
                elif arcname == "src/background/config_manager.js":
                    with open(file_path, 'r') as f:
                        content = f.read()
                    content = content.replace('"http://localhost:8000"', f'"{cmp_url}"')
                    zf.writestr(arcname, content)
                else:
                    zf.write(file_path, arcname)

    memory_file.seek(0)

    return StreamingResponse(
        memory_file,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=one-chromebook-sensor-{int(time.time())}.zip"}
    )

@router.get(
    "/api/v1/chromebooks/download/policy.json",
    summary="Download Google Workspace Admin Policy (.json)"
)
async def download_chromebook_policy_json():
    """Serves the Google Workspace Admin Console configuration policy schema."""
    candidate_paths = [
        Path(__file__).resolve().parent.parent.parent / "chromebook-sensor" / "dist" / "google_workspace_policy_v1.0.0.json",
        Path("/app/chromebook-sensor/dist/google_workspace_policy_v1.0.0.json"),
        Path("/data/Open_Network_Experience/chromebook-sensor/dist/google_workspace_policy_v1.0.0.json"),
        Path("/home/kern/Open_Network_Experience/chromebook-sensor/dist/google_workspace_policy_v1.0.0.json")
    ]
    for p in candidate_paths:
        if p.exists():
            return FileResponse(str(p), media_type="application/json", filename="google_workspace_policy_v1.0.0.json")
    raise NotFoundException(detail="Google Workspace policy JSON not found.")

@router.get(
    "/api/v1/chromebooks/roaming-trail",
    response_model=list[RoamingEventResponse],
    summary="Get Recent Chromebook AP Roaming Events"
)
async def get_chromebook_roaming_trail(limit: int = 50):
    """Returns the most recent AP BSSID handover transitions for roaming visualization."""
    return ROAMING_EVENTS_DB[-limit:]

@router.get(
    "/api/v1/chromebooks/{sensor_id}",
    summary="Get Detailed Chromebook Fleet Sensor Diagnostics"
)
async def get_chromebook_detail(sensor_id: str):
    """Returns granular diagnostic, hardware, RF, and probe telemetry for a specific Chromebook."""
    sensor = SENSORS_DB.get(sensor_id)
    if not sensor:
        raise NotFoundException(detail="Chromebook sensor not found")
    now = __import__('time').time()
    is_online = (int(now) - sensor.get("last_seen", 0)) < 180 and sensor.get("last_seen", 0) > 0
    return {
        "sensor_id": sensor_id,
        "is_online": is_online,
        "serial_number": sensor.get("serial_number"),
        "asset_id": sensor.get("asset_id"),
        "annotated_user": sensor.get("annotated_user"),
        "directory_device_id": sensor.get("directory_device_id"),
        "hostname": sensor.get("hostname"),
        "ip_address": sensor.get("ip_address"),
        "mac_address": sensor.get("mac_address"),
        "last_seen": sensor.get("last_seen", 0),
        "location": sensor.get("location"),
        "campus_id": sensor.get("campus_id"),
        "wifi": sensor.get("wifi_telemetry", {}),
        "hardware": sensor.get("hardware_telemetry", {}),
        "probes": sensor.get("probe_telemetry", {})
    }











from pydantic import BaseModel


class BurstTriggerRequest(BaseModel):
    sensor_ids: list[str]
    duration_seconds: int = 60
    reason: str = "packet_loss_investigation"
