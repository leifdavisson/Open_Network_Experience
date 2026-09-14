# Release Notes — Open Network Experience (ONE) v0.7.8

**Release Date:** September 13, 2026  
**License:** GNU Affero General Public License v3.0 (AGPLv3)

---

## 🚀 Highlights & Architecture Overview

Open Network Experience (ONE) **v0.7.8** introduces a major streamlining of control plane management and edge sensor onboarding, eliminates credential leakage, establishes least-privilege host boundaries, and expands deep synthetic RF spectrum auditing.

---

### 1. Unified Root CLI Helper (`./one`)
A centralized management tool located at repository root simplifying daily NOC and DevOps operations:
- **`./one cmp up|down|restart|status|logs`**: Complete Docker Compose lifecycle management for the Central Monitoring Platform.
- **`./one sensor add|list|offboard`**: One-line command generation for zero-touch curl deployment, live registry queries, and clean de-provisioning.
- **`./one reset [--cmp|--all]`**: Idempotent bench and lab reset harness.

### 2. Dedicated `one-sensor` System Account & Least-Privilege Sudoers
Edge sensors no longer execute as `root` or default vendor accounts:
- Automatically creates dedicated system user `one-sensor` with membership in `netdev` and `docker`.
- Configures scoped sudoers rules in `/etc/sudoers.d/99-one-sensor-probes` strictly for hardware prober binaries (`iw`, `tcpdump`, `/usr/local/bin/*`).
- Demotes `sensor-reconciler.service` execution to `User=one-sensor` and `Group=one-sensor`.

### 3. Zero-Touch Ed25519 SSH Key Delegation
Passwordless, zero-trust remote probe execution:
- CMP automatically generates an Ed25519 keypair at boot in `/app/data/id_ed25519` and serves `GET /api/v1/auth/cmp.pub`.
- `sensor/install.sh` and `sensor/onboarding/wizard.py` automatically authorize the CMP public key in `/home/one-sensor/.ssh/authorized_keys`.
- CMP on-demand diagnostics execute over SSH batch mode with zero password prompts or `.env` credential storage.

### 4. Wi-Fi Multi-Band Hardware & Per-Channel RF Spectrum Probe
Introduced `sensor/wifi_multiband_probe.py`:
- Audits client physical WNic chipset capabilities (Wi-Fi 4 / 5 / 6 / 6E / 7, MIMO antenna configurations, supported channel widths).
- Inspects active negotiated PHY link speeds, channel, BSSID, RSSI signal strength, and VHT/HE/EHT modes.
- Scans full 2.4 GHz, 5 GHz, and 6 GHz spectrum for AP channel density, overlapping BSSIDs, and co-channel congestion.
- Correlates client-to-AP generation alignment to detect suboptimal band steering or legacy fallbacks.

### 5. ADR-015 Probe Taxonomy & Web UI Reorganization
- Reorganized dashboard diagnostics dropdown and schedule selector into 6 clean functional tiers:
  - 🚀 Comprehensive Suites
  - 📶 Wi-Fi & RF Spectrum
  - 🏥 Core Infrastructure & Health (L1 - L4)
  - 🔒 Security & Zero Trust Isolation
  - 📜 Compliance & Content Filtering
  - ☁️ SaaS, Collaboration & Voice

### 6. Security Hardening & Bench Tooling Pruning
- Pruned redundant reset scripts (`server/deploy/bench_reset.sh`), consolidating into `scripts/reset_bench.sh`.
- Scrubbed lab bench IP addresses and credentials from tracked markdown files, configuration templates, and examples.
- Documented future automated captive portal resolution architecture in `docs/ROADMAP_CAPTIVE_PORTAL_AUTOMATION.md`.

---

## 🧪 Verification & Parity
- **Test Suite**: 100% pass across all unit and integration tests (`server/test_diagnostics_vv.py`, `server/test_onboarding_and_delegation.py`, `sensor/test_wifi_multiband_probe.py`, `server/test_telemetry_hardening.py`).
- **Physical Testbed**: Clean wipe, zero-touch 1-line installation, and live RF probing verified on physical edge sensor `10.98.2.105` and CMP `10.98.2.125`.
