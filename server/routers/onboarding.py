"""
Open Network Experience (ONE) - Onboarding, USB Staging & Installer Router
Copyright (C) 2026 Open Network Experience Authors.
Licensed under the GNU Affero General Public License v3.0 (AGPLv3).
"""

import os
import io
import json
import zipfile
from typing import Optional
from fastapi import APIRouter, Request, Query, HTTPException, Response
from fastapi.responses import PlainTextResponse

router = APIRouter(tags=["Onboarding & Provisioning"])

@router.get("/install.sh", summary="1-Line Sensor SSH Installer Script")
@router.get("/bootstrap.sh", summary="1-Line Sensor SSH Installer Script")
async def get_install_script(
    request: Request,
    site: Optional[str] = Query(None, alias="site"),
    campus: Optional[str] = Query(None, alias="campus"),
    building: Optional[str] = Query(None, alias="building"),
    room: Optional[str] = Query(None, alias="room"),
    district: Optional[str] = Query(None, alias="district"),
    notes: Optional[str] = Query(None, alias="notes"),
    token: Optional[str] = Query(None, alias="token"),
    wifi_ssid: Optional[str] = Query(None, alias="wifi_ssid"),
    wifi_psk: Optional[str] = Query(None, alias="wifi_psk"),
    wizard: Optional[bool] = Query(None, alias="wizard"),
    force: Optional[bool] = Query(None, alias="force")
):
    """Serves the dynamic 1-line curl-to-bash edge sensor installer with query parameter presets."""
    base_url = str(request.base_url).rstrip("/")
    sensor_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "sensor"))
    install_file = os.path.join(sensor_root, "install.sh")
    if os.path.exists(install_file):
        with open(install_file, "r") as f:
            content = f.read()
            content = content.replace("http://central-monitoring-platform.local/api/v1", f"{base_url}/api/v1")
            target_site = site or campus
            if target_site:
                content = content.replace('SITE_NAME="Main Campus"', f'SITE_NAME="{target_site}"')
                content = content.replace('EXPLICIT_ARGS=0', 'EXPLICIT_ARGS=1')
            if building:
                content = content.replace('BUILDING_NAME="Main Building"', f'BUILDING_NAME="{building}"')
                content = content.replace('EXPLICIT_ARGS=0', 'EXPLICIT_ARGS=1')
            if room:
                content = content.replace('ROOM_NAME="Room 101"', f'ROOM_NAME="{room}"')
                content = content.replace('EXPLICIT_ARGS=0', 'EXPLICIT_ARGS=1')
            if district:
                content = content.replace('DISTRICT_NAME="Kern County Superintendent of Schools"', f'DISTRICT_NAME="{district}"')
            if notes:
                content = content.replace('LOCATION_NOTES="Ceiling AP Drop"', f'LOCATION_NOTES="{notes}"')
            if token:
                content = content.replace('ENROLL_TOKEN=""', f'ENROLL_TOKEN="{token}"')
            if wifi_ssid:
                content = content.replace('WIFI_SSID=""', f'WIFI_SSID="{wifi_ssid}"')
            if wifi_psk:
                content = content.replace('WIFI_PSK=""', f'WIFI_PSK="{wifi_psk}"')
            if wizard is True:
                content = content.replace('LAUNCH_WIZARD=0', 'LAUNCH_WIZARD=1')
            if force is True:
                content = content.replace('FORCE_INSTALL=0', 'FORCE_INSTALL=1')
            return PlainTextResponse(content, media_type="text/x-shellscript")
    raise HTTPException(status_code=404, detail="install.sh not found on server")

@router.get("/sensor/scripts/{script_name}", summary="Download Edge Sensor Probe Script")
async def get_sensor_script(script_name: str):
    """Serves synthetic probe scripts to edge sensor installer during curl bootstrapping."""
    sensor_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "sensor"))

    search_paths = [
        os.path.join(sensor_dir, script_name),
        os.path.join(sensor_dir, "reconciler", script_name),
        os.path.join(sensor_dir, "onboarding", script_name)
    ]
    if script_name == "reconciler.py":
        search_paths.insert(0, os.path.join(sensor_dir, "reconciler", "reconciler.py"))
    elif script_name == "wizard.py":
        search_paths.insert(0, os.path.join(sensor_dir, "onboarding", "wizard.py"))
    elif script_name == "usb_provisioner.py":
        search_paths.insert(0, os.path.join(sensor_dir, "onboarding", "usb_provisioner.py"))
    elif script_name == "setup.sh":
        search_paths.insert(0, os.path.join(sensor_dir, "onboarding", "setup.sh"))

    for target_path in search_paths:
        if os.path.exists(target_path) and os.path.isfile(target_path):
            with open(target_path, "r", encoding="utf-8", errors="ignore") as f:
                return PlainTextResponse(f.read(), media_type="text/plain")

    raise HTTPException(status_code=404, detail=f"Script '{script_name}' not found")

