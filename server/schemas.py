"""
Pydantic schemas for the Central Monitoring Platform (CMP) API.

Defines schemas for edge sensor reports, target state reconciliation configurations,
and safe administrative responses that redact sensitive credentials.
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional

# --- Sensor Reports (Incoming from Edge) ---

class RunningContainer(BaseModel):
    image: str = Field(..., description="The running image tag or digest")
    id: str = Field(..., description="The short container ID")

class SensorReportRequest(BaseModel):
    sensor_id: str = Field(..., description="Unique hardware UUID of the sensor")
    os: str = Field(..., description="Operating system type of the sensor host")
    timestamp: int = Field(..., description="Epoch timestamp of report")
    containers: Dict[str, RunningContainer] = Field(
        default_factory=dict,
        description="Map of container names to their running specs"
    )

class SensorRegisterRequest(BaseModel):
    sensor_id: str = Field(..., description="Unique hardware UUID of the sensor")
    os: str = Field(..., description="Operating system type of the sensor host")
    hostname: str = Field(..., description="Host name of the sensor")
    mac_address: str = Field(..., description="Primary network MAC address of the sensor")
    timestamp: int = Field(..., description="Epoch timestamp of registration request")

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
    pcap_trigger: PcapTriggerSpec = Field(
        default_factory=PcapTriggerSpec,
        description="One-shot incident PCAP capture trigger"
    )
    custom_probes: List[CustomProbeSpec] = Field(
        default_factory=list,
        description="Dynamic custom synthetic probes created via WYSIWYG EasyBuilder"
    )

class EvidenceBundleInfo(BaseModel):
    bundle_id: str
    sensor_id: str
    timestamp: int
    reason: str
    filename: str
    size_bytes: int

# --- Management / Administrative API Schemas ---

class SensorConfigUpdate(BaseModel):
    wifi: Optional[WifiSpec] = None
    containers: Optional[Dict[str, TargetContainerSpec]] = None
    schedules: Optional[TestSchedulesSpec] = None
    custom_probes: Optional[List[CustomProbeSpec]] = None

class SensorStatusResponse(BaseModel):
    sensor_id: str
    last_seen: int
    os: str
    is_online: bool
    reconciled_ok: bool
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
    pcap_trigger: PcapTriggerSpec = Field(default_factory=PcapTriggerSpec)
    custom_probes: List[CustomProbeSpec] = Field(default_factory=list)

class SensorStatusResponseSafe(BaseModel):
    """Admin-facing sensor status with credentials redacted."""
    sensor_id: str
    last_seen: int
    os: str
    is_online: bool
    reconciled_ok: bool
    status: str
    reported_containers: Dict[str, RunningContainer]
    target_config: SensorReconcileResponseSafe

    @classmethod
    def from_internal(cls, sensor_id, last_seen, os_val, is_online, reconciled_ok, status_val, reported_containers, target_config):
        """
        Maps the internal DB state of a sensor to an admin-safe response payload,
        invoking from_wifi_spec to scrub credentials from the outgoing target configuration.
        """
        safe_config = SensorReconcileResponseSafe(
            reset=target_config.reset,
            wifi=WifiSpecSafe.from_wifi_spec(target_config.wifi),
            containers=target_config.containers,
            schedules=getattr(target_config, "schedules", TestSchedulesSpec()),
            pcap_trigger=getattr(target_config, "pcap_trigger", PcapTriggerSpec()),
            custom_probes=getattr(target_config, "custom_probes", [])
        )
        return cls(
            sensor_id=sensor_id,
            last_seen=last_seen,
            os=os_val,
            is_online=is_online,
            reconciled_ok=reconciled_ok,
            status=status_val,
            reported_containers=reported_containers,
            target_config=safe_config
        )
