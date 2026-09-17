import yaml
with open('server/deploy/docker-compose.yml', 'r') as f:
    data = yaml.safe_load(f)

if 'iperf3' not in data['services']:
    data['services']['iperf3'] = {
        'image': 'networkstatic/iperf3:latest',
        'container_name': 'iperf3-server',
        'restart': 'always',
        'ports': [
            '5201:5201/tcp',
            '5201:5201/udp'
        ],
        'command': '-s',
        'networks': ['cmp_backend']
    }
    with open('server/deploy/docker-compose.yml', 'w') as f:
        yaml.dump(data, f, sort_keys=False)
