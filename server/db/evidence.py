import json
import time
import logging
from typing import Dict, List, Optional
from .connection import get_connection

logger = logging.getLogger(__name__)

def load_all_evidence() -> Dict[str, List[dict]]:
    """Loads all evidence records grouped by sensor_id."""
    evidence_dict: Dict[str, List[dict]] = {}
    with get_connection() as conn:
        cursor = conn.execute("SELECT * FROM evidence ORDER BY timestamp DESC;")
        for row in cursor.fetchall():
            s_id = row["sensor_id"]
            if s_id not in evidence_dict:
                evidence_dict[s_id] = []
            bundle = json.loads(row["bundle_json"]) if row["bundle_json"] else {}
            bundle["id"] = row["id"]
            bundle["sensor_id"] = s_id
            bundle["timestamp"] = row["timestamp"]
            bundle["trigger_reason"] = row["trigger_reason"]
            evidence_dict[s_id].append(bundle)
    return evidence_dict

def save_evidence(sensor_id: str, bundle: dict):
    """Saves an evidence bundle to SQLite."""
    b_id = bundle.get("id") or bundle.get("bundle_id") or f"ev-{int(time.time())}-{sensor_id[:6]}"
    bundle["id"] = b_id
    bundle["bundle_id"] = b_id
    with get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO evidence (id, sensor_id, timestamp, trigger_reason, bundle_json)
            VALUES (?, ?, ?, ?, ?);
        """, (
            b_id,
            sensor_id,
            bundle.get("timestamp", int(time.time())),
            bundle.get("trigger_reason", "manual_trigger"),
            json.dumps(bundle)
        ))
        conn.commit()

def load_evidence_by_id(evidence_id: str) -> Optional[dict]:
    """Loads a single evidence bundle by ID."""
    with get_connection() as conn:
        cursor = conn.execute("SELECT * FROM evidence WHERE id = ?;", (evidence_id,))
        row = cursor.fetchone()
        if row:
            bundle = json.loads(row["bundle_json"]) if row["bundle_json"] else {}
            bundle["id"] = row["id"]
            bundle["sensor_id"] = row["sensor_id"]
            bundle["timestamp"] = row["timestamp"]
            bundle["trigger_reason"] = row["trigger_reason"]
            return bundle
    return None
