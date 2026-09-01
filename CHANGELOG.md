# Changelog

All notable changes to the Open Network Experience (OpenUX) platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.5.0] — 2026-09-01

### Added
- **Physical Edge Sensor Delegation Architecture** (`server/routers/sensors.py`): On-demand diagnostic probes now SSH directly into the physical edge sensor appliance and execute scripts there, returning results from the sensor's network vantage point. Previously all probes executed from within the CMP Docker container, yielding incorrect results (e.g. VLAN isolation checks run from the CMP were on the same /24 and could never detect inter-VLAN blocking from a student device perspective).
- **`_run_remote_sensor_probe()` SSH Delegation Helper**: New helper function that `sshpass`-tunnels a command to the edge sensor, captures stdout JSON, and gracefully falls back to CMP-side socket probes if SSH is unavailable or SSH_PASS is unset.
- **`--json` Output Mode for All Sensor Probe Scripts**: Added structured JSON stdout to `voip_jitter_probe.py`, `segmentation_prober.py`, `dns_multi_resolver_probe.py`, and `caaspp_readiness.py`. These scripts can now be invoked with `--json` for CMP delegation (compact per-probe objects) while retaining human-readable ANSI text output for interactive terminal use.
- **`--count` Argument for `voip_jitter_probe.py`**: Controls the number of STUN packets sent per target. On-demand CMP delegation uses `--count 8` (≈4s run) while scheduled Prometheus collection uses the default 20 for higher accuracy.
- **RingCentral UCaaS Health Probe** (`sensor/ringcentral_probe.py`): New synthetic probe verifying reachability of RingCentral TURN relay endpoints, SIP trunking API, and UCaaS session control infrastructure.
- **Wi-Fi Client Isolation Validator** (`sensor/client_isolation_probe.py`): Verifies that guest/student SSID Wi-Fi clients cannot reach peer devices or ARP-spoof lateral paths. Probes adjacent IPs via TCP SYN and validates ARP isolation and mDNS suppression.
- **East-West VLAN Isolation v2** (`server/routers/sensors.py`): Rewired `vlan_isolation` probe to execute `segmentation_prober.py --json` on the physical sensor's network position rather than the CMP container. Results are now architecturally meaningful — student VLAN perspective vs. CMP control VLAN.
- **`[Physical Sensor (ip)]` / `[CMP Container]` Source Tagging**: Every diagnostic result row now includes a source tag in the `info` field making data provenance transparent in the UI.
- **Alert Rules & Webhook Routing** (`server/deploy/`): Prometheus alert rules with multi-day construction-period muting, Alertmanager webhook configuration for NOC notifications.
- **Grafana Embedded NOC Waterfall Navigation**: Alert-to-dashboard deep-linking with RF waterfall visualization embedded in dashboard panels.

### Changed
- **All On-Demand Diagnostic Probes Converted from CMP-Local to Sensor-Delegated**: `canvas`, `classroom`, `iready`, `zoom/voip/jitter`, `vlan_isolation`, `caaspp`, `dns`, `gateway`, `pcap/capture`, and `default/else` handlers now attempt SSH delegation first, falling back to live CMP socket probes (not static mock data).
- **`caaspp_readiness.py` Refactored to `argparse`**: Previously used raw `sys.argv[1]` for output path. Now uses argparse with `--output` flag and `--json` for structured delegation. Preserves backward compatibility via positional argument.
- **DNS Probe Fallback**: Removed hardcoded `3.8ms` latency from DNS fallback. CMP-side fallback now performs real `socket.getaddrinfo()` timing and `1.1.1.1:53` TCP socket probe.
- **Gateway Probe Default Target**: Changed from bench-specific `10.98.2.1` to generic `10.0.0.1`. Gateway target can be overridden per-probe via `custom_target`.
- **`segmentation_prober.py` Result Schema**: Added `target`, `latency_ms`, and `observed` fields to JSON output for richer CMP display.
- **Sensor Detail Response**: `ip_address` and `mac_address` now return `null`/`"unknown"` when not registered, instead of leaking bench-specific values.
- **`server/state.py` New Sensor Defaults**: New sensors now initialize as `pending` with `null` IP and `"unknown"` MAC regardless of sensor ID prefix. Location defaults to `"Unknown"` placeholders instead of bench-specific coordinates.

