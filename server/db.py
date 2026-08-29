"""
SQLite Persistence & Disaster Recovery Engine for Open Network Experience (ONE) CMP Control Plane.

Stores all sensor records, cryptographic API keys, location specs, WYSIWYG custom probes,
and incident evidence records to a persistent SQLite database (/app/data/cmp.db).
Supports 1-click JSON backup export and restore.
"""

import sqlite3
import json
import os
import time
from typing import Dict, List, Optional, Any

DB_PATH = os.environ.get("DB_PATH", "/app/data/cmp.db")
BACKUP_DIR = os.environ.get("BACKUP_DIR", "/app/data/backups")

def get_connection() -> sqlite3.Connection:
    """Returns a SQLite connection with WAL mode enabled and parent directory created."""
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    os.makedirs(BACKUP_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes SQLite tables if they do not exist."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sensors (
                sensor_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                api_key TEXT,
                hostname TEXT,
                mac_address TEXT,
                os TEXT,
                last_seen INTEGER,
                reset_flag BOOLEAN DEFAULT 0,
                location_json TEXT,
                target_config_json TEXT,
                reported_containers_json TEXT,
                updated_at INTEGER
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS probes (
                probe_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                probe_type TEXT NOT NULL,
                target TEXT NOT NULL,
                cadence_minutes INTEGER DEFAULT 5,
                timeout_seconds REAL DEFAULT 4.0,
                expected_status_code INTEGER DEFAULT 200,
                target_sensors_json TEXT,
                enabled BOOLEAN DEFAULT 1,
                updated_at INTEGER
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS evidence (
                id TEXT PRIMARY KEY,
                sensor_id TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                trigger_reason TEXT,
                bundle_json TEXT
            );
        """)
        conn.commit()

# --- Sensors CRUD ---

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
                "location": json.loads(row["location_json"]) if row["location_json"] else None,
                "target_config": json.loads(row["target_config_json"]) if row["target_config_json"] else {},
                "reported_containers": json.loads(row["reported_containers_json"]) if row["reported_containers_json"] else {}
            }
    return sensors

def save_sensor(sensor: dict):
    """Saves or updates a single sensor record in SQLite."""
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO sensors (
                sensor_id, status, api_key, hostname, mac_address, os,
                last_seen, reset_flag, location_json, target_config_json,
                reported_containers_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(sensor_id) DO UPDATE SET
                status=excluded.status,
                api_key=excluded.api_key,
                hostname=excluded.hostname,
                mac_address=excluded.mac_address,
                os=excluded.os,
                last_seen=excluded.last_seen,
                reset_flag=excluded.reset_flag,
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
            json.dumps(sensor.get("location").model_dump() if hasattr(sensor.get("location"), "model_dump") else sensor.get("location")),
            json.dumps(sensor.get("target_config").model_dump() if hasattr(sensor.get("target_config"), "model_dump") else sensor.get("target_config")),
            json.dumps(sensor.get("reported_containers", {})),
            int(time.time())
        ))
        conn.commit()

def delete_sensor(sensor_id: str):
    """Deletes a sensor record from SQLite."""
    with get_connection() as conn:
        conn.execute("DELETE FROM sensors WHERE sensor_id = ?;", (sensor_id,))
        conn.commit()

# --- Custom Probes CRUD ---

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

# --- Evidence Bundles CRUD ---

def load_all_evidence() -> Dict[str, List[dict]]:
    """Loads all evidence records grouped by sensor_id."""
    evidence_dict = {}
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
    b_id = bundle.get("id") or f"ev-{int(time.time())}-{sensor_id[:6]}"
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

# --- Backup & Disaster Recovery ---

def export_backup_json() -> dict:
    """Exports complete database state as a portable JSON backup dictionary."""
    sensors = load_all_sensors()
    probes = load_all_probes()
    evidence = load_all_evidence()

    # Save a nightly rotation file on disk
    backup_payload = {
        "platform": "Open Network Experience (ONE)",
        "version": "0.3.0",
        "export_timestamp": int(time.time()),
        "export_date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sensors": sensors,
        "probes": probes,
        "evidence": evidence
    }

    try:
        backup_filename = os.path.join(BACKUP_DIR, f"cmp_backup_{time.strftime('%Y-%m-%d')}.json")
        with open(backup_filename, "w", encoding="utf-8") as f:
            json.dump(backup_payload, f, indent=2)
    except Exception as e:
        print(f"Warning: Failed to save nightly backup file: {e}")

    return backup_payload

def restore_backup_json(data: dict) -> bool:
    """Restores database from a JSON backup manifest and commits directly to SQLite."""
    sensors = data.get("sensors", {})
    probes = data.get("probes", {})
    evidence = data.get("evidence", {})

    init_db()

    for s_id, s_data in sensors.items():
        save_sensor(s_data)

    for p_id, p_data in probes.items():
        save_probe(p_data)

    for s_id, ev_list in evidence.items():
        for bundle in ev_list:
            save_evidence(s_id, bundle)

    return True
