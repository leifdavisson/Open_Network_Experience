"""
Open Network Experience (ONE) - Alertmanager Ingestion, Lifecycle & Outbound Webhook Router
Copyright (C) 2026 Open Network Experience Authors.
Licensed under the GNU Affero General Public License v3.0 (AGPLv3).
"""

import asyncio
import hashlib
import json
import smtplib
import ssl
import time
import uuid
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional, Dict, Any

import httpx
from fastapi import APIRouter, HTTPException, Query, Request, status

import server.db as db
from server.state import EVIDENCE_DB
from server.schemas import (
    AlertRecord,
    AlertAcknowledgeRequest,
    AlertResolveRequest,
    AlertSimulateRequest,
    AlertSummaryResponse,
    CustomAlertRuleSpec,
    NotificationChannelSpec,
    ChannelTestRequest,
    MaintenanceWindowSpec
)

router = APIRouter(tags=["Alerts & Alertmanager"])


def _parse_iso_timestamp(ts_str: Optional[str]) -> Optional[int]:
    """Parses ISO8601 datetime string to UTC epoch timestamp."""
    if not ts_str or ts_str.startswith("0001-01-01"):
        return None
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return int(dt.timestamp())
    except Exception:
        return int(time.time())


def _compute_alert_fingerprint(labels: Dict[str, Any]) -> str:
    """Computes a deterministic fingerprint for an alert based on identifying labels."""
    if not labels:
        return f"fp-{uuid.uuid4().hex[:12]}"
    sorted_items = sorted((str(k), str(v)) for k, v in labels.items() if k not in ("severity", "value"))
    hash_src = "|".join(f"{k}={v}" for k, v in sorted_items)
    return f"fp-{hashlib.sha256(hash_src.encode('utf-8')).hexdigest()[:16]}"


def _generate_pcap_evidence_bundle(
    sensor_id: Optional[str],
    alertname: str,
    title: str,
    description: str,
    probe_id: Optional[str]
) -> dict:
    """Simulates an edge-sensor freezing its 32MB circular RAM ring-buffer into an immutable PCAP evidence bundle."""
    now = int(time.time())
    b_id = f"ev-pcap-{now}-{uuid.uuid4().hex[:6]}"
    target_sensor = sensor_id or "pi5-edge-noc-01"

    bundle = {
        "id": b_id,
        "bundle_id": b_id,
        "sensor_id": target_sensor,
        "timestamp": now,
        "trigger_reason": f"Automatic PCAP Freeze for Alarm: {alertname} ({title})",
        "reason": f"Automatic PCAP Freeze for Alarm: {alertname} ({title})",
        "filename": f"{b_id}.pcap",
        "size_bytes": 1843200,
        "probe_id": probe_id or "synthetic_engine",
        "pcap_file": f"/var/log/open-ux/captures/{b_id}.pcap",
        "pcap_size_bytes": 1843200,
        "packets_captured": 4500,
        "interfaces": ["eno1", "wlp1s0"],
        "sha256": uuid.uuid4().hex,
        "ring_buffer_seconds": 60,
        "dissection": {
            "protocols": ["ETH", "IP", "TCP", "TLSv1.3", "DNS", "ICMP"],
            "top_talkers": [
                {"src": "10.100.4.15", "dst": "10.100.0.1", "packets": 480, "bytes": 624000},
                {"src": "10.100.4.15", "dst": "8.8.8.8", "packets": 210, "bytes": 158000}
            ],
            "tcp_flags": {"SYN": 45, "ACK": 1200, "RST": 12, "FIN": 38},
            "anomalies_detected": [
                "TCP Retransmission Rate > 4.2%",
                "TLS ServerHello Certificate Issuer: Self-Signed / SSL-Inspection Proxy"
            ]
        },
        "created_at": now
    }

    db.save_evidence(target_sensor, bundle)
    return bundle


def _severity_rank(sev: str) -> int:
    ranks = {"info": 1, "warning": 2, "critical": 3}
    return ranks.get(sev.lower(), 1)


async def dispatch_alert_notifications(alert: Optional[dict]):
    """
    Asynchronously formats and sends outbound webhook notifications to all enabled channels
    whose min_severity threshold is satisfied. Suppresses dispatch if alert is within an active muting window.
    """
    if not alert:
        return
    if alert.get("is_muted"):
        # Alert was generated during an active scheduled maintenance window -> suppress push notifications
        return

    channels = db.load_all_notification_channels(active_only=True)
    if not channels:
        return

    alert_sev_rank = _severity_rank(alert.get("severity", "warning"))
    tasks = []

    for chan in channels:
        chan_min_rank = _severity_rank(chan.get("min_severity", "warning"))
        if alert_sev_rank >= chan_min_rank:
            tasks.append(_send_single_notification(chan, alert))

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


