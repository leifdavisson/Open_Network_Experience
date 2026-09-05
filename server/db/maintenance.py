import json
import time
import logging
from typing import List, Optional
from .connection import get_connection

logger = logging.getLogger(__name__)

def load_all_maintenance_windows(active_only: bool = False) -> List[dict]:
    """Loads all scheduled maintenance/muting windows from SQLite."""
    windows = []
    with get_connection() as conn:
        query = "SELECT * FROM maintenance_windows"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY starts_at DESC;"
        cursor = conn.execute(query)
        for row in cursor.fetchall():
            keys = row.keys()
            windows.append({
                "id": row["id"],
                "name": row["name"],
                "description": row["description"] or "",
                "window_type": row["window_type"] if "window_type" in keys and row["window_type"] else "maintenance",
                "campus_id": row["campus_id"],
                "sensor_id": row["sensor_id"],
                "probe_id": row["probe_id"],
                "alertname_pattern": row["alertname_pattern"],
                "starts_at": row["starts_at"],
                "ends_at": row["ends_at"],
                "is_active": bool(row["is_active"]),
                "reminded_24h": bool(row["reminded_24h"]) if "reminded_24h" in keys else False,
                "reminded_2h": bool(row["reminded_2h"]) if "reminded_2h" in keys else False,
                "notify_channel_ids": json.loads(row["notify_channel_ids_json"]) if "notify_channel_ids_json" in keys and row["notify_channel_ids_json"] else [],
                "created_by": row["created_by"] or "NOC Admin",
                "created_at": row["created_at"] or row["starts_at"],
                "updated_at": row["updated_at"] or row["starts_at"]
            })
    return windows

def load_maintenance_window_by_id(window_id: str) -> Optional[dict]:
    """Loads a single maintenance window by ID."""
    with get_connection() as conn:
        cursor = conn.execute("SELECT * FROM maintenance_windows WHERE id = ?;", (window_id,))
        row = cursor.fetchone()
        if row:
            keys = row.keys()
            return {
                "id": row["id"],
                "name": row["name"],
                "description": row["description"] or "",
                "window_type": row["window_type"] if "window_type" in keys and row["window_type"] else "maintenance",
                "campus_id": row["campus_id"],
                "sensor_id": row["sensor_id"],
                "probe_id": row["probe_id"],
                "alertname_pattern": row["alertname_pattern"],
                "starts_at": row["starts_at"],
                "ends_at": row["ends_at"],
                "is_active": bool(row["is_active"]),
                "reminded_24h": bool(row["reminded_24h"]) if "reminded_24h" in keys else False,
                "reminded_2h": bool(row["reminded_2h"]) if "reminded_2h" in keys else False,
                "notify_channel_ids": json.loads(row["notify_channel_ids_json"]) if "notify_channel_ids_json" in keys and row["notify_channel_ids_json"] else [],
                "created_by": row["created_by"] or "NOC Admin",
                "created_at": row["created_at"],
                "updated_at": row["updated_at"]
            }
    return None

def save_maintenance_window(window_data: dict) -> str:
    """Creates or updates a maintenance window in SQLite."""
    import uuid
    w_id = window_data.get("id") or f"maint_{int(time.time())}_{uuid.uuid4().hex[:4]}"
    now = int(time.time())
    starts_at = int(window_data.get("starts_at") or now)
    ends_at = int(window_data.get("ends_at") or (starts_at + 7200)) # Default 2 hours
    channels = window_data.get("notify_channel_ids", [])

    with get_connection() as conn:
        conn.execute("""
            INSERT INTO maintenance_windows (
                id, name, description, window_type, campus_id, sensor_id, probe_id,
                alertname_pattern, starts_at, ends_at, is_active, reminded_24h, reminded_2h,
                notify_channel_ids_json, created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                description = excluded.description,
                window_type = excluded.window_type,
                campus_id = excluded.campus_id,
                sensor_id = excluded.sensor_id,
                probe_id = excluded.probe_id,
                alertname_pattern = excluded.alertname_pattern,
                starts_at = excluded.starts_at,
                ends_at = excluded.ends_at,
                is_active = excluded.is_active,
                reminded_24h = excluded.reminded_24h,
                reminded_2h = excluded.reminded_2h,
                notify_channel_ids_json = excluded.notify_channel_ids_json,
                created_by = excluded.created_by,
                updated_at = excluded.updated_at;
        """, (
            w_id,
            window_data.get("name", "Scheduled Maintenance"),
            window_data.get("description", ""),
            window_data.get("window_type", "maintenance"),
            window_data.get("campus_id"),
            window_data.get("sensor_id"),
            window_data.get("probe_id"),
            window_data.get("alertname_pattern"),
            starts_at,
            ends_at,
            1 if window_data.get("is_active", True) else 0,
            1 if window_data.get("reminded_24h", False) else 0,
            1 if window_data.get("reminded_2h", False) else 0,
            json.dumps(channels) if channels else None,
            window_data.get("created_by", "NOC Admin"),
            window_data.get("created_at", now),
            now
        ))
        conn.commit()
    return w_id