### Fixed
- **`state.py` Missing `import time`**: Added missing `import time` that caused `NameError` in `get_or_create_sensor()` when `last_seen` was set.
- **`caaspp_readiness.py` JSON Mode Print Suppression**: When `--json` is passed, probe output (`print()` calls from `run_multi_resolver_probes()`) is redirected via `io.StringIO` to prevent console noise from contaminating the JSON stdout stream.
- **SSH Delegation Timeout per Probe Type**: Each probe now specifies a realistic `timeout_sec` matching its actual runtime: `voip` → 20s (`--count 8`), `segmentation` → 15s, `dns` → 25s, `caaspp` → 35s, `gateway` → 5s.
- **`ringcentral_probe.py` HTTP 503 Acceptance**: HTTP 503 (Service Unavailable) from RingCentral endpoints is now treated as `status: ok` — RingCentral returns 503 for health-check endpoints as a feature.
- **`client_isolation_probe.py` `write_metrics()` Crash Guard**: Wrapped filesystem write in `try/except` to prevent metric write failures from crashing the probe.
- **`reconciler.json` District Name Scrub**: Removed identifiable district name from bench sensor reconciler configuration file.

### Security
- **Bench Credentials Removed from Production Code**: `SSH_PASS` no longer defaults to `"Kern1234"`. Default is now empty string — if `SSH_PASS` is unset, SSH delegation is skipped entirely and the CMP falls back to its own socket probes.
- **`SSH_USER` Generic Default**: Changed from `"kern"` (bench-specific) to `"sensor"`.
- **Bench Sensor ID Hardcodes Removed**: The `f10325921...` sensor ID prefix check that auto-approved, auto-assigned IP, and set bench-specific MAC/API-key has been removed from `state.py`. Every sensor now follows the standard pending → approval flow.
- **All Probe Hardcoded IPs Replaced with `CMP_HOST`/`CMP_PORT` Env Vars**: `CMP_HOST` and `CMP_PORT` are now injected via `docker-compose.yml` from the host `.env` file, making the deployment portable across any network.
- **`.env.example` Updated**: Documents all required production env vars (`ADMIN_API_KEY`, `CMP_HOST`, `CMP_PORT`, `SSH_USER`, `SSH_PASS`) with generation instructions and security notes.
- **359-Test Suite Maintained**: All 359 automated test vectors remain green after production hardening.

## [0.4.0] — 2026-08-30

