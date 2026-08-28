#!/usr/bin/env python3
"""
Sensor Reconciler Agent
Runs on the edge sensor host. Periodically phones home to the Central Monitoring
Platform (CMP) to report running containers and reconcile desired host state:
  - Containers: Reconciles running Docker containers with image mismatch detection,
    stopped container cleanup to prevent naming collisions, and a safety threshold
    that refuses reconciliation if CMP returns an empty container manifest.
  - Wi-Fi: Reconfigures wpa_supplicant for Open, WPA-PSK, and WPA-EAP (PEAP) networks.
  - Reset: Executes clean factory reset/prune if instructed by CMP.
  - Sensor ID: Automatically detects/derives unique host ID via /etc/machine-id or UUID.
"""

import os
import sys
import json
import uuid
import time
import subprocess
import urllib.request
import urllib.error

# Default Paths & Configuration
CONFIG_PATH = "/etc/sensor/reconciler.json"
DEFAULT_CONFIG = {
    "cmp_url": "http://central-monitoring-platform.local/api/v1",
    "sensor_id": "",
    "api_key": "",
    "check_interval_seconds": 60,
    "wifi_interface": "wlan0",
    "wifi_config_path": "/etc/wpa_supplicant/wpa_supplicant.conf"
}

GLOBAL_DISCOVERY_URL = "https://discovery.openux.org/api/v1"

def discover_domain():
    """Reads /etc/resolv.conf to find the search domain suffix."""
    if os.path.exists("/etc/resolv.conf"):
        try:
            with open("/etc/resolv.conf", "r") as f:
                for line in f:
                    parts = line.split()
                    if parts and parts[0] in ("search", "domain"):
                        return parts[1]
        except Exception:
            pass
    return None

def resolve_cmp_via_dns():
    """Attempts L2/L3 DNS discovery by resolving openux-cmp.<search-domain>."""
    import socket
    domain = discover_domain()
    if domain:
        hostname = f"openux-cmp.{domain}"
        try:
            socket.gethostbyname(hostname)
            return f"http://{hostname}:8000/api/v1"
        except socket.gaierror:
            pass
    return None

def get_cmp_url(config):
    """
    Three-way cloud discovery:
      1. Explicitly configured cmp_url in reconciler.json
      2. Local DHCP Search Domain resolution (openux-cmp.<search-domain>)
      3. Global fallback discovery cloud service
    """
    url = config.get("cmp_url", "")
    # If the cmp_url is default/local or empty, check DNS options
    if not url or "central-monitoring-platform.local" in url:
        discovered = resolve_cmp_via_dns()
        if discovered:
            print(f"Discovered cloud CMP via DNS: {discovered}")
            return discovered
        # Fallback to public global discovery url if local discovery fails
        if not url:
            print(f"No local discovery. Fallback to global portal: {GLOBAL_DISCOVERY_URL}")
            return GLOBAL_DISCOVERY_URL
    return url

def load_config():
    """Loads configuration from CONFIG_PATH or creates a default one."""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                config = {**DEFAULT_CONFIG, **json.load(f)}
            # Translate "auto" or empty sensor_id to actual machine UUID
            if config.get("sensor_id") in ("", "auto"):
                config["sensor_id"] = get_sensor_uuid()
            return config
        except Exception as e:
            print(f"Error reading config: {e}. Using defaults.")

    # Auto-generate Sensor ID if empty
    config = DEFAULT_CONFIG.copy()
    config["sensor_id"] = get_sensor_uuid()

    # Try to write default config if directory exists
    try:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=4)
        print(f"Generated default config at {CONFIG_PATH}")
    except Exception as e:
        print(f"Could not save default config: {e}")

    return config

def save_config(config):
    """Saves the active configuration back to configuration file path."""
    try:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=4)
        print(f"Successfully saved updated config to {CONFIG_PATH}")
    except Exception as e:
        print(f"Error saving config file: {e}")

def get_sensor_uuid():
    """Gets or generates a unique hardware identifier."""
    # Try systemd machine-id first
    if os.path.exists("/etc/machine-id"):
        with open("/etc/machine-id", "r") as f:
            return f.read().strip()
    # Fallback to UUID
    return str(uuid.uuid4())

