with open('/data/Open_Network_Experience/server/schemas.py', 'r') as f:
    content = f.read()

target = """        return cls(
            sensor_id=sensor_id,
            last_seen=last_seen,"""

replacement = """        return cls(
            sensor_id=sensor_id,
            hostname=hostname,
            ip_address=ip_address,
            mac_address=mac_address,
            last_seen=last_seen,"""

if target in content:
    content = content.replace(target, replacement)
    with open('/data/Open_Network_Experience/server/schemas.py', 'w') as f:
        f.write(content)
    print("PATCH APPLIED")
else:
    print("TARGET NOT FOUND")
