# Comprehensive Architecture Decision Record (ADR) & Decision Log
**Project:** Open Network Experience (ONE)
**Version:** v0.4.0 (Comprehensive Compilation)
**Date:** August 30, 2026

---

## 1. Monolithic Server Deconstruction & Domain Routing

**Decision ID:** ADR-001
**Title:** Refactor Server Monolith into Domain-Specific FastAPI Routers
**Status:** Accepted

**Context & Problem Statement:**
The `server/main.py` had grown into a massive monolith (nearly 5,000 lines), containing inline HTML/CSS/JS, frontend logic, and backend endpoints all in a single file. This lack of separation of concerns made testing, maintenance, and modular scaling increasingly difficult.

**Decision Made:**
Deconstruct the monolithic `server/main.py` down to a lightweight 282-line core. Extract 3,300+ lines of raw UI code into Jinja2 templates (`server/templates/dashboard.html`). Decompose backend functionality into 8 modular FastAPI `APIRouters` (e.g., `server/routers/`).

**Alternatives Considered & Rejected:**
- *Keeping the Monolith with Refactored Functions:* Rejected because it fails to properly decouple the frontend from the API and limits the ease of parallel development or isolated testing.

**Key Trade-offs / Consequences:**
- **Pros:** Massive readability boost, clean MVC-like separation, simplified unit testing, easier to enforce type-safety per module.
- **Cons:** Requires slight structural overhead (more files to manage) and updating import paths across the codebase.

---

## 2. Alerts System Architecture & Alertmanager Integration

**Decision ID:** ADR-002
**Title:** Implementation of Active Alerts Center via Alertmanager Webhooks
**Status:** Accepted

**Context & Problem Statement:**
The monitoring suite required a centralized way to handle incoming alerts, deduplicate them, track their lifecycle (Open, Acknowledged, Closed), and display them to NOC operators in real-time without alert fatigue.

**Decision Made:**
Implement an Alertmanager Webhook Receiver (`/api/v1/alerts/webhook`) backed by a SQLite `alerts` schema.
Build a Fingerprint Deduplication & Lifecycle Engine to automatically deduplicate redundant alarms. Expose REST Endpoints (`GET /alerts`, `POST ack`, `POST resolve`) and create a dedicated interactive "Active Alert Center" frontend tab under the Monitor section.

**Alternatives Considered & Rejected:**
- *Third-party SaaS Alerting (e.g., PagerDuty):* Passed over in favor of keeping ONE self-contained and cost-effective, utilizing local SQLite and standard Alertmanager protocols to allow district IT directors to maintain internal control.

**Key Trade-offs / Consequences:**
- **Pros:** Deeply integrated into the local stack, native deduplication via standard Prometheus/Alertmanager fingerprinting.
- **Cons:** Relies on local database state for tracking lifecycles.

---

## 3. High-Assurance Verification & Validation (V&V) Strategy

**Decision ID:** ADR-003
**Title:** Enforce 100% Requirements Traceability and Coverage-Driven V&V
**Status:** Accepted

**Context & Problem Statement:**
To ensure high stability and reliability for enterprise networking environments, the codebase required rigorous testing, type-safety guarantees, and clear traceability to software requirements.

**Decision Made:**
Adopt the "Automated V&V Architect" methodology. Implement `mypy` strict static typing targeting zero errors. Enforce 100% Requirements Traceability (24 INCOSE/IEEE 830 requirements). Implement an MC/DC Truth-Table Engine for logic decisions, and drive Python/Node test suites to over 95% statement and branch coverage (310/310 passing tests).

**Alternatives Considered & Rejected:**
- *Standard Unit Testing without Traceability:* Passed over because basic unit testing does not guarantee that specific system requirements (like security and zero-trust) are tested and met.

**Key Trade-offs / Consequences:**
- **Pros:** Extremely high confidence in code safety and logic correctness; regressions are caught immediately.
- **Cons:** High initial engineering effort to build MC/DC tables and strict typings; developer velocity might be slightly reduced.

---

## 4. Defense-in-Depth Security & CI Pipeline

