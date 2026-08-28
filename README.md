# Open Network Experience (OpenUX) Synthetic Monitoring Platform

OpenUX is a fully open-source, edge-based synthetic network experience monitoring platform designed as a modern, self-hosted alternative to Aruba UXI. It enables network administrators to continuously measure real end-user experience from client vantage points across distributed school sites, campus buildings, and branch offices.

This platform isolates network slowness and troubleshoots L2/L3 onboarding, WAN/DHCP failures, firewall SSL inspection performance, Wi-Fi RRM/DARRP flapping, state testing readiness (CAASPP/ELPAC), and internet content filtering compliance (CIPA).

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

> 📖 **New to OpenUX?** Check out the step-by-step [**Getting Started Guide (GETTING_STARTED.md)**](GETTING_STARTED.md) for full deployment instructions, dashboard walkthroughs, and custom probe templates!

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
