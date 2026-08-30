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

DEFAULT_DATA_DIR = "/app/data" if os.path.exists("/app") and os.access("/app", os.W_OK) else os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DB_PATH = os.environ.get("DB_PATH", os.path.join(DEFAULT_DATA_DIR, "cmp.db"))
BACKUP_DIR = os.environ.get("BACKUP_DIR", os.path.join(DEFAULT_DATA_DIR, "backups"))

def get_connection() -> sqlite3.Connection:
    """Returns a SQLite connection with WAL mode enabled and parent directory created."""
    try:
        os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
        os.makedirs(BACKUP_DIR, exist_ok=True)
    except Exception:
        pass
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes SQLite tables if they do not exist."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS campuses (
                campus_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT DEFAULT 'High School',
                district TEXT DEFAULT 'Default District',
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                address TEXT,
                contact_email TEXT,
                created_at INTEGER
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS campus_subnets (
                id TEXT PRIMARY KEY,
                subnet_cidr TEXT NOT NULL UNIQUE,
                campus_id TEXT NOT NULL,
                campus_name TEXT NOT NULL,
                building_default TEXT DEFAULT 'Main Building',
                auto_approve BOOLEAN DEFAULT 1
            );
        """)
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
                campus_id TEXT,
                probing_state TEXT DEFAULT 'GREEN',
                location_json TEXT,
                target_config_json TEXT,
                reported_containers_json TEXT,
                updated_at INTEGER
            );
        """)
        # Run schema migration for existing DBs that might lack campus_id or probing_state
        try:
            conn.execute("ALTER TABLE sensors ADD COLUMN campus_id TEXT;")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE sensors ADD COLUMN probing_state TEXT DEFAULT 'GREEN';")
        except Exception:
            pass
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schedules (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                probe_id TEXT NOT NULL,
                mode TEXT DEFAULT 'daily_once',
                days_of_week_json TEXT,
                start_time TEXT DEFAULT '07:15',
                end_time TEXT DEFAULT '16:00',
                interval_value INTEGER DEFAULT 15,
                interval_unit TEXT DEFAULT 'minutes',
                cron_expr TEXT,
                target_scope TEXT DEFAULT 'all',
                guardrails_enabled BOOLEAN DEFAULT 1,
                is_active BOOLEAN DEFAULT 1,
                created_at INTEGER
            );
        """)
        conn.commit()

# --- Campuses CRUD ---

def load_all_campuses() -> Dict[str, dict]:
    """Loads all campuses from SQLite."""
    campuses = {}
    with get_connection() as conn:
        cursor = conn.execute("SELECT * FROM campuses;")
        for row in cursor.fetchall():
            c_id = row["campus_id"]
            campuses[c_id] = {
                "campus_id": c_id,
                "name": row["name"],
                "category": row["category"] or "High School",
                "district": row["district"] or "Default District",
                "latitude": float(row["latitude"]),
                "longitude": float(row["longitude"]),
                "address": row["address"] or "",
                "contact_email": row["contact_email"] or "",
                "created_at": row["created_at"] or int(time.time())
            }
    return campuses

def save_campus(campus: dict):
    """Saves or updates a campus record."""
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO campuses (
                campus_id, name, category, district, latitude, longitude, address, contact_email, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(campus_id) DO UPDATE SET
                name=excluded.name,
                category=excluded.category,
                district=excluded.district,
                latitude=excluded.latitude,
                longitude=excluded.longitude,
                address=excluded.address,
                contact_email=excluded.contact_email;
        """, (
            campus["campus_id"],
            campus["name"],
            campus.get("category", "High School"),
            campus.get("district", "Default District"),
            float(campus["latitude"]),
            float(campus["longitude"]),
            campus.get("address", ""),
            campus.get("contact_email", ""),
            campus.get("created_at", int(time.time()))
        ))
        conn.commit()

def delete_campus(campus_id: str):
    """Deletes a campus record."""
    with get_connection() as conn:
        conn.execute("DELETE FROM campuses WHERE campus_id = ?;", (campus_id,))
        conn.commit()

# --- Subnet Auto-Enrollment Rules CRUD ---

def load_all_subnets() -> List[dict]:
    """Loads all auto-enrollment subnet rules."""
    rules = []
    with get_connection() as conn:
        cursor = conn.execute("SELECT * FROM campus_subnets;")
        for row in cursor.fetchall():
            rules.append({
                "id": row["id"],
                "subnet_cidr": row["subnet_cidr"],
                "campus_id": row["campus_id"],
                "campus_name": row["campus_name"],
                "building_default": row["building_default"],
                "auto_approve": bool(row["auto_approve"])
            })
    return rules

