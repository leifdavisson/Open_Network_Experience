import json
import time
import logging
import os

from .campuses import load_all_campuses, save_campus, save_subnet_rule, load_all_subnets
from .sensors import load_all_sensors, save_sensor
from .probes import load_all_probes, save_probe
from .schedules import load_all_schedules, save_schedule
from .evidence import load_all_evidence, save_evidence
from .alerts import load_all_alerts, save_alert, load_all_alert_rules, save_alert_rule, load_all_notification_channels, save_notification_channel
from .maintenance import load_all_maintenance_windows, save_maintenance_window


logger = logging.getLogger(__name__)
BACKUP_DIR = "backups"
os.makedirs(BACKUP_DIR, exist_ok=True)

def export_backup_json() -> dict:
    """Exports complete database state as a portable JSON backup dictionary."""
    sensors = load_all_sensors()
    probes = load_all_probes()
    evidence = load_all_evidence()
    campuses = load_all_campuses()
    subnets = load_all_subnets()
    schedules = load_all_schedules()
    alerts = load_all_alerts(limit=5000)
    rules = load_all_alert_rules()
    channels = load_all_notification_channels() if 'load_all_notification_channels' in globals() else []
    maintenance_windows = load_all_maintenance_windows()

    backup_payload = {
        "platform": "Open Network Experience",
        "version": "0.6.1",
        "exported_at": int(time.time()),
        "export_date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sensors": sensors,
        "probes": probes,
        "evidence": evidence,
        "campuses": campuses,
        "subnets": subnets,
        "schedules": schedules,
        "alerts": alerts,
        "custom_alert_rules": rules,
        "notification_channels": channels,
        "maintenance_windows": maintenance_windows
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
    from . import init_db
    sensors = data.get("sensors", {})
    probes = data.get("probes", {})
    evidence = data.get("evidence", {})
    campuses = data.get("campuses", {})
    subnets = data.get("subnets", [])
    schedules = data.get("schedules", [])
    alerts = data.get("alerts", [])
    rules = data.get("custom_alert_rules", [])
    channels = data.get("notification_channels", [])
    maintenance_windows = data.get("maintenance_windows", [])

    init_db()

    for c_id, c_data in campuses.items():
        save_campus(c_data)

    for rule in subnets:
        save_subnet_rule(rule)

    for s_id, s_data in sensors.items():
        save_sensor(s_data)

    for p_id, p_data in probes.items():
        save_probe(p_data)

    for sch in schedules:
        save_schedule(sch)

    for s_id, ev_list in evidence.items():
        for bundle in ev_list:
            save_evidence(s_id, bundle)

    for alt in alerts:
        save_alert(alt)

    for r in rules:
        save_alert_rule(r)

    if 'save_notification_channel' in globals():
        for ch in channels:
            save_notification_channel(ch)

    for mw in maintenance_windows:
        save_maintenance_window(mw)

    return True