**Decision ID:** ADR-004
**Title:** Layered Defense-in-Depth and Automated CI Enforcement
**Status:** Accepted

**Context & Problem Statement:**
Missing a robust pipeline to prevent secrets from being committed, ensure code style, and guarantee tests pass before merges. Early GitHub Actions builds were failing due to missing dependencies and incorrect Docker context.

**Decision Made:**
Implement a layered security and validation architecture:
1. **Pre-Commit / Local:** Gitleaks secret scanner, Ruff/Pylint formatting, and standard git hooks.
2. **GitHub Actions CI (SAST):** Run Mypy Strict Static Typing and full test suites with properly mocked Node environments and corrected Docker build contexts.

**Alternatives Considered & Rejected:**
- *Relying only on CI (No Pre-Commit):* Rejected because discovering secret leaks or formatting errors only after pushing to GitHub is slow and poses a security risk.

**Key Trade-offs / Consequences:**
- **Pros:** Shifts security "left" to the developer workstation. Prevents secret spillage. Guarantees that the main branch always passes tests.
- **Cons:** Developers must ensure their local environment has pre-commit installed and correctly configured to commit successfully.

---

## 5. Sensor Onboarding Architecture

**Decision ID:** ADR-005
**Title:** Sensor Auto-Discovery via DHCP Option 43 and DNS
**Status:** Accepted

**Context & Problem Statement:**
Deploying hardware sensors across multiple K-12 campuses requires a zero-touch onboarding process. Manual IP/URL configuration for every sensor does not scale.

**Decision Made:**
Adopt a DHCP Option 43 and DNS Service Discovery (SRV) model. Sensors will automatically discover the ONE server upon booting by broadcasting for DHCP Option 43 or looking up a local `_one._tcp` DNS SRV record.

**Alternatives Considered & Rejected:**
- *Hardcoded server IP addresses or manual web-UI bootstrapping on the sensor:* Rejected due to high labor costs and lack of enterprise scalability when deploying hundreds of devices.

**Key Trade-offs / Consequences:**
- **Pros:** True zero-touch provisioning for District IT.
- **Cons:** Requires the District IT Director to have access to and correctly configure core DHCP/DNS servers prior to sensor deployment.

---

## 6. Alert Routing & Setup UI Architecture

**Decision ID:** ADR-006
**Title:** Waterfall of Attention Framework for Alerts UI
**Status:** Accepted

**Context & Problem Statement:**
Configuration screens for custom alert thresholds, webhooks, and active alarms were causing UI clutter and user confusion in the dashboard.

**Decision Made:**
Implement a "Waterfall of Attention" architecture across the frontend:
1. **Monitor (Frequent):** The NOC Overview and Active Alert Center (live triage).
2. **Configure (Infrequent):** Alert Thresholds and Rules (e.g., Latency > 300ms, VoIP MOS < 3.8).
3. **Setup (Rare):** External Webhook Configuration.

**Alternatives Considered & Rejected:**
- *Single-page Alert Settings View:* Rejected as it overwhelms the operator by mixing daily triage functions with rare backend system configuration.

**Key Trade-offs / Consequences:**
- **Pros:** Drastically improves operator UX, separates permissions, and reduces cognitive load during a network crisis.
- **Cons:** Requires slight navigational updates and quick-jump links (e.g., `[⚙️ Configure Rules ➔]`) to avoid isolating related configurations.

---

## 7. Native K-12 Email Dispatcher

**Decision ID:** ADR-007
**Title:** Native K-12 District SMTP Email Delivery Support
**Status:** Accepted

**Context & Problem Statement:**
K-12 IT departments often rely on existing standard communication stacks (Google Workspace, Microsoft 365, internal Postfix relays) and might not have budgets or approval for external SaaS notification services.

**Decision Made:**
Implement native SMTP email delivery capabilities into the Outbound Notification Dispatcher (`server/routers/alerts.py`). Create easy presets for Google Workspace, Microsoft 365, internal LAN relays, and transactional cloud providers.

