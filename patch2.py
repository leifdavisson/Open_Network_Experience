
with open('/data/Open_Network_Experience/server/routers/sensors.py', 'r') as f:
    content = f.read()

content = content.replace(
    '''            SensorStatusResponseSafe.from_internal(
                sensor_id=s_id,
                last_seen=data["last_seen"],
                os_val=data["os"],
                is_online=is_online,
                reconciled_ok=reconciled_ok,
                status_val=data["status"],
                reported_containers=data.get("reported_containers", {}),
                target_config=data.get("target_config"),
                location_val=data.get("location"),
                probing_state=data.get("probing_state", "GREEN")
            )''',
    '''            SensorStatusResponseSafe.from_internal(
                sensor_id=s_id,
                last_seen=data["last_seen"],
                os_val=data["os"],
                is_online=is_online,
                reconciled_ok=reconciled_ok,
                status_val=data["status"],
                reported_containers=data.get("reported_containers", {}),
                target_config=data.get("target_config"),
                location_val=data.get("location"),
                probing_state=data.get("probing_state", "GREEN"),
                hostname=data.get("hostname"),
                ip_address=data.get("ip_address"),
                mac_address=data.get("mac_address")
            )'''
)

with open('/data/Open_Network_Experience/server/routers/sensors.py', 'w') as f:
    f.write(content)
