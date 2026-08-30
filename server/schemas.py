"""
Pydantic schemas for the Central Monitoring Platform (CMP) API.

Defines schemas for edge sensor reports, target state reconciliation configurations,
and safe administrative responses that redact sensitive credentials.
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any

# --- Sensor Reports (Incoming from Edge) ---

class RunningContainer(BaseModel):
    image: str = Field(..., description="The running image tag or digest")
    id: str = Field(..., description="The short container ID")

class LocationSpec(BaseModel):
    district: str = Field("Default District", description="School district or organization")
    site: str = Field("Main Campus", description="School name or campus")
    building: str = Field("Main Building", description="Building name or wing")
    room: str = Field("Room 101", description="Classroom, library, or office identifier")
    notes: Optional[str] = Field(None, description="Installation notes, e.g. 'Ceiling mounted near AP-04'")
    latitude: Optional[float] = Field(None, description="GPS Latitude (-90 to +90)")
    longitude: Optional[float] = Field(None, description="GPS Longitude (-180 to +180)")
    altitude_meters: Optional[float] = Field(None, description="GPS Altitude in meters")
    is_gps_auto: bool = Field(False, description="True if coordinates were automatically resolved via onboard GPS")
    last_gps_fix: Optional[int] = Field(None, description="Epoch timestamp of last GPS fix")

class SensorReportRequest(BaseModel):
    sensor_id: str = Field(..., description="Unique hardware UUID of the sensor")
    os: str = Field(..., description="Operating system type of the sensor host")
    timestamp: int = Field(..., description="Epoch timestamp of report")
    location: Optional[LocationSpec] = Field(default_factory=LocationSpec, description="Physical location or GPS coordinates")
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
    device_info: Optional[ChromebookDeviceInfo] = Field(default_factory=ChromebookDeviceInfo)
    location: Optional[LocationSpec] = Field(default_factory=LocationSpec)
    wifi: Optional[ChromebookWifiTelemetry] = Field(default_factory=ChromebookWifiTelemetry)
    hardware: Optional[Dict[str, Any]] = Field(default_factory=dict)
    probes: Optional[Dict[str, Any]] = Field(default_factory=dict)

class SensorRegisterRequest(BaseModel):
    sensor_id: str = Field(..., description="Unique hardware UUID of the sensor")
    os: str = Field(..., description="Operating system type of the sensor host")
    hostname: str = Field(..., description="Host name of the sensor")
    mac_address: str = Field(..., description="Primary network MAC address of the sensor")
    timestamp: int = Field(..., description="Epoch timestamp of registration request")
    location: Optional[LocationSpec] = Field(default_factory=LocationSpec, description="Initial location or GPS coordinates")

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
    command: Optional[str] = Field(None, description="Command overrides run on execution")

# --- Adaptive Probing & Dynamic Resolution Schemas ---

class AdaptiveProbingConfig(BaseModel):
    enabled: bool = Field(True, description="Enable dynamic camera-shutter resolution scaling")
    green_ping_interval_seconds: int = Field(15, description="Ping cadence in Green/Quiescent state")
    amber_ping_interval_seconds: int = Field(5, description="Ping cadence in Amber/Triage state")
    red_ping_interval_seconds: int = Field(1, description="High-resolution 1-second cadence during Active Incident")
    blackout_interval_seconds: int = Field(300, description="Dampened backoff cadence (5 min) during complete WAN/Gateway failure")
    cooldown_seconds: int = Field(90, description="Seconds of healthy metrics before stepping down from Red->Amber->Green")
    on_demand_burst_duration_seconds: int = Field(60, description="Duration of 1 Hz burst when triggered by NOC on-demand")

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
    category: str = Field("High School", description="High School, Middle School, Elementary, Admin, DataCenter")
    district: str = Field("Default District", description="Parent district or LEA")
    latitude: float = Field(..., description="GIS Latitude")
    longitude: float = Field(..., description="GIS Longitude")
    address: Optional[str] = Field(None, description="Street address")
    contact_email: Optional[str] = Field(None, description="Site tech coordinator email")

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
    building_default: str = Field("Main Building", description="Default building tag")
    auto_approve: bool = Field(True, description="Automatically approve new sensors without manual TOFU queue")

class BatchApprovalRequest(BaseModel):
    sensor_ids: List[str] = Field(..., description="List of pending sensor IDs to approve in bulk")
    campus_id: Optional[str] = Field(None, description="Optional campus to assign all approved sensors to")
    building: Optional[str] = Field(None, description="Optional building assignment")

class OnDemandBurstTrigger(BaseModel):
    sensor_ids: List[str] = Field(default_factory=lambda: ["all"], description="Target sensor IDs or ['all']")
    duration_seconds: int = Field(60, description="Duration of high-frequency 1-second burst capture")
    reason: str = Field("manual_noc_drilldown", description="Incident triage reason")

# --- Test Scheduling Schemas ---

class BandwidthScheduleSpec(BaseModel):
    enabled: bool = Field(False, description="Whether scheduled bandwidth testing is active")
    server: str = Field("iperf3.district.local", description="Target iperf3 server IP or hostname")
    port: int = Field(5201, description="Target iperf3 port")
    duration_seconds: int = Field(10, description="Test duration in seconds")
    bandwidth_cap_mbps: int = Field(100, description="Bandwidth throttling limit in Mbps (0 for unmetered)")
    interfaces: List[str] = Field(default_factory=lambda: ["eth0", "wlan0"], description="Interfaces to test in staggered sequence")
    allowed_hours: List[str] = Field(default_factory=lambda: ["20:00-06:00"], description="Allowed execution windows (e.g. off-peak hours)")
    interval_seconds: int = Field(3600, description="Execution interval in seconds")
    run_now: bool = Field(False, description="One-shot trigger to execute test immediately on next check-in")

class CipaScheduleSpec(BaseModel):
    enabled: bool = Field(True, description="Whether CIPA compliance checks are enabled")
    interval_seconds: int = Field(300, description="Execution interval in seconds")

class BrowserScheduleSpec(BaseModel):
    enabled: bool = Field(True, description="Whether synthetic browser transactions are enabled")
    interval_seconds: int = Field(300, description="Execution interval in seconds")
    targets: List[str] = Field(default_factory=lambda: ["https://google.com"], description="Target web applications to test")

class CaasppScheduleSpec(BaseModel):
    enabled: bool = Field(True, description="Whether CAASPP/ELPAC state testing readiness validation is enabled")
    interval_seconds: int = Field(300, description="Execution interval in seconds")

class TestSchedulesSpec(BaseModel):
    bandwidth: BandwidthScheduleSpec = Field(default_factory=BandwidthScheduleSpec)
    cipa: CipaScheduleSpec = Field(default_factory=CipaScheduleSpec)
    browser: BrowserScheduleSpec = Field(default_factory=BrowserScheduleSpec)
    caaspp: CaasppScheduleSpec = Field(default_factory=CaasppScheduleSpec)

class PcapTriggerSpec(BaseModel):
    trigger_now: bool = Field(False, description="One-shot signal instructing edge sensor to slice and package an incident PCAP snapshot")
    reason: str = Field("manual_noc_trigger", description="Trigger reason or incident description")

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
        default_factory=TestSchedulesSpec,
        description="Dynamic test schedules and bandwidth testing parameters"
    )
    adaptive_probing: AdaptiveProbingConfig = Field(
        default_factory=AdaptiveProbingConfig,
        description="Adaptive multi-resolution probing configuration"
    )
    probing_state: str = Field("GREEN", description="Current or commanded probing state: GREEN, AMBER, RED, BLACKOUT, ON_DEMAND")
    pcap_trigger: PcapTriggerSpec = Field(
        default_factory=PcapTriggerSpec,
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
    last_seen: int
    os: str
    is_online: bool
    reconciled_ok: bool
    location: LocationSpec = Field(default_factory=LocationSpec)
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
    schedules: TestSchedulesSpec = Field(default_factory=TestSchedulesSpec)
    adaptive_probing: AdaptiveProbingConfig = Field(default_factory=AdaptiveProbingConfig)
    probing_state: str = "GREEN"
    pcap_trigger: PcapTriggerSpec = Field(default_factory=PcapTriggerSpec)
    custom_probes: List[CustomProbeSpec] = Field(default_factory=list)
    unified_schedules: List[UnifiedScheduleSpec] = Field(default_factory=list)

class SensorStatusResponseSafe(BaseModel):
    """Admin-facing sensor status with credentials redacted."""
    sensor_id: str
    last_seen: int
    os: str
    is_online: bool
    reconciled_ok: bool
    status: str
    probing_state: str = "GREEN"
    location: LocationSpec = Field(default_factory=LocationSpec)
    reported_containers: Dict[str, RunningContainer]
    target_config: SensorReconcileResponseSafe

    @classmethod
    def from_internal(cls, sensor_id, last_seen, os_val, is_online, reconciled_ok, status_val, reported_containers, target_config, location_val=None, probing_state="GREEN"):
        """
        Maps the internal DB state of a sensor to an admin-safe response payload,
        invoking from_wifi_spec to scrub credentials from the outgoing target configuration.
        """
        safe_config = SensorReconcileResponseSafe(
            reset=target_config.reset,
            wifi=WifiSpecSafe.from_wifi_spec(target_config.wifi),
            containers=target_config.containers,
            schedules=getattr(target_config, "schedules", TestSchedulesSpec()),
            adaptive_probing=getattr(target_config, "adaptive_probing", AdaptiveProbingConfig()),
            probing_state=getattr(target_config, "probing_state", probing_state),
            pcap_trigger=getattr(target_config, "pcap_trigger", PcapTriggerSpec()),
            custom_probes=getattr(target_config, "custom_probes", []),
            unified_schedules=getattr(target_config, "unified_schedules", [])
        )
        return cls(
            sensor_id=sensor_id,
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
