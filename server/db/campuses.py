import time
import logging
from typing import Dict, List, Optional
from .connection import get_connection

logger = logging.getLogger(__name__)

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
