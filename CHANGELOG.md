# Changelog

All notable changes to the Open Network Experience (OpenUX) platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.5.0] — 2026-08-30

### Added
- **USB Flash Drive Auto-Staging Engine (`usb_provisioner.py` & `setup.sh`)**: Rapid assembly-line fleet imprinting from any standard FAT32/exFAT USB flash drive containing `one-bootstrap.json`. Supports offline synthetic probe deployment, Wi-Fi configuration, sequential Room Pool assignment, and physical CSV audit receipts (`provisioned_sensors.csv`).
- **1-Click "Download USB Staging Kit (.zip)"** (`/api/v1/onboarding/usb-kit.zip`): Generates in-memory ready-to-copy USB staging bundles directly from the CMP Web Console with pre-filled campus, room, and Wi-Fi presets.
- **Enterprise DHCP Option 43 & DNS-SD Zero-Touch Discovery Guide**: First-principles architectural guide ([`docs/DHCP_OPTION_43_AND_DNS_DISCOVERY_GUIDE.md`](file:///data/Open_Network_Experience/docs/DHCP_OPTION_43_AND_DNS_DISCOVERY_GUIDE.md)) with trade-offs matrix, interactive decision tree, cautionary VoIP/AP collision rules, and configuration templates across Microsoft Windows Server DHCP, ISC Kea, dnsmasq, Cisco IOS-XE, Fortinet FortiOS, MikroTik, and Infoblox.
- **USB Auto-Provisioner Test Suite** (`sensor/onboarding/test_usb_provisioner.py`): 7 unit tests verifying mount discovery, bootstrap parsing, room pool popping, Wi-Fi configuration, offline probe staging, and audit receipt logging.

## [0.4.0] — 2026-08-30

### Added
- **1-Line Remote Web Bootstrapper with URL Query Presets**: CMP Control Plane `/install.sh` and `/bootstrap.sh` endpoints now support dynamic parameter injection (e.g. `?site=West+High&room=204&wizard=true`), enabling 1-click generation of custom bootstrap commands.
- **Interactive Terminal Setup Wizard (`one-wizard`)** (`sensor/onboarding/wizard.py`): Guided CLI tool for helpdesk technicians and field administrators featuring automated hardware/NIC inspection, 4-way CMP auto-discovery with live latency checks, campus/room tagging, live Wi-Fi SSID site surveys with [wpa_supplicant](https://w1.fi/wpa_supplicant) configuration, and instant Zero-Touch Provisioning (ZTP) feedback.
- **Zero-Touch Onboarding & Helpdesk Provisioner UI Card**: Dedicated control card in the CMP Web Console (**Fleet & Registration** tab) with interactive 1-line command generator, clipboard copy, and field technician protocol cheat sheet.
- **CMP Platform Health Probe** (`/api/v1/health` and `/health`): Lightweight readiness endpoint returning active fleet counts and server timestamp for field connectivity verification.
- **Comprehensive Wizard Test Suite** (`sensor/onboarding/test_wizard.py`): 11 unit and integration tests validating diagnostic discovery, HTTP reachability testing, Wi-Fi config generation, and batch provisioning.

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
