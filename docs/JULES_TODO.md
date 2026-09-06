# Open Network Experience (ONE) — Jules Engineering Backlog & TODOs

This backlog documents identified technical debt, refactoring targets, and optimization opportunities discovered during test bench staging and testing workflows.

---

## 1. Database Architecture & Package Exports (`server/db/`)
- **Location**: [`server/db/__init__.py`](file:///data/Open_Network_Experience/server/db/__init__.py)
- **Status**: Partially Resolved in PR #12 (Explicit `__all__` added)
- **Context**: Monolithic `server/db.py` was refactored into modular submodules (`alerts.py`, `campuses.py`, `maintenance.py`, `sensors.py`, `probes.py`, `schedules.py`, `evidence.py`, `backup.py`, `tsdb.py`).
- **TODO (Jules)**:
  - [x] Define explicit `__all__` in `server/db/__init__.py` to declare the public interface (Resolved in PR #12).
  - [ ] Implement a dedicated schema migration runner (e.g. Alembic or lightweight SQLite migration manager) instead of dynamic `ALTER TABLE ... try/except` blocks in `init_db()`.
  - [ ] Add a unit test verifying that all public functions declared in submodules are correctly exported by `server.db`.

---

## 2. Test Isolation & Network Decoupling (`server/test_integration.py`)
- **Location**: [`server/test_integration.py`](file:///data/Open_Network_Experience/server/test_integration.py#L314-L325)
- **Status**: Partially Resolved in PR #12 (`TestClient` integration & db isolation)
- **Context**: `test_07_web_ui_and_easybuilder_studio` previously opened a raw `urllib.request.urlopen("http://localhost:8000/")` socket call against port 8000 instead of using FastAPI's in-process `TestClient`.
- **TODO (Jules)**:
  - [ ] Audit all test files (`server/test_*.py` and `sensor/test_*.py`) with Bandit / Semgrep to ensure zero raw HTTP calls to `localhost` without mocking or `TestClient`.
  - [x] Ensure pytest fixtures cleanly isolate SQLite database files into `tmp_path` across all tests (Resolved in PR #12 via `server/conftest.py`).

---

## 3. Sensor Deployment & Fleet Management Automation
- **Location**: [`scripts/deploy_bench.sh`](file:///data/Open_Network_Experience/scripts/deploy_bench.sh) & [`scripts/reset_bench.sh`](file:///data/Open_Network_Experience/scripts/reset_bench.sh)
- **Status**: Multi-sensor support and interactive password prompting added
- **Context**: `deploy_bench.sh` previously only handled a single sensor. Now supports multi-sensor arrays (`10.98.2.105`, `10.98.2.141`, etc.) and interactive password prompts.
- **TODO (Jules)**:
  - [ ] Migrate developer bash deployment harnesses to an automated testbench orchestrator using Pyinfra or Ansible for idempotent state management.
  - [ ] Add pre-flight SSH key exchange helper (`ssh-copy-id`) so password prompts are not required on recurring bench deployments.

---

## 4. Edge Sensor Textfile Collector & Node Exporter Health Timing
- **Location**: [`scripts/deploy_bench.sh`](file:///data/Open_Network_Experience/scripts/deploy_bench.sh#L122-L125)
- **Status**: Resolved in PR #12
- **Context**: Node Exporter (port 9100) requires a probe execution cycle before `/metrics` exposes `wifi_rrm_rssi_dbm`. Checking immediately after restarting `sensor-reconciler` can produce false negatives.
- **Resolution**:
  - [x] Added 10-second polling retry loop with backoff in `deploy_bench.sh` (Resolved in PR #12).
  - [ ] Ensure `node_exporter` is formally checked as an active systemd service on the sensor before inspecting port 9100.

---

## 5. Edge Sensor `reconciler.json` Hardcoded `cmp_url` Fallback
- **Location**: `/etc/sensor/reconciler.json` & [`sensor/install.sh`](file:///data/Open_Network_Experience/sensor/install.sh) & [`sensor/reconciler/reconciler.py`](file:///data/Open_Network_Experience/sensor/reconciler/reconciler.py)
- **Status**: Partially Resolved in PR #12
- **Context**: Both bench sensors had `"cmp_url": "http://localhost:8000/api/v1"`, causing `sensor-reconciler` to poll `localhost:8000` instead of the CMP host (`10.98.2.125:8000`), failing with `[Errno 111] Connection refused`.
- **Resolution**:
  - [x] In `sensor/install.sh`, dynamically parse remote CMP IP from `SSH_CONNECTION` (Resolved in PR #12).
  - [ ] Update `scripts/deploy_bench.sh` to automatically verify `cmp_url` in `/etc/sensor/reconciler.json` on remote hosts.

---

## 6. Docker Image Registry & `open-ux/playwright-runner:latest` on Sensors
- **Location**: [`sensor/playwright-runner/`](file:///data/Open_Network_Experience/sensor/playwright-runner/) & [`server/state.py`](file:///data/Open_Network_Experience/server/state.py)
- **Status**: Resolved in PR #12
- **Context**: The CMP's default `target_config` includes a `browser-transaction-tester` container using image `open-ux/playwright-runner:latest`. Edge sensors attempt to `docker pull open-ux/playwright-runner:latest`, which fails because the image is not hosted on a public registry.
- **Resolution**:
  - [x] Added local Docker build step for `sensor/playwright-runner/Dockerfile` on edge sensors in `deploy_bench.sh` (Resolved in PR #12).
  - [ ] Optionally configure CMP server to host an internal lightweight container registry (e.g. `registry:2` in `docker-compose.yml`) or push images to GHCR (`ghcr.io/open-ux/...`).

---

## 7. Python stdout Line Buffering in Systemd Daemon
- **Location**: [`sensor/reconciler/reconciler.py`](file:///data/Open_Network_Experience/sensor/reconciler/reconciler.py) & [`sensor/reconciler/sensor-reconciler.service`](file:///data/Open_Network_Experience/sensor/reconciler/sensor-reconciler.service)
- **Status**: Fixed in `reconciler.py` via `sys.stdout.reconfigure(line_buffering=True)`
- **Context**: When running under systemd as a non-TTY service, standard Python block-buffers stdout, causing `journalctl -u sensor-reconciler -f` to show zero logs until 4KB buffer fills.
- **TODO (Jules)**:
  - [ ] Standardize `Environment=PYTHONUNBUFFERED=1` across all systemd service templates in `sensor/` and `install.sh`.

---

## 8. Database Schema Missing `ip_address` Column on `sensors` Table
- **Location**: [`server/db/__init__.py`](file:///data/Open_Network_Experience/server/db/__init__.py#L31-L45) & [`server/db/sensors.py`](file:///data/Open_Network_Experience/server/db/sensors.py) & [`server/routers/sensor_telemetry.py`](file:///data/Open_Network_Experience/server/routers/sensor_telemetry.py#L207)
- **Status**: Resolved & Deployed to Bench CMP
- **Context**: In SQLite, the `sensors` table schema defines `hostname`, `mac_address`, `os`, `campus_id`, etc., but was missing an `ip_address TEXT` column.
- **Resolution**:
  - [x] Added `ip_address TEXT` column and migration in `server/db/__init__.py`.
  - [x] Updated `server/db/sensors.py` and `server/routers/sensor_telemetry.py` to continuously record client IP from `X-Forwarded-For` or socket connection.
  - [x] Deployed to CMP test bench (`10.98.2.125`).

---

## 9. Frontend ES Module Migration & Window Event Handler Scoping
- **Location**: [`server/static/js/modules/`](file:///data/Open_Network_Experience/server/static/js/modules/) & [`server/templates/dashboard.html`](file:///data/Open_Network_Experience/server/templates/dashboard.html)
- **Status**: Resolved in PR #12
- **Context**: Inline HTML `onclick` attributes failed to resolve with native ES modules because top-level functions are module-scoped.
- **Resolution**:
  - [x] Replaced inline HTML event handlers in `dashboard.html` with declarative `data-action` and `data-submit` attributes delegated in `static/js/modules/events.js` (Resolved in PR #12).
  - [ ] Add an automated frontend CI linting/bundling step (e.g. `esbuild` or Playwright headless tests) to catch syntax errors and unbound handlers before deploying.

---

## 10. Diagnostic Probe Runner `ADMIN_KEY` Undefined Scope Error
- **Location**: [`server/static/js/modules/sensors.js`](file:///data/Open_Network_Experience/server/static/js/modules/sensors.js#L932) & [`server/static/js/modules/main.js`](file:///data/Open_Network_Experience/server/static/js/modules/main.js#L96)
- **Status**: Resolved in PR #12
- **Context**: On-demand diagnostic probe actions failed with `ReferenceError: ADMIN_KEY is not defined` because `ADMIN_KEY` was scoped to `main.js`.
- **Resolution**:
  - [x] Centralized API calls into `server/static/js/modules/api.js` handling authentication headers and error dispatching (Resolved in PR #12).
  - [ ] Implement dynamic API key configuration retrieved from user session/cookie rather than constants.