def toggle_maintenance_window(window_id: str) -> Optional[dict]:
    """Toggles active state of a maintenance window."""
    now = int(time.time())
    with get_connection() as conn:
        cursor = conn.execute("SELECT is_active FROM maintenance_windows WHERE id = ?;", (window_id,))
        row = cursor.fetchone()
        if not row:
            return None
        new_state = 0 if row["is_active"] else 1
        conn.execute("UPDATE maintenance_windows SET is_active = ?, updated_at = ? WHERE id = ?;", (new_state, now, window_id))
        conn.commit()
    return load_maintenance_window_by_id(window_id)

def delete_maintenance_window(window_id: str) -> bool:
    """Removes a maintenance window."""
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM maintenance_windows WHERE id = ?;", (window_id,))
        conn.commit()
        return cursor.rowcount > 0

def get_maintenance_windows_needing_reminders(now_ts: Optional[int] = None) -> List[dict]:
    """
    Finds active maintenance windows that are approaching their expiration and need warning dispatches:
    - 24-hour warning: window is active, ends_at - now <= 86400, and reminded_24h is False.
    - 2-hour warning: window is active, ends_at - now <= 7200, and reminded_2h is False.
    """
    now = now_ts or int(time.time())
    results = []
    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT * FROM maintenance_windows
            WHERE is_active = 1
              AND ends_at > ?
              AND (
                (ends_at - ? <= 86400 AND (reminded_24h IS NULL OR reminded_24h = 0))
                OR
                (ends_at - ? <= 7200 AND (reminded_2h IS NULL OR reminded_2h = 0))
              );
        """, (now, now, now))
        for row in cursor.fetchall():
            keys = row.keys()
            ends_at = row["ends_at"]
            rem_24 = bool(row["reminded_24h"]) if "reminded_24h" in keys else False
            rem_2 = bool(row["reminded_2h"]) if "reminded_2h" in keys else False

            reminder_type = None
            if ends_at - now <= 7200 and not rem_2:
                reminder_type = "2h"
            elif ends_at - now <= 86400 and not rem_24:
                reminder_type = "24h"

            if reminder_type:
                results.append({
                    "window": {
                        "id": row["id"],
                        "name": row["name"],
                        "description": row["description"] or "",
                        "window_type": row["window_type"] if "window_type" in keys and row["window_type"] else "maintenance",
                        "campus_id": row["campus_id"],
                        "starts_at": row["starts_at"],
                        "ends_at": row["ends_at"],
                        "notify_channel_ids": json.loads(row["notify_channel_ids_json"]) if "notify_channel_ids_json" in keys and row["notify_channel_ids_json"] else []
                    },
                    "reminder_type": reminder_type
                })
    return results

def mark_maintenance_window_reminded(window_id: str, reminder_type: str):
    """Marks a maintenance window as having sent a 24h or 2h reminder."""
    col = "reminded_2h" if reminder_type == "2h" else "reminded_24h"
    with get_connection() as conn:
        conn.execute(f"UPDATE maintenance_windows SET {col} = 1 WHERE id = ?;", (window_id,))
        conn.commit()

def get_active_maintenance_windows_for_alert(
    campus_id: Optional[str] = None,
    sensor_id: Optional[str] = None,
    probe_id: Optional[str] = None,
    alertname: Optional[str] = None,
    now_ts: Optional[int] = None
) -> Optional[dict]:
    """
    Checks if a firing alert falls within an active scheduled maintenance window matching scope.
    Returns the matching maintenance window dict or None if alert should NOT be suppressed.
    """
    import fnmatch
    now = now_ts or int(time.time())

    with get_connection() as conn:
        cursor = conn.execute("""
            SELECT * FROM maintenance_windows
            WHERE is_active = 1
              AND starts_at <= ?
              AND ends_at >= ?
            ORDER BY starts_at ASC;
        """, (now, now))

        for row in cursor.fetchall():
            # Check campus scope
            if row["campus_id"] and campus_id and row["campus_id"] != campus_id:
                continue
            # Check sensor scope
            if row["sensor_id"] and sensor_id and row["sensor_id"] != sensor_id:
                continue
            # Check probe scope
            if row["probe_id"] and probe_id and row["probe_id"] != probe_id:
                continue
            # Check alertname pattern
            if row["alertname_pattern"] and alertname:
                pattern = row["alertname_pattern"].lower()
                if not fnmatch.fnmatch(alertname.lower(), pattern) and pattern not in alertname.lower():
                    continue

            # Match confirmed!
            return {
                "id": row["id"],
                "name": row["name"],
                "description": row["description"] or "",
                "starts_at": row["starts_at"],
                "ends_at": row["ends_at"]
            }

    return None
