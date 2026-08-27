# OpenUX Sensor Guide

This directory contains the codebase, configuration, and scripts for the hardware-based synthetic monitoring sensors. The sensors act as virtual end-users, continuously testing local RF, Wi-Fi RRM/DARRP behavior, L2/L3 onboarding, DHCP, DNS, state testing readiness (CAASPP), bandwidth capacity, and application delivery.

---

## Hardware Requirements

To ensure accurate synthetic testing (particularly for resource-intensive Playwright browser automation) and to prevent telemetry metrics from being skewed by local hardware bottlenecks, each sensor must meet the following minimum specification:

* **CPU:** 4-core 64-bit Processor (ARM64 or x86_64)
* **RAM:** **8 GB RAM minimum**
* **Storage:** 32 GB high-endurance storage (eMMC or SSD recommended)
* **Wired NIC:** 1x Gigabit / 2.5GbE Ethernet (`eth0` — used as the scientific control group)
* **Wireless NIC:** 1x Wi-Fi 6 / 6E / Wi-Fi 7 adapter (`wlan0` — supporting station mode, WPA3/WPA2, and 802.1X EAP-PEAP)

### Recommended Platforms
* **Raspberry Pi 5 (8GB RAM)**
* **Intel N100 / N300 Mini PC (8GB/16GB RAM)**

---

## Sensor Diagnostic Modules

| Script | Purpose | Output Metric File |
|---|---|---|
| **`reconciler/reconciler.py`** | Pull-based edge daemon. Reconciles Docker targets, Wi-Fi specs, test schedules, and executes on-demand triggers. | Control Plane API |
| **`caaspp_readiness.py`** | Validates Cambium TDS/TIDE, ETS TOMS, Smarter Balanced SSO, and verifies SSL Inspection bypass. | `/var/lib/node_exporter/textfile_collector/caaspp.prom` |
| **`rrm_darrp_monitor.py`** | Tracks Fortinet DARRP / GSK dynamic channel switches, channel dwell stability, and co-channel interference. | `/var/lib/node_exporter/textfile_collector/wifi_rrm.prom` |
| **`iperf3_runner.py`** | Scheduled and on-demand throughput/jitter testing with bandwidth throttling and time-window restrictions. | `/var/lib/node_exporter/textfile_collector/iperf3.prom` |
| **`cipa_compliance.py`** | Tests filtering of restricted content categories (CSAM, Terrorist, Adult, etc.) with pre-flight control probe. | `/var/lib/node_exporter/textfile_collector/cipa.prom` |
| **`wifi_dhcp_exporter.py`** | Parses system logs for Association, Authentication, and DHCP lease duration metrics. | `/var/lib/node_exporter/textfile_collector/wifi_dhcp.prom` |
| **`browser_transaction.py`** | Headless Chromium Playwright runner tracking page load times and blocked tracker domains. | `/var/lib/node_exporter/textfile_collector/browser.prom` |

---

## Installation & Configuration

### 1. Automated Installation
Execute the installation script with root privileges:
```bash
sudo ./install.sh
```

### 2. Configure `/etc/sensor/reconciler.json`
```json
{
    "cmp_url": "http://your-cmp-server:8000/api/v1",
    "sensor_id": "auto",
    "api_key": "",
    "check_interval_seconds": 60,
    "wifi_interface": "wlan0",
    "wifi_config_path": "/etc/wpa_supplicant/wpa_supplicant.conf"
}
```
* **Leave `api_key` empty (`""`)**: Initiates the Trust-On-First-Use (TOFU) registration flow. The sensor will register in a pending state and automatically download its cryptographic key upon admin approval.

### 3. Service Management
```bash
sudo systemctl start sensor-reconciler
sudo systemctl enable sensor-reconciler
sudo journalctl -u sensor-reconciler -f
```