def save_subnet_rule(rule: dict):
    """Saves or updates an auto-enrollment subnet rule."""
    import uuid
    rule_id = rule.get("id") or f"sub-{uuid.uuid4().hex[:8]}"
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO campus_subnets (id, subnet_cidr, campus_id, campus_name, building_default, auto_approve)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(subnet_cidr) DO UPDATE SET
                campus_id=excluded.campus_id,
                campus_name=excluded.campus_name,
                building_default=excluded.building_default,
                auto_approve=excluded.auto_approve;
        """, (
            rule_id,
            rule["subnet_cidr"].strip(),
            rule["campus_id"],
            rule["campus_name"],
            rule.get("building_default", "Main Building"),
            1 if rule.get("auto_approve", True) else 0
        ))
        conn.commit()

def delete_subnet_rule(rule_id: str):
    """Deletes an auto-enrollment subnet rule."""
    with get_connection() as conn:
        conn.execute("DELETE FROM campus_subnets WHERE id = ?;", (rule_id,))
        conn.commit()

def match_subnet_auto_enroll(ip_address: str) -> Optional[dict]:
    """Checks if an IP address belongs to any configured auto-enrollment subnet CIDR."""
    import ipaddress
    if not ip_address or ip_address in ("127.0.0.1", "localhost", "unknown"):
        return None
    try:
        ip = ipaddress.ip_address(ip_address)
        rules = load_all_subnets()
        for r in rules:
            try:
                network = ipaddress.ip_network(r["subnet_cidr"], strict=False)
                if ip in network:
                    return r
            except Exception:
                continue
    except Exception:
        pass
    return None

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
                "campus_id": row["campus_id"] if "campus_id" in row.keys() else None,
                "probing_state": row["probing_state"] if "probing_state" in row.keys() else "GREEN",
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
            json.dumps(sensor.get("location").model_dump() if hasattr(sensor.get("location"), "model_dump") else sensor.get("location")),
            json.dumps(sensor.get("target_config").model_dump() if hasattr(sensor.get("target_config"), "model_dump") else sensor.get("target_config")),
            json.dumps(sensor.get("reported_containers", {})),
            int(time.time())
        ))
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

# --- Unified Probe Schedules CRUD ---

def load_all_schedules() -> List[dict]:
    """Loads all probe schedules from SQLite."""
    schedules = []
    with get_connection() as conn:
        cursor = conn.execute("SELECT * FROM schedules ORDER BY created_at DESC;")
        for row in cursor.fetchall():
            days = json.loads(row["days_of_week_json"]) if row["days_of_week_json"] else ["mon", "tue", "wed", "thu", "fri"]
            schedules.append({
                "id": row["id"],
                "name": row["name"],
                "probe_id": row["probe_id"],
                "mode": row["mode"] or "daily_once",
                "days_of_week": days,
                "start_time": row["start_time"] or "07:15",
                "end_time": row["end_time"] or "16:00",
                "interval_value": row["interval_value"] or 15,
                "interval_unit": row["interval_unit"] or "minutes",
                "cron_expr": row["cron_expr"],
                "target_scope": row["target_scope"] or "all",
                "guardrails_enabled": bool(row["guardrails_enabled"]),
                "is_active": bool(row["is_active"]),
                "created_at": row["created_at"]
            })
    return schedules

def save_schedule(schedule: dict):
    """Saves or updates a probe schedule in SQLite."""
    days_json = json.dumps(schedule.get("days_of_week", ["mon", "tue", "wed", "thu", "fri"]))
    created_at = schedule.get("created_at") or int(time.time())
    with get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO schedules (
                id, name, probe_id, mode, days_of_week_json, start_time, end_time,
                interval_value, interval_unit, cron_expr, target_scope, guardrails_enabled, is_active, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            schedule["id"],
            schedule["name"],
            schedule["probe_id"],
            schedule.get("mode", "daily_once"),
            days_json,
            schedule.get("start_time", "07:15"),
            schedule.get("end_time", "16:00"),
            schedule.get("interval_value", 15),
            schedule.get("interval_unit", "minutes"),
            schedule.get("cron_expr"),
            schedule.get("target_scope", "all"),
            1 if schedule.get("guardrails_enabled", True) else 0,
            1 if schedule.get("is_active", True) else 0,
            created_at
        ))
        conn.commit()

def delete_schedule(schedule_id: str):
    """Deletes a probe schedule from SQLite."""
    with get_connection() as conn:
        conn.execute("DELETE FROM schedules WHERE id = ?;", (schedule_id,))
        conn.commit()

def toggle_schedule(schedule_id: str) -> bool:
    """Toggles active state of a schedule."""
    with get_connection() as conn:
        cursor = conn.execute("SELECT is_active FROM schedules WHERE id = ?;", (schedule_id,))
        row = cursor.fetchone()
        if row:
            new_state = 0 if row["is_active"] else 1
            conn.execute("UPDATE schedules SET is_active = ? WHERE id = ?;", (new_state, schedule_id))
            conn.commit()
            return bool(new_state)
    return False

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