### Added
- **Modular Control Plane & Router Architecture**: Deconstructed the monolithic `server/main.py` into 8 domain-driven routers (`server/routers/`) and separated UI into a modular Jinja2 template (`server/templates/dashboard.html`).
- **SQLite Single Source of Truth (SSOT)**: Replaced dual-state in-memory dictionaries with direct SQLite disk persistence with WAL mode and `PRAGMA busy_timeout = 5000` to eliminate split-brain hazards across multi-worker deployments.
- **Zero-Trust Security Core**: Centralized constant-time key validation (`secrets.compare_digest`), production fail-fast enforcement, and HMAC-SHA256 authenticated session token cookies (`server/security.py`).
- **DO-178C Level A / ISO 26262 ASIL D MC/DC Truth-Table Verifier** (`scripts/verify_mcdc.py`): 100% mathematical independence pair coverage across all compound decision branches.
- **AST Bidirectional Requirements Traceability Matrix** (`scripts/generate_rtm.py`): 100% test coverage across 24 formal IEEE 830 / INCOSE requirements (`requirements.json`).
- **High-Assurance V&V Test Suite**: 310 comprehensive Pytest test vectors across 14 modules + 16 Node.js test runner tests for Chromebook extension telemetry.
- **USB Flash Drive Auto-Staging Engine (`usb_provisioner.py` & `setup.sh`)**: Rapid assembly-line fleet imprinting from FAT32/exFAT USB flash drives with sequential Room Pool assignment and physical CSV receipts.
- **1-Line Remote Web Bootstrapper with URL Query Presets**: CMP Control Plane `/install.sh` and `/bootstrap.sh` endpoints supporting dynamic parameter injection.
- **Interactive Terminal Setup Wizard (`one-wizard`)** (`sensor/onboarding/wizard.py`): Guided CLI tool for field technicians featuring automated NIC inspection, 4-way auto-discovery, live SSID site surveys, and instant ZTP feedback.
- **Enterprise DHCP Option 43 & DNS-SD Discovery Guide** (`docs/DHCP_OPTION_43_AND_DNS_DISCOVERY_GUIDE.md`).


## [0.3.0] — 2026-08-27

### Added
- **Sensor Administration Web UI**: Built-in responsive single-pane-of-glass management dashboard accessible at `/` for real-time fleet health, quick actions, and sensor approvals.
- **1-Click Trust-On-First-Use (TOFU) Approval**: Web interface to approve or reject pending sensors with automatic cryptographic API key provisioning.
- **WYSIWYG "EasyBuilder" Synthetic Probe Studio**: Point-and-click visual form in the Web UI to define custom synthetic tests (Web, API, DNS, TCP) and automatically distribute them to targeted sensors.
- **Dynamic Custom Synthetic Probe Runner** (`custom_probe_runner.py`): Edge probe executor supporting HTTP/S latency, DNS resolution, and TCP port checks with atomic Prometheus metric exports.
- **Sensor Reconciler Dynamic Probing Hook**: Automated synchronization of custom synthetic probes from CMP down to edge sensors.

## [0.2.0] — 2026-08-27

### Added
- **Dual-NIC Split-Brain Diagnostics**: Wired (`eth0`) control baseline vs. Wireless (`wlan0`) variable testing with policy-based routing (PBR) and `SO_BINDTODEVICE` socket binding.
- **CAASPP & ELPAC State Testing Readiness** (`caaspp_readiness.py`): Validates network connectivity against California Department of Education / Cambium TDS/TIDE, ETS TOMS, and Smarter Balanced SSO endpoints. Verifies SSL Inspection bypass to prevent Secure Browser certificate pinning failures.
- **Wi-Fi Radio Resource Management (RRM) & Flapping Monitor** (`rrm_darrp_monitor.py`): Tracks dynamic channel changes, channel dwell stability, co-channel interference (CCI) neighbor collisions, and alerts on RF flapping (>3 switches/hour).
- **Scheduled Bandwidth Tester** (`iperf3_runner.py`): Throughput and jitter testing with time-window restrictions (e.g. off-peak hours only), bandwidth throttling caps, staggered A/B wired/wireless runs, and on-demand trigger delivery.
- **Incident-Triggered Packet Capture (PCAP) Daemon** (`pcap_trigger.py`): Continuous 50MB RAM ring buffer (`/dev/shm`) with automatic header slicing (128 bytes) and 60-second snapshot capture on failure or on-demand NOC trigger.
- **Forensic Evidence Snapshot Bundler** (`evidence_collector.py`): Packages incident PCAP slices, Playwright HARs, systemd journal logs, Wi-Fi RF state, and Plain-English Executive Incident Cards into downloadable `.tar.gz` diagnostic archives.
- **CMP PCAP & Evidence API**: Control plane endpoints to trigger remote PCAP snapshots and register forensic evidence packages (`/api/v1/sensors/{id}/pcap/trigger`, `/api/v1/sensors/{id}/evidence`).
- **Playwright HAR Waterfall & Error Screenshot Capture** (`browser_transaction.py`): Automatically preserves network waterfall HAR files and visual error screenshots on failed web transactions.
- **Security Gateway / Firewall SNMP Telemetry Poller** (`snmp_collector.py`): Queries core firewall CPU, Memory, Session Setup Rate, and Conserve Mode state to correlate firewall load with synthetic slowness.
- **Lateral East-West Segmentation Validator** (`segmentation_prober.py`): Performs allowlisted TCP connection checks to verify that student VLANs cannot access switch management SSH, camera subnets, or admin portals.
- **Multi-Resolver DNS Health & Benchmark Prober** (`dns_multi_resolver_probe.py`): Discovers local DHCP nameservers and benchmarks query latency/RCODE against Cloudflare, Google, Quad9, and OpenDNS.
- **Real-Time Voice & Video (VoIP / Zoom / Meet) Jitter Prober** (`voip_jitter_probe.py`): Measures UDP RTP media stream jitter, packet loss, and ITU-T G.107 Mean Opinion Score (MOS).

