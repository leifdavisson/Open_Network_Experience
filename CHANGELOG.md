# Changelog

All notable changes to the Open Network Experience (OpenUX) platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
- **Grafana NOC Dashboard** (`noc_dashboard.json`): Three-tier provisioned dashboard — Site NOC (CIPA status table, WAN indicator), Diagnostic Path (page load timelines, blocked domain bar gauge), Sensor Health (CPU/memory gauges, Playwright log viewer).
- **Integration Test Suite** (`test_integration.py`): End-to-end lifecycle validation of registration, approval, reconciliation, reset delivery, and revocation.
- **GitHub Actions CI** (`ci.yml`): Pylint, py_compile, bash syntax check, Docker build validation, integration tests, YAML/JSON config validation.
- **GitHub Actions Security** (`security.yml`): pip-audit, Trivy container scanning, Gitleaks secret detection.
