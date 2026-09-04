"""
Open Network Experience (ONE) - Synthetic Studio Custom Probes Router
Copyright (C) 2026 Open Network Experience Authors.
Licensed under the GNU Affero General Public License v3.0 (AGPLv3).
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException
from server.schemas import CustomProbeSpec
from server.security import verify_admin_key
from server.state import PROBES_DB
import server.db as db

router = APIRouter(prefix="/api/v1/probes", tags=["Custom Synthetic Probes"])

@router.get(
    "",
    response_model=List[CustomProbeSpec],
    summary="List Custom Synthetic Probes",
    dependencies=[Depends(verify_admin_key)]
)
async def list_custom_probes():
    """Lists all synthetic probes created via WYSIWYG EasyBuilder Studio."""
    return list(PROBES_DB.values())

@router.post(
    "",
    summary="Create/Update Custom Synthetic Probe",
    dependencies=[Depends(verify_admin_key)]
)
async def save_custom_probe(probe: CustomProbeSpec):
    """Creates or updates a custom synthetic probe via WYSIWYG Studio."""
    probe_dict = probe.model_dump()
    PROBES_DB[probe.id] = probe_dict
    db.save_probe(probe_dict)

    # Synchronize to fleet target configs
    from server.state import SENSORS_DB
    for s_id, s_data in SENSORS_DB.items():
        if "target_config" in s_data:
            target_scope = probe_dict.get("target_sensors", ["all"])
            is_targeted = "all" in target_scope or s_id in target_scope

            # Remove old definition if it exists
            if hasattr(s_data["target_config"], "custom_probes"):
                s_data["target_config"].custom_probes = [p for p in s_data["target_config"].custom_probes if p.id != probe.id]
                if is_targeted and probe_dict.get("enabled", True):
                    s_data["target_config"].custom_probes.append(probe)
            elif isinstance(s_data["target_config"], dict):
                custom_probes = s_data["target_config"].get("custom_probes", [])
                s_data["target_config"]["custom_probes"] = [p for p in custom_probes if (p.get("id") if isinstance(p, dict) else p.id) != probe.id]
                if is_targeted and probe_dict.get("enabled", True):
                    s_data["target_config"]["custom_probes"].append(probe)
            db.save_sensor(s_data)

    return {"status": "success", "message": f"Custom probe '{probe.name}' saved and ready for distribution."}

@router.delete(
    "/{probe_id}",
    summary="Delete Custom Synthetic Probe",
    dependencies=[Depends(verify_admin_key)]
)
async def delete_custom_probe(probe_id: str):
    """Deletes a custom synthetic probe."""
    if probe_id in PROBES_DB:
        del PROBES_DB[probe_id]
        db.delete_probe(probe_id)

        # Synchronize deletion to fleet target configs
        from server.state import SENSORS_DB
        for s_id, s_data in SENSORS_DB.items():
            if "target_config" in s_data:
                if hasattr(s_data["target_config"], "custom_probes"):
                    s_data["target_config"].custom_probes = [p for p in s_data["target_config"].custom_probes if p.id != probe_id]
                elif isinstance(s_data["target_config"], dict):
                    custom_probes = s_data["target_config"].get("custom_probes", [])
                    s_data["target_config"]["custom_probes"] = [p for p in custom_probes if (p.get("id") if isinstance(p, dict) else p.id) != probe_id]
                db.save_sensor(s_data)

        return {"status": "success", "message": f"Probe '{probe_id}' deleted."}
    raise HTTPException(status_code=404, detail="Probe not found")