def get_running_containers():
    """Queries Docker CLI for currently running containers."""
    try:
        cmd = ["docker", "ps", "--format", "{{.Names}}\t{{.Image}}\t{{.ID}}"]
        output = subprocess.check_output(cmd, text=True).strip()
        containers = {}
        if output:
            for line in output.split("\n"):
                parts = line.split("\t")
                if len(parts) == 3:
                    containers[parts[0]] = {"image": parts[1], "id": parts[2]}
        return containers
    except Exception as e:
        print(f"Error querying Docker: {e}")
        return {}

def get_all_container_names():
    """Queries Docker CLI for ALL containers (running + stopped) to avoid name collisions."""
    try:
        cmd = ["docker", "ps", "-a", "--format", "{{.Names}}"]
        output = subprocess.check_output(cmd, text=True).strip()
        return set(output.split("\n")) if output else set()
    except Exception as e:
        print(f"Error querying all containers: {e}")
        return set()

def run_cmd(cmd):
    """Utility to run shell command and return status."""
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {' '.join(cmd)}. Error: {e}")
        return False

def pull_image(image):
    """Pulls latest image digest."""
    print(f"Pulling Docker image: {image}...")
    return run_cmd(["docker", "pull", image])

def stop_and_remove_container(name):
    """Stops and deletes a container."""
    print(f"Stopping and removing container: {name}...")
    run_cmd(["docker", "stop", name])
    run_cmd(["docker", "rm", name])

def start_container(name, container_spec):
    """Launches a container according to specification."""
    image = container_spec["image"]
    ports = container_spec.get("ports", [])
    volumes = container_spec.get("volumes", [])
    env = container_spec.get("env", {})
    command = container_spec.get("command", "")

    cmd = ["docker", "run", "-d", "--name", name, "--restart", "always"]

    for port in ports:
        cmd.extend(["-p", port])
    for vol in volumes:
        cmd.extend(["-v", vol])
    for k, v in env.items():
        cmd.extend(["-e", f"{k}={v}"])

    cmd.append(image)
    if command:
        cmd.extend(command.split())

    print(f"Starting container {name} using command: {' '.join(cmd)}")
    return run_cmd(cmd)

def reconcile_containers(target_containers):
    """Aligns host docker state with the target spec."""
    # Safety threshold: refuse to wipe all containers if CMP returns empty state
    if not target_containers:
        print("WARNING: CMP returned empty container target state. Skipping reconciliation to prevent accidental wipe.")
        return

    running = get_running_containers()
    all_names = get_all_container_names()

    # 1. Stop containers not in target spec
    for name in list(running.keys()):
        if name not in target_containers:
            stop_and_remove_container(name)

    # 2. Reconcile matching and missing containers
    for name, spec in target_containers.items():
        needs_start = False
        if name in running:
            # If the image tag/digest changed, recreate it
            if running[name]["image"] != spec["image"]:
                print(f"Image mismatch for {name}. Target: {spec['image']}, Running: {running[name]['image']}")
                stop_and_remove_container(name)
                pull_image(spec["image"])
                needs_start = True
        else:
            # Container is not running. Check if a stopped container with this name exists.
            if name in all_names:
                print(f"Removing stopped container '{name}' before restarting...")
                stop_and_remove_container(name)
            pull_image(spec["image"])
            needs_start = True

        if needs_start:
            start_container(name, spec)

    # 3. Clean up dangling images to save disk space
    run_cmd(["docker", "image", "prune", "-f"])

