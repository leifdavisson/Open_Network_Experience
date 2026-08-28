# Open Network Experience (ONE)

**Open Network Experience (ONE)** is a 24/7 digital assistant for school and district networks. Think of it as a virtual student and teacher sitting in classrooms, libraries, and offices around the clock—constantly testing the Wi-Fi, online learning tools, and school internet to ensure everything works smoothly *before* the school day begins.

Instead of waiting for a classroom of students to get disconnected during state testing or finding out a video lesson is buffering during second period, Open Network Experience continuously tests the network from the student's point of view. It alerts school technology teams to Wi-Fi dead spots, slow learning portals, or content filter issues instantly so problems can be solved before they disrupt teaching and learning.

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](LICENSE)
[![CI](https://github.com/leifdavisson/Open_Network_Experience/actions/workflows/ci.yml/badge.svg)](https://github.com/leifdavisson/Open_Network_Experience/actions/workflows/ci.yml)
[![Security](https://github.com/leifdavisson/Open_Network_Experience/actions/workflows/security.yml/badge.svg)](https://github.com/leifdavisson/Open_Network_Experience/actions/workflows/security.yml)

---

## Key Capabilities

1. **Dual-NIC Split-Brain Diagnostics**: Leverages both Wired (`eth0`) and Wireless (`wlan0`) NICs. The wired connection acts as a **scientific control group** — instantly isolating whether degradation is caused by local RF/AP interference vs. upstream switch, firewall, or ISP failures.
2. **CAASPP & ELPAC State Testing Readiness**: Validates network reachability and latency against official California Assessment endpoints (Cambium TDS/TIDE, ETS TOMS, Smarter Balanced SSO) and verifies **SSL Inspection Bypass** (certificate pinning integrity) so secure testing browsers do not crash.
3. **Wi-Fi RRM, DARRP & GSK Optimization Monitor**: Observes dynamic Radio Resource Management (RRM) events from Fortinet FortiAPs (DARRP / Global Spectrum Knowledge) and enterprise controllers. Tracks channel dwell stability, counts Co-Channel Interference (CCI) collisions, and alerts on aggressive **channel flapping** (>3 switches/hour).
4. **Scheduled & Rate-Limited Bandwidth Testing (`iperf3`)**: Supports automated throughput and jitter testing with time-window restrictions (e.g., off-peak 20:00–06:00 only), bandwidth throttling caps, and on-demand NOC test triggers.
5. **Synthetic Browser Transactions (Playwright)**: Runs headless Chromium browser workflows on a loop, reporting full render timings, DOMContentLoaded events, and tracking exactly which blocked third-party domains (ads, trackers) cause page slowness.
6. **L2/L3 Onboarding Exporter**: Dynamically parses system event logs to measure Access Point association speed, WPA/EAP authentication handshakes, and DHCP lease acquisition timings in seconds.
7. **CIPA Compliance Checker**: Conducts pre-flight internet connectivity checks, then tests connection categories (CSAM, Terrorist content, Pornography, SSL Decryption, swearing) using `testfiltering.com` tokens. Reports filter failure alerts immediately.
8. **Trust-On-First-Use (TOFU) Registration Queue**: Brand new edge sensors register in a `pending` state. Administrators approve devices via the administrative console, generating unique, revoked-at-will API keys for telemetry write authorizations.
9. **Three-Way Cloud Discovery**: Sensors automatically locate the CMP Cloud server via local configuration, DHCP search domain DNS (`openux-cmp.<domain>`), or global fallback portal.
10. **Pre-built 6-Tier NOC Dashboards**: Automatically provisions VictoriaMetrics, Loki logs, and Alertmanager inside Grafana, pre-loading an end-to-end NOC dashboard.

> 📖 **New to Open Network Experience?** Check out the step-by-step [**Getting Started Guide (GETTING_STARTED.md)**](GETTING_STARTED.md) for full deployment instructions, dashboard walkthroughs, and custom probe templates!

---

## 🎯 Prerequisites & Learning Curve

### Who Is This Platform Built For?
Open Network Experience (ONE) is designed for **K-12 Technology Directors, Network Administrators, Systems Engineers, and Field Technicians**.

### What Basic Knowledge Is Helpful Before Rolling This Out?
You don't need a high-level engineering certification (like a CCIE or CWNE) to deploy and operate ONE, but having familiarity with the following core concepts will give you the best experience:

1. **Basic Linux Command Line**:
   * Navigating folders and managing files (`cd`, `ls`, `mkdir`, `cp`).
   * Executing administrative commands with `sudo`.
   * Editing simple configuration files using a terminal editor (like `nano` or `vim`).
   * Checking system logs and service health (`journalctl -u <service> -f`, `systemctl status`).
2. **Fundamental Networking Concepts**:
   * Understanding IP addresses, Subnet Masks, Default Gateways, and DNS resolvers.
   * How clients obtain dynamic IP addresses via **DHCP**.
   * The difference between **Wired (Ethernet)** and **Wireless (Wi-Fi 2.4/5/6 GHz)** network segments.
   * Connecting devices to school Wi-Fi networks (WPA2/WPA3 Pre-Shared Keys or 802.1X enterprise logins).
3. **Basic Docker Container Concepts**:
   * Understanding that server applications run in lightweight background containers (`docker compose up -d`, `docker ps`).

---

> [!TIP]
> ### 💡 A Great Way to Learn Linux and Network Engineering!
> If you are a junior IT technician, school help desk specialist, or student intern looking to sharpen your Linux, Docker, and enterprise network troubleshooting skills, **Open Network Experience is a fantastic, hands-on learning project!**
>
> The platform automates the complex scripting and provides clean visual web dashboards, allowing you to learn by exploring real-world network metrics and telemetry.

---

## Directory Structure

* **[`/sensor`](file:///data/Open_Network_Experience/sensor)**: Codebase and configurations running on edge sensor hardware.
  * `install.sh`: Hardware compliance checker (4-core, 8GB RAM, 32GB disk) and system bootstrap script.
  * `reconciler/reconciler.py`: Edge state pull agent, container orchestrator, and test schedule runner.
  * `caaspp_readiness.py`: State testing network readiness and SSL inspection bypass validator.
  * `rrm_darrp_monitor.py`: FortiGate DARRP / GSK dynamic channel shift and RF flapping monitor.
  * `iperf3_runner.py`: Rate-limited scheduled and on-demand bandwidth/jitter tester.
  * `cipa_compliance.py`: CIPA web filtering compliance check.
  * `wifi_dhcp_exporter.py`: Passive journald log parsing for L2/L3 handshake speed.
  * `browser_transaction.py`: Playwright web transaction and blocked asset tracking.
* **[`/server`](file:///data/Open_Network_Experience/server)**: Backend FastAPI Control Plane and telemetry deployment configuration.
  * `main.py`: FastAPI endpoints for edge registration, reconcile check-in, test scheduling, on-demand triggers, and key management.
  * `schemas.py`: Pydantic validation schemas, credential redaction models (`SensorStatusResponseSafe`), and test schedule specifications.
  * `test_integration.py`: End-to-end integration test suite validating registration, approval, test schedules, and revocation.
  * `deploy/`: Docker Compose deployment stack (VictoriaMetrics, Grafana, Loki, Alertmanager, dashboards).

---

## Getting Started

### 1. Launch the CMP Server Telemetry Stack (Cloud / Datacenter)
To spin up the control plane and Grafana visualizations:
```bash
cd server/deploy
docker compose up --build -d
```
* **Interactive API Documentation (Swagger)**: `http://<server-ip>:8000/docs`
* **Grafana NOC Dashboard**: `http://<server-ip>:3000` (User: `admin` / Password: `admin`)
* **VictoriaMetrics TSDB**: `http://<server-ip>:8428`

### 2. Set Up a New Edge Sensor
On your single-board computer (Raspberry Pi 5 / Intel N100) running Debian 12 or Ubuntu 22.04 LTS:
1. Copy the `sensor/` directory onto the device.
2. Run the automated installer:
   ```bash
   sudo ./install.sh
   ```
3. Edit `/etc/sensor/reconciler.json`. Point `cmp_url` to your server's IP/domain and leave `api_key` empty (`""`) to initiate registration:
   ```json
   {
       "cmp_url": "http://<your-server-ip>:8000/api/v1",
       "sensor_id": "auto",
       "api_key": "",
       "check_interval_seconds": 60,
       "wifi_interface": "wlan0",
       "wifi_config_path": "/etc/wpa_supplicant/wpa_supplicant.conf"
   }
   ```
4. Start the reconciler daemon:
   ```bash
   sudo systemctl start sensor-reconciler
   sudo systemctl enable sensor-reconciler
   ```

### 3. Approve the Sensor
Administrators can view pending registrations and approve them:
```bash
# View pending sensors (admin key required)
curl -H "X-API-Key: admin-noc-key-change-me" http://localhost:8000/api/v1/sensors

# Approve the sensor (generates and provisions its unique API key)
curl -X POST -H "X-API-Key: admin-noc-key-change-me" \
  http://localhost:8000/api/v1/sensors/<sensor_uuid>/approve
```

---

## Running Diagnostics Manually

You can test individual diagnostic modules on the sensor directly:

```bash
# CAASPP / ELPAC State Testing Readiness & SSL Bypass Check
python3 /data/Open_Network_Experience/sensor/caaspp_readiness.py

# Wi-Fi RRM / DARRP / GSK Radio Optimization & Flapping Check
python3 /data/Open_Network_Experience/sensor/rrm_darrp_monitor.py

# Scheduled Bandwidth Test (Rate-limited to 100M)
python3 /data/Open_Network_Experience/sensor/iperf3_runner.py --server iperf3.district.org --bandwidth-cap 100

# CIPA Content Filter Compliance
python3 /data/Open_Network_Experience/sensor/cipa_compliance.py

# Wi-Fi & DHCP Onboarding Timings
python3 /data/Open_Network_Experience/sensor/wifi_dhcp_exporter.py
```

---

## Development & Test Execution

Run the integration test suite against the live Docker stack:
```bash
python3 server/test_integration.py
```

---

## License

This project is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**. See the [LICENSE](LICENSE) file for the full license text.

---

## Disclaimers & Trademarks

* **Trademarks**: All product names, logos, brands, trademarks, and registered trademarks mentioned within this project or documentation are property of their respective owners. Their use does not imply any affiliation with, endorsement by, or sponsorship by those owners.
* **Privacy & Compliance**: OpenUX is a synthetic network telemetry platform. It generates synthetic test traffic to measure infrastructure performance and does not collect or inspect human student, staff, or user payload data. Packet capture modules enforce automatic header slicing (`-s 128`) to discard application payloads.
* **Warranty**: As provided under the AGPL-3.0 license, this software is provided "AS IS", without warranty of any kind, express or implied.
