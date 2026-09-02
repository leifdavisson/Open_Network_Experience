
with open('/data/Open_Network_Experience/server/schemas.py', 'r') as f:
    content = f.read()

# 1. Add fields to ChromebookFleetItemResponse
cb_fleet_target = """class ChromebookFleetItemResponse(BaseModel):
    sensor_id: str
    serial_number: Optional[str] = "UNTAGGED"
    asset_id: Optional[str] = "UNTAGGED"
    annotated_location: Optional[str] = "Mobile Fleet"
    annotated_user: Optional[str] = None"""

cb_fleet_replacement = """class ChromebookFleetItemResponse(BaseModel):
    sensor_id: str
    serial_number: Optional[str] = "UNTAGGED"
    asset_id: Optional[str] = "UNTAGGED"
    directory_device_id: Optional[str] = None
    is_managed: bool = False
    user_agent: Optional[str] = None
    annotated_location: Optional[str] = "Mobile Fleet"
    annotated_user: Optional[str] = None"""

content = content.replace(cb_fleet_target, cb_fleet_replacement)

# 2. Add fields to SensorStatusResponse
status_target = """class SensorStatusResponse(BaseModel):
    sensor_id: str
    hostname: Optional[str] = None
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None"""

status_replacement = """class SensorStatusResponse(BaseModel):
    sensor_id: str
    hostname: Optional[str] = None
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    serial_number: Optional[str] = None
    asset_id: Optional[str] = None
    annotated_user: Optional[str] = None
    directory_device_id: Optional[str] = None"""

content = content.replace(status_target, status_replacement)

# 3. Add fields to SensorStatusResponseSafe
safe_target = """class SensorStatusResponseSafe(BaseModel):
    \"\"\"Admin-facing sensor status with credentials redacted.\"\"\"
    sensor_id: str
    hostname: Optional[str] = None
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None"""

safe_replacement = """class SensorStatusResponseSafe(BaseModel):
    \"\"\"Admin-facing sensor status with credentials redacted.\"\"\"
    sensor_id: str
    hostname: Optional[str] = None
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    serial_number: Optional[str] = None
    asset_id: Optional[str] = None
    annotated_user: Optional[str] = None
    directory_device_id: Optional[str] = None"""

content = content.replace(safe_target, safe_replacement)

# 4. Update from_internal signature and return in SensorStatusResponseSafe
from_internal_target = """def from_internal(cls, sensor_id, last_seen, os_val, is_online, reconciled_ok, status_val, reported_containers, target_config, location_val=None, probing_state="GREEN", hostname=None, ip_address=None, mac_address=None):"""

from_internal_replacement = """def from_internal(cls, sensor_id, last_seen, os_val, is_online, reconciled_ok, status_val, reported_containers, target_config, location_val=None, probing_state="GREEN", hostname=None, ip_address=None, mac_address=None, serial_number=None, asset_id=None, annotated_user=None, directory_device_id=None):"""

content = content.replace(from_internal_target, from_internal_replacement)

ret_target = """        return cls(
            sensor_id=sensor_id,
            hostname=hostname,
            ip_address=ip_address,
            mac_address=mac_address,"""

ret_replacement = """        return cls(
            sensor_id=sensor_id,
            hostname=hostname,
            ip_address=ip_address,
            mac_address=mac_address,
            serial_number=serial_number,
            asset_id=asset_id,
            annotated_user=annotated_user,
            directory_device_id=directory_device_id,"""

content = content.replace(ret_target, ret_replacement)

with open('/data/Open_Network_Experience/server/schemas.py', 'w') as f:
    f.write(content)
