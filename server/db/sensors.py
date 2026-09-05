import json
import time
import logging
from typing import Dict, List, Optional
from .connection import get_connection

logger = logging.getLogger(__name__)

def load_all_sensors() -> Dict[str, dict]:
    """Loads all sensors from SQLite into memory dict structure."""
    sensors = {}
    with get_connection() as conn:
        cursor = conn.execute("SELECT * FROM sensors;")
        for row in cursor.fetchall():
            s_id = row["sensor_id"]
            sensors[s_id] = {
                "sensor_id": s_id,
                "status": row["status"],
                "api_key": row["api_key"] or "",
                "hostname": row["hostname"] or "unknown",
                "mac_address": row["mac_address"] or "unknown",
                "os": row["os"] or "unknown",
                "last_seen": row["last_seen"] or 0,
                "reset_flag": bool(row["reset_flag"]),
                "campus_id": row["campus_id"] if "campus_id" in row.keys() else None,
                "probing_state": row["probing_state"] if "probing_state" in row.keys() else "GREEN",
                "location": json.loads(row["location_json"]) if row["location_json"] else None,
                "target_config": json.loads(row["target_config_json"]) if row["target_config_json"] else {},
                "reported_containers": json.loads(row["reported_containers_json"]) if row["reported_containers_json"] else {}
            }
    return sensors

def load_sensor(sensor_id: str) -> Optional[dict]:
    """Loads a single sensor record directly from SQLite."""
    with get_connection() as conn:
        cursor = conn.execute("SELECT * FROM sensors WHERE sensor_id = ?;", (sensor_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "sensor_id": row["sensor_id"],
            "status": row["status"],
            "api_key": row["api_key"] or "",
            "hostname": row["hostname"] or "unknown",
            "mac_address": row["mac_address"] or "unknown",
            "os": row["os"] or "unknown",
            "last_seen": row["last_seen"] or 0,
            "reset_flag": bool(row["reset_flag"]),
            "campus_id": row["campus_id"] if "campus_id" in row.keys() else None,
            "probing_state": row["probing_state"] if "probing_state" in row.keys() else "GREEN",
            "location": json.loads(row["location_json"]) if row["location_json"] else None,
            "target_config": json.loads(row["target_config_json"]) if row["target_config_json"] else {},
            "reported_containers": json.loads(row["reported_containers_json"]) if row["reported_containers_json"] else {}
        }

def save_sensor(sensor: dict):
    """Saves or updates a single sensor record in SQLite."""
    loc_val = sensor.get("location")
    loc_json = json.dumps(loc_val.model_dump() if hasattr(loc_val, "model_dump") else loc_val) if loc_val is not None else None
    target_cfg_val = sensor.get("target_config")
    target_cfg_json = json.dumps(target_cfg_val.model_dump() if hasattr(target_cfg_val, "model_dump") else target_cfg_val) if target_cfg_val is not None else None

    with get_connection() as conn:
        conn.execute("""
            INSERT INTO sensors (
                sensor_id, status, api_key, hostname, mac_address, os,
                last_seen, reset_flag, campus_id, probing_state, location_json, target_config_json,
                reported_containers_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(sensor_id) DO UPDATE SET
                status=excluded.status,
                api_key=excluded.api_key,
                hostname=excluded.hostname,
                mac_address=excluded.mac_address,
                os=excluded.os,
                last_seen=excluded.last_seen,
                reset_flag=excluded.reset_flag,
                campus_id=excluded.campus_id,
                probing_state=excluded.probing_state,
                location_json=excluded.location_json,
                target_config_json=excluded.target_config_json,
                reported_containers_json=excluded.reported_containers_json,
                updated_at=excluded.updated_at;
        """, (
            sensor["sensor_id"],
            sensor["status"],
            sensor.get("api_key", ""),
            sensor.get("hostname", "unknown"),
            sensor.get("mac_address", "unknown"),
            sensor.get("os", "unknown"),
            sensor.get("last_seen", 0),
            1 if sensor.get("reset_flag") else 0,
            sensor.get("campus_id"),
            sensor.get("probing_state", "GREEN"),
            loc_json,
            target_cfg_json,
            json.dumps(sensor.get("reported_containers", {})),
            int(time.time())
        ))
        conn.commit()

def batch_save_sensors(sensors: List[dict]):
    """Saves or updates multiple sensor records in SQLite in a single transaction."""
    rows = []
    for sensor in sensors:
        loc_val = sensor.get("location")
        loc_json = json.dumps(loc_val.model_dump() if hasattr(loc_val, "model_dump") else loc_val) if loc_val is not None else None
        target_cfg_val = sensor.get("target_config")
        target_cfg_json = json.dumps(target_cfg_val.model_dump() if hasattr(target_cfg_val, "model_dump") else target_cfg_val) if target_cfg_val is not None else None
        rows.append((
            sensor["sensor_id"],
            sensor["status"],
            sensor.get("api_key", ""),
            sensor.get("hostname", "unknown"),
            sensor.get("mac_address", "unknown"),
            sensor.get("os", "unknown"),
            sensor.get("last_seen", 0),
            1 if sensor.get("reset_flag") else 0,
            sensor.get("campus_id"),
            sensor.get("probing_state", "GREEN"),
            loc_json,
            target_cfg_json,
            json.dumps(sensor.get("reported_containers", {})),
            int(time.time())
        ))

    with get_connection() as conn:
        conn.executemany("""
            INSERT INTO sensors (
                sensor_id, status, api_key, hostname, mac_address, os,
                last_seen, reset_flag, campus_id, probing_state, location_json, target_config_json,
                reported_containers_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(sensor_id) DO UPDATE SET
                status=excluded.status,
                api_key=excluded.api_key,
                hostname=excluded.hostname,
                mac_address=excluded.mac_address,
                os=excluded.os,
                last_seen=excluded.last_seen,
                reset_flag=excluded.reset_flag,
                campus_id=excluded.campus_id,
                probing_state=excluded.probing_state,
                location_json=excluded.location_json,
                target_config_json=excluded.target_config_json,
                reported_containers_json=excluded.reported_containers_json,
                updated_at=excluded.updated_at;
        """, rows)
        conn.commit()

def batch_approve_sensors(sensor_ids: List[str], campus_id: Optional[str] = None, building: Optional[str] = None) -> List[str]:
    """Approves multiple sensors in a single transaction and assigns them to a campus."""
    import secrets
    approved_keys = []
    with get_connection() as conn:
        for s_id in sensor_ids:
            new_key = f"key_{secrets.token_hex(16)}"
            approved_keys.append(new_key)
            conn.execute("""
                UPDATE sensors SET
                    status = 'approved',
                    api_key = ?,
                    campus_id = COALESCE(?, campus_id),
                    updated_at = ?
                WHERE sensor_id = ?;
            """, (new_key, campus_id, int(time.time()), s_id))
        conn.commit()
    return approved_keys

def delete_sensor(sensor_id: str):
    """Deletes a sensor record from SQLite."""
    with get_connection() as conn:
        conn.execute("DELETE FROM sensors WHERE sensor_id = ?;", (sensor_id,))
        conn.commit()
