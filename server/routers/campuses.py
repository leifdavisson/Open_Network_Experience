"""
Open Network Experience (ONE) - Multi-Campus Hierarchy & Auto-TOFU Subnets Router
Copyright (C) 2026 Open Network Experience Authors.
Licensed under the GNU Affero General Public License v3.0 (AGPLv3).
"""

import time
from typing import List, Dict, Any
from fastapi import APIRouter, Depends
from server.schemas import CampusCreate, SubnetAutoEnrollRule, BatchApprovalRequest
from server.security import verify_admin_key
from server.state import SENSORS_DB
import server.db as db

router = APIRouter(prefix="/api/v1", tags=["Campuses & Subnets"])

@router.get("/campuses", summary="List all campus sites", dependencies=[Depends(verify_admin_key)])
async def list_campuses():
    """Returns list of campuses with aggregated sensor counts and health statistics."""
    campuses = db.load_all_campuses()
    now = int(time.time())

    results = []
    for c_id, c_data in campuses.items():
        c_sensors = [
            s for s in SENSORS_DB.values()
            if s.get("campus_id") == c_id or (s.get("location") and getattr(s.get("location"), "site", "") == c_data["name"])
        ]
        online_count = sum(1 for s in c_sensors if (now - s.get("last_seen", 0)) < 120 and s.get("last_seen", 0) > 0)
        sensor_count = len(c_sensors)
        sla_pct = round((online_count / sensor_count * 100.0), 1) if sensor_count > 0 else 100.0

        results.append({
            **c_data,
            "sensor_count": sensor_count,
            "online_count": online_count,
            "degraded_count": sum(1 for s in c_sensors if s.get("probing_state") in ("AMBER", "RED")),
            "offline_count": sensor_count - online_count,
            "sla_percentage": sla_pct
        })
    return results

@router.post("/campuses", summary="Create or update campus site", dependencies=[Depends(verify_admin_key)])
async def create_campus(campus: CampusCreate):
    """Adds a new school campus to the district hierarchy."""
    db.save_campus(campus.model_dump())
    return {"status": "success", "message": f"Campus '{campus.name}' saved.", "campus": campus.model_dump()}

@router.delete("/campuses/{campus_id}", summary="Delete campus site", dependencies=[Depends(verify_admin_key)])
async def delete_campus(campus_id: str):
    """Removes a school campus from the district hierarchy."""
    db.delete_campus(campus_id)
    return {"status": "success", "message": f"Campus {campus_id} deleted."}

@router.get("/subnets", summary="List auto-enrollment subnet rules", dependencies=[Depends(verify_admin_key)])
async def list_subnets():
    """Lists CIDR subnet rules for Zero-Touch Provisioning (ZTP)."""
    return db.load_all_subnets()

@router.post("/subnets", summary="Create or update auto-enrollment subnet rule", dependencies=[Depends(verify_admin_key)])
async def create_subnet_rule(rule: SubnetAutoEnrollRule):
    """Configures a subnet CIDR for automatic TOFU sensor approval and campus assignment."""
    db.save_subnet_rule(rule.model_dump())
    return {"status": "success", "message": f"Subnet rule for {rule.subnet_cidr} saved."}

@router.delete("/subnets/{rule_id}", summary="Delete auto-enrollment subnet rule", dependencies=[Depends(verify_admin_key)])
async def delete_subnet_rule(rule_id: str):
    """Deletes an auto-enrollment subnet rule."""
    db.delete_subnet_rule(rule_id)
    return {"status": "success", "message": f"Subnet rule {rule_id} deleted."}

@router.post("/sensors/batch-approve", summary="Batch approve pending sensors", dependencies=[Depends(verify_admin_key)])
async def batch_approve(request: BatchApprovalRequest):
    """Bulk approves pending sensors across campuses in a single click."""
    db.batch_approve_sensors(request.sensor_ids, request.campus_id, request.building)
    for s_id in request.sensor_ids:
        if s_id in SENSORS_DB:
            SENSORS_DB[s_id]["status"] = "approved"
            if request.campus_id:
                SENSORS_DB[s_id]["campus_id"] = request.campus_id
    return {"status": "success", "approved_count": len(request.sensor_ids)}
