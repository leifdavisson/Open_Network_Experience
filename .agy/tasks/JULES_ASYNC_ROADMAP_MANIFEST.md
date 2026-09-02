# Gemini Jules Asynchronous Task Manifest
**Project:** Open Network Experience (ONE)
**Release Target:** v0.6.1 / v0.7.0
**Generated Date:** September 02, 2026
**License:** [GNU AGPLv3](https://www.gnu.org/licenses/agpl-3.0.en.html)

This manifest outlines pending backlog items and architectural enhancements ready for autonomous execution by Gemini Jules.

---

### Task 1: Chromebook WebRTC Jitter & Packet Loss Analytics Ingestion
- **Title:** Implement Granular WebRTC STUN & Jitter Telemetry Aggregation in TSDB
- **Description:** While the Chromebook sensor executes WebRTC STUN measurements via its offscreen document, the CMP server currently aggregates these metrics in memory without full VictoriaMetrics PromQL time-series extraction. Build dedicated PromQL metrics for ChromeOS WebRTC Round Trip Time (RTT), jitter variance, and packet loss percentages.
- **Acceptance Criteria:**
  1. `server/routers/sensors.py` parses `webrtc` objects from incoming `/api/v1/chromebook/metrics` reports.
  2. Metrics are exported to VictoriaMetrics via `server/routers/sensors.py:forward_chromebook_metrics_to_tsdb()` with labels `sensor_id`, `serial_number`, `campus_id`.
  3. Metric `openux_chromebook_webrtc_rtt_seconds` and `openux_chromebook_webrtc_jitter_seconds` are registered in Prometheus/VictoriaMetrics schema.
  4. Unit and integration tests verify metric ingestion with sample WebRTC payload fixtures.
- **Context Files:**
  - `server/routers/sensors.py`
  - `chromebook-sensor/src/probes/webrtc_stun.js`
  - `chromebook-sensor/src/background/service_worker.js`
  - `server/test_telemetry_hardening.py`
- **Dependencies:** None

---

### Task 2: Multi-Campus Geographic Radius & Subnet Auto-Assignment
- **Title:** Automated Campus Assignment via Geofencing & Subnet Range Matching
- **Description:** Expand auto-onboarding rules so Chromebook sensors reporting latitude/longitude or internal IP addresses automatically assign themselves to the nearest campus hierarchy entity without manual NOC intervention.
- **Acceptance Criteria:**
  1. Add Haversine distance geofence matching in `server/db.py:match_subnet_auto_enroll()`.
  2. Sensor reports containing `location.latitude` and `location.longitude` within a campus's configured `radius_meters` auto-bind `campus_id`.
  3. Provide API endpoints in `server/routers/campuses.py` to configure campus boundary coordinates.
  4. Write comprehensive Pytest test cases covering boundary edge cases.
- **Context Files:**
  - `server/routers/campuses.py`
  - `server/routers/sensors.py`
  - `server/db.py`
  - `server/schemas.py`
- **Dependencies:** None

---

### Task 3: Chromebook Managed Storage Policy Generator UI
- **Title:** Interactive Google Workspace Managed Configuration Builder
- **Description:** Provide a visual builder in the CMP Web Dashboard to generate custom `policy.json` schema files for Google Admin Console, enabling IT directors to enforce customized probe cadence, STUN servers, and lockdown PINs without editing JSON manually.
- **Acceptance Criteria:**
  1. Create `/api/v1/chromebooks/download/policy.json` endpoint that generates dynamic JSON adhering to `chromebook-sensor/schema.json`.
  2. Add visual form modal in `server/templates/dashboard.html` allowing admins to toggle WebRTC probing, adjust cadence sliders, and set helpdesk PIN.
  3. Provide download and copy-to-clipboard functionality in UI.
  4. Ensure output schema validates against Chrome Enterprise Policy guidelines.
- **Context Files:**
  - `chromebook-sensor/schema.json`
  - `server/routers/sensors.py`
  - `server/templates/dashboard.html`
- **Dependencies:** Task 1

---

### Task 4: Rollback & Health Pinning for Edge Sensor OTA Pipeline
- **Title:** Implement Automatic Rollback Watchdog for Failed Edge Sensor OTA Upgrades
- **Description:** Enhance `sensor/reconciler/reconciler.py` with an automatic backup snapshot and rollback watchdog. If an updated daemon fails to check in with the CMP within 3 subsequent reconciliation cycles after an OTA upgrade, the supervisor automatically restores the backup executable.
- **Acceptance Criteria:**
  1. Before replacing `reconciler.py`, create backup at `/usr/local/bin/reconciler.py.bak`.
  2. Implement watchdog flag file `/var/run/sensor_ota_verifying` cleared on first successful report.
  3. If reconciler crashes continuously on boot, fallback bootloader / bash wrapper restores `.bak` binary.
  4. Mock failure scenarios in `sensor/reconciler/test_reconciler.py` to achieve 100% test coverage.
- **Context Files:**
  - `sensor/reconciler/reconciler.py`
  - `sensor/reconciler/test_reconciler.py`
  - `server/routers/sensors.py`
- **Dependencies:** None
