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
        return {"status": "success", "message": f"Probe '{probe_id}' deleted."}
    raise HTTPException(status_code=404, detail="Probe not found")
