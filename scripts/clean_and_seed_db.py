#!/usr/bin/env python3
"""
Clean and Seed Script for Open Network Experience (ONE) Database.
Resets the SQLite database to a clean, production-grade baseline.
"""

import os
import sys
import sqlite3
import json
import time

def reset_db(db_path: str):
    print(f"Cleaning and seeding database at: {db_path}")
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")

    # Drop all existing tables
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
    for t in tables:
        if not t.startswith("sqlite_"):
            conn.execute(f"DROP TABLE IF EXISTS {t};")

    # Re-create tables
    conn.execute("""
        CREATE TABLE campuses (
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
        CREATE TABLE campus_subnets (
            id TEXT PRIMARY KEY,
            subnet_cidr TEXT NOT NULL UNIQUE,
            campus_id TEXT NOT NULL,
            campus_name TEXT NOT NULL,
            building_default TEXT DEFAULT 'Main Building',
            auto_approve BOOLEAN DEFAULT 1
        );
    """)
    conn.execute("""
        CREATE TABLE sensors (
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
    conn.execute("""
        CREATE TABLE probes (
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
        CREATE TABLE evidence (
            id TEXT PRIMARY KEY,
            sensor_id TEXT NOT NULL,
            timestamp INTEGER NOT NULL,
            trigger_reason TEXT,
            bundle_json TEXT
        );
    """)
    conn.execute("""
        CREATE TABLE schedules (
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

    now = int(time.time())

    # 1. Seed Campus
    conn.execute("""
        INSERT INTO campuses VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        "CAMPUS-WEST-HIGH",
        "West High School",
        "High School",
        "Metro Unified School District",
        35.3582,
        -119.0471,
        "1200 New St, Bakersfield, CA 93309",
        "tech@westhigh.edu",
        now
    ))

    # 2. Seed Campus Subnet
    conn.execute("""
        INSERT INTO campus_subnets VALUES (?, ?, ?, ?, ?, ?);
    """, (
        "sub-6110b487",
        "10.142.10.0/24",
        "CAMPUS-WEST-HIGH",
        "West High School",
        "Science Wing & STEM Lab",
        1
    ))

    # 3. Seed Clean Probers
    loc1 = {
        "district": "Metro Unified School District",
        "site": "West High School",
        "building": "Building A",
        "room": "Library Media Center",
        "notes": "Ceiling mount near AP-LIB-01",
        "latitude": 35.3582,
        "longitude": -119.0471,
        "is_gps_auto": False
    }
    containers1 = {
        "reconciler": {"image": "open-ux/sensor-reconciler:v0.4.0", "id": "rec-lib-01"},
        "wifi_dhcp_exporter": {"image": "open-ux/wifi-prober:v0.4.0", "id": "prober-lib-01"}
    }
    conn.execute("""
        INSERT INTO sensors VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        "sensor-whs-lib-01",
        "approved",
        "key_a1b2c3d4e5f60718293a4b5c6d7e8f90",
        "pi5-whs-library",
        "d8:3a:dd:24:60:11",
        "Debian GNU/Linux 12 (bookworm) aarch64",
        now,
        0,
        "CAMPUS-WEST-HIGH",
        "GREEN",
        json.dumps(loc1),
        json.dumps({}),
        json.dumps(containers1),
        now
    ))

    loc2 = {
        "district": "Metro Unified School District",
        "site": "West High School",
        "building": "Science Wing",
        "room": "STEM Robotics Lab 204",
        "notes": "Lab wall rack AP-STEM-02",
        "latitude": 35.3585,
        "longitude": -119.0475,
        "is_gps_auto": False
    }
    containers2 = {
        "reconciler": {"image": "open-ux/sensor-reconciler:v0.4.0", "id": "rec-stem-02"},
        "wifi_dhcp_exporter": {"image": "open-ux/wifi-prober:v0.4.0", "id": "prober-stem-02"}
    }
    conn.execute("""
        INSERT INTO sensors VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        "sensor-whs-stem-02",
        "approved",
        "key_f9e8d7c6b5a43210fedcba0987654321",
        "n100-whs-stem",
        "50:eb:f6:1a:2b:3c",
        "Ubuntu 22.04.4 LTS x86_64",
        now,
        0,
        "CAMPUS-WEST-HIGH",
        "GREEN",
        json.dumps(loc2),
        json.dumps({}),
        json.dumps(containers2),
        now
    ))

    # 4. Seed Probes
    conn.execute("""
        INSERT INTO probes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        "probe_caaspp",
        "CAASPP State Testing Readiness",
        "http",
        "https://caaspp.org",
        5,
        4.0,
        200,
        json.dumps(["all"]),
        1,
        now
    ))
    conn.execute("""
        INSERT INTO probes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        "probe_classroom",
        "Google Classroom & Drive SLA",
        "http",
        "https://classroom.google.com",
        5,
        4.0,
        200,
        json.dumps(["all"]),
        1,
        now
    ))

    # 5. Seed Schedules
    conn.execute("""
        INSERT INTO schedules VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        "sched_caaspp_morning",
        "Morning CAASPP Pre-Flight",
        "probe_caaspp",
        "daily_once",
        json.dumps(["mon", "tue", "wed", "thu", "fri"]),
        "07:15",
        "16:00",
        15,
        "minutes",
        None,
        "all",
        1,
        1,
        now
    ))
    conn.execute("""
        INSERT INTO schedules VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        "sched_classroom_school_hours",
        "Classroom SaaS Continuous SLA",
        "probe_classroom",
        "recurring_interval",
        json.dumps(["mon", "tue", "wed", "thu", "fri"]),
        "07:30",
        "16:30",
        15,
        "minutes",
        None,
        "all",
        1,
        1,
        now
    ))

    conn.commit()
    conn.close()
    print("Database cleaned and seeded successfully.")

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "/data/Open_Network_Experience/server/data/cmp.db"
    reset_db(target)