def _send_smtp_sync(chan: dict, alert: dict) -> bool:
    """Synchronous worker that constructs and dispatches MIME multipart email via SMTP."""
    auth_config = chan.get("auth_headers") or {}
    endpoint = chan.get("endpoint_url", "")

    # Extract host and port
    if ":" in endpoint and not endpoint.startswith("http"):
        parts = endpoint.split(":")
        smtp_host = parts[0]
        try:
            smtp_port = int(parts[1])
        except Exception:
            smtp_port = 587
    else:
        smtp_host = auth_config.get("smtp_host") or endpoint or "smtp-relay.gmail.com"
        smtp_port = int(auth_config.get("smtp_port") or 587)

    security_mode = (auth_config.get("security_mode") or ("ssl_tls" if smtp_port == 465 else "starttls")).lower()
    from_email = auth_config.get("from_email") or "noc-alerts@district.edu"
    from_name = auth_config.get("from_name") or "ONE Platform Alerts"
    recipients_raw = auth_config.get("recipients") or []
    if isinstance(recipients_raw, str):
        recipients = [r.strip() for r in recipients_raw.split(",") if r.strip()]
    else:
        recipients = list(recipients_raw)

    if not recipients:
        recipients = ["noc@district.edu"]

    username = auth_config.get("username")
    password = auth_config.get("password")

    # Mock / simulation detection for testing without live SMTP server
    if "example.com" in smtp_host or smtp_host == "mock-smtp" or (smtp_host == "smtp-relay.gmail.com" and not password and not auth_config.get("live_relay")):
        db.update_channel_dispatch_status(chan["id"], f"Simulated Email ({len(recipients)} rcpt)")
        return True

    status_icon = "🚨" if alert.get("status") == "firing" else "✅"
    title = alert.get("title", "Network Alarm")
    severity = alert.get("severity", "warning").upper()
    campus = alert.get("campus_id", "District Fleet")
    sensor = alert.get("sensor_id", "Edge Prober")
    desc = alert.get("description", "No details provided.")
    probe_id = alert.get("probe_id", "N/A")
    alert_id = alert.get("id", "N/A")
    trigger_time = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(alert.get("starts_at", time.time())))

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"{status_icon} [{severity}] {title} — {campus}"
    msg["From"] = f'"{from_name}" <{from_email}>'
    msg["To"] = ", ".join(recipients)
    msg["X-Priority"] = "1" if severity == "CRITICAL" else "3"

    text_content = f"""===================================================================
{status_icon} [{severity}] {title}
Open Network Experience (ONE) - High-Assurance K-12 Telemetry
===================================================================

Status:       {alert.get("status", "firing").upper()}
Severity:     {severity}
Campus:       {campus}
Sensor Host:  {sensor}
Probe ID:     {probe_id}
Incident ID:  {alert_id}
Triggered At: {trigger_time}

Description:
{desc}

-------------------------------------------------------------------
View live incident details and PCAP forensics in the ONE Console:
http://localhost:8000/#view-monitor-alerts
===================================================================
"""

    sev_color = "#ef4444" if severity == "CRITICAL" else "#f59e0b" if severity == "WARNING" else "#3b82f6"
    html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f3f4f6; margin: 0; padding: 20px; }}
  .card {{ max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 8px; overflow: hidden; border: 1px solid #e5e7eb; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }}
  .header {{ background-color: {sev_color}; color: #ffffff; padding: 18px 24px; }}
  .header h1 {{ margin: 0; font-size: 18px; font-weight: 700; }}
  .body {{ padding: 24px; color: #1f2937; }}
  .metric-table {{ width: 100%; border-collapse: collapse; margin: 16px 0; }}
  .metric-table td {{ padding: 8px 12px; border-bottom: 1px solid #f3f4f6; font-size: 13px; }}
  .metric-table td.label {{ font-weight: 600; color: #6b7280; width: 35%; }}
  .description-box {{ background: #f9fafb; border-left: 4px solid {sev_color}; padding: 12px 16px; margin: 16px 0; font-size: 13px; color: #374151; }}
  .btn {{ display: inline-block; background-color: {sev_color}; color: #ffffff; text-decoration: none; padding: 10px 20px; border-radius: 6px; font-weight: 600; font-size: 13px; margin-top: 12px; }}
  .footer {{ background: #f9fafb; border-top: 1px solid #e5e7eb; padding: 12px 24px; font-size: 11px; color: #9ca3af; text-align: center; }}
</style>
</head>
<body>
  <div class="card">
    <div class="header">
      <h1>{status_icon} [{severity}] {title}</h1>
    </div>
    <div class="body">
      <p style="margin-top:0; font-size:14px;">An alert threshold condition has been triggered on your district network monitoring fleet.</p>

      <div class="description-box">
        <strong>Root Cause / Condition:</strong><br>
        {desc}
      </div>

      <table class="metric-table">
        <tr><td class="label">Incident Status:</td><td><strong>{alert.get("status", "firing").upper()}</strong></td></tr>
        <tr><td class="label">Campus Location:</td><td>{campus}</td></tr>
        <tr><td class="label">Sensor Probe Host:</td><td><code>{sensor}</code></td></tr>
        <tr><td class="label">Synthetic Probe:</td><td>{probe_id}</td></tr>
        <tr><td class="label">Triggered Timestamp:</td><td>{trigger_time}</td></tr>
        <tr><td class="label">Incident Tracking ID:</td><td><code>{alert_id}</code></td></tr>
      </table>

      <div style="text-align: center; margin-top: 20px;">
        <a href="http://localhost:8000/#view-monitor-alerts" class="btn" style="color:#ffffff;">🚨 Triage & Inspect PCAP in Alert Center ➔</a>
      </div>
    </div>
    <div class="footer">
      Open Network Experience (ONE) Platform &bull; Automated K-12 Telemetry &bull; Confidential District IT Notice
    </div>
  </div>
</body>
</html>"""

    msg.attach(MIMEText(text_content, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        server: Any
        if security_mode == "ssl_tls" or smtp_port == 465:
            ssl_ctx = ssl.create_default_context()
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, context=ssl_ctx, timeout=8.0)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=8.0)
            if security_mode == "starttls" or (security_mode != "none" and smtp_port == 587):
                ssl_ctx = ssl.create_default_context()
                server.starttls(context=ssl_ctx)

        if username and password:
            server.login(username, password)

        server.send_message(msg)
        server.quit()
        db.update_channel_dispatch_status(chan["id"], f"Sent Email ({len(recipients)} rcpt)")
        return True
    except Exception as ex:
        db.update_channel_dispatch_status(chan["id"], f"SMTP Error: {str(ex)[:35]}")
        return False


async def _send_single_notification(chan: dict, alert: dict) -> bool:
    """Sends formatted HTTP webhook or SMTP email to a specific notification channel."""
    c_type = chan.get("channel_type", "webhook").lower()
    url = chan.get("endpoint_url", "")

    if c_type == "email":
        return await asyncio.to_thread(_send_smtp_sync, chan, alert)

    if not url or url.startswith("https://hooks.slack.com/services/T00/B00/X00"):
        # Skip mock/dummy URL
        db.update_channel_dispatch_status(chan["id"], "Simulated (Mock URL)")
        return True

    headers = {"Content-Type": "application/json", "User-Agent": "ONE-CMP-Alerts/1.0"}
    if chan.get("auth_headers"):
        headers.update(chan["auth_headers"])

    status_icon = "🚨" if alert.get("status") == "firing" else "✅"
    title = alert.get("title", "Network Alarm")
    severity = alert.get("severity", "warning").upper()
    campus = alert.get("campus_id", "District Fleet")
    sensor = alert.get("sensor_id", "Edge Prober")

    payload: Dict[str, Any] = {}

    if c_type == "slack":
        color = "#ef4444" if severity == "CRITICAL" else "#f59e0b" if severity == "WARNING" else "#3b82f6"
        payload = {
            "text": f"{status_icon} *[{severity}] {title}*",
            "attachments": [
                {
                    "color": color,
                    "fields": [
                        {"title": "Status", "value": alert.get("status", "firing").upper(), "short": True},
                        {"title": "Campus", "value": campus, "short": True},
                        {"title": "Sensor Host", "value": sensor, "short": True},
                        {"title": "Probe ID", "value": alert.get("probe_id", "N/A"), "short": True},
                        {"title": "Description", "value": alert.get("description", "No details provided."), "short": False}
                    ],
                    "footer": "Open Network Experience (ONE) Platform",
                    "ts": alert.get("starts_at", int(time.time()))
                }
            ]
        }
    elif c_type == "teams":
        theme_color = "EA4335" if severity == "CRITICAL" else "FBBC05" if severity == "WARNING" else "4285F4"
        payload = {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "summary": f"{severity}: {title}",
            "themeColor": theme_color,
            "title": f"{status_icon} [{severity}] {title}",
            "sections": [
                {
                    "facts": [
                        {"name": "Status", "value": alert.get("status", "firing").upper()},
                        {"name": "Campus", "value": campus},
                        {"name": "Sensor", "value": sensor},
                        {"name": "Triggered At", "value": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(alert.get("starts_at", time.time())))}
                    ],
                    "text": alert.get("description", "")
                }
            ]
        }
    else:
        # Generic ITSM / ServiceNow / Jira JSON
        payload = {
            "event": "alert.lifecycle",
            "alert_id": alert.get("id"),
            "fingerprint": alert.get("fingerprint"),
            "status": alert.get("status"),
            "severity": alert.get("severity"),
            "title": title,
            "description": alert.get("description"),
            "campus_id": campus,
            "sensor_id": sensor,
            "probe_id": alert.get("probe_id"),
            "evidence_id": alert.get("evidence_id"),
            "starts_at": alert.get("starts_at"),
            "ends_at": alert.get("ends_at"),
            "timestamp": int(time.time())
        }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code < 300:
                db.update_channel_dispatch_status(chan["id"], f"Delivered ({resp.status_code})")
                return True
            else:
                db.update_channel_dispatch_status(chan["id"], f"HTTP Error {resp.status_code}")
                return False
    except Exception as ex:
        db.update_channel_dispatch_status(chan["id"], f"Network Error: {str(ex)[:30]}")
        return False


# --- INGESTION WEBHOOKS ---

@router.post(
    "/api/v1/alerts/webhook",
    summary="Prometheus Alertmanager Webhook Ingestion Receiver",
    status_code=status.HTTP_200_OK
)
@router.post(
    "/api/v1/alerts",
    summary="Prometheus Alertmanager Webhook Ingestion Receiver (Alias)",
    status_code=status.HTTP_200_OK
)
async def alertmanager_webhook(request: Request) -> Dict[str, Any]:
    """
    Receives standard Prometheus Alertmanager webhook payloads.
    Deduplicates alerts by fingerprint, updates lifecycle state (firing vs resolved),
    automatically triggers forensic PCAP capture for critical/warning events,
    dispatches outbound notifications, and records full forensic metadata to SQLite.
    """
    try:
        raw_body = await request.body()
        if not raw_body:
            return {"status": "ignored", "reason": "empty body"}
        payload_data = json.loads(raw_body.decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON payload: {e}")

    alerts_list = payload_data.get("alerts", [])
    now = int(time.time())
    processed_count = 0
    resolved_count = 0
    firing_count = 0

    for item in alerts_list:
        labels = item.get("labels", {})
        annotations = item.get("annotations", {})
        item_status = item.get("status", payload_data.get("status", "firing")).lower()
        fp = item.get("fingerprint") or _compute_alert_fingerprint(labels)

        starts_at = _parse_iso_timestamp(item.get("startsAt")) or now
        alertname = labels.get("alertname", "NetworkAlarm")
        title = annotations.get("summary") or annotations.get("title") or alertname
        description = annotations.get("description") or annotations.get("summary") or ""
        severity = labels.get("severity", "warning").lower()
        sensor_id = labels.get("sensor_id")
        campus_id = labels.get("campus_id")
        probe_id = labels.get("probe_id")
        evidence_id = labels.get("evidence_id") or annotations.get("evidence_id")

        # Auto-trigger PCAP evidence capture if not already provided
        autocapture_flag = labels.get("autocapture_pcap", "true").lower() == "true"
        if item_status == "firing" and not evidence_id and (autocapture_flag or severity in ("critical", "warning")):
            pcap_bundle = _generate_pcap_evidence_bundle(sensor_id, alertname, title, description, probe_id)
            evidence_id = pcap_bundle["id"]

        active_alert = db.load_active_alert_by_fingerprint(fp)

        # Check active maintenance window / muting suppression
        maint_window = db.get_active_maintenance_windows_for_alert(
            campus_id=campus_id,
            sensor_id=sensor_id,
            probe_id=probe_id,
            alertname=alertname,
            now_ts=now
        )
        is_muted = maint_window is not None
        muted_by_id = maint_window["id"] if maint_window else None
        muted_by_name = maint_window["name"] if maint_window else None

        if item_status == "firing":
            firing_count += 1
            if active_alert:
                active_alert["title"] = title
                active_alert["description"] = description
                active_alert["severity"] = severity
                active_alert["sensor_id"] = sensor_id or active_alert.get("sensor_id")
                active_alert["campus_id"] = campus_id or active_alert.get("campus_id")
                active_alert["probe_id"] = probe_id or active_alert.get("probe_id")
                active_alert["evidence_id"] = evidence_id or active_alert.get("evidence_id")
                active_alert["is_muted"] = is_muted
                active_alert["muted_by_window_id"] = muted_by_id
                active_alert["muted_by_window_name"] = muted_by_name
                active_alert["raw_labels"] = labels
                active_alert["raw_annotations"] = annotations
                active_alert["updated_at"] = now
                db.save_alert(active_alert)
                await dispatch_alert_notifications(active_alert)
            else:
                new_alert = {
                    "id": f"alt-{now}-{uuid.uuid4().hex[:6]}",
                    "fingerprint": fp,
                    "status": "firing",
                    "severity": severity,
                    "title": title,
                    "description": description,
                    "sensor_id": sensor_id,
                    "campus_id": campus_id,
                    "probe_id": probe_id,
                    "starts_at": starts_at,
                    "ends_at": None,
                    "evidence_id": evidence_id,
                    "is_muted": is_muted,
                    "muted_by_window_id": muted_by_id,
                    "muted_by_window_name": muted_by_name,
                    "raw_labels": labels,
                    "raw_annotations": annotations,
                    "updated_at": now
                }
                db.save_alert(new_alert)
                await dispatch_alert_notifications(new_alert)
        elif item_status == "resolved":
            resolved_count += 1
            if active_alert:
                res_alert = db.resolve_alert(active_alert["id"], resolution_notes="Auto-resolved by Prometheus Alertmanager webhook.")
                if res_alert:
                    await dispatch_alert_notifications(res_alert)

        processed_count += 1

    return {
        "status": "success",
        "processed_alerts": processed_count,
        "firing_updated": firing_count,
        "resolved_updated": resolved_count,
        "timestamp": now
    }


# --- ALERT RECORDS & SUMMARY ---

@router.get(
    "/api/v1/alerts",
    response_model=List[AlertRecord],
    summary="List Alerts with Multi-Criteria Filtering"
)
async def list_alerts(
    status: Optional[str] = Query(None, description="Filter: active, firing, acknowledged, resolved, or all"),
    severity: Optional[str] = Query(None, description="Filter: critical, warning, info, or all"),
    campus_id: Optional[str] = Query(None, description="Campus identifier filter"),
    sensor_id: Optional[str] = Query(None, description="Sensor identifier filter"),
    limit: int = Query(100, ge=1, le=1000, description="Max records to return"),
    offset: int = Query(0, ge=0, description="Pagination offset")
) -> List[dict]:
    """Retrieves alerts matching criteria sorted by priority and recency."""
    return db.load_all_alerts(
        status=status,
        severity=severity,
        campus_id=campus_id,
        sensor_id=sensor_id,
        limit=limit,
        offset=offset
    )


@router.get(
    "/api/v1/alerts/summary",
    response_model=AlertSummaryResponse,
    summary="Get Alert Aggregation Metrics & KPI Counts"
)
async def get_alerts_summary() -> dict:
    """Returns real-time aggregate statistics for alarms (active, critical, warning, resolved)."""
    return db.get_alerts_summary()


# --- 3. CONFIGURE: CUSTOM ALERT RULES REST API (must come before /{alert_id} catch-all) ---

@router.get(
    "/api/v1/alerts/rules",
    response_model=List[CustomAlertRuleSpec],
    summary="List Configured Custom Alert Rules"
)
async def list_alert_rules() -> List[dict]:
    """Lists all custom detection rules and threshold triggers."""
    return db.load_all_alert_rules()


@router.post(
    "/api/v1/alerts/rules",
    response_model=CustomAlertRuleSpec,
    summary="Create or Update Custom Alert Rule"
)
async def save_custom_alert_rule(rule: CustomAlertRuleSpec) -> dict:
    """Creates or updates a custom detection rule with metric threshold and target scope."""
    rule_dict = rule.model_dump()
    saved_id = db.save_alert_rule(rule_dict)
    loaded = db.load_alert_rule_by_id(saved_id)
    if not loaded:
        raise HTTPException(status_code=500, detail="Failed to save custom alert rule.")
    return loaded


@router.get(
    "/api/v1/alerts/rules/{rule_id}",
    response_model=CustomAlertRuleSpec,
    summary="Get Custom Alert Rule by ID"
)
async def get_alert_rule(rule_id: str) -> dict:
    """Fetches a single custom alert rule by ID."""
    rule = db.load_alert_rule_by_id(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Alert rule '{rule_id}' not found.")
    return rule


@router.post(
    "/api/v1/alerts/rules/{rule_id}/toggle",
    response_model=CustomAlertRuleSpec,
    summary="Toggle Custom Alert Rule State"
)
async def toggle_rule_state(rule_id: str) -> dict:
    """Toggles active/paused state of a custom alert rule."""
    updated = db.toggle_alert_rule(rule_id)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Alert rule '{rule_id}' not found.")
    return updated


@router.delete(
    "/api/v1/alerts/rules/{rule_id}",
    summary="Delete Custom Alert Rule"
)
async def delete_rule(rule_id: str) -> Dict[str, Any]:
    """Removes a custom alert rule."""
    deleted = db.delete_alert_rule(rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Alert rule '{rule_id}' not found.")
    return {"status": "success", "message": f"Alert rule '{rule_id}' deleted."}


# --- 4. SETUP: OUTBOUND NOTIFICATION CHANNELS & WEBHOOKS REST API (must come before /{alert_id} catch-all) ---

@router.get(
    "/api/v1/alerts/channels",
    response_model=List[NotificationChannelSpec],
    summary="List Outbound Notification Channels"
)
async def list_notification_channels() -> List[dict]:
    """Lists configured webhook notification channels (Slack, MS Teams, PagerDuty, ITSM)."""
    return db.load_all_notification_channels()


@router.post(
    "/api/v1/alerts/channels",
    response_model=NotificationChannelSpec,
    summary="Create or Update Notification Channel"
)
async def save_notification_channel_endpoint(chan: NotificationChannelSpec) -> dict:
    """Saves an outbound notification channel or webhook configuration."""
    chan_dict = chan.model_dump()
    saved_id = db.save_notification_channel(chan_dict)
    loaded = db.load_notification_channel_by_id(saved_id)
    if not loaded:
        raise HTTPException(status_code=500, detail="Failed to save notification channel.")
    return loaded


@router.get(
    "/api/v1/alerts/channels/{channel_id}",
    response_model=NotificationChannelSpec,
    summary="Get Notification Channel by ID"
)
async def get_notification_channel(channel_id: str) -> dict:
    """Fetches a single notification channel configuration."""
    chan = db.load_notification_channel_by_id(channel_id)
    if not chan:
        raise HTTPException(status_code=404, detail=f"Notification channel '{channel_id}' not found.")
    return chan


@router.post(
    "/api/v1/alerts/channels/{channel_id}/test",
    summary="Send Test Notification to Channel"
)
async def test_notification_channel(channel_id: str, req: ChannelTestRequest = ChannelTestRequest()) -> Dict[str, Any]:
    """Dispatches a test notification message to verify webhook connectivity."""
    chan = db.load_notification_channel_by_id(channel_id)
    if not chan:
        raise HTTPException(status_code=404, detail=f"Notification channel '{channel_id}' not found.")

    test_alert = {
        "id": f"alt-test-{int(time.time())}",
        "fingerprint": "fp-test-webhook",
        "status": "firing",
        "severity": req.sample_severity or "warning",
        "title": req.sample_title or "Test Webhook Dispatch",
        "description": req.sample_message or "Verifying outbound webhook connectivity from ONE Platform.",
        "campus_id": "CAMPUS-WEST-HIGH",
        "sensor_id": "pi5-science-01",
        "probe_id": "webhook_test",
        "starts_at": int(time.time())
    }

    success = await _send_single_notification(chan, test_alert)
    updated = db.load_notification_channel_by_id(channel_id)
    return {
        "status": "success" if success else "failed",
        "delivered": success,
        "channel": updated
    }


@router.delete(
    "/api/v1/alerts/channels/{channel_id}",
    summary="Delete Notification Channel"
)
async def delete_channel_endpoint(channel_id: str) -> Dict[str, Any]:
    """Deletes a notification channel configuration."""
    deleted = db.delete_notification_channel(channel_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Notification channel '{channel_id}' not found.")
    return {"status": "success", "message": f"Notification channel '{channel_id}' deleted."}


# --- 3. CONFIGURE: MAINTENANCE & MUTING WINDOWS REST API (must come before /{alert_id} catch-all) ---

@router.get(
    "/api/v1/alerts/maintenance-windows",
    response_model=List[MaintenanceWindowSpec],
    summary="List Scheduled Maintenance & Muting Windows"
)
async def list_maintenance_windows(active_only: bool = Query(False, description="Filter for active windows only")) -> List[dict]:
    """Lists all scheduled and active maintenance/muting windows."""
    return db.load_all_maintenance_windows(active_only=active_only)


@router.post(
    "/api/v1/alerts/maintenance-windows",
    response_model=MaintenanceWindowSpec,
    summary="Create or Update Maintenance Window"
)
async def save_maintenance_window_endpoint(window: MaintenanceWindowSpec) -> dict:
    """Creates or updates a scheduled IT maintenance window with time and scope criteria."""
    w_dict = window.model_dump()
    saved_id = db.save_maintenance_window(w_dict)
    loaded = db.load_maintenance_window_by_id(saved_id)
    if not loaded:
        raise HTTPException(status_code=500, detail="Failed to save maintenance window.")
    return loaded


@router.get(
    "/api/v1/alerts/maintenance-windows/active-now",
    response_model=List[MaintenanceWindowSpec],
    summary="Get Currently Active Maintenance Windows"
)
async def get_active_maintenance_windows_now() -> List[dict]:
    """Returns maintenance windows that are currently active right now."""
    now = int(time.time())
    windows = db.load_all_maintenance_windows(active_only=True)
    return [w for w in windows if w["starts_at"] <= now <= w["ends_at"]]


@router.get(
    "/api/v1/alerts/maintenance-windows/{window_id}",
    response_model=MaintenanceWindowSpec,
    summary="Get Maintenance Window by ID"
)
async def get_maintenance_window(window_id: str) -> dict:
    """Fetches a single maintenance window configuration."""
    w = db.load_maintenance_window_by_id(window_id)
    if not w:
        raise HTTPException(status_code=404, detail=f"Maintenance window '{window_id}' not found.")
    return w


@router.post(
    "/api/v1/alerts/maintenance-windows/{window_id}/toggle",
    response_model=MaintenanceWindowSpec,
    summary="Toggle Maintenance Window State"
)
async def toggle_maintenance_window_state(window_id: str) -> dict:
    """Toggles active/disabled state of a maintenance window."""
    updated = db.toggle_maintenance_window(window_id)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Maintenance window '{window_id}' not found.")
    return updated


@router.delete(
    "/api/v1/alerts/maintenance-windows/{window_id}",
    summary="Delete Maintenance Window"
)
async def delete_maintenance_window_endpoint(window_id: str) -> Dict[str, Any]:
    """Removes a maintenance window configuration."""
    deleted = db.delete_maintenance_window(window_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Maintenance window '{window_id}' not found.")
    return {"status": "success", "message": f"Maintenance window '{window_id}' deleted."}


@router.post(
    "/api/v1/alerts/maintenance-windows/check-reminders",
    summary="Check and Dispatch Maintenance Expiration Reminders (24h & 2h Warnings)"
)
async def check_and_dispatch_maintenance_reminders() -> Dict[str, Any]:
    """
    Evaluates all active maintenance windows and dispatches 24-hour or 2-hour expiration warning notifications
    to configured outbound channels (Slack, Teams, Email, ITSM).
    """
    items = db.get_maintenance_windows_needing_reminders()
    dispatched = []

    for item in items:
        win = item["window"]
        rem_type = item["reminder_type"]
        rem_label = "24 Hours" if rem_type == "24h" else "2 Hours"
        end_time_str = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(win["ends_at"]))
        win_type_label = "Facility Construction / Rewiring" if win.get("window_type") == "construction" else "Scheduled IT Maintenance"

        reminder_alert = {
            "id": f"maint-rem-{win['id']}-{rem_type}",
            "fingerprint": f"fp-maint-rem-{win['id']}",
            "status": "firing",
            "severity": "warning",
            "title": f"⚠️ {win_type_label} Expiring in {rem_label}: {win['name']}",
            "description": f"The muting window for '{win['name']}' ({win.get('description') or 'Scheduled Window'}) is set to expire in {rem_label} at {end_time_str}. Standard automated alerting will resume across all monitored probes upon expiration.",
            "campus_id": win.get("campus_id"),
            "starts_at": int(time.time()),
            "evidence_id": None
        }

        # Find target channels
        channels = db.load_all_notification_channels(active_only=True)
        if win.get("notify_channel_ids"):
            channels = [c for c in channels if c["id"] in win["notify_channel_ids"]]

        tasks = [_send_single_notification(c, reminder_alert) for c in channels]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        db.mark_maintenance_window_reminded(win["id"], rem_type)
        dispatched.append({
            "window_id": win["id"],
            "window_name": win["name"],
            "reminder_type": rem_type,
            "channel_count": len(channels)
        })

    return {
        "status": "success",
        "reminders_dispatched": len(dispatched),
        "details": dispatched
    }


# --- ALERT RECORD DETAIL & LIFECYCLE (parameterized /{alert_id} — must come AFTER all literal sub-paths) ---

@router.get(
    "/api/v1/alerts/{alert_id}",
    response_model=AlertRecord,
    summary="Get Detailed Alert by ID"
)
async def get_alert(alert_id: str) -> dict:
    """Fetches a single alert record with complete raw annotations and evidence bindings."""
    alert = db.load_alert_by_id(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found.")
    return alert


@router.get(
    "/api/v1/alerts/{alert_id}/evidence",
    summary="Get Linked PCAP Forensic Evidence Bundle for Alert"
)
async def get_alert_evidence(alert_id: str) -> dict:
    """Fetches the detailed PCAP and packet forensic bundle bound to an alert."""
    alert = db.load_alert_by_id(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found.")

    evidence_id = alert.get("evidence_id")
    if not evidence_id:
        raise HTTPException(status_code=404, detail=f"No forensic evidence bundle attached to alert '{alert_id}'.")

    evidence = db.load_evidence_by_id(evidence_id)
    if not evidence:
        for s_list in EVIDENCE_DB.values():
            for b in s_list:
                if b.get("id") == evidence_id or b.get("bundle_id") == evidence_id:
                    return b
        raise HTTPException(status_code=404, detail=f"Evidence bundle '{evidence_id}' not found.")
    return evidence


@router.post(
    "/api/v1/alerts/{alert_id}/capture-pcap",
    summary="Trigger Manual PCAP Freeze & Attach to Alert"
)
async def capture_alert_pcap(alert_id: str) -> dict:
    """Triggers an immediate ring-buffer packet freeze on the sensor and binds evidence to the alert."""
    alert = db.load_alert_by_id(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found.")

    bundle = _generate_pcap_evidence_bundle(
        alert.get("sensor_id"),
        alert.get("raw_labels", {}).get("alertname", "ManualTrigger"),
        alert.get("title", "Manual PCAP Freeze"),
        alert.get("description", "On-demand operator PCAP trigger."),
        alert.get("probe_id")
    )
    alert["evidence_id"] = bundle["id"]
    alert["updated_at"] = int(time.time())
    db.save_alert(alert)
    return {"status": "success", "evidence_id": bundle["id"], "evidence": bundle}


@router.post(
    "/api/v1/alerts/{alert_id}/acknowledge",
    response_model=AlertRecord,
    summary="Acknowledge Active Alarm"
)
@router.post(
    "/api/v1/alerts/{alert_id}/ack",
    response_model=AlertRecord,
    summary="Acknowledge Active Alarm (Alias)"
)
async def acknowledge_alert(alert_id: str, payload: AlertAcknowledgeRequest = AlertAcknowledgeRequest()) -> dict:
    """Transitions an alert from firing to acknowledged, capturing operator ID and timestamp."""
    updated = db.acknowledge_alert(alert_id, acknowledged_by=payload.acknowledged_by or "NOC Operator")
    if not updated:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found.")
    return updated


@router.post(
    "/api/v1/alerts/{alert_id}/resolve",
    response_model=AlertRecord,
    summary="Manually Resolve / Close Alarm"
)
async def resolve_alert(alert_id: str, payload: AlertResolveRequest = AlertResolveRequest()) -> dict:
    """Closes an active alarm with operator resolution notes and notifies outbound webhooks."""
    updated = db.resolve_alert(alert_id, resolution_notes=payload.resolution_notes or "Resolved via CMP Console")
    if not updated:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found.")
    await dispatch_alert_notifications(updated)
    return updated


@router.post(
    "/api/v1/alerts/simulate",
    response_model=AlertRecord,
    summary="Simulate / Trigger Test Alert"
)
async def simulate_alert(req: AlertSimulateRequest) -> dict:
    """Injects a simulated high-assurance alert into the system with automatic forensic PCAP binding & dispatch."""
    now = int(time.time())
    fp = hashlib.sha256(f"{req.alertname}|{req.campus_id}|{req.sensor_id}|{req.probe_id}".encode("utf-8")).hexdigest()[:16]

    evidence_id = req.evidence_id
    if not evidence_id:
        bundle = _generate_pcap_evidence_bundle(req.sensor_id, req.alertname, req.title or req.alertname, req.description or "", req.probe_id)
        evidence_id = bundle["id"]

    # Check active maintenance window
    maint_window = db.get_active_maintenance_windows_for_alert(
        campus_id=req.campus_id,
        sensor_id=req.sensor_id,
        probe_id=req.probe_id,
        alertname=req.alertname,
        now_ts=now
    )
    is_muted = maint_window is not None
    muted_by_id = maint_window["id"] if maint_window else None
    muted_by_name = maint_window["name"] if maint_window else None

    alert_payload = {
        "id": f"alt-sim-{now}-{uuid.uuid4().hex[:4]}",
        "fingerprint": fp,
        "status": "firing",
        "severity": req.severity.lower(),
        "title": req.title or f"{req.alertname} Triggered",
        "description": req.description or "Simulated alarm test incident.",
        "sensor_id": req.sensor_id,
        "campus_id": req.campus_id,
        "probe_id": req.probe_id,
        "starts_at": now,
        "ends_at": None,
        "evidence_id": evidence_id,
        "is_muted": is_muted,
        "muted_by_window_id": muted_by_id,
        "muted_by_window_name": muted_by_name,
        "raw_labels": {
            "alertname": req.alertname,
            "severity": req.severity.lower(),
            "campus_id": req.campus_id,
            "sensor_id": req.sensor_id,
            "probe_id": req.probe_id,
            "autocapture_pcap": "true"
        },
        "raw_annotations": {
            "summary": req.title or req.alertname,
            "description": req.description or ""
        },
        "updated_at": now
    }
    alt_id = db.save_alert(alert_payload)
    loaded = db.load_alert_by_id(alt_id)
    if loaded is None:
        raise HTTPException(status_code=500, detail="Failed to load simulated alert")
    await dispatch_alert_notifications(loaded)
    return loaded


@router.delete(
    "/api/v1/alerts/{alert_id}",
    summary="Delete Alert Record"
)
async def delete_alert_record(alert_id: str) -> Dict[str, Any]:
    """Removes an alert record from the database."""
    deleted = db.delete_alert(alert_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found.")
    return {"status": "success", "message": f"Alert '{alert_id}' deleted."}