**Alternatives Considered & Rejected:**
- *Forcing integration through SaaS platforms (e.g., PagerDuty, Opsgenie):* Passed over to respect the typical K-12 budget and ensure the system is completely autonomous and free of recurring SaaS fees.

**Key Trade-offs / Consequences:**
- **Pros:** Cost-effective, plays nicely with existing K-12 infrastructure.
- **Cons:** Handling raw SMTP can sometimes result in deliverability issues or spam-folder filtering if the district doesn't correctly configure STARTTLS/App Passwords.

---

## 8. Alert Suppression

**Decision ID:** ADR-008
**Title:** Scheduled Maintenance Windows for Alert Suppression
**Status:** Accepted

**Context & Problem Statement:**
During scheduled district-wide IT maintenance (e.g., firmware upgrades or switch reboots), the alerting engine would fire off hundreds of false-positive alerts, causing "alert fatigue" and spamming webhooks.

**Decision Made:**
Build a Scheduled Maintenance Windows engine that actively suppresses outbound notifications and resolves false-positive alerts generated during predefined downtime periods.

**Alternatives Considered & Rejected:**
- *Manual "Pause All Alerts" Toggle:* Rejected because operators often forget to re-enable alerts post-maintenance, leading to unmonitored critical infrastructure.

**Key Trade-offs / Consequences:**
- **Pros:** Prevents false alarms, preserves the integrity of historical SLA metrics, automates suppression.
- **Cons:** A bug in the initial UI implementation caused page navigation and scrolling issues (which was subsequently investigated and resolved).

---

## 9. Baseline CIPA Compliance Monitoring

**Decision ID:** ADR-009
**Title:** CIPA Compliance Connectivity Control Probe
**Status:** Accepted

