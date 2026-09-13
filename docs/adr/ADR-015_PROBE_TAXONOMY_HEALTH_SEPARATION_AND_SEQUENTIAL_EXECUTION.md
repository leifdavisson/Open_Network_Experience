# Architecture Decision Record (ADR)
**Decision ID:** ADR-015  
**Title:** Diagnostic Architecture: Separation of Core Health vs. Synthetic Probes, Sequential Execution, and Dynamic Target Configurations  
**Status:** Accepted  
**Date:** September 13, 2026  
**License:** [GNU AGPLv3](https://www.gnu.org/licenses/agpl-3.0.en.html)  

---

## Context & Problem Statement
During initial prototyping and early field testing across enterprise and K-12 school environments, the diagnostic testing engine in `server/routers/sensor_diagnostics.py` accumulated significant architectural ambiguity:
1. **Conflation of Core Health and Synthetic Probes**: Fundamental sensor vitals (Wi-Fi link state, DHCP lease, gateway reachability, local DNS) were mixed with external SaaS synthetic application tests (Canvas, Google Classroom, i-Ready, CAASPP).
2. **Harmful Parallel Execution ("Run All" Skew)**: Firing all diagnostic tests simultaneously generated severe contention on the sensor's Wi-Fi radio and CPU, skewing latency, jitter, and throughput measurements while risking Denial of Service (DoS) conditions on the Central Monitoring Platform (CMP).
3. **Vendor Hardcoding & Inflexible Targets**: Tests were branded with proprietary vendor names (e.g. `ringcentral` instead of generic SIP/VoIP, `canvas` instead of generic LMS, `lightspeed` instead of CIPA compliance), with hardcoded dummy endpoints (e.g. `10.98.x.x`, `sso.example.edu`, `clever.com/in/district`) that fail when deployed to different school districts or enterprises.
4. **Vantage Point & Dual-Interface Ambiguity**: Edge sensors feature both wired (`eth0`) and wireless (`wlan0`) interfaces. When Wi-Fi issues occurred, traffic silently escaped through Ethernet, hiding real wireless issues from NOC engineers.
5. **Masked Failure Root Causes**: An application probe failure caused by a broken local DNS resolver was reported as an application outage rather than an isolated local DNS infrastructure failure.

---

## Decision

### 1. Clear Delineation: Core Health vs. Synthetic Add-On Probes
* **Core Health (Built-In Vitals)**:
  - Definition: Metrics and checks intrinsic to the sensor's physical hardware, operating system, and local subnet attachment.
  - Components:
    - **`wifi_health`**: Primary user-plane test interface. Continuous monitoring of RSSI, BSSID, channel, and roaming cadence. If Wi-Fi drops, failover to wired must generate a high-priority alert capturing the disconnect reason code.
    - **`dhcp`**: Verifies dynamic lease acquisition on the active interface. Strictly uses authentic timing data; never fabricates dummy DORA timing constants.
    - **`gateway`**: Dynamically determined from the active DHCP lease/kernel routing table (`ip route show default`). Probed via ICMP/ARP with TCP fallback. Rejects static `10.98.x.x` assumptions.
    - **`dns`**: Discovers the pair of local DHCP-assigned DNS resolvers. Strictly enforces standard UDP Port 53 resolution. Flags a warning if fewer than two resolvers are provided.
    - **`captive_portal`**: Active HTTP 204 check (`connectivitycheck.gstatic.com/generate_204`). Intercepted splash pages immediately trigger a critical alert and pause subsequent SaaS tests with an explicit captive portal notification.
    - **`system_vitals`**: Sensor hardware telemetry (CPU, RAM, disk utilization, and SoC temperature to detect thermal throttling in ceiling/IDF closet deployments).
    - **`iperf3`**: Native point-to-point Layer 4 throughput test on physical edge sensors. Retains the explicit application name `iperf3`. Supports dual targets: Local Sensor $\rightarrow$ CMP, and Local Sensor $\rightarrow$ Public/WAN iPerf3 server. On Chromebooks, raw TCP iPerf3 is sandboxed by ChromeOS, so the sensor automatically executes an HTTP5 chunked micro-burst benchmark with loaded latency (Bufferbloat scoring A–F).
* **Synthetic Add-On Probes (Modular External Workloads)**:
  - Definition: Configurable, pluggable simulations of end-user transactions against external services.
  - Components:
    - **`client_isolation`** (Security Probe): Dynamically computes local subnet mask from DHCP and scans adjacent IPs via ARP/ICMP/TCP SYN. Passes only if the default gateway is the sole responsive host.
    - **`vlan_isolation`** (Security Probe): Prompts the administrator for restricted subnets/VLANs to test. Prompts include an option to save presets per district/customer. If unconfigured, the probe is skipped with a clear configuration prompt rather than testing fictitious subnets.
    - **`voip_realtime_jitter`** (Media Probe): Measures UDP burst packet loss, RFC 3550 interarrival jitter, and ITU-T G.107 MOS score against standard STUN or customer media gateways.
    - **`sip_telephony`** (Voice Signaling Probe): Validates SIP signaling (TCP/UDP 5060, TLS 5061, OPTIONS ping) with a preset dropdown of common vendors (RingCentral, Zoom Phone, Cisco CallManager, Teams SIP) and custom IP/port overrides.
    - **`saas_apps`** (LMS / State Testing / Portals): HTTP/TLS TTFB verification with district presets (Canvas, Google Classroom, i-Ready, CAASPP) and custom URL overrides.
    - **`m365`** (Enterprise Cloud Probe): Comprehensive Microsoft 365 endpoint audit (Teams media, Outlook Exchange, OneDrive, SharePoint) via `m365_connectivity_probe.py`.
    - **`windows_update`** (Infrastructure / CDN Probe): Validates Windows Update (WaaS), BITS range headers, Delivery Optimization (DO) cloud tracking, and local P2P LAN peer listener (TCP 7680 / MCC cache) via `windows_update_do_probe.py`.
    - **`cipa`** (Compliance Probe): Standardized against recognized safe test filtering domains (`testfiltering.com`).
* **Forensics Actions**:
  - **`pcap`**: Reclassified as an **On-Demand Diagnostic Action** rather than a pass/fail connectivity probe. Executes rolling ring-buffer packet capture strictly on physical edge sensors; explicitly blocked on Chromebook extensions.

### 2. Sequential Execution Pipeline & Concurrency Guardrails
* **No Unregulated Parallelism**: The diagnostic engine replaces concurrent parallel execution with an asynchronous **sequential execution queue** (one test at a time in defined stages).
* **CMP & Sensor Backpressure**: When an on-demand diagnostic suite is executing on a sensor, that sensor enters a `DIAGNOSTIC_ACTIVE` state, locking further triggers until the sequence completes or times out.
* **Two-Stage Execution Flow**:
  1. *Stage 1 (Pre-Flight Health)*: Verifies Wi-Fi link, DHCP lease, gateway reachability, and local DNS.
  2. *Stage 2 (Selected Synthetic Probes)*: Executes active probes sequentially.

### 3. Root-Cause Isolation (Pre-Flight DNS Decoupling)
* If an application synthetic probe (e.g. SIP or Canvas) fails to resolve a hostname, the failure must be attributed specifically to **Local DNS Failure**, preventing false alarms on external SaaS provider status.

### 4. Dynamic Vendor & District Target Configuration
* Introduces a centralized target configuration schema stored in CMP (`target_config` database table).
* Operators can define, save, and switch between regional or district profiles (e.g. "District A - Clever + Canvas", "District B - ClassLink + Schoology") without editing source code.

---

## Consequences & Trade-offs

### Pros
- **Measurement Accuracy**: Sequential execution prevents CPU and RF saturation, eliminating artificial jitter and packet drops caused by self-contention.
- **Truthful Telemetry**: Complete eradication of hardcoded dummy fallbacks (`10.98.x.x`, `942.8 Mbps`, `4.2ms DORA`).
- **Zero Vendor Lock-In**: Generic protocol probing with flexible presets enables deployment across any enterprise, hospital, or K-12 environment.
- **Root Cause Clarity**: Distinguishes between local Wi-Fi/DHCP/DNS failures and genuine external cloud outages.

### Cons
- **Total Test Duration**: Sequential execution takes longer than parallel firing (e.g. 15–30 seconds for a full suite versus 5 seconds of burst traffic).
- **Configuration Requirement**: VLAN isolation requires one-time administrative input of restricted subnets rather than running out-of-the-box against dummy targets.

---

## References
- [ADR-004: Vantage-Point Truthfulness](file:///data/Open_Network_Experience/docs/ADR_AND_DECISION_LOG.md#L60)
- [ADR-014: Chromebook Sensor MV3 Architecture](file:///data/Open_Network_Experience/docs/adr/ADR-014_CHROMEBOOK_SENSOR_MV3_ARCHITECTURE.md)
- [HANDOFF_PROBES_AND_HEALTH.md](file:///data/Open_Network_Experience/docs/HANDOFF_PROBES_AND_HEALTH.md)
