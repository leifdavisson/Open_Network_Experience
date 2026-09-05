import json
import time
import logging
from typing import List
from .connection import get_connection

logger = logging.getLogger(__name__)

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
