# Handoff: Diagnostic Probes & Fleet Health Cleanup

**Document ID:** HANDOFF-2026-09-13-PROBES-HEALTH  
**Status:** Ready for Execution  
**Author:** Pair Programming Session (Antigravity CLI + User)  
**Date:** September 13, 2026  
**License:** [GNU AGPLv3](https://www.gnu.org/licenses/agpl-3.0.en.html)  

---

## 1. Executive Summary & Objective

This handoff outlines the complete technical context, architecture boundaries, current probe taxonomy, and concrete step-by-step action plan for **cleaning up synthetic probes and health diagnostics** across:
1. **Physical Linux Edge Sensors** (`sensor/` Python synthetic daemons).
2. **ChromeOS Extension Sensors** (`chromebook-sensor/` MV3 JavaScript engine).
3. **Central Monitoring Platform (CMP)** (`server/routers/sensor_diagnostics.py` and `server/routers/sensor_telemetry.py`).
4. **Operations NOC Dashboard** (`server/static/js/modules/sensors.js` and `dashboard.html`).

The goal is to eliminate hardcoded fallbacks, standardize probe classification and SLA scoring, guarantee architectural vantage-point truthfulness, and unify health evaluation across the platform.

---

## 2. Current Architecture & State Overview

### 2.1 The Two Sensor Vantage Points

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                CENTRAL MONITORING PLATFORM (CMP)                       │
│                                                                                        │
│   FastAPI Router: server/routers/sensor_diagnostics.py                                 │
│   Ingestion Router: server/routers/sensor_telemetry.py                                 │
│   SQLite Database: server/db/ (sensors, alerts, probes, evidence)                      │
│   TSDB Spool: VictoriaMetrics (port 8428)                                              │
└───────────────────▲────────────────────────────────────────────────▲───────────────────┘
                    │                                                │
         HTTP JSON Telemetry Ingestion                    SSH Remote Delegation
        (or IndexedDB offline buffer)                    (_run_remote_sensor_probe)
                    │                                                │
┌───────────────────┴────────────────────┐      ┌────────────────────┴───────────────────┐
│     CHROMEBOOK MV3 SENSOR              │      │       FIXED LINUX EDGE SENSOR          │
│     (ChromeOS / Chromebook Fleet)      │      │       (Raspberry Pi 5 / Debian)        │
├────────────────────────────────────────┤      ├────────────────────────────────────────┤
│ • Layer 3/4 Application Probes         │      │ • Full Raw Socket Access (Layer 2 - 7) │
│ • Dual-Stack DNS (DoH vs Local)        │      │ • True 802.11 RF Interface Injection   │
│ • Micro-Burst Downlink Throughput      │      │ • Native TCP iPerf3 Line-Rate Tests    │
│ • Bufferbloat Scoring (Grade A-F)      │      │ • Hardware Wi-Fi Driver Flapping & RRM │
│ • WebRTC Real-Time MOS & Jitter        │      │ • VLAN Isolation & ARP Snooping        │
│ • Captive Portal Detection             │      │ • CIPA Filtering Compliance            │
│ • EdTech Filter Telemetry (Securly,   │      │ • Active PCAP Ring-Buffer Freeze       │
│   Lightspeed, GoGuardian)              │      │ • GPS NMEA Geolocation Fix             │
│ • Sandbox Boundary: No ioctl / L1 /    │      │ • Full Root / Systemd Daemon Execution │
│   Raw TCP iPerf3 Binary                │      │                                        │
└────────────────────────────────────────┘      └────────────────────────────────────────┘
```

---

## 3. Inventory of Probe Types & Current Discrepancies

The diagnostic engine currently handles 16 primary probe categories in [`server/routers/sensor_diagnostics.py`](file:///data/Open_Network_Experience/server/routers/sensor_diagnostics.py#L220-L820). The table below documents their current implementation status, architectural vantage point, and cleanup targets:

| Probe Identifier | Test Purpose | Edge Execution (`sensor/`) | Chromebook Execution (`chromebook-sensor/`) | CMP Fallback Execution | Cleanup Priority / Issue |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`all`** | Full 7-Layer OSI & SaaS suite | SSH runs local checks | Local MV3 probe suite | TCP 80/443 + DNS to 8.8.8.8 | 🟡 **Medium**: Synthetic mock fallback strings in CMP fallback path |
| **`speedtest` / `iperf3`** | Bandwidth Throughput & Bufferbloat | Native binary `/usr/bin/iperf3` | HTTP chunked micro-burst | Hardcoded text mock (`942.8 Mbps`) | 🔴 **High**: Replace CMP hardcoded mock text with live socket/speedtest probe |
| **`dns`** | Multi-Resolver DNS Benchmark | `dns_multi_resolver_probe.py` | `dual_stack_dns.js` (DoH vs Local) | Derived from subnet via `_get_sensor_dns` | 🟢 **Healthy**: Recently enhanced in PR #27 |
| **`gateway`** | Egress Gateway & Core Switch RTT | TCP connect to derived gateway | `gateway_probe.js` (LNA compliant) | TCP connect to derived gateway | 🟢 **Healthy**: Uses dynamic `_get_sensor_gateway` |
| **`wifi_flapping` / `rrm`** | AP Roaming & BSSID Thrashing | Reads `wpa_cli` / syslog | `wifi_health_analyzer.js` | Generic healthy telemetry | 🟡 **Medium**: Standardize event payload structure |
| **`vlan_isolation` / `segmentation`**| East-West Lateral & DTP Hopping | `segmentation_prober.py` | Not supported (Sandbox) | TCP to adjacent subnets | 🔴 **High**: Ensure CMP never reports pass if sensor SSH fails |
| **`client_isolation`** | Intra-BSS Peer Defense & ARP | `client_isolation_probe.py` | Not supported (Sandbox) | Simulated peer drop | 🔴 **High**: Clarify vantage point in output info string |
| **`cipa`** | CSAM / Threat Content Filtering | `lightspeed_filter_probe.py` | `edtech_filter_probe.js` | HTTP to `iwf.testfiltering.com` | 🟢 **Healthy**: Both platforms have dedicated implementations |
| **`dhcp`** | DHCP DORA Handshake & Lease Timing | `wifi_dhcp_exporter.py` | Derives lease from network stack | TCP port 67 probe | 🟡 **Medium**: Replace hardcoded DORA timing constants with live timing |
| **`canvas`** | Canvas LMS & SSO Accessibility | HTTP synthetic probe | HTTP synthetic probe | HTTP synthetic probe | 🟢 **Healthy**: Includes 503 Cloudflare/maintenance grace |
| **`classroom` / `google`** | Google Classroom & Drive API | `google_workspace_chromeos_probe.py`| HTTP synthetic probe | HTTP synthetic probe | 🟢 **Healthy** |
| **`iready`** | i-Ready Assessment & CDN | HTTP synthetic probe | HTTP synthetic probe | HTTP synthetic probe | 🟢 **Healthy** |
| **`ringcentral` / `rc_voip`** | RingCentral SIP & VoIP SLA | `ringcentral_probe.py` | WebRTC MOS estimation | Simulated SIP registration | 🟡 **Medium**: Wire Chromebook WebRTC jitter metrics directly |
| **`zoom` / `voip` / `jitter`** | RTP Packet Loss, Jitter, MOS | `voip_jitter_probe.py` | `mos_calculator.js` | ITU-T G.107 E-Model estimation | 🟢 **Healthy**: Uses standard R-factor algorithm |
| **`caaspp`** | Cambium TDS Secure Browser Readiness | `caaspp_readiness.py` | HTTP synthetic probe | HTTP synthetic probe | 🟢 **Healthy** |
| **`pcap`** | Incident Ring-Buffer Freeze | `/usr/local/bin/pcap_trigger.py` | Not supported (Sandbox) | Saves evidence bundle record | 🟢 **Healthy**: Clean UI separation via Evidence Vault |

---

## 4. Key Lessons Learned & Architectural Constraints (Do Not Violate)

When refactoring probes or health evaluations, always adhere to the principles established in the project's Architecture Decision Records:

1. **Vantage-Point Truthfulness ([ADR-004](file:///data/Open_Network_Experience/docs/ADR_AND_DECISION_LOG.md#L60) & [ADR-014](file:///data/Open_Network_Experience/docs/adr/ADR-014_CHROMEBOOK_SENSOR_MV3_ARCHITECTURE.md)):**
   - **Never run network isolation tests from the CMP container and pretend they represent the sensor.** A VLAN or Client Isolation test executed from the CMP tests the CMP's network segment, not the student or sensor VLAN.
   - If the remote sensor is unreachable via SSH, explicitly output `[CMP Container (sensor SSH unavailable)]` in the status log and do **not** claim full isolation compliance.
2. **Zero-Guessing Principle ([ADR-014](file:///data/Open_Network_Experience/docs/adr/ADR-014_CHROMEBOOK_SENSOR_MV3_ARCHITECTURE.md)):**
   - The sensor must never invent dummy MAC addresses, fabricate signal strengths, or guess Wi-Fi channels when running on unmanaged devices.
   - Display explicit `Not supported (Requires Managed ChromeOS)` or `Not supported (Unmanaged)` badges.
3. **Chromium Local Network Access (LNA) Compliance:**
   - Any synthetic HTTP probe targeting local private IP addresses (`10.x`, `192.168.x`, `172.16.x`, `localhost`) from the browser extension must include `targetAddressSpace: 'local'` and handle preflight CORS gracefully.
4. **Decoupled API Authentication ([ADR-001](file:///data/Open_Network_Experience/docs/ADR_AND_DECISION_LOG.md#L8)):**
   - All frontend diagnostic and telemetry calls must route through [`server/static/js/modules/api.js`](file:///data/Open_Network_Experience/server/static/js/modules/api.js) rather than embedding raw API keys or ad-hoc fetch calls.

---

## 5. Technical Debt & Cleanup Target Areas

### 5.1 Cleanup Target A: Hardcoded Mock Fallbacks in `sensor_diagnostics.py`
- **File:** [`server/routers/sensor_diagnostics.py`](file:///data/Open_Network_Experience/server/routers/sensor_diagnostics.py#L265-L278)
- **Problem:** When `speedtest` is requested on a Linux edge sensor without SSH credentials or while offline, lines 265–278 output hardcoded synthetic strings (`"942.8 Mbps"`, `"0 TCP retransmits"`).
- **Remedy:**
  - Execute a live local HTTP speedtest probe against the CMP server or public iPerf3 target instead of returning fabricated stdout lines.
  - Return status `SKIPPED` or `OFFLINE` with a clear message: `"Target sensor offline or SSH unreachable for line-rate iPerf3 testing"`.

### 5.2 Cleanup Target B: Hardcoded DHCP DORA Timings in `sensor_diagnostics.py`
- **File:** [`server/routers/sensor_diagnostics.py`](file:///data/Open_Network_Experience/server/routers/sensor_diagnostics.py#L362-L366)
- **Problem:** Lines 362–366 hardcode `dora_discover_ms = 4.2`, `dora_offer_ms = 12.8`, `dora_request_ms = 6.1`, `dora_ack_ms = 18.4`.
- **Remedy:**
  - When SSH is available, execute `python3 /usr/local/bin/wifi_dhcp_exporter.py --once` to capture genuine kernel DHCP lease timings.
  - When running CMP fallback, measure the actual TCP round-trip time to port 67 or local default gateway.

### 5.3 Cleanup Target C: Unify Health Calculation Logic
- **File:** [`server/routers/sensor_diagnostics.py`](file:///data/Open_Network_Experience/server/routers/sensor_diagnostics.py#L810-L815) & [`chromebook-sensor/src/probes/wifi_health_analyzer.js`](file:///data/Open_Network_Experience/chromebook-sensor/src/probes/wifi_health_analyzer.js)
- **Problem:** In `sensor_diagnostics.py`, overall status is a binary `PASS` vs `FAIL` based on `all(d.get("passed") for d in details)`. However, in the Chromebook sensor, health is classified into `HEALTHY`, `WARNING`, and `CRITICAL` with MOS and bufferbloat grading.
- **Remedy:**
  - Add standard three-tier status (`PASS`, `WARNING`, `FAIL`) to `sensor_diagnostics.py`.
  - Mark high-latency or degraded metrics (e.g. bufferbloat Grade D, or EdTech filter overhead > 100ms) as `WARNING` rather than either outright failing or falsely passing.

### 5.4 Cleanup Target D: Live Diagnostic Target Presets Refactoring
- **File:** [`server/static/js/modules/sensors.js`](file:///data/Open_Network_Experience/server/static/js/modules/sensors.js#L780-L960)
- **Problem:** Dynamic Safe Presets were added for DNS and Gateway in PR #27, but application probes (`canvas`, `classroom`, `iready`, `ringcentral`, `zoom`) still use static placeholder objects without validating whether the district has custom endpoints configured.
- **Remedy:**
  - Connect target hints to `target_config` stored in the database for the selected sensor or campus.

---

## 6. Action Plan & Next Steps for Incoming Engineer

```
Phase 1: Diagnostic Backend Cleanup (sensor_diagnostics.py)
├── Step 1.1: Replace hardcoded mock output in speedtest & dhcp fallback branches
├── Step 1.2: Upgrade final status calculation to support WARNING state (SLA degradation)
└── Step 1.3: Add unit tests in server/test_diagnostics_vv.py verifying non-mocked outputs

Phase 2: Health Scoring & Telemetry Alignment
├── Step 2.1: Align edge sensor health metrics with Chromebook MOS & bufferbloat grading
├── Step 2.2: Ensure /api/v1/sensors/{sensor_id}/diagnostics/run returns structured health grade
└── Step 2.3: Update dashboard Live Diagnostics UI to render WARNING chips (yellow) properly

Phase 3: Sensor Script Verification
├── Step 3.1: Verify edge sensor scripts in sensor/ execute cleanly under Python 3.14
└── Step 3.2: Run scripts/package_chromebook_sensor.py to ensure extension builds cleanly
```

---

## 7. Verification & Testing Commands

To verify probe and health logic before committing changes:

```bash
# 1. Run all unit and integration tests for server diagnostics & probes
pytest server/test_diagnostics_vv.py server/test_telemetry_hardening.py -v

# 2. Run full backend suite (excluding sudo host offboard tests)
pytest -m "not sudo" --ignore=tests/test_offboard.py

# 3. Run Chromebook sensor MV3 unit and mock suite
cd chromebook-sensor
npm test
cd ..

# 4. Package Chromebook sensor extension
python3 scripts/package_chromebook_sensor.py
```

---

## 8. References & Related Documents

- **Master Decision Log:** [`docs/ADR_AND_DECISION_LOG.md`](file:///data/Open_Network_Experience/docs/ADR_AND_DECISION_LOG.md)
- **Chromebook Sensor MV3 ADR:** [`docs/adr/ADR-014_CHROMEBOOK_SENSOR_MV3_ARCHITECTURE.md`](file:///data/Open_Network_Experience/docs/adr/ADR-014_CHROMEBOOK_SENSOR_MV3_ARCHITECTURE.md)
- **Engineering Backlog:** [`docs/JULES_TODO.md`](file:///data/Open_Network_Experience/docs/JULES_TODO.md)
- **Live Diagnostics Router:** [`server/routers/sensor_diagnostics.py`](file:///data/Open_Network_Experience/server/routers/sensor_diagnostics.py)
- **Frontend Sensors Module:** [`server/static/js/modules/sensors.js`](file:///data/Open_Network_Experience/server/static/js/modules/sensors.js)
