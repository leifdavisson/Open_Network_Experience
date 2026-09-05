import json
import time
import logging
from typing import Dict
from .connection import get_connection

logger = logging.getLogger(__name__)

def load_all_probes() -> Dict[str, dict]:
    """Loads all custom synthetic probes from SQLite."""
    probes = {}
    with get_connection() as conn:
        cursor = conn.execute("SELECT * FROM probes;")
        for row in cursor.fetchall():
            p_id = row["probe_id"]
            probes[p_id] = {
                "id": p_id,
                "name": row["name"],
                "probe_type": row["probe_type"],
                "target": row["target"],
                "cadence_minutes": row["cadence_minutes"],
                "timeout_seconds": row["timeout_seconds"],
                "expected_status_code": row["expected_status_code"],
                "target_sensors": json.loads(row["target_sensors_json"]) if row["target_sensors_json"] else ["all"],
                "enabled": bool(row["enabled"])
            }
    return probes

def save_probe(probe: dict):
    """Saves or updates a custom probe record in SQLite."""
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO probes (
                probe_id, name, probe_type, target, cadence_minutes,
                timeout_seconds, expected_status_code, target_sensors_json,
                enabled, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(probe_id) DO UPDATE SET
                name=excluded.name,
                probe_type=excluded.probe_type,
                target=excluded.target,
                cadence_minutes=excluded.cadence_minutes,
                timeout_seconds=excluded.timeout_seconds,
                expected_status_code=excluded.expected_status_code,
                target_sensors_json=excluded.target_sensors_json,
                enabled=excluded.enabled,
                updated_at=excluded.updated_at;
        """, (
            probe["id"],
            probe["name"],
            probe["probe_type"],
            probe["target"],
            probe.get("cadence_minutes", 5),
            probe.get("timeout_seconds", 4.0),
            probe.get("expected_status_code", 200),
            json.dumps(probe.get("target_sensors", ["all"])),
            1 if probe.get("enabled", True) else 0,
            int(time.time())
        ))
        conn.commit()

def delete_probe(probe_id: str):
    """Deletes a custom probe from SQLite."""
    with get_connection() as conn:
        conn.execute("DELETE FROM probes WHERE probe_id = ?;", (probe_id,))
        conn.commit()