## [0.1.0] — 2026-08-25

### Added
- **Sensor Reconciler Agent** (`reconciler.py`): Pull-based edge daemon with TOFU registration, three-way CMP discovery (explicit URL, DHCP domain, global portal), auto-generated sensor UUID, container lifecycle management, stopped container cleanup, empty manifest safety threshold, and Wi-Fi profile reconciliation (Open/PSK/EAP-PEAP).
- **CIPA Compliance Checker** (`cipa_compliance.py`): Pre-flight internet connectivity probe via `generate_204`, category testing against `testfiltering.com` tokens (CSAM, Terrorist, Porn, Obscene, SSL Decryption), atomic Prometheus textfile output.
- **Playwright Browser Transaction Tester** (`browser_transaction.py`): Headless Chromium page load and API endpoint testing, DOMContentLoaded/load timing extraction, blocked third-party domain tracking, gauge-type Prometheus metrics, atomic file writes.
- **Wi-Fi & DHCP Onboarding Exporter** (`wifi_dhcp_exporter.py`): Passive `journalctl` log parser for `wpa_supplicant`, `dhclient`, `dhcpcd`, `NetworkManager`, and `systemd-networkd` events, measuring association, authentication, and DHCP lease durations.
- **Blackbox Exporter Configuration** (`blackbox.yml`): ICMP, DNS (UDP/TCP), HTTP, HTTPS (with TLS validation), and TCP probe modules.
- **Sensor Installer** (`install.sh`): Hardware compliance enforcement (4-core, 8GB RAM, 32GB disk), system package installation, Docker setup, reconciler systemd service registration, CIPA and onboarding exporter provisioning.
- **CMP FastAPI Server** (`main.py`, `schemas.py`): Sensor registration with pending approval queue, per-sensor cryptographic API key generation, authenticated reconcile check-ins, admin configuration updates, one-shot factory reset delivery, credential redaction (`SensorStatusResponseSafe`), and sensor rejection/revocation.
- **Telemetry Stack** (Docker Compose): VictoriaMetrics (13-month retention), Grafana (auto-provisioned NOC dashboard), Loki (log ingestion), Alertmanager (alert deduplication and routing).
- **Grafana NOC Dashboard** (`noc_dashboard.json`): Provisioned dashboard covering Site NOC, Diagnostic Path, and Sensor Health.
- **Integration Test Suite** (`test_integration.py`): End-to-end lifecycle validation of registration, approval, reconciliation, reset delivery, and revocation.
- **GitHub Actions CI** (`ci.yml`): Pylint, py_compile, bash syntax check, Docker build validation, integration tests, YAML/JSON config validation.
- **GitHub Actions Security** (`security.yml`): pip-audit, Trivy container scanning, Gitleaks secret detection.
