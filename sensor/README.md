# Open-Source Aruba UXI Alternative: Sensor Guide

This directory contains the codebase, configuration, and scripts for the hardware-based synthetic monitoring sensors. The sensors act as virtual end-users, continuously testing local RF, L2/L3 onboarding, DHCP, DNS, Security Gateway inspection, and application delivery (Playwright).

---

## Minimum Hardware Requirements

To ensure accurate synthetic testing (particularly for resource-intensive Playwright browser automation) and to prevent telemetry metrics from being skewed by local hardware bottlenecks, each sensor must meet the following minimum specification:

* **CPU:** 4-core 64-bit Processor (ARM64 or x86_64)
* **RAM:** **8 GB RAM minimum**
* **Storage:** 32 GB high-endurance storage (such as high-endurance SD cards, eMMC, or SSD)
* **Wired Interface:** 1x Gigabit Ethernet (for management and wired path comparison)
* **Wi-Fi Interface:** 1x Wi-Fi 6 (or later) adapter that supports:
  * Active station mode (client association)
  * wpa_supplicant control interface integration
  * Monitor mode (optional, for passive RF logging)

### Recommended Platforms
* **Raspberry Pi 5 (8GB RAM)**
* **Intel N100 Mini PC (8GB/16GB RAM)**

---

## Installation

An automated script is provided to verify system compliance and bootstrap the sensor runtime.

### 1. Prerequisites
Ensure you are running a clean installation of a Debian-based Linux distribution (Debian 12 or Ubuntu 22.04 LTS recommended).

### 2. Run the Installer
Execute the installation script with root privileges:

```bash
sudo ./install.sh
```

The script will:
* Check CPU cores, RAM size, and disk space.
* Install required system dependencies (`wpasupplicant`, `docker`, `iperf3`, `mtr-tiny`, `python3`).
* Copy the reconciler agent to `/usr/local/bin/reconciler.py` and register the systemd service.
* Copy the CIPA compliance checker to `/usr/local/bin/cipa_compliance.py`.

---

## Sensor Reconciler & Configuration

The sensor is managed via a pull-based Agent (`reconciler.py`) running as a systemd service. It periodically checks in with the Central Monitoring Platform (CMP) server, reports running containers, and reconciles the host container/network state with the target configuration.

### Configuration (`/etc/sensor/reconciler.json`)
After running the installer, configure the reconciler with your server endpoints and security keys:

```json
{
    "cmp_url": "http://your-cmp-server:8000/api/v1",
    "sensor_id": "auto",
    "api_key": "sensor-edge-key-change-me",
    "check_interval_seconds": 60,
    "wifi_interface": "wlan0",
    "wifi_config_path": "/etc/wpa_supplicant/wpa_supplicant.conf"
}
```

* **`cmp_url`**: The base URL of the CMP API server.
* **`sensor_id`**: Set to `"auto"` (default) to automatically generate a unique ID using the host's `/etc/machine-id` or system UUID.
* **`api_key`**: The edge security API key required by the CMP for authentication (`X-API-Key` header).
* **`wifi_interface`**: Local wireless interface name.
* **`wifi_config_path`**: Path to the `wpa_supplicant.conf` configuration file.

### Service Management
Manage the reconciler using standard systemd commands:
```bash
# Start the reconciler agent
sudo systemctl start sensor-reconciler

# Enable service boot autostart
sudo systemctl enable sensor-reconciler

# Watch reconciler logs
sudo journalctl -u sensor-reconciler -f
```

---

## CIPA Compliance Testing

The sensor contains a dedicated Children's Internet Protection Act (CIPA) compliance checker (`cipa_compliance.py`). It attempts to connect to standardized verification URLs to determine if the local school network is successfully filtering restricted categories (CSAM, Terrorist content, Pornography, etc.).

### Manual Execution
Run the compliance check directly from the command line:
```bash
python3 cipa_compliance.py
```

### Prometheus Integration
The script can be run on a cron timer to populate Node Exporter metrics:
```bash
# Run every 5 minutes and write to Node Exporter textfile collector directory
*/5 * * * * /usr/local/bin/cipa_compliance.py /var/lib/node_exporter/textfile_collector/cipa_compliance.prom
```
If the filter successfully blocks a category, it exposes `cipa_compliance_status = 1` (Compliant). If a category is allowed, it exposes `0` (Non-Compliant), instantly triggering Grafana alert boards.

---

## Wi-Fi Onboarding Timing

The sensor includes an onboarding performance timing tool (`wifi_dhcp_exporter.py`). It parses system log entries to measure exactly how long it takes the client wireless adapter to:
1. **Associate** with the AP (L2 connection)
2. **Authenticate** using WPA/EAP encryption
3. **Lease an IP address** from the local DHCP server

### Manual Execution
Run the onboarding timing script directly from the command line:
```bash
python3 wifi_dhcp_exporter.py
```

### Prometheus Integration
The script can be scheduled on a cron job to continuously feed diagnostic telemetry back to the NOC dashboard:
```bash
# Parse logs every 2 minutes and write metrics
*/2 * * * * /usr/local/bin/wifi_dhcp_exporter.py /var/lib/node_exporter/textfile_collector/wifi_dhcp.prom
```

Metrics exposed:
* `wifi_association_duration_seconds`: Time taken to associate with the access point.
* `wifi_authentication_duration_seconds`: Time taken to complete EAP/WPA encryption handshake.
* `wifi_dhcp_lease_duration_seconds`: Time taken to solicit and receive a DHCP IP address lease.
* `wifi_onboarding_success`: Binary success indicator (`1` = Connection successful, `0` = Authentication/DHCP timeout).

