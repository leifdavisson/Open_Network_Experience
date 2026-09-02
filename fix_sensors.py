with open('/data/Open_Network_Experience/server/routers/sensors.py', 'r') as f:
    content = f.read()

# 1. Add directory_device_id, is_managed, user_agent to ingest mapping
ingest_target = """for field in ["hostname", "serial_number", "asset_id", "annotated_user", "directory_device_id", "mac_address", "version"]:"""
ingest_replacement = """for field in ["hostname", "serial_number", "asset_id", "annotated_user", "directory_device_id", "mac_address", "version", "is_managed", "user_agent"]:"""
content = content.replace(ingest_target, ingest_replacement)

# 2. Add them to list_chromebook_fleet ChromebookFleetItemResponse mapping
list_target = """            result.append(ChromebookFleetItemResponse(
                sensor_id=s_id,
                serial_number=s.get("serial_number") or "UNTAGGED",
                asset_id=s.get("asset_id") or "UNTAGGED",
                annotated_location=str(getattr(s.get("location"), "room", "Mobile Fleet") or "Mobile Fleet"),
                annotated_user=s.get("annotated_user"),"""
list_replacement = """            result.append(ChromebookFleetItemResponse(
                sensor_id=s_id,
                serial_number=s.get("serial_number") or "UNTAGGED",
                asset_id=s.get("asset_id") or "UNTAGGED",
                directory_device_id=s.get("directory_device_id"),
                is_managed=s.get("is_managed", False),
                user_agent=s.get("user_agent"),
                annotated_location=str(getattr(s.get("location"), "room", "Mobile Fleet") or "Mobile Fleet"),
                annotated_user=s.get("annotated_user"),"""
content = content.replace(list_target, list_replacement)

# 3. Add to list_sensors mapping
sensor_ret_target = """                hostname=data.get("hostname"),
                ip_address=data.get("ip_address"),
                mac_address=data.get("mac_address")
            )
        )"""
sensor_ret_replacement = """                hostname=data.get("hostname"),
                ip_address=data.get("ip_address"),
                mac_address=data.get("mac_address"),
                serial_number=data.get("serial_number"),
                asset_id=data.get("asset_id"),
                annotated_user=data.get("annotated_user"),
                directory_device_id=data.get("directory_device_id")
            )
        )"""
content = content.replace(sensor_ret_target, sensor_ret_replacement)

with open('/data/Open_Network_Experience/server/routers/sensors.py', 'w') as f:
    f.write(content)
