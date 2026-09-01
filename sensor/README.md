# Open Network Experience (ONE) — Edge Sensor Architecture & Operating Guide

This directory contains the codebase, configuration, and diagnostic engines for the **Open Network Experience (ONE)** hardware synthetic monitoring edge sensors.

Sensors act as continuous virtual end-users placed across school campuses, testing local RF environments, Wi-Fi Radio Resource Management (RRM), DHCP/DNS latency, state testing platforms (CAASPP/ELPAC), Lateral East-West VLAN segmentation, real-time UDP voice/video jitter (MOS), web transactions, and GPS fleet geolocation.

---

## 📋 Table of Contents

1. [Hardware Requirements & Recommended Platforms](#-hardware-requirements--recommended-platforms)
2. [GPS / GNSS Hardware Compatibility Guide & Purchase Links](#-gps--gnss-hardware-compatibility-guide--purchase-links)
3. [Dual-NIC Architecture (Split-Brain Diagnostics)](#-dual-nic-architecture-split-brain-diagnostics)
4. [Complete Sensor Diagnostic Suite](#-complete-sensor-diagnostic-suite)
5. [Installation & Service Setup](#-installation--service-setup)
6. [Troubleshooting & Verification](#-troubleshooting--verification)

---

## 🖥️ Hardware Requirements & Recommended Platforms

To guarantee accurate synthetic measurements—especially for resource-intensive headless Chromium Playwright browser transactions—and prevent metrics from being skewed by local CPU/memory throttling, each physical sensor must meet the following baseline specifications:

| Component | Minimum Specification | Recommended Specification |
|---|---|---|
| **Processor** | 4-Core 64-bit CPU (ARM64 or x86_64) | 4-Core or 8-Core modern CPU (ARM Cortex-A76 / Intel Alder Lake-N) |
| **Memory** | **8 GB RAM** | **8 GB – 16 GB RAM** |
| **Storage** | 32 GB eMMC / High-Endurance MicroSD | 64 GB+ NVMe SSD / M.2 SATA |
| **Control NIC** | 1x 1GbE Gigabit Ethernet (`eth0`) | 1x 1GbE / 2.5GbE PoE-capable Ethernet |
| **Test NIC** | 1x Wi-Fi 6 (802.11ax) Adapter (`wlan0`) | 1x Wi-Fi 6E / Wi-Fi 7 Tri-Band (2.4 / 5 / 6 GHz) Adapter |

### Tested & Approved Hardware Platforms:
1. **Raspberry Pi 5 (8GB RAM)**: Ideal for classroom ceiling drops and wall-mount enclosures. Can be powered via Official Raspberry Pi PoE+ HAT.
2. **Intel N100 / N300 Mini PC (8GB/16GB RAM)**: Ideal for high-density MDF/IDF network closets and lab testing environments with dual integrated 2.5GbE Intel i226-V NICs.
3. **Raspberry Pi 4 Model B (8GB RAM)**: Supported baseline platform for standard synthetic workloads.

---

## 🛰️ GPS / GNSS Hardware Compatibility Guide & Purchase Links

The ONE Sensor includes an autonomous GPS & precision geolocation engine (`sensor/gps_location_collector.py`). When an outdoor or window-adjacent sensor has a GPS dongle plugged into USB, it parses NMEA `$GPGGA` and `$GPRMC` sentences, tracks satellite locks, and automatically pins its live coordinates to the Central Management Web UI and Grafana GIS maps.

### Tested & Compatible GPS / GNSS Receivers

| Model | Chipset | Interface | Mounting / Enclosure | Approx. Price | Buy Link |
|---|---|---|---|---|---|
| **VK-162 G-Mouse USB GPS** | u-blox 7 | USB (CDC-ACM / PL2303) | Weatherproof Magnetic Base (2m cable) | ~$14 USD | [Amazon](https://www.amazon.com/dp/B01EROIUEW) |
| **VK-172 USB GPS Stick** | u-blox 7 | USB-A Dongle | Ultra-compact Flash Drive form-factor | ~$11 USD | [Amazon](https://www.amazon.com/dp/B01MTU9KTF) |
| **GlobalSat BU-353-S4** | SiRF Star IV | USB-A (PL2303) | Weatherproof Magnetic Dome (1.5m cable) | ~$35 USD | [Amazon](https://www.amazon.com/dp/B0082X32XA) |
| **Adafruit Ultimate GPS USB** | MTK3339 | USB-A (CP2104) | Internal patch antenna + external SMA | ~$39 USD | [Adafruit](https://www.adafruit.com/product/4279) |
| **Waveshare GNSS HAT (Pi)** | u-blox MAX-M8Q | 40-pin GPIO / UART | Raspberry Pi HAT + Active Antenna | ~$28 USD | [Waveshare](https://www.waveshare.com/pico-gps-l76b.htm) / [Amazon](https://www.amazon.com/dp/B07P96MV8K) |

### Supported GNSS Constellations:
* **GPS (USA)**
* **GLONASS (Russia)**
* **Galileo (European Union)**
* **BeiDou (China)**
* **SBAS / WAAS** (Wide Area Augmentation System for sub-3 meter accuracy)

### How to Verify GPS Hardware on Linux:
```bash
# 1. Check if the kernel detected the USB serial device
ls -l /dev/ttyUSB* /dev/ttyACM* /dev/serial0

# 2. View raw NMEA satellite data stream (e.g. at 9600 baud)
cat /dev/ttyACM0

# Expected output:
# $GPGGA,194530.000,3522.3975,N,11901.1227,W,1,08,0.9,120.4,M,46.9,M,,*47
# $GPRMC,194530.000,A,3522.3975,N,11901.1227,W,0.02,84.62,270826,,,A*7B

# 3. Test ONE's automated GPS telemetry collector
python3 /usr/local/bin/gps_location_collector.py
```

*Note: For indoor sensors where satellite signals cannot penetrate concrete walls, the sensor seamlessly falls back to the static campus location profile (`/etc/sensor/location.json`) configured via the Web UI.*

---

## 🔀 Dual-NIC Architecture (Split-Brain Diagnostics)

To eliminate false positives caused by WAN upstream outages, ONE sensors utilize **Split-Brain Dual-NIC Policy-Based Routing (PBR)**:

```
                      ┌──────────────────────────────┐
                      │    ONE Hardware Sensor       │
                      │                              │
[Core Switch / PoE] ──┼─► eth0 (Control Baseline)    │ ──► CMP Reconciler & Heartbeats
                      │   - Static IP / Mgmt VLAN    │ ──► Control Baseline Metrics
                      │                              │
[Classroom Wi-Fi AP] ─┼─► wlan0 (Variable Testing)   │ ──► Synthetic Browser Transactions
                      │   - DHCP / Student VLAN      │ ──► State Testing (CAASPP) Readiness
                      │   - 802.1X / PSK SSID        │ ──► Real-Time VoIP Jitter (MOS)
                      └──────────────────────────────┘
```

* **Wired Interface (`eth0`)**: Acts as the unshakeable **scientific control**. Telemetry check-ins, Prometheus remote write, and baseline latency tests egress here. If Google/Canvas goes down globally, `eth0` catches it.
* **Wireless Interface (`wlan0`)**: Acts as the **experimental variable**. Probes bind directly to `wlan0` using Linux `SO_BINDTODEVICE` and routing table `100 wlan-test`. If tests fail on `wlan0` but pass on `eth0`, the problem is proven to be local Wi-Fi RF, DHCP, or AP congestion.

---

## 🔬 Complete Sensor Diagnostic Suite

| Diagnostic Module | Execution Method | Prometheus Metric Output | Description |
|---|---|---|---|
| **`reconciler/reconciler.py`** | Systemd Daemon (`sensor-reconciler.service`) | Control Plane API (`/api/v1/sensors/reconcile`) | Pull-based state engine. Reconciles Wi-Fi credentials, Docker containers, test schedules, custom probes, and remote triggers. |
| **`gps_location_collector.py`** | Periodic Runner / Textfile Exporter | `openux_sensor_gps_*.prom` | Reads NMEA GPS hardware (`$GPGGA`) or campus location profiles and exports latitude, longitude, and satellite lock status. |
| **`custom_probe_runner.py`** | Periodic Dynamic Engine | `openux_custom_probe_*.prom` | Executes WYSIWYG EasyBuilder probes (HTTP, API, DNS, TCP) configured via the Web UI. |
| **`dns_multi_resolver_probe.py`** | Periodic Probe | `openux_dns_resolver_*.prom` | Benchmarks local DHCP resolvers against Cloudflare (`1.1.1.1`), Google (`8.8.8.8`), Quad9 (`9.9.9.9`), and OpenDNS (`208.67.222.222`). |
| **`voip_jitter_probe.py`** | Periodic UDP Stream | `openux_voip_*.prom` | Measures 20ms G.711/Opus RTP media packet jitter, loss %, and calculates ITU-T G.107 Mean Opinion Score (MOS 1.0–4.5) for Zoom/Meet/Teams. |
| **`segmentation_prober.py`** | Security Audit Probe | `openux_segmentation_*.prom` | Validates East-West student VLAN isolation against switch SSH, camera networks, and administrative subnets. |
| **`caaspp_readiness.py`** | Synthetic Probe | `openux_caaspp_*.prom` | Validates Cambium TDS/TIDE, ETS TOMS, Smarter Balanced SSO, and verifies SSL Inspection bypass to prevent Secure Browser certificate errors. |
| **`rrm_darrp_monitor.py`** | RF Background Monitor | `openux_wifi_rrm_*.prom` | Monitors dynamic channel switching, channel dwell time, co-channel interference (CCI), and alerts on RF flapping (>3 switches/hr). |
| **`browser_transaction.py`** | Headless Chromium Container | `openux_browser_*.prom` | End-to-end user transactions with automated Playwright `.har` waterfall and `.png` error screenshot capture upon failure. |
| **`pcap_trigger.py`** | RAM Buffer Daemon | `/var/lib/sensor/snapshots/*.pcap` | High-speed circular RAM buffer (`/dev/shm`) slicing 128-byte packet headers and dumping 60-second PCAPs on anomaly or NOC demand. |
| **`evidence_collector.py`** | Forensic Packager | `/var/lib/sensor/evidence_bundles/*.tar.gz` | Bundles PCAP slices, HAR waterfalls, systemd journal logs, RF state, and Plain-English Executive Incident Cards. |
| **`iperf3_runner.py`** | Scheduled Bandwidth Runner | `openux_iperf3_*.prom` | Bandwidth throughput and jitter testing with off-peak time restrictions and speed caps. |
| **`cipa_compliance.py`** | Content Filter Probe | `openux_cipa_*.prom` | Validates CIPA content filtering compliance against restricted categories with pre-flight control probes. |
| **`wifi_dhcp_exporter.py`** | Syslog Parser | `openux_wifi_dhcp_*.prom` | Measures exact elapsed time for 802.11 Association, 802.1X EAP Authentication, and DHCP DORA lease acquisition. |

---

## 🚀 Installation & Service Setup

### 1. ⚡ 1-Line Remote SSH Installer & Zero-Touch Bootstrap (Recommended)

You can provision a fresh sensor over SSH with a **single command**. The installer automatically audits hardware specs, installs dependencies (Docker, `wpasupplicant`, `iperf3`, `mtr-tiny`), downloads all 12 synthetic diagnostic modules directly from the CMP server, generates `/etc/sensor/reconciler.json`, and starts the `sensor-reconciler.service` daemon:

#### A. Standard Campus Provisioning (with Location Metadata)
```bash
curl -sSL http://192.0.2.10:8000/install.sh | sudo bash -s -- \
  --cmp http://192.0.2.10:8000/api/v1 \
  --district "Metro Unified School District" \
  --site "West High School" \
  --building "Science Wing" \
  --room "Room 102"
```

#### B. Zero-Configuration DHCP Option 43 / DNS Auto-Discovery
If your campus DHCP server provides **DHCP Option 43** or DNS search domains (`openux-cmp.example.com`):
```bash
curl -sSL http://192.0.2.10:8000/install.sh | sudo bash
```

#### C. Lab / Low-Power Hardware Override
If testing on entry-level development boards, VMs, or Raspberry Pi boards with <8GB RAM or 2 cores:
```bash
curl -sSL http://192.0.2.10:8000/install.sh | sudo bash -s -- --cmp http://192.0.2.10:8000/api/v1 --force
```

---

### 2. Manual / Offline Installation (From Git Clone)

If deploying from a local clone of this repository:
```bash
cd sensor
sudo ./install.sh --cmp http://192.0.2.10:8000/api/v1 --site "City Center" --room "IT Operations"
```

---

### 3. Sensor Configuration File (`/etc/sensor/reconciler.json`)

The installer generates `/etc/sensor/reconciler.json`:
```json
{
    "cmp_url": "http://192.0.2.10:8000/api/v1",
    "sensor_id": "f10325921e2b43b2b5fcf33cadad864b",
    "api_key": "",
    "enrollment_token": "",
    "check_interval_seconds": 15,
    "wifi_interface": "wlan0",
    "wifi_config_path": "/etc/wpa_supplicant/wpa_supplicant.conf",
    "initial_location": {
        "district": "Unified School District",
        "site": "City Center",
        "building": "1300 17th St",
        "room": "IT Operations"
    }
}
```

* **Trust-On-First-Use (TOFU) Registration**: Leave `"api_key": ""` blank. When the sensor first boots:
  * **Subnet Auto-Approval**: If the sensor's subnet CIDR matches a rule in CMP, it is **instantly approved** and assigned to its campus site.
  * **Manual Approval**: Otherwise, it registers in `pending` status. A NOC administrator can click **`[✓ Approve]`** or use **`[Batch Approve]`** in the Web UI dashboard.

---

### 4. Service Management & Live Logs
```bash
# Check service status
sudo systemctl status sensor-reconciler

# Restart the service
sudo systemctl restart sensor-reconciler

# View live adaptive resolution transitions and check-in logs
sudo journalctl -u sensor-reconciler -f
```

---

## 🔍 Troubleshooting & Verification

### Test Individual Diagnostic Modules Manually:
```bash
# Test Multi-Resolver DNS Health
python3 /usr/local/bin/dns_multi_resolver_probe.py

# Test Voice/Video RTP Jitter & MOS calculation
python3 /usr/local/bin/voip_jitter_probe.py

# Test East-West VLAN Segmentation
python3 /usr/local/bin/segmentation_prober.py

# Test State Testing (CAASPP) Endpoints
python3 /usr/local/bin/caaspp_readiness.py

# Run Custom WYSIWYG Probes
python3 /usr/local/bin/custom_probe_runner.py

# Query Live GPS Fix & Campus Geolocation
python3 /usr/local/bin/gps_location_collector.py
```

### Inspect Output Prometheus Metric Files:
```bash
ls -la /var/lib/node_exporter/textfile_collector/*.prom
cat /var/lib/node_exporter/textfile_collector/location.prom
cat /var/lib/node_exporter/textfile_collector/voip_jitter.prom
cat /var/lib/node_exporter/textfile_collector/dns_resolvers.prom
```