@router.get("/api/v1/onboarding/usb-kit.zip", summary="Generate & Download USB Flash Drive Staging Kit (.zip)")
@router.get("/download/usb-kit.zip", summary="Generate & Download USB Flash Drive Staging Kit (.zip)")
async def download_usb_staging_kit(
    request: Request,
    site: Optional[str] = Query(None, alias="site"),
    campus: Optional[str] = Query(None, alias="campus"),
    building: Optional[str] = Query(None, alias="building"),
    room: Optional[str] = Query(None, alias="room"),
    rooms: Optional[str] = Query(None, alias="rooms"),
    district: Optional[str] = Query(None, alias="district"),
    notes: Optional[str] = Query(None, alias="notes"),
    token: Optional[str] = Query(None, alias="token"),
    wifi_ssid: Optional[str] = Query(None, alias="wifi_ssid"),
    wifi_psk: Optional[str] = Query(None, alias="wifi_psk")
):
    """Generates an in-memory zip bundle ready to extract onto a FAT32 USB drive for assembly-line auto-staging."""
    base_url = str(request.base_url).rstrip("/")
    cmp_api_url = f"{base_url}/api/v1"

    target_site = site or campus or "Main Campus"
    target_building = building or "Main Building"
    target_room = room or "Room 101"
    room_pool = [r.strip() for r in rooms.split(",") if r.strip()] if rooms else []

    bootstrap_data = {
        "cmp_url": cmp_api_url,
        "enrollment_token": token or "",
        "check_interval_seconds": 15,
        "location": {
            "district": district or "Kern County Superintendent of Schools",
            "site": target_site,
            "building": target_building,
            "room": target_room,
            "notes": notes or "Auto-Provisioned via ONE USB Staging Kit"
        },
        "auto_eject_and_sync": True
    }
    if room_pool:
        bootstrap_data["room_pool"] = room_pool
    if wifi_ssid:
        bootstrap_data["wifi"] = {
            "ssid": wifi_ssid,
            "security": "psk" if wifi_psk else "open",
            "psk": wifi_psk or ""
        }

    sensor_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "sensor"))

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("one-bootstrap.json", json.dumps(bootstrap_data, indent=4))

        readme_text = f"""================================================================
  🚀 OPEN NETWORK EXPERIENCE (ONE) - USB STAGING KIT
================================================================

HOW TO RAPID-STAGE SENSORS:
1. Extract ALL files from this zip onto the root of any FAT32 / exFAT USB flash drive.
2. Boot your Raspberry Pi 5 or x86 SBC (with fresh Ubuntu Server or Raspberry Pi OS).
3. Insert this USB drive into the sensor.
4. Open the terminal and run:
     sudo ./setup.sh
   (Or from any directory: sudo /media/*/*/setup.sh)
5. The provisioner will automatically:
   • Deploy synthetic diagnostic probes
   • Configure Wi-Fi credentials ({wifi_ssid or 'Wired Ethernet'})
   • Connect and register with CMP ({cmp_api_url})
   • Log the sensor UUID, MAC, and IP onto 'provisioned_sensors.csv' on this USB drive!
6. Once green confirmation appears, unplug the USB drive and insert into the next sensor.
"""
        zf.writestr("README_USB_STAGING.txt", readme_text)

        files_to_pack = [
            ("install.sh", os.path.join(sensor_dir, "install.sh")),
            ("setup.sh", os.path.join(sensor_dir, "onboarding", "setup.sh")),
            ("usb_provisioner.py", os.path.join(sensor_dir, "onboarding", "usb_provisioner.py")),
            ("wizard.py", os.path.join(sensor_dir, "onboarding", "wizard.py")),
            ("reconciler.py", os.path.join(sensor_dir, "reconciler", "reconciler.py")),
            ("cipa_compliance.py", os.path.join(sensor_dir, "cipa_compliance.py")),
            ("caaspp_readiness.py", os.path.join(sensor_dir, "caaspp_readiness.py")),
            ("iperf3_runner.py", os.path.join(sensor_dir, "iperf3_runner.py")),
            ("wifi_dhcp_exporter.py", os.path.join(sensor_dir, "wifi_dhcp_exporter.py")),
            ("rrm_darrp_monitor.py", os.path.join(sensor_dir, "rrm_darrp_monitor.py")),
            ("pcap_trigger.py", os.path.join(sensor_dir, "pcap_trigger.py")),
            ("evidence_collector.py", os.path.join(sensor_dir, "evidence_collector.py")),
            ("segmentation_prober.py", os.path.join(sensor_dir, "segmentation_prober.py")),
            ("dns_multi_resolver_probe.py", os.path.join(sensor_dir, "dns_multi_resolver_probe.py")),
            ("voip_jitter_probe.py", os.path.join(sensor_dir, "voip_jitter_probe.py")),
            ("custom_probe_runner.py", os.path.join(sensor_dir, "custom_probe_runner.py")),
            ("gps_location_collector.py", os.path.join(sensor_dir, "gps_location_collector.py"))
        ]

        for arcname, fpath in files_to_pack:
            if os.path.exists(fpath) and os.path.isfile(fpath):
                zf.write(fpath, arcname=arcname)

    zip_buffer.seek(0)
    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=one_usb_staging_kit.zip"}
    )