**Context & Problem Statement:**
To serve the K-12 market effectively, the monitoring system must continuously verify that content filtering required for CIPA (Children's Internet Protection Act) compliance is active and not bypassed by student devices.

**Decision Made:**
Implement a dedicated `cipa_compliance.py` probe on the sensor. This probe periodically tests connectivity to known blocked domains or safe-search APIs to verify that the district's firewall/web-filter is successfully dropping or redirecting the traffic.

**Alternatives Considered & Rejected:**
- *Passive Traffic Analysis:* Rejected because it requires full packet inspection and TLS decryption on the sensor, which raises privacy concerns and performance bottlenecks compared to active synthetic probing.

**Key Trade-offs / Consequences:**
- **Pros:** Provides an immediate, audible alarm if the district filter fails open, mitigating massive liability.
- **Cons:** Requires strict maintenance of the test URL list so the probe doesn't flag false negatives if the filtering vendor changes block-page behavior.

---

## 10. Synthetic Browser Transactions

**Decision ID:** ADR-010
**Title:** Playwright for Synthetic Browser Testing
**Status:** Accepted

**Context & Problem Statement:**
Network administrators need to know if critical educational web apps (e.g., Canvas, Google Classroom, state testing sites) are not just "pingable", but fully rendering and usable by students.

**Decision Made:**
Integrate Playwright (`browser_transaction.py`) into the sensor to perform headless browser transactions. The tests track full page load times, API response latency, and monitor for blocked assets to simulate real user experience.

**Alternatives Considered & Rejected:**
- *Selenium or pure cURL:* Selenium is too heavy and slow for low-resource ARM sensors. Pure cURL cannot execute JavaScript to test actual Single Page Application (SPA) rendering. Playwright offers the best balance of headless performance and modern web support.

**Key Trade-offs / Consequences:**
- **Pros:** Authentic measurement of student UX on complex web applications.
- **Cons:** Headless browsers consume significant RAM and CPU, requiring careful scheduling to not overwhelm the sensor hardware.

---

## 11. Sensor Zero-Trust Authentication

**Decision ID:** ADR-011
**Title:** TOFU (Trust On First Use) Sensor Registration & API Key Auth
**Status:** Accepted

**Context & Problem Statement:**
Hardware sensors placed in untrusted physical locations (e.g., school hallways) could be stolen or compromised. The central management platform (CMP) must securely authenticate them before accepting metrics or issuing commands.

**Decision Made:**
Adopt a TOFU (Trust On First Use) registration model. Sensors initially register via a provisioning endpoint. The CMP admin manually approves the pending sensor in the dashboard, generating a unique `x-api-key` which is then securely exchanged and used for all subsequent API requests.

**Alternatives Considered & Rejected:**
- *Mutual TLS (mTLS) with pre-installed certificates:* Rejected because managing a full PKI infrastructure and distributing certificates to remote headless sensors is too operationally complex for the target user base (small district IT teams).

**Key Trade-offs / Consequences:**
- **Pros:** Balances strong security with operational simplicity; prevents rogue sensors from polluting the database.
- **Cons:** Requires a manual approval step in the UI for every new sensor deployed.

---

## 12. Lessons Learned

### 12.1 Probe Truthfulness & Architectural Perspective
During the development of on-demand diagnostic probes, a fundamental architecture flaw was identified: the Central Monitoring Platform (CMP) was executing network tests (like VLAN isolation and VoIP jitter) from within its own Docker container, rather than delegating them to the physical edge sensors.
- **Lesson:** Network telemetry is highly dependent on the physical and logical network vantage point. A VLAN isolation check run from the CMP (which sits on a management/control VLAN) will incorrectly report that isolation is working, because it isn't testing from the student/guest VLAN where the physical sensor resides.
- **Resolution:** All on-demand probe handlers were rewritten to use SSH delegation (`_run_remote_sensor_probe()`) to execute scripts directly on the physical sensor, parsing the JSON stdout. This restored architectural truthfulness to the diagnostic data.

### 12.2 Hardcoded Credentials & Lab Bench Artifacts
During rapid prototyping, lab bench IP addresses (`10.98.2.125`, `10.98.2.105`) and credentials (`SSH_USER=kern`, `SSH_PASS=Kern1234`) were inadvertently hardcoded into core routing logic, state initializers, and fallbacks.
- **Lesson:** Hardcoded environment-specific variables create technical debt, security vulnerabilities, and brittle systems that fail when deployed to production or new environments.
- **Resolution:** A comprehensive credential scrub was performed. All hardcoded IPs were replaced with environment variables (`CMP_HOST`, `CMP_PORT`) injected via `docker-compose.yml`. Passwords were removed from default arguments, and fallback IPs in responses were replaced with `null` or `"unknown"`. The `deploy_bench.sh` script was updated to handle dynamic environment injection without polluting the codebase.

### 12.3 High-Assurance CI/CD Validation
The implementation of a rigorous 359-test suite that included unit testing, integration testing, static type checking (`mypy`), linting (`ruff`), and security scanning (`bandit`) proved invaluable during the v0.5.0 production hardening phase.
- **Lesson:** Deep architectural refactors (like moving from local socket probes to SSH-delegated JSON probes across 12 different network protocols) can be executed rapidly and safely when backed by a comprehensive test suite.
- **Resolution:** The tests immediately caught edge cases—such as missing imports, unused variables, and incongruous state transitions—that would have otherwise caused production outages, proving that the upfront cost of writing tests pays off during major refactors.

### 12.4 Sensor Trust & Identity (The Bench Auto-Approval Trap)
During early development, the lab bench sensor (ID `f10325921...`) was hardcoded into the CMP's state engine to automatically approve its own registration, assign itself a static IP/MAC, and bypass the normal Trust On First Use (TOFU) workflow.
- **Lesson:** Bypassing security controls for the sake of developer convenience creates severe security vulnerabilities if those shortcuts persist into production. A hardcoded sensor auto-approval path effectively backdoor'd the zero-trust onboarding model, allowing any device mimicking that ID to automatically gain access to the CMP.
- **Resolution:** The bench-specific auto-approval logic was completely removed from `state.py`. All sensors, including the developer bench sensor, must now follow the standard zero-trust provisioning flow (Pending Registration -> Administrator Manual Approval -> Secure API Key Exchange) via the dashboard UI or database seeding scripts.