def reconcile_wifi(wifi_spec, interface, config_path):
    """Reconciles Wi-Fi settings (re-writes wpa_supplicant if changed)."""
    if not wifi_spec:
        return

    ssid = wifi_spec.get("ssid")
    sec_type = wifi_spec.get("security", "open").lower()

    # Build wpa_supplicant blocks based on security type
    config_blocks = [
        "ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev",
        "update_config=1",
        "country=US\n"
    ]

    network_block = ["network={", f'    ssid="{ssid}"']

    if sec_type == "open":
        network_block.append("    key_mgmt=NONE")
    elif sec_type == "psk":
        psk = wifi_spec.get("psk")
        network_block.append(f'    psk="{psk}"')
        network_block.append("    key_mgmt=WPA-PSK")
    elif sec_type == "eap-peap":
        username = wifi_spec.get("username")
        password = wifi_spec.get("password")
        network_block.append("    key_mgmt=WPA-EAP")
        network_block.append("    eap=PEAP")
        network_block.append(f'    identity="{username}"')
        network_block.append(f'    password="{password}"')
        network_block.append("    phase2=\"auth=MSCHAPV2\"")

    network_block.append("}")
    config_blocks.append("\n".join(network_block))
    new_config = "\n".join(config_blocks)

    # Check if existing config matches
    current_config = ""
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            current_config = f.read()

    if new_config.strip() != current_config.strip():
        print(f"Wi-Fi config change detected. Writing new config for SSID: {ssid}")
        try:
            with open(config_path, "w") as f:
                f.write(new_config)

            # Restart wpa_supplicant to apply configuration
            print("Restarting Wi-Fi interface...")
            run_cmd(["wpa_cli", "-i", interface, "reconfigure"])
        except Exception as e:
            print(f"Failed to update Wi-Fi: {e}")

def wipe_and_reset():
    """Wipes all containers and images for a clean reinstall."""
    print("WARNING: CMP requested complete factory reset of the sensor containers!")
    # Stop all running containers
    try:
        running_ids = subprocess.check_output(["docker", "ps", "-q"], text=True).strip().split()
        if running_ids:
            subprocess.run(["docker", "stop"] + running_ids)
    except Exception:
        pass

    # Remove all containers, volumes, and networks
    run_cmd(["docker", "system", "prune", "-a", "--volumes", "-f"])

def register_sensor(config, cmp_url):
    """Phones home to register the sensor and check approval status.
    If approved, returns the generated API Key. Otherwise, returns None."""
    url = f"{cmp_url}/sensors/register"

    # Get hostname and mac address for metadata
    import socket
    import re
    try:
        hostname = socket.gethostname()
    except Exception:
        hostname = "unknown"

    try:
        # Simple MAC address lookup from first active interface
        import uuid
        mac_addr = ':'.join(re.findall('..', '%012x' % uuid.getnode()))
    except Exception:
        mac_addr = "unknown"

    payload = {
        "sensor_id": config["sensor_id"],
        "os": sys.platform,
        "hostname": hostname,
        "mac_address": mac_addr,
        "timestamp": int(time.time())
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                if data.get("status") == "approved":
                    return data.get("api_key")
    except Exception as e:
        print(f"Registration poll failed: {e}")
    return None

def phone_home(config, cmp_url):
    """Reaches out to the CMP API to report status and get target configuration."""
    url = f"{cmp_url}/sensors/reconcile"

    # Gather basic host metrics to send to CMP
    payload = {
        "sensor_id": config["sensor_id"],
        "os": sys.platform,
        "timestamp": int(time.time()),
        "containers": get_running_containers()
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-API-Key": config.get("api_key", "")
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                return data
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print("CMP returned 401 Unauthorized. Key may have been revoked or is invalid.")
            # Clear invalid key locally
            config["api_key"] = ""
            save_config(config)
        else:
            print(f"HTTP Error checking in: {e}")
    except urllib.error.URLError as e:
        print(f"Failed to connect to Central Monitoring Platform at {url}: {e}")
    except Exception as e:
        print(f"Error reporting status: {e}")

    return None

def reconcile_schedules(schedules: dict, config: dict):
    """Evaluates dynamic test schedules from CMP and executes scheduled or on-demand tests.
    Spawns test runners in background processes with strict process bounds so the main
    reconciler check-in loop never drops heartbeats."""
    if not schedules:
        return

    bw_spec = schedules.get("bandwidth", {})
    if bw_spec.get("enabled") or bw_spec.get("run_now"):
        server = bw_spec.get("server", "iperf3.district.local")
        port = str(bw_spec.get("port", 5201))
        duration = str(bw_spec.get("duration_seconds", 10))
        cap = str(bw_spec.get("bandwidth_cap_mbps", 100))
        interfaces = bw_spec.get("interfaces", ["eth0", "wlan0"])
        allowed = bw_spec.get("allowed_hours", [])

        cmd = [
            "/usr/local/bin/iperf3_runner.py",
            "--server", server,
            "--port", port,
            "--duration", duration,
            "--bandwidth-cap", cap,
            "--interfaces"
        ] + interfaces

        if allowed:
            cmd.append("--allowed-hours")
            cmd.extend(allowed)

        if bw_spec.get("run_now"):
            cmd.append("--force")
            print("Executing on-demand bandwidth test triggered by CMP...")
        else:
            print("Checking scheduled bandwidth test parameters...")

        # Run in background non-blocking subprocess so reconciler never drops heartbeats
        try:
            runner_script = "/usr/local/bin/iperf3_runner.py"
            if not os.path.exists(runner_script):
                runner_script = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "iperf3_runner.py"))
            if os.path.exists(runner_script):
                cmd[0] = runner_script
                subprocess.Popen(["python3"] + cmd)
        except Exception as e:
            print(f"Failed to spawn bandwidth test: {e}")

