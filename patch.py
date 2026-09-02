
with open('/data/Open_Network_Experience/server/schemas.py', 'r') as f:
    content = f.read()

content = content.replace(
    'class SensorStatusResponse(BaseModel):\n    sensor_id: str',
    'class SensorStatusResponse(BaseModel):\n    sensor_id: str\n    hostname: Optional[str] = None\n    ip_address: Optional[str] = None\n    mac_address: Optional[str] = None'
)

content = content.replace(
    'class SensorStatusResponseSafe(BaseModel):\n    """Admin-facing sensor status with credentials redacted."""\n    sensor_id: str',
    'class SensorStatusResponseSafe(BaseModel):\n    """Admin-facing sensor status with credentials redacted."""\n    sensor_id: str\n    hostname: Optional[str] = None\n    ip_address: Optional[str] = None\n    mac_address: Optional[str] = None'
)

# Fix from_internal signature
content = content.replace(
    'def from_internal(cls, sensor_id, last_seen, os_val, is_online, reconciled_ok, status_val, reported_containers, target_config, location_val=None, probing_state="GREEN"):',
    'def from_internal(cls, sensor_id, last_seen, os_val, is_online, reconciled_ok, status_val, reported_containers, target_config, location_val=None, probing_state="GREEN", hostname=None, ip_address=None, mac_address=None):'
)

# Fix from_internal return
content = content.replace(
    '''        return cls(
            sensor_id=sensor_id,
            last_seen=last_seen,
            os=os_val,
            is_online=is_online,
            reconciled_ok=reconciled_ok,
            status=status_val,
            probing_state=probing_state,
            location=location_val if location_val else LocationSpec(),
            reported_containers=reported_containers,
            target_config=safe_config
        )''',
    '''        return cls(
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
            location=location_val if location_val else LocationSpec(),
            reported_containers=reported_containers,
            target_config=safe_config
        )'''
)

with open('/data/Open_Network_Experience/server/schemas.py', 'w') as f:
    f.write(content)
