"""
Pydantic schemas for the Central Monitoring Platform (CMP) API.

Defines schemas for edge sensor reports, target state reconciliation configurations,
and safe administrative responses that redact sensitive credentials.
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any, Union

# --- Sensor Reports (Incoming from Edge) ---

class RunningContainer(BaseModel):
    image: str = Field(..., description="The running image tag or digest")
    id: str = Field(..., description="The short container ID")

class LocationSpec(BaseModel):
    district: str = Field(default="Default District", description="School district or organization")
    site: str = Field(default="Main Campus", description="School name or campus")
    building: str = Field(default="Main Building", description="Building name or wing")
    room: str = Field(default="Room 101", description="Classroom, library, or office identifier")
    notes: Optional[str] = Field(default=None, description="Installation notes, e.g. 'Ceiling mounted near AP-04'")
    latitude: Optional[float] = Field(default=None, description="GPS Latitude (-90 to +90)")
    longitude: Optional[float] = Field(default=None, description="GPS Longitude (-180 to +180)")
    altitude_meters: Optional[float] = Field(default=None, description="GPS Altitude in meters")
    is_gps_auto: bool = Field(default=False, description="True if coordinates were automatically resolved via onboard GPS")
    last_gps_fix: Optional[int] = Field(default=None, description="Epoch timestamp of last GPS fix")

class SensorReportRequest(BaseModel):
    sensor_id: str = Field(..., description="Unique hardware UUID of the sensor")
    os: str = Field(..., description="Operating system type of the sensor host")
    timestamp: int = Field(..., description="Epoch timestamp of report")
    location: Optional[LocationSpec] = Field(default_factory=lambda: LocationSpec(), description="Physical location or GPS coordinates")
    containers: Dict[str, RunningContainer] = Field(
        default_factory=dict,
        description="Map of container names to their running specs"
    )

class ChromebookDeviceInfo(BaseModel):
    serial_number: Optional[str] = None
    asset_id: Optional[str] = None
    annotated_location: Optional[str] = None
    annotated_user: Optional[str] = None
    directory_device_id: Optional[str] = None
    hostname: Optional[str] = None
    mac_address: Optional[str] = None
    is_managed: bool = False
    user_agent: Optional[str] = None

class ChromebookWifiTelemetry(BaseModel):
    connected: bool = True
    ssid: Optional[str] = None
    bssid: Optional[str] = None
    rssi_dbm: Optional[int] = None
    signal_strength_pct: Optional[int] = None
    frequency_mhz: Optional[int] = None
    channel: Optional[int] = None
    band: Optional[str] = None
    security: Optional[str] = None
    roamed_recently: bool = False

class ChromebookTelemetryReport(BaseModel):
    sensor_id: str = Field(..., description="Unique hardware or enterprise serial UUID")
    sensor_type: str = Field("chromebook", description="Sensor form factor: chromebook or linux_edge")
    os: str = Field("ChromeOS", description="Operating system")
    timestamp: int = Field(..., description="Epoch timestamp of report")
    campus_id: Optional[str] = Field("CAMPUS-CHROMEBOOK-FLEET", description="Associated campus ID")
    device_info: Optional[ChromebookDeviceInfo] = Field(default_factory=lambda: ChromebookDeviceInfo())
    location: Optional[LocationSpec] = Field(default_factory=lambda: LocationSpec())
    wifi: Optional[ChromebookWifiTelemetry] = Field(default_factory=lambda: ChromebookWifiTelemetry())
    hardware: Optional[Dict[str, Any]] = Field(default_factory=dict)
    probes: Optional[Dict[str, Any]] = Field(default_factory=dict)

class SensorRegisterRequest(BaseModel):
    sensor_id: str = Field(..., description="Unique hardware UUID of the sensor")
    os: str = Field(..., description="Operating system type of the sensor host")
    hostname: str = Field(..., description="Host name of the sensor")
    mac_address: str = Field(..., description="Primary network MAC address of the sensor")
    timestamp: int = Field(..., description="Epoch timestamp of registration request")
    location: Optional[LocationSpec] = Field(default=None, description="Initial location or GPS coordinates")

class SensorRegisterResponse(BaseModel):
    status: str = Field(..., description="Approval status: pending or approved")
    api_key: Optional[str] = Field(None, description="The unique secret API key for future check-ins (returned only once when approved)")

# --- Target Configurations (Outgoing to Edge) ---

class WifiSpec(BaseModel):
    ssid: str = Field(..., description="Target Wi-Fi SSID")
    security: str = Field("open", description="Security type: open, psk, or eap-peap")
    psk: Optional[str] = Field(None, description="Pre-shared key (for PSK networks)")
    username: Optional[str] = Field(None, description="EAP Identity/Username (for EAP-PEAP)")
    password: Optional[str] = Field(None, description="EAP Password (for EAP-PEAP)")

class TargetContainerSpec(BaseModel):
    image: str = Field(..., description="Docker image registry path and tag/digest")
    ports: List[str] = Field(default_factory=list, description="Port forward mappings, e.g. ['80:80']")
    volumes: List[str] = Field(default_factory=list, description="Volume mappings, e.g. ['/data:/data']")
    env: Dict[str, str] = Field(default_factory=dict, description="Environment variables passed to container")
    command: Optional[Union[str, List[str]]] = Field(None, description="Command overrides run on execution")

# --- Adaptive Probing & Dynamic Resolution Schemas ---

class AdaptiveProbingConfig(BaseModel):
    enabled: bool = Field(default=True, description="Enable dynamic camera-shutter resolution scaling")
    green_ping_interval_seconds: int = Field(default=15, description="Ping cadence in Green/Quiescent state")
    amber_ping_interval_seconds: int = Field(default=5, description="Ping cadence in Amber/Triage state")
    red_ping_interval_seconds: int = Field(default=1, description="High-resolution 1-second cadence during Active Incident")
    blackout_interval_seconds: int = Field(default=300, description="Dampened backoff cadence (5 min) during complete WAN/Gateway failure")
    cooldown_seconds: int = Field(default=90, description="Seconds of healthy metrics before stepping down from Red->Amber->Green")
    on_demand_burst_duration_seconds: int = Field(default=60, description="Duration of 1 Hz burst when triggered by NOC on-demand")

class ProbingStateEnum(str):
    GREEN = "GREEN"         # Normal baseline
    AMBER = "AMBER"         # Triage (minor jitter / 1 packet loss)
    RED = "RED"             # Forensic (SLA breach / active failure / 1 Hz)
    BLACKOUT = "BLACKOUT"   # Hard-down / Gateway dead (5-15 min backoff)
    ON_DEMAND = "ON_DEMAND" # NOC triggered high-frequency burst

# --- Multi-Campus Hierarchy Schemas ---

class CampusCreate(BaseModel):
    campus_id: str = Field(..., description="Unique campus ID, e.g. 'CAMPUS-WEST-HIGH'")
    name: str = Field(..., description="Campus display name, e.g. 'West High School'")
    category: str = Field(default="High School", description="High School, Middle School, Elementary, Admin, DataCenter")
    district: str = Field(default="Default District", description="Parent district or LEA")
    latitude: float = Field(..., description="GIS Latitude")
    longitude: float = Field(..., description="GIS Longitude")
    address: Optional[str] = Field(default=None, description="Street address")
    contact_email: Optional[str] = Field(default=None, description="Site tech coordinator email")

class CampusResponse(CampusCreate):
    sensor_count: int = 0
    online_count: int = 0
    degraded_count: int = 0
    offline_count: int = 0
    sla_percentage: float = 100.0

class SubnetAutoEnrollRule(BaseModel):
    id: Optional[str] = None
    subnet_cidr: str = Field(..., description="CIDR block, e.g. '10.142.10.0/24'")
    campus_id: str = Field(..., description="Target campus ID for sensors on this subnet")
    campus_name: str = Field(..., description="Campus display name")
    building_default: str = Field(default="Main Building", description="Default building tag")
    auto_approve: bool = Field(default=True, description="Automatically approve new sensors without manual TOFU queue")

class BatchApprovalRequest(BaseModel):
    sensor_ids: List[str] = Field(..., description="List of pending sensor IDs to approve in bulk")
    campus_id: Optional[str] = Field(default=None, description="Optional campus to assign all approved sensors to")
    building: Optional[str] = Field(default=None, description="Optional building assignment")

class OnDemandBurstTrigger(BaseModel):
    sensor_ids: List[str] = Field(default_factory=lambda: ["all"], description="Target sensor IDs or ['all']")
    duration_seconds: int = Field(default=60, description="Duration of high-frequency 1-second burst capture")
    reason: str = Field(default="manual_noc_drilldown", description="Incident triage reason")

# --- Test Scheduling Schemas ---

class BandwidthScheduleSpec(BaseModel):
    enabled: bool = Field(default=False, description="Whether scheduled bandwidth testing is active")
    server: str = Field(default="iperf3.example.com", description="Target iperf3 server IP or hostname")
    port: int = Field(default=5201, description="Target iperf3 port")
    duration_seconds: int = Field(default=10, description="Test duration in seconds")
    bandwidth_cap_mbps: int = Field(default=100, description="Bandwidth throttling limit in Mbps (0 for unmetered)")
    interfaces: List[str] = Field(default_factory=lambda: ["eth0", "wlan0"], description="Interfaces to test in staggered sequence")
    allowed_hours: List[str] = Field(default_factory=lambda: ["20:00-06:00"], description="Allowed execution windows (e.g. off-peak hours)")
    interval_seconds: int = Field(default=3600, description="Execution interval in seconds")
    run_now: bool = Field(default=False, description="One-shot trigger to execute test immediately on next check-in")

class CipaScheduleSpec(BaseModel):
    enabled: bool = Field(default=True, description="Whether CIPA compliance checks are enabled")
    interval_seconds: int = Field(default=300, description="Execution interval in seconds")

class BrowserScheduleSpec(BaseModel):
    enabled: bool = Field(default=True, description="Whether synthetic browser transactions are enabled")
    interval_seconds: int = Field(default=300, description="Execution interval in seconds")
    targets: List[str] = Field(default_factory=lambda: ["https://google.com"], description="Target web applications to test")

class CaasppScheduleSpec(BaseModel):
    enabled: bool = Field(default=True, description="Whether CAASPP/ELPAC state testing readiness validation is enabled")
    interval_seconds: int = Field(default=300, description="Execution interval in seconds")

class TestSchedulesSpec(BaseModel):
    bandwidth: BandwidthScheduleSpec = Field(default_factory=lambda: BandwidthScheduleSpec())
    cipa: CipaScheduleSpec = Field(default_factory=lambda: CipaScheduleSpec())
    browser: BrowserScheduleSpec = Field(default_factory=lambda: BrowserScheduleSpec())
    caaspp: CaasppScheduleSpec = Field(default_factory=lambda: CaasppScheduleSpec())

class PcapTriggerSpec(BaseModel):
    trigger_now: bool = Field(default=False, description="One-shot signal instructing edge sensor to slice and package an incident PCAP snapshot")
    reason: str = Field(default="manual_noc_trigger", description="Trigger reason or incident description")

class CustomProbeSpec(BaseModel):
    id: str = Field(..., description="Unique slug for probe, e.g. 'canvas-lms'")
    name: str = Field(..., description="Human-readable probe name")
    probe_type: str = Field(default="http", description="http | api | dns | tcp")
    target: str = Field(..., description="URL, hostname, or IP address")
    cadence_minutes: int = Field(default=5, ge=1, le=1440)
    timeout_seconds: float = Field(default=5.0)
    expected_status_code: int = Field(default=200)
    match_body_regex: Optional[str] = None
    target_sensors: List[str] = Field(default_factory=lambda: ["all"], description="Target sensor IDs or 'all'")
    enabled: bool = True

class SensorIngestResponse(BaseModel):
    status: str = "received"
    sensor_id: str
    timestamp: int
    probing_state: str = "GREEN"
    settings_locked: bool = Field(True, description="Whether local extension settings UI is locked against student modification")
    helpdesk_pin_required: bool = Field(True, description="Whether PIN is required to unlock settings locally")
    helpdesk_pin: Optional[str] = Field(None, description="Active helpdesk unlock PIN if updated centrally")
    custom_probes: List[CustomProbeSpec] = Field(default_factory=list, description="WYSIWYG custom synthetic probes configured in CMP")

# --- Unified Visual Probe Scheduler Schemas ---

class UnifiedScheduleSpec(BaseModel):
    id: str = Field(..., description="Unique schedule identifier")
    name: str = Field(..., description="Human-readable schedule name")
    probe_id: str = Field(..., description="Target probe module or EasyBuilder probe ID")
    mode: str = Field("daily_once", description="Timing mode: daily_once, window_repeat, continuous_interval, raw_cron")
    days_of_week: List[str] = Field(default_factory=lambda: ["mon", "tue", "wed", "thu", "fri"], description="List of active days: mon, tue, wed, thu, fri, sat, sun")
    start_time: str = Field("07:15", description="Start time in 24h format HH:MM")
    end_time: str = Field("16:00", description="End time in 24h format HH:MM for window_repeat")
    interval_value: int = Field(15, description="Interval magnitude")
    interval_unit: str = Field("minutes", description="Interval unit: seconds, minutes, hours, days, weeks")
    cron_expr: Optional[str] = Field(None, description="Equivalent 5-field cron expression")
    target_scope: str = Field("all", description="Target sensor scope: all, campus:<id>, or sensor:<id>")
    guardrails_enabled: bool = Field(True, description="Enforce instructional hours and congestion check guardrails")
    is_active: bool = Field(True, description="Whether this schedule is currently enabled")
    created_at: Optional[int] = Field(None, description="Epoch creation timestamp")

class SensorReconcileResponse(BaseModel):
    reset: bool = Field(False, description="Tells the sensor to perform a factory cleanup of all containers")
    wifi: Optional[WifiSpec] = Field(None, description="Wi-Fi configuration profiles")
    containers: Dict[str, TargetContainerSpec] = Field(
        default_factory=dict,
        description="Map of desired container names to their target specifications"
    )
    schedules: TestSchedulesSpec = Field(
        default_factory=lambda: TestSchedulesSpec(),
        description="Dynamic test schedules and bandwidth testing parameters"
    )
    adaptive_probing: AdaptiveProbingConfig = Field(
        default_factory=lambda: AdaptiveProbingConfig(),
        description="Adaptive multi-resolution probing configuration"
    )
    probing_state: str = Field("GREEN", description="Current or commanded probing state: GREEN, AMBER, RED, BLACKOUT, ON_DEMAND")
    pcap_trigger: PcapTriggerSpec = Field(
        default_factory=lambda: PcapTriggerSpec(),
        description="One-shot incident PCAP capture trigger"
    )
    custom_probes: List[CustomProbeSpec] = Field(
        default_factory=list,
        description="Dynamic custom synthetic probes created via WYSIWYG EasyBuilder"
    )
    unified_schedules: List[UnifiedScheduleSpec] = Field(
        default_factory=list,
        description="Unified visual probe schedules and timing windows"
    )

class EvidenceBundleInfo(BaseModel):
    bundle_id: str
    sensor_id: str
    timestamp: int
    reason: str
    filename: str
    size_bytes: int

class ChromebookFleetItemResponse(BaseModel):
    sensor_id: str
    serial_number: Optional[str] = "UNTAGGED"
    asset_id: Optional[str] = "UNTAGGED"
    annotated_location: Optional[str] = "Mobile Fleet"
    annotated_user: Optional[str] = None
    hostname: Optional[str] = None
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    is_online: bool = True
    last_seen: int = 0
    campus_id: Optional[str] = "CAMPUS-CHROMEBOOK-FLEET"
    wifi_ssid: Optional[str] = None
    wifi_bssid: Optional[str] = None
    wifi_rssi_dbm: Optional[int] = None
    wifi_signal_pct: Optional[int] = None
    wifi_channel: Optional[int] = None
    wifi_band: Optional[str] = None
    battery_level_pct: Optional[int] = None
    battery_charging: Optional[bool] = None
    cpu_usage_pct: Optional[float] = None
    memory_usage_pct: Optional[float] = None
    webrtc_mos: Optional[float] = None
    webrtc_mos_grade: Optional[str] = None
    app_sla_pct: Optional[float] = None
    roamed_recently: bool = False
    location: Optional[LocationSpec] = None
    settings_locked: bool = True
    version: Optional[str] = "1.0.0"
    is_latest_version: bool = True
    target_version: Optional[str] = "1.0.0"

class ChromebookLockUpdateRequest(BaseModel):
    locked: bool = Field(True, description="Set whether Chromebook sensor settings panel is locked")
    helpdesk_pin: Optional[str] = Field(None, description="Optional custom helpdesk unlock PIN")

class RoamingEventResponse(BaseModel):
    sensor_id: str
    serial_number: Optional[str] = None
    old_bssid: Optional[str] = None
    new_bssid: Optional[str] = None
    ssid: Optional[str] = None
    timestamp: int
    campus_id: Optional[str] = None

# --- Management / Administrative API Schemas ---

class SensorConfigUpdate(BaseModel):
    wifi: Optional[WifiSpec] = None
    containers: Optional[Dict[str, TargetContainerSpec]] = None
    schedules: Optional[TestSchedulesSpec] = None
    adaptive_probing: Optional[AdaptiveProbingConfig] = None
    probing_state: Optional[str] = None
    custom_probes: Optional[List[CustomProbeSpec]] = None
    location: Optional[LocationSpec] = None

class SensorStatusResponse(BaseModel):
    sensor_id: str
    hostname: Optional[str] = None
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    last_seen: int
    os: str
    is_online: bool
    reconciled_ok: bool
    location: LocationSpec = Field(default_factory=lambda: LocationSpec())
    reported_containers: Dict[str, RunningContainer]
    target_config: SensorReconcileResponse

# --- Safe Response Models (Redact Credentials for Admin API) ---

class WifiSpecSafe(BaseModel):
    """Wi-Fi config view with credentials redacted for admin dashboard safety."""
    ssid: str
    security: str
    psk: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None

    @classmethod
    def from_wifi_spec(cls, spec: Optional[WifiSpec]) -> Optional["WifiSpecSafe"]:
        """
        Constructs a safe, credential-redacted Wi-Fi spec from a raw WifiSpec.
        Replaces PSK and password with standard redacted placeholder text.
        """
        if spec is None:
            return None
        return cls(
            ssid=spec.ssid,
            security=spec.security,
            psk="[REDACTED]" if spec.psk else None,
            username="[REDACTED]" if spec.username else None,
            password="[REDACTED]" if spec.password else None
        )

class SensorReconcileResponseSafe(BaseModel):
    """Safe target config with Wi-Fi credentials scrubbed for admin views."""
    reset: bool = False
    wifi: Optional[WifiSpecSafe] = None
    containers: Dict[str, TargetContainerSpec] = Field(default_factory=dict)
    schedules: TestSchedulesSpec = Field(default_factory=lambda: TestSchedulesSpec())
    adaptive_probing: AdaptiveProbingConfig = Field(default_factory=lambda: AdaptiveProbingConfig())
    probing_state: str = "GREEN"
    pcap_trigger: PcapTriggerSpec = Field(default_factory=lambda: PcapTriggerSpec())
    custom_probes: List[CustomProbeSpec] = Field(default_factory=list)
    unified_schedules: List[UnifiedScheduleSpec] = Field(default_factory=list)

class SensorStatusResponseSafe(BaseModel):
    """Admin-facing sensor status with credentials redacted."""
    sensor_id: str
    hostname: Optional[str] = None
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    last_seen: int
    os: str
    is_online: bool
    reconciled_ok: bool
    status: str
    probing_state: str = "GREEN"
    location: LocationSpec = Field(default_factory=lambda: LocationSpec())
    reported_containers: Dict[str, RunningContainer]
    target_config: SensorReconcileResponseSafe

    @classmethod
    def from_internal(cls, sensor_id, last_seen, os_val, is_online, reconciled_ok, status_val, reported_containers, target_config, location_val=None, probing_state="GREEN", hostname=None, ip_address=None, mac_address=None):
        """
        Maps the internal DB state of a sensor to an admin-safe response payload,
        invoking from_wifi_spec to scrub credentials from the outgoing target configuration.
        """
        if isinstance(target_config, dict):
            target_config = SensorReconcileResponse(**target_config)
        elif target_config is None:
            target_config = SensorReconcileResponse()

        safe_config = SensorReconcileResponseSafe(
            reset=getattr(target_config, "reset", False),
            wifi=WifiSpecSafe.from_wifi_spec(target_config.wifi) if getattr(target_config, "wifi", None) else WifiSpecSafe(ssid="none", security="open"),
            containers=getattr(target_config, "containers", {}),
            schedules=getattr(target_config, "schedules", TestSchedulesSpec()),
            adaptive_probing=getattr(target_config, "adaptive_probing", AdaptiveProbingConfig()),
            probing_state=getattr(target_config, "probing_state", probing_state),
            pcap_trigger=getattr(target_config, "pcap_trigger", PcapTriggerSpec()),
            custom_probes=getattr(target_config, "custom_probes", []),
            unified_schedules=getattr(target_config, "unified_schedules", [])
        )
        return cls(
            sensor_id=sensor_id,
            hostname=hostname,
            ip_address=ip_address,
            mac_address=mac_address,
            last_seen=last_seen,
            os=os_val,
            is_online=is_online,
            reconciled_ok=reconciled_ok,
            status=status_val,
            probing_state=probing_state,
            location=location_val if location_val is not None else LocationSpec(),
            reported_containers=reported_containers,
            target_config=safe_config
        )

# --- Alertmanager & Alert Lifecycle Schemas ---

class AlertmanagerAlert(BaseModel):
    status: str = Field("firing", description="Alert status: 'firing' or 'resolved'")
    labels: Dict[str, str] = Field(default_factory=dict, description="Key-value labels identifying the alert")
    annotations: Dict[str, str] = Field(default_factory=dict, description="Descriptive annotations")
    startsAt: Optional[str] = Field(None, description="ISO8601 start timestamp")
    endsAt: Optional[str] = Field(None, description="ISO8601 end timestamp")
    generatorURL: Optional[str] = Field(None, description="Source URL / rule link")
    fingerprint: Optional[str] = Field(None, description="Unique Alertmanager fingerprint hash")

class AlertmanagerWebhookPayload(BaseModel):
    version: Optional[str] = "4"
    groupKey: Optional[str] = None
    status: Optional[str] = "firing"
    receiver: Optional[str] = None
    groupLabels: Optional[Dict[str, str]] = Field(default_factory=dict)
    commonLabels: Optional[Dict[str, str]] = Field(default_factory=dict)
    commonAnnotations: Optional[Dict[str, str]] = Field(default_factory=dict)
    externalURL: Optional[str] = None
    alerts: List[AlertmanagerAlert] = Field(default_factory=list)

class AlertRecord(BaseModel):
    id: str
    fingerprint: str
    status: str = Field(..., description="'firing', 'acknowledged', 'resolved'")
    severity: str = Field("warning", description="'critical', 'warning', 'info'")
    title: str
    description: Optional[str] = ""
    sensor_id: Optional[str] = None
    campus_id: Optional[str] = None
    probe_id: Optional[str] = None
    starts_at: int
    ends_at: Optional[int] = None
    acknowledged_at: Optional[int] = None
    acknowledged_by: Optional[str] = None
    resolution_notes: Optional[str] = ""
    evidence_id: Optional[str] = None
    is_muted: Optional[bool] = False
    muted_by_window_id: Optional[str] = None
    muted_by_window_name: Optional[str] = None
    raw_labels: Optional[Dict[str, Any]] = Field(default_factory=dict)
    raw_annotations: Optional[Dict[str, Any]] = Field(default_factory=dict)
    updated_at: Optional[int] = None

class AlertAcknowledgeRequest(BaseModel):
    acknowledged_by: Optional[str] = Field("NOC Operator", description="Operator identity acknowledging alarm")

class AlertResolveRequest(BaseModel):
    resolution_notes: Optional[str] = Field("Resolved via CMP Webhook/Console", description="Resolution notes")

class AlertSimulateRequest(BaseModel):
    alertname: str = Field("CAASPPUntrustedCertificate", description="Alarm name / rule")
    severity: str = Field("critical", description="Severity: critical, warning, info")
    title: Optional[str] = Field("CAASPP Secure Browser SSL Certificate Interception Detected", description="Alarm Title")
    description: Optional[str] = Field("Untrusted MITM certificate detected during pre-flight synthetic TLS probe to Cambium TDS.", description="Alarm Details")
    campus_id: Optional[str] = Field("CAMPUS-WEST-HIGH", description="Target campus")
    sensor_id: Optional[str] = Field("pi5-science-01", description="Target sensor")
    probe_id: Optional[str] = Field("caaspp_readiness", description="Target synthetic probe")
    evidence_id: Optional[str] = Field(None, description="Linked PCAP or log forensic ID")

class AlertSummaryResponse(BaseModel):
    open_count: int
    firing_count: int
    acknowledged_count: int
    critical_count: int
    warning_count: int
    info_count: int
    resolved_24h_count: int
    total_count: int

class CustomAlertRuleSpec(BaseModel):
    id: str = Field(..., description="Unique Rule identifier")
    name: str = Field(..., description="Human-readable rule name")
    probe_id: str = Field(..., description="Target probe: caaspp_readiness, dual_nic_ping, dns_multi_resolver, etc.")
    metric: str = Field("latency_ms", description="Metric to evaluate: latency_ms, packet_loss_pct, mos_score, failure_count, etc.")
    operator: str = Field("gt", description="Comparison operator: gt, lt, eq, gte, lte")
    threshold_value: float = Field(..., description="Numerical threshold limit")
    unit: Optional[str] = Field("ms", description="Unit of measurement: ms, %, score, count")
    duration_seconds: Optional[int] = Field(30, description="Evaluation window / duration before firing")
    severity: str = Field("critical", description="Severity level: critical, warning, info")
    campus_id: Optional[str] = Field(None, description="Scope filter by campus or None for all")
    sensor_id: Optional[str] = Field(None, description="Scope filter by sensor or None for all")
    channels: List[str] = Field(default_factory=list, description="Target notification channel IDs")
    autocapture_pcap: bool = Field(True, description="Automatically freeze RAM circular PCAP buffer on trigger")
    is_active: bool = Field(True, description="Whether rule evaluation is active")
    created_at: Optional[int] = None
    updated_at: Optional[int] = None

class NotificationChannelSpec(BaseModel):
    id: str = Field(..., description="Unique Channel identifier")
    name: str = Field(..., description="Channel name: e.g. Primary Slack, Teams Alerting")
    channel_type: str = Field("slack", description="Type: slack, teams, webhook, pagerduty, email")
    endpoint_url: str = Field(..., description="Webhook URL, API endpoint, or SMTP host")
    auth_headers: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Custom HTTP headers, auth tokens, or SMTP configuration")
    min_severity: str = Field("warning", description="Minimum severity to dispatch: info, warning, critical")
    is_active: bool = Field(True, description="Whether outbound dispatch is enabled")
    last_dispatched_at: Optional[int] = None
    last_status: Optional[str] = None
    created_at: Optional[int] = None
    updated_at: Optional[int] = None

class ChannelTestRequest(BaseModel):
    sample_title: Optional[str] = "TEST ALARM — Open Network Experience (ONE)"
    sample_severity: Optional[str] = "warning"
    sample_message: Optional[str] = "This is a test notification verifying outbound webhook delivery from the ONE Central Monitoring Platform."

class MaintenanceWindowSpec(BaseModel):
    id: str = Field(..., description="Unique Maintenance Window ID")
    name: str = Field(..., description="Descriptive maintenance window title")
    description: Optional[str] = Field(None, description="Reason or change control ticket reference")
    window_type: Optional[str] = Field("maintenance", description="Type: maintenance, construction, upgrade, renovation")
    campus_id: Optional[str] = Field(None, description="Scope filter by campus (None = All)")
    sensor_id: Optional[str] = Field(None, description="Scope filter by sensor (None = All)")
    probe_id: Optional[str] = Field(None, description="Scope filter by probe (None = All)")
    alertname_pattern: Optional[str] = Field(None, description="Glob/pattern match on alertname or None for all")
    starts_at: int = Field(..., description="Start UTC epoch timestamp")
    ends_at: int = Field(..., description="End UTC epoch timestamp")
    is_active: bool = Field(True, description="Whether the window is enabled")
    reminded_24h: Optional[bool] = Field(False, description="Whether 24-hour expiration warning was dispatched")
    reminded_2h: Optional[bool] = Field(False, description="Whether 2-hour expiration warning was dispatched")
    notify_channel_ids: Optional[List[str]] = Field(default_factory=list, description="Target notification channels for expiration warnings")
    created_by: Optional[str] = Field("NOC Admin", description="Creator identity")
    created_at: Optional[int] = None
    updated_at: Optional[int] = None