def reconcile_pcap_trigger(pcap_spec: dict, config: dict):
    """Checks for on-demand incident PCAP snapshot triggers from CMP."""
    if not pcap_spec or not pcap_spec.get("trigger_now"):
        return

    reason = pcap_spec.get("reason", "cmp_remote_trigger")
    print(f"Executing incident PCAP snapshot capture (Reason: {reason})...")
    try:
        runner_script = "/usr/local/bin/pcap_trigger.py"
        if not os.path.exists(runner_script):
            runner_script = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "pcap_trigger.py"))
        if os.path.exists(runner_script):
            subprocess.Popen(["python3", runner_script, "--trigger", reason])
    except Exception as e:
        print(f"Failed to trigger PCAP snapshot: {e}")

def reconcile_custom_probes(custom_probes: list, config: dict):
    """Synchronizes custom synthetic probes from CMP with /etc/sensor/custom_probes.json
    and spawns the custom probe runner."""
    if custom_probes is None:
        return

    probes_file = "/etc/sensor/custom_probes.json"
    os.makedirs(os.path.dirname(probes_file), exist_ok=True)

    current_probes = []
    if os.path.exists(probes_file):
        try:
            with open(probes_file, "r") as f:
                current_probes = json.load(f)
        except Exception:
            pass

    if current_probes != custom_probes:
        print(f"Updating custom synthetic probes configuration ({len(custom_probes)} probes)...")
        try:
            with open(probes_file + ".tmp", "w") as f:
                json.dump(custom_probes, f, indent=2)
            os.replace(probes_file + ".tmp", probes_file)
        except Exception as e:
            print(f"Failed to write {probes_file}: {e}")

    try:
        runner_script = "/usr/local/bin/custom_probe_runner.py"
        if not os.path.exists(runner_script):
            runner_script = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "custom_probe_runner.py"))
        if os.path.exists(runner_script):
            subprocess.Popen(["python3", runner_script, "--config", probes_file])
    except Exception as e:
        print(f"Failed to spawn custom probe runner: {e}")

def main():
    print("Starting Sensor Reconciler service...")
    config = load_config()

    while True:
        # Dynamically discover the cloud server location
        cmp_url = get_cmp_url(config)

        # If the sensor has no API Key, run registration approval flow
        if not config.get("api_key"):
            print(f"Sensor is pending approval. Querying registry at {cmp_url}...")
            api_key = register_sensor(config, cmp_url)
            if api_key:
                print("Registration approved! API Key received.")
                config["api_key"] = api_key
                save_config(config)
            else:
                # Sleep and retry registration
                time.sleep(config["check_interval_seconds"])
                continue

        # Authenticated reconcile loop
        target_state = phone_home(config, cmp_url)

        if target_state:
            # Check for reset trigger
            if target_state.get("reset", False):
                wipe_and_reset()

            # Reconcile local networking, docker runtimes, test schedules, and PCAP triggers
            reconcile_wifi(target_state.get("wifi"), config["wifi_interface"], config["wifi_config_path"])
            reconcile_containers(target_state.get("containers", {}))
            reconcile_schedules(target_state.get("schedules", {}), config)
            reconcile_pcap_trigger(target_state.get("pcap_trigger", {}), config)
            reconcile_custom_probes(target_state.get("custom_probes", []), config)

        time.sleep(config["check_interval_seconds"])

if __name__ == "__main__":
    main()
