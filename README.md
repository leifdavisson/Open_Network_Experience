# Open Network Experience (OpenUX) Synthetic Monitoring Platform

OpenUX is a fully open-source, edge-based synthetic network experience monitoring platform designed as a self-hosted alternative to Aruba UXI. It enables network administrators to continuously measure real end-user experience from client vantage points across distributed school sites and branch offices.

This platform was built to isolate network slowness and troubleshoot L2/L3 onboarding, WAN/DHCP failures, firewall SSL inspection performance, and internet content filtering compliance.

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](LICENSE)

---

## Key Features

1. **Synthetic Transactions (Playwright)**: Runs headless Chromium browser workflows on a loop, reporting full render timings, DOMContentLoaded events, and tracking exactly which blocked third-party domains (ads, trackers) cause page slowness.
2. **L2/L3 Onboarding Exporter**: Dynamically parses system event logs to measure Access Point association speed, WPA/EAP authentication handshakes, and DHCP lease acquisition timings in seconds.
3. **CIPA Compliance Checker**: Conducts pre-flight internet connectivity checks, then tests connection categories (CSAM, Terrorist content, Pornography, SSL Decryption, swearing) using `testfiltering.com` tokens. Reports filter failure alerts immediately.
4. **Disposable Reconciler Agent**: Light edge agent that checks in with the CMP control plane to pull container specs and Wi-Fi profiles. Self-heals stopped containers and supports on-demand factory wipes.
5. **Secure Onboarding Queue (TOFU)**: Brand new sensors register in a `pending` state. Administrators approve devices via the administrative console, generating unique, revoked-at-will API keys for telemetry write authorizations.
6. **Three-Way Discovery**: Sensors automatically locate the CMP Cloud server via:
   - Option A: Explicit configured URL in `reconciler.json`
   - Option B: DHCP Option 15 search domain query (`openux-cmp.<domain>`)
   - Option C: Fallback to global discovery routing service (`discovery.openux.org`)
7. **Pre-built NOC Dashboards**: Automatically provisions VictoriaMetrics, Loki logs, and Alertmanager inside Grafana, pre-loading a three-tiered NOC dashboard.

---

## Directory Structure

* **[`/sensor`](file:///data/Open_Network_Experience/sensor)**: Codebase and configurations running on edge sensor hardware.
  * `install.sh`: Hardware check (4-core, 8GB RAM, 32GB disk) and system bootstrap script.
  * `cipa_compliance.py`: CIPA web filtering compliance check.
  * `browser_transaction.py`: Playwright web transaction and blocked asset tracking.
  * `wifi_dhcp_exporter.py`: Passive journald log parsing for L2/L3 handshake speed.
  * `reconciler/reconciler.py`: Edge state pull agent and docker orchestrator.
* **[`/server`](file:///data/Open_Network_Experience/server)**: Backend FastAPI Control Plane and telemetry deployment configuration.
  * `main.py`: FastAPI endpoints for edge register/reconcile, admin configuration, and key management.
  * `schemas.py`: Pydantic input/output schemas and credential redaction models.
  * `test_integration.py`: Integration test suite validating the endpoint lifecycle.
  * `deploy/`: Docker Compose deployment stack (VM, Grafana, Loki, Alertmanager, dashboards).

---

## Getting Started

### 1. Launch the CMP Server Telemetry Stack
To spin up the control plane and Grafana visualizations in your cloud or datacenter:
```bash
cd server/deploy
docker compose up --build -d
```
* **Swagger API Documentation**: `http://localhost:8000/docs`
* **Grafana NOC Dashboard**: `http://localhost:3000` (User: `admin` / Password: `admin`)

### 2. Set Up a New Edge Sensor
On your single-board computer (Raspberry Pi 5 / Intel N100) running a Debian-based Linux distribution:
1. Copy the `sensor/` directory onto the device.
2. Run the automated installer:
   ```bash
   sudo ./install.sh
   ```
3. Edit the `/etc/sensor/reconciler.json` config. Point the `cmp_url` to your server's IP/domain and leave the `api_key` empty (`""`) to initiate registration.
4. Start the reconciler daemon:
   ```bash
   sudo systemctl start sensor-reconciler
   ```

### 3. Approve the Sensor
Administrators can check for pending registrations and approve them:
```bash
# View pending sensors (admin key required)
curl -H "X-API-Key: admin-noc-key-change-me" http://localhost:8000/api/v1/sensors

# Approve the sensor (generates and stores its specific API key)
curl -X POST -H "X-API-Key: admin-noc-key-change-me" \
  http://localhost:8000/api/v1/sensors/<sensor_uuid>/approve
```

---

## Development & Test Execution

Run the integration test suite to verify registry, authorization, configuration, and teardown flows against the running Docker stack:
```bash
python3 server/test_integration.py
```

---

## License

This project is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**. See the [LICENSE](LICENSE) file for the full license text.
