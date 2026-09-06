# Standardized modular database package interface
from .connection import get_connection, DB_PATH
from .alerts import (
    _seed_default_alert_configs, load_all_alerts, load_alert_by_id,
    load_active_alert_by_fingerprint, save_alert, acknowledge_alert, resolve_alert,
    delete_alert, get_alerts_summary, load_all_alert_rules, load_alert_rule_by_id,
    save_alert_rule, toggle_alert_rule, delete_alert_rule, load_all_notification_channels,
    load_notification_channel_by_id, save_notification_channel, update_channel_dispatch_status,
    delete_notification_channel
)
from .maintenance import (
    load_all_maintenance_windows, load_maintenance_window_by_id,
    save_maintenance_window, toggle_maintenance_window, delete_maintenance_window,
    get_maintenance_windows_needing_reminders, mark_maintenance_window_reminded,
    get_active_maintenance_windows_for_alert
)
from .campuses import (
    load_all_campuses, save_campus, delete_campus,
    load_all_subnets, save_subnet_rule, delete_subnet_rule, match_subnet_auto_enroll
)
from .sensors import load_all_sensors, load_sensor, save_sensor, batch_save_sensors, batch_approve_sensors, delete_sensor
from .probes import load_all_probes, save_probe, delete_probe
from .schedules import load_all_schedules, save_schedule, delete_schedule, toggle_schedule
from .evidence import load_all_evidence, save_evidence, load_evidence_by_id
from .backup import export_backup_json, restore_backup_json
from .tsdb import enqueue_tsdb_spool, dequeue_tsdb_spool, delete_tsdb_spool_entries, increment_tsdb_spool_attempts, get_tsdb_spool_count, clear_tsdb_spool_queue

__all__ = [
    'get_connection',
    'DB_PATH',
    'init_db',
    'load_all_alerts', 'load_alert_by_id', 'load_active_alert_by_fingerprint', 'save_alert', 'acknowledge_alert', 'resolve_alert', 'delete_alert', 'get_alerts_summary',
    'load_all_alert_rules', 'load_alert_rule_by_id', 'save_alert_rule', 'toggle_alert_rule', 'delete_alert_rule',
    'load_all_notification_channels', 'load_notification_channel_by_id', 'save_notification_channel', 'update_channel_dispatch_status', 'delete_notification_channel',
    'load_all_maintenance_windows', 'load_maintenance_window_by_id', 'save_maintenance_window', 'toggle_maintenance_window', 'delete_maintenance_window', 'get_maintenance_windows_needing_reminders', 'mark_maintenance_window_reminded', 'get_active_maintenance_windows_for_alert',
    'load_all_campuses', 'save_campus', 'delete_campus', 'load_all_subnets', 'save_subnet_rule', 'delete_subnet_rule', 'match_subnet_auto_enroll',
    'load_all_sensors', 'load_sensor', 'save_sensor', 'batch_save_sensors', 'batch_approve_sensors', 'delete_sensor',
    'load_all_probes', 'save_probe', 'delete_probe',
    'load_all_schedules', 'save_schedule', 'delete_schedule', 'toggle_schedule',
    'load_all_evidence', 'save_evidence', 'load_evidence_by_id',
    'export_backup_json', 'restore_backup_json',
    'enqueue_tsdb_spool', 'dequeue_tsdb_spool', 'delete_tsdb_spool_entries', 'increment_tsdb_spool_attempts', 'get_tsdb_spool_count', 'clear_tsdb_spool_queue'
]


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
                ip_address TEXT,
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
        # Run schema migration for existing DBs that might lack campus_id, probing_state, or ip_address
        try:
            conn.execute("ALTER TABLE sensors ADD COLUMN campus_id TEXT;")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE sensors ADD COLUMN probing_state TEXT DEFAULT 'GREEN';")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE sensors ADD COLUMN ip_address TEXT;")
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id TEXT PRIMARY KEY,
                fingerprint TEXT NOT NULL,
                status TEXT NOT NULL,          -- 'firing', 'acknowledged', 'resolved'
                severity TEXT NOT NULL,        -- 'critical', 'warning', 'info'
                title TEXT NOT NULL,
                description TEXT,
                sensor_id TEXT,
                campus_id TEXT,
                probe_id TEXT,
                starts_at INTEGER NOT NULL,
                ends_at INTEGER,
                acknowledged_at INTEGER,
                acknowledged_by TEXT,
                resolution_notes TEXT,
                evidence_id TEXT,
                is_muted BOOLEAN DEFAULT 0,
                muted_by_window_id TEXT,
                muted_by_window_name TEXT,
                raw_labels_json TEXT,
                raw_annotations_json TEXT,
                updated_at INTEGER
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_fingerprint ON alerts(fingerprint);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_starts_at ON alerts(starts_at);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_campus ON alerts(campus_id);")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS custom_alert_rules (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                probe_id TEXT NOT NULL,
                metric TEXT NOT NULL,
                operator TEXT NOT NULL,
                threshold_value REAL NOT NULL,
                unit TEXT DEFAULT 'ms',
                duration_seconds INTEGER DEFAULT 30,
                severity TEXT NOT NULL DEFAULT 'critical',
                campus_id TEXT,
                sensor_id TEXT,
                channels_json TEXT,
                autocapture_pcap BOOLEAN DEFAULT 1,
                is_active BOOLEAN DEFAULT 1,
                created_at INTEGER,
                updated_at INTEGER
            );
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS notification_channels (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                channel_type TEXT NOT NULL,
                endpoint_url TEXT NOT NULL,
                auth_headers_json TEXT,
                min_severity TEXT NOT NULL DEFAULT 'warning',
                is_active BOOLEAN DEFAULT 1,
                last_dispatched_at INTEGER,
                last_status TEXT,
                created_at INTEGER,
                updated_at INTEGER
            );
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS maintenance_windows (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                window_type TEXT DEFAULT 'maintenance',
                campus_id TEXT,
                sensor_id TEXT,
                probe_id TEXT,
                alertname_pattern TEXT,
                starts_at INTEGER NOT NULL,
                ends_at INTEGER NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                reminded_24h BOOLEAN DEFAULT 0,
                reminded_2h BOOLEAN DEFAULT 0,
                notify_channel_ids_json TEXT,
                created_by TEXT DEFAULT 'NOC Admin',
                created_at INTEGER,
                updated_at INTEGER
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tsdb_spool_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                payload TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                attempts INTEGER DEFAULT 0
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tsdb_spool_created ON tsdb_spool_queue(created_at, attempts);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_maint_times ON maintenance_windows(starts_at, ends_at, is_active);")

        # Safe migrations for existing tables
        for col, ctype in [("is_muted", "BOOLEAN DEFAULT 0"), ("muted_by_window_id", "TEXT"), ("muted_by_window_name", "TEXT")]:
            try:
                conn.execute(f"ALTER TABLE alerts ADD COLUMN {col} {ctype};")
            except Exception:
                pass

        for col, ctype in [
            ("window_type", "TEXT DEFAULT 'maintenance'"),
            ("reminded_24h", "BOOLEAN DEFAULT 0"),
            ("reminded_2h", "BOOLEAN DEFAULT 0"),
            ("notify_channel_ids_json", "TEXT")
        ]:
            try:
                conn.execute(f"ALTER TABLE maintenance_windows ADD COLUMN {col} {ctype};")
            except Exception:
                pass

        conn.commit()

    # Seed default notification channels and alert configs if empty
    _seed_default_alert_configs()
