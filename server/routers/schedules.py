"""
Open Network Experience (ONE) - Visual Unified Schedules Router
Copyright (C) 2026 Open Network Experience Authors.
Licensed under the GNU Affero General Public License v3.0 (AGPLv3).
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException
from server.schemas import UnifiedScheduleSpec
from server.security import verify_admin_key
from server.state import SCHEDULES_DB
import server.db as db

router = APIRouter(prefix="/api/v1/schedules", tags=["Probe Schedules"])

@router.get(
    "",
    response_model=List[UnifiedScheduleSpec],
    summary="List Visual Probe Schedules",
    dependencies=[Depends(verify_admin_key)]
)
async def list_schedules():
    """Lists all configured probe schedules with calendar days, timing windows, and guardrails."""
    return list(SCHEDULES_DB.values())

@router.post(
    "",
    summary="Create/Update Visual Probe Schedule",
    dependencies=[Depends(verify_admin_key)]
)
async def save_schedule_endpoint(schedule: UnifiedScheduleSpec):
    """Saves or updates a visual calendar or interval probe schedule."""
    sch_dict = schedule.model_dump()
    SCHEDULES_DB[schedule.id] = sch_dict
    db.save_schedule(sch_dict)

    # Synchronize to fleet target configs
    from server.state import SENSORS_DB
    for s_id, s_data in SENSORS_DB.items():
        if "target_config" in s_data:
            target_scope = sch_dict.get("target_scope", "all")
            is_targeted = "all" in target_scope or s_id in target_scope or (s_data.get("campus_id") and s_data.get("campus_id") in target_scope)

            if hasattr(s_data["target_config"], "unified_schedules"):
                s_data["target_config"].unified_schedules = [s for s in s_data["target_config"].unified_schedules if s.id != schedule.id]
                if is_targeted and sch_dict.get("is_active", True):
                    s_data["target_config"].unified_schedules.append(schedule)
            elif isinstance(s_data["target_config"], dict):
                unified_schedules = s_data["target_config"].get("unified_schedules", [])
                s_data["target_config"]["unified_schedules"] = [s for s in unified_schedules if (s.get("id") if isinstance(s, dict) else s.id) != schedule.id]
                if is_targeted and sch_dict.get("is_active", True):
                    s_data["target_config"]["unified_schedules"].append(schedule)
            db.save_sensor(s_data)

    return {"status": "success", "message": f"Schedule '{schedule.name}' saved.", "schedule": sch_dict}

@router.delete(
    "/{schedule_id}",
    summary="Delete Probe Schedule",
    dependencies=[Depends(verify_admin_key)]
)
async def delete_schedule_endpoint(schedule_id: str):
    """Deletes a probe schedule."""
    if schedule_id in SCHEDULES_DB:
        del SCHEDULES_DB[schedule_id]
        db.delete_schedule(schedule_id)

        # Synchronize deletion to fleet target configs
        from server.state import SENSORS_DB
        for s_id, s_data in SENSORS_DB.items():
            if "target_config" in s_data:
                if hasattr(s_data["target_config"], "unified_schedules"):
                    s_data["target_config"].unified_schedules = [s for s in s_data["target_config"].unified_schedules if s.id != schedule_id]
                elif isinstance(s_data["target_config"], dict):
                    unified_schedules = s_data["target_config"].get("unified_schedules", [])
                    s_data["target_config"]["unified_schedules"] = [s for s in unified_schedules if (s.get("id") if isinstance(s, dict) else s.id) != schedule_id]
                db.save_sensor(s_data)

        return {"status": "success", "message": f"Schedule '{schedule_id}' deleted."}
    raise HTTPException(status_code=404, detail="Schedule not found")

@router.put(
    "/{schedule_id}/toggle",
    summary="Toggle Probe Schedule Active Status",
    dependencies=[Depends(verify_admin_key)]
)
async def toggle_schedule_endpoint(schedule_id: str):
    """Enables or disables a probe schedule."""
    if schedule_id in SCHEDULES_DB:
        new_state = db.toggle_schedule(schedule_id)
        SCHEDULES_DB[schedule_id]["is_active"] = new_state

        # Synchronize toggle to fleet target configs
        from server.state import SENSORS_DB
        from server.schemas import UnifiedScheduleSpec
        for s_id, s_data in SENSORS_DB.items():
            if "target_config" in s_data:
                if hasattr(s_data["target_config"], "unified_schedules"):
                    s_data["target_config"].unified_schedules = [s for s in s_data["target_config"].unified_schedules if s.id != schedule_id]
                    if new_state:
                        # If turning back on, append if targeted
                        sch_dict = SCHEDULES_DB[schedule_id]
                        target_scope = sch_dict.get("target_scope", "all")
                        is_targeted = "all" in target_scope or s_id in target_scope or (s_data.get("campus_id") and s_data.get("campus_id") in target_scope)
                        if is_targeted:
                            s_data["target_config"].unified_schedules.append(UnifiedScheduleSpec(**sch_dict))
                elif isinstance(s_data["target_config"], dict):
                    unified_schedules = s_data["target_config"].get("unified_schedules", [])
                    s_data["target_config"]["unified_schedules"] = [s for s in unified_schedules if (s.get("id") if isinstance(s, dict) else s.id) != schedule_id]
                    if new_state:
                        # If turning back on, append if targeted
                        sch_dict = SCHEDULES_DB[schedule_id]
                        target_scope = sch_dict.get("target_scope", "all")
                        is_targeted = "all" in target_scope or s_id in target_scope or (s_data.get("campus_id") and s_data.get("campus_id") in target_scope)
                        if is_targeted:
                            s_data["target_config"]["unified_schedules"].append(UnifiedScheduleSpec(**sch_dict))
                db.save_sensor(s_data)

        return {
            "status": "success",
            "is_active": new_state,
            "message": f"Schedule '{schedule_id}' is now {'active' if new_state else 'paused'}."
        }
    raise HTTPException(status_code=404, detail="Schedule not found")
