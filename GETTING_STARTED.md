# Open Network Experience (ONE) Getting Started Guide

Welcome to the **Open Network Experience (ONE)** platform! This comprehensive guide walks you through standing up the Central Monitoring Platform (CMP) server stack in Docker, deploying physical edge sensors, using the pre-built Grafana NOC dashboards, and building custom synthetic tests for your local applications.

---

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Part 1: Standing Up the Server Stack (Docker Compose)](#part-1-standing-up-the-server-stack)
3. [Part 2: Deploying Physical & Virtual Sensors](#part-2-deploying-physical--virtual-sensors)
4. [Part 3: Exploring the Pre-Built Grafana Dashboards](#part-3-exploring-the-pre-built-grafana-dashboards)
5. [Part 4: Building Custom Synthetic Application Tests](#part-4-building-custom-synthetic-application-tests)
6. [Part 5: Troubleshooting & Operational FAQ](#part-5-troubleshooting--operational-faq)

---

## Architecture Overview

```mermaid
flowchart TD
    subgraph Cloud / Datacenter ["Central Monitoring Platform (CMP) Stack"]
        CMP["FastAPI Control Plane\n(:8000)"]
        VM["VictoriaMetrics TSDB\n(:8428)"]
        Grafana["Grafana Dashboards\n(:3000)"]
        Loki["Loki Log Engine\n(:3100)"]
        AM["Alertmanager\n(:9093)"]
    end

    subgraph Edge Sensor ["Remote Site / School Sensor (Pi 5 or Intel Mini PC)"]
        Reconciler["Sensor Reconciler Daemon\n(reconciler.py)"]
        PromAgent["Prometheus Agent\n(Buffers & remote_writes)"]
        NodeExp["Node Exporter + Textfile Collector\n(/var/lib/node_exporter/textfile_collector)"]

        subgraph Probes ["Diagnostic Synthetic Probes"]
            DualNIC["Dual-NIC Latency & iperf3\n(eth0 vs wlan0)"]
            CAASPP["CAASPP State Testing\n(caaspp_readiness.py)"]
            RRM["Wi-Fi DARRP / GSK Monitor\n(rrm_darrp_monitor.py)"]
            CIPA["CIPA Content Filter Check\n(cipa_compliance.py)"]
            Playwright["Playwright Browser Synthetics\n(browser_transaction.py)"]
            Custom["Custom Application Probes\n(custom_synthetic_probe.py)"]
        end
    end

    Probes -->|Atomically write .prom metrics| NodeExp
    NodeExp -->|Scraped locally| PromAgent
    PromAgent -->|HTTPS remote_write| VM
    Reconciler <-->|Polls configs & reports status| CMP
    VM -->|Queries metrics| Grafana
    Loki -->|Queries logs| Grafana
```

---

## Part 1: Standing Up the Server Stack

### 1. Prerequisites
* A Linux server or Cloud VM (Ubuntu 22.04 / 24.04 LTS or Debian 12 recommended).
* Minimum **2 CPU Cores**, **4 GB RAM**, and **20 GB Disk**.
* **Docker Engine** (v24+) and **Docker Compose** installed.

### 2. Clone and Launch
```bash
# 1. Clone the repository
git clone https://github.com/leifdavisson/Open_Network_Experience.git
cd Open_Network_Experience/server/deploy

# 2. Build and start all 5 containers in detached mode
docker compose up --build -d
```

### 3. Verify Container Status
Run `docker compose ps` to verify all services are running:
```bash
NAME                        IMAGE                            STATUS
cmp-server                  open-ux/cmp-server:latest        Up (healthy)
victoriametrics             victoriametrics/victoria-metrics Up
grafana                     grafana/grafana:latest           Up
loki                        grafana/loki:latest              Up
alertmanager                prom/alertmanager:latest         Up
```

### 4. Access the Web Portals
* **Grafana Dashboards**: `http://<your-server-ip>:3000` (User: `admin` / Password: `admin`)
* **Interactive API Documentation (Swagger)**: `http://<your-server-ip>:8000/docs`
* **VictoriaMetrics TSDB API**: `http://<your-server-ip>:8428`

---

## Part 2: Deploying Physical & Virtual Sensors

### 1. Hardware Requirements
* **Recommended Platforms**: Raspberry Pi 5 (8GB) or Intel N100 / N300 Mini-PC.
* **Network Interfaces**:
  * **Wired NIC (`eth0`)**: Connects to the local switch / wall jack (serves as the scientific control baseline).
  * **Wireless NIC (`wlan0`)**: Wi-Fi 6 / 6E / 7 radio connecting to school/enterprise SSIDs.

### 2. Recommended Operating Systems (OS)
To ensure reliable driver support for Wi-Fi 6/6E adapters, USB GPS receivers, and Chromium Playwright browser testing, install a **64-bit headless Linux OS**:

| Platform | Primary Recommendation | Alternative Supported OS | Key Sizing Notes |
|---|---|---|---|
| **Raspberry Pi 5 / 4** | **Raspberry Pi OS (64-bit) Lite** (Bookworm) | **Ubuntu Server 24.04 LTS (ARM64)** | Use **64-bit Lite** (no GUI/desktop) to dedicate all 8GB RAM to synthetic tests. |
| **Intel N100 / N300 Mini PCs** | **Ubuntu Server 24.04 LTS** (64-bit) | **Debian 12 (Bookworm) Minimal** | Native support for dual Intel i226 2.5GbE Ethernet and USB 3.2. |
| **Virtual Appliance (VMware/Proxmox)** | **Ubuntu Server 24.04 LTS** | **Debian 12** | Allocate 4 vCPUs and 8 GB vRAM with PCIe/USB Wi-Fi passthrough. |

> [!TIP]
> **Why 64-bit Headless?** Modern headless Chromium and Playwright binaries require a 64-bit architecture (`arm64` or `x86_64`). Running a headless "Server" or "Lite" image keeps idle OS memory footprint under 250 MB, leaving maximum headroom for packet captures and browser transactions.

### 3. Deploying Sensors (Helpdesk-Friendly Methods)

#### Option A: 1-Line URL-Preset Web Bootstrapper (Zero-Touch)
Generate and copy the exact 1-line command from the CMP Web Console (**Fleet & Registration** tab) or run:

```bash
# 1-Line Remote Provisioning with URL Presets:
curl -sSL "http://<YOUR_CMP_SERVER_IP>:8000/install.sh?site=West+High+School&room=Room+204&building=Science+Wing" | sudo bash
```

Or pass explicit CLI flags:
```bash
curl -sSL http://<YOUR_CMP_SERVER_IP>:8000/install.sh | sudo bash -s -- \
  --site "West High School" \
  --room "Room 204" \
  --wifi-ssid "School-Staff" \
  --wifi-psk "SecurePassword123"
```

#### Option B: Interactive Terminal Setup Wizard (`one-wizard`)
For field technicians unboxing a new Raspberry Pi or troubleshooting on-site, launch the guided terminal wizard:

```bash
# Run wizard directly via installer:
curl -sSL http://<YOUR_CMP_SERVER_IP>:8000/install.sh | sudo bash -s -- --wizard

# Or re-run anytime on an already provisioned sensor:
sudo one-wizard
```

The interactive wizard guides technicians step-by-step through:
1. **Hardware & Interface Diagnostics**: Real-time Ethernet link status, Wi-Fi radio detection, MAC address, and persistent hardware UUID.
2. **CMP Control Plane Discovery & Health Check**: Automatic DHCP Option 43 & DNS resolution with live ping/latency verification.
3. **Campus Location & Drop ID Tagging**: District, campus, building, room number, and asset notes.
4. **Live Wi-Fi Site Survey**: Scans nearby SSIDs, signal strength, and configures [wpa_supplicant](https://w1.fi/wpa_supplicant) for WPA2/WPA3 Personal or 802.1X Enterprise.
5. **Instant Zero-Touch Registration & ZTP Check**: Evaluates registration and provisions API keys automatically.

#### Option C: USB Flash Drive Auto-Staging (Assembly-Line Fleet Staging)
For staging large batches of sensors (20 to 100+ Raspberry Pis / x86 Mini-PCs) rapidly before sending them out to school campuses:

1. In the CMP Web Dashboard (View 5), click **`💾 Download USB Kit (.zip)`** or curl the archive:
   ```bash
   curl -sSL "http://<YOUR_CMP_SERVER_IP>:8000/api/v1/onboarding/usb-kit.zip?site=West+High&room=Room+204" -o usb_staging_kit.zip
   ```
2. Unzip the contents directly onto any standard FAT32 / exFAT USB flash drive.
3. Plug the USB flash drive into a newly booted Ubuntu / Raspberry Pi sensor and execute:
   ```bash
   sudo ./setup.sh
   # (Or if already in a subfolder: sudo /media/*/*/setup.sh)
   ```
4. The auto-provisioner automatically copies offline synthetic probes, provisions Wi-Fi, registers with the CMP, and writes a physical audit receipt (`provisioned_sensors.csv`) back to the USB drive with the sensor's MAC, UUID, and assigned IP address.
5. Unplug the USB drive and insert it into the next sensor!

> [!NOTE]
> The bootstrapper automatically detects hardware specs, installs dependencies, downloads synthetic probe modules from the CMP server, writes `/etc/sensor/reconciler.json`, symlinks `/usr/local/bin/one-wizard`, and activates `sensor-reconciler.service`.

> [!TIP]
> **Enterprise Zero-Touch DHCP & DNS Setup**: For step-by-step instructions on setting up DHCP Option 43/60 and DNS discovery without impacting VoIP phones or Wi-Fi APs, see the comprehensive [DHCP Option 43 & DNS Discovery Guide](file:///data/Open_Network_Experience/docs/DHCP_OPTION_43_AND_DNS_DISCOVERY_GUIDE.md) (`file:///data/Open_Network_Experience/docs/DHCP_OPTION_43_AND_DNS_DISCOVERY_GUIDE.md`).

### 4. Zero-Touch & TOFU Approval

1. **Subnet Auto-Approval (ZTP)**: If the sensor IP matches an auto-enrollment subnet CIDR configured in CMP (`/api/v1/subnets`), it is **approved instantly** and assigned to its campus site without technician interaction.
2. **1-Click Web UI Approval (TOFU)**: If manual approval is enabled, open the CMP Dashboard at `http://<YOUR_CMP_SERVER_IP>:8000` and click **`[✓ Approve]`** or **`[Batch Approve]`** in the Pending Approval queue.

### 5. Monitor Live Sensor Activity
```bash
# Stream live adaptive resolution state transitions and check-in logs
sudo journalctl -u sensor-reconciler -f

# Check sensor systemd daemon status
sudo systemctl status sensor-reconciler
```

---

## Part 3: Exploring the Pre-Built Grafana Dashboards

When you open Grafana at `http://<your-server-ip>:3000`, three production-grade dashboards are automatically provisioned:

### 1. Master NOC Dashboard (`OpenUX NOC & Diagnostic Dashboard`)
* **Level 1 — Site NOC Overview**: CIPA content filter compliance table and WAN connectivity indicator.
* **Level 2 — Diagnostic Path Latency**: End-to-end hop-by-hop latency breakdowns.
* **Level 3 — Sensor Host Health**: Sensor CPU, memory, and Playwright execution event logs.
* **Level 4 — Dual-NIC & Bandwidth Diagnostics**: Side-by-side Wired (`eth0`) vs. Wireless (`wlan0`) latency comparison and scheduled `iperf3` throughput metrics.
* **Level 5 — CAASPP & ELPAC State Testing Readiness**: Live health table of California Assessment testing services and SSL inspection bypass validation.
* **Level 6 — Wi-Fi RRM & DARRP Spectrum Health**: AP channel dwelling timeline, flapping alerts (>3 switches/hour), and co-channel neighbor collision counts.

### 2. CAASPP State Testing Readiness Dashboard (`openux-caaspp`)
* Dedicated for school testing seasons.
* Highlights **Cambium Student Testing Interface**, **TIDE**, **ETS TOMS**, and **Smarter Balanced SSO**.
* Displays immediate red warnings if a firewall MITM certificate is detected.

### 3. Wi-Fi RF, DARRP & Spectrum Health Dashboard (`openux-wifi-rf`)
* Dedicated for Wi-Fi and RF engineers.
* Charts RSSI signal strength, Signal-to-Noise Ratio (SNR), and 802.11 Association, WPA/EAP Authentication, and DHCP lease duration metrics.

---

## Part 4: Building Custom Synthetic Application Tests

OpenUX makes it simple to test any internal application (e.g. Canvas LMS, PowerSchool SIS, Print Servers, SIP Gateways) using the **Prometheus Textfile Collector pattern**.

### 1. Use the Provided Probe Template
A complete starter template is located in [`sensor/examples/custom_synthetic_probe.py`](file:///data/Open_Network_Experience/sensor/examples/custom_synthetic_probe.py):

```python
#!/usr/bin/env python3
import time, urllib.request, os

TARGET_URL = "https://canvas.district.edu/login"
OUTPUT_FILE = "/var/lib/node_exporter/textfile_collector/custom_canvas.prom"

def test_canvas():
    start = time.time()
    try:
        req = urllib.request.Request(TARGET_URL, headers={"User-Agent": "OpenUX-Probe/1.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            latency = time.time() - start
            status = 1 if response.status == 200 else 0
    except Exception:
        status, latency = 0, time.time() - start

    # Atomically write metrics
    prom_data = f"""# HELP custom_canvas_status LMS health status (1=OK, 0=Fail)
# TYPE custom_canvas_status gauge
custom_canvas_status {status}
# HELP custom_canvas_latency_seconds Response time in seconds
# TYPE custom_canvas_latency_seconds gauge
custom_canvas_latency_seconds {latency:.4f}
"""
    tmp = OUTPUT_FILE + ".tmp"
    with open(tmp, "w") as f:
        f.write(prom_data)
    os.replace(tmp, OUTPUT_FILE)

if __name__ == "__main__":
    test_canvas()
```

### 2. Schedule Your Custom Probe
Add a cron job on the sensor to execute your custom test every 2 minutes:
```bash
sudo crontab -e
```
```text
*/2 * * * * /usr/bin/python3 /usr/local/bin/custom_canvas.py > /dev/null 2>&1
```

### 3. Graph It in Grafana
In your Grafana dashboard, simply add a panel with the PromQL query:
```promql
custom_canvas_latency_seconds{instance=~"$sensor"} * 1000
```
Node Exporter and VictoriaMetrics will automatically ingest your custom metrics!

---

## Part 5: Troubleshooting & Operational FAQ

### Q1: How do I check sensor logs in real time?
```bash
sudo journalctl -u sensor-reconciler -f
```

### Q2: Why is the sensor showing "Pending Approval"?
Brand new sensors must be approved by an administrator before they can check in. Run:
```bash
curl -X POST -H "X-API-Key: admin-noc-key-change-me" http://<CMP_IP>:8000/api/v1/sensors/<sensor-id>/approve
```

### Q3: How do I run a manual test on the sensor immediately?
```bash
# Test CAASPP state testing endpoints & SSL bypass
python3 /usr/local/bin/caaspp_readiness.py

# Test Wi-Fi DARRP / GSK channel switches and RF health
python3 /usr/local/bin/rrm_darrp_monitor.py

# Test CIPA content filtering compliance
python3 /usr/local/bin/cipa_compliance.py

# Run a 100 Mbps rate-limited bandwidth test
python3 /usr/local/bin/iperf3_runner.py --server speedtest.district.org --bandwidth-cap 100
```

### Q4: How do I change the administrative API key?
In `server/main.py`, update `ADMIN_API_KEY` (or pass it via an environment variable) and restart the `cmp-server` container:
```bash
cd server/deploy && docker compose restart cmp-server
```
