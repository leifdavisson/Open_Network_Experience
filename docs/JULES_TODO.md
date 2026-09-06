# Open Network Experience (ONE) — Jules Engineering Backlog & TODOs

This backlog documents identified technical debt, refactoring targets, and optimization opportunities discovered during test bench staging and testing workflows.

---

## 1. Database Architecture & Package Exports (`server/db/`)
- **Location**: [`server/db/__init__.py`](file:///data/Open_Network_Experience/server/db/__init__.py)
- **Status**: Intermediately Resolved / Needs Formalization
- **Context**: Monolithic `server/db.py` was refactored into modular submodules (`alerts.py`, `campuses.py`, `maintenance.py`, `sensors.py`, `probes.py`, `schedules.py`, `evidence.py`, `backup.py`, `tsdb.py`).
- **TODO (Jules)**:
  - Define explicit `__all__` in `server/db/__init__.py` to declare the public interface.
  - Implement a dedicated schema migration runner (e.g. Alembic or lightweight SQLite migration manager) instead of dynamic `ALTER TABLE ... try/except` blocks in `init_db()`.
  - Add a unit test verifying that all public functions declared in submodules are correctly exported by `server.db`.

---

## 2. Test Isolation & Network Decoupling (`server/test_integration.py`)
- **Location**: [`server/test_integration.py`](file:///data/Open_Network_Experience/server/test_integration.py#L314-L325)
- **Status**: Intermediately Resolved
- **Context**: `test_07_web_ui_and_easybuilder_studio` previously opened a raw `urllib.request.urlopen("http://localhost:8000/")` socket call against port 8000 instead of using FastAPI's in-process `TestClient`.
- **TODO (Jules)**:
  - Audit all test files (`server/test_*.py` and `sensor/test_*.py`) with Bandit / Semgrep to ensure zero raw HTTP calls to `localhost` without mocking or `TestClient`.
  - Ensure pytest fixtures cleanly isolate SQLite database files into `tmp_path` across all tests.

---

## 3. Sensor Deployment & Fleet Management Automation
- **Location**: [`scripts/deploy_bench.sh`](file:///data/Open_Network_Experience/scripts/deploy_bench.sh) & [`scripts/reset_bench.sh`](file:///data/Open_Network_Experience/scripts/reset_bench.sh)
- **Status**: Multi-sensor support and interactive password prompting added
- **Context**: `deploy_bench.sh` previously only handled a single sensor. Now supports multi-sensor arrays (`10.98.2.105`, `10.98.2.141`, etc.) and interactive password prompts.
- **TODO (Jules)**:
  - Migrate developer bash deployment harnesses to an automated testbench orchestrator using Pyinfra or Ansible for idempotent state management.
  - Add pre-flight SSH key exchange helper (`ssh-copy-id`) so password prompts are not required on recurring bench deployments.

---

## 4. Edge Sensor Textfile Collector & Node Exporter Health Timing
- **Location**: [`scripts/deploy_bench.sh`](file:///data/Open_Network_Experience/scripts/deploy_bench.sh#L122-L125)
- **Status**: Open
- **Context**: Node Exporter (port 9100) requires a probe execution cycle before `/metrics` exposes `wifi_rrm_rssi_dbm`. Checking immediately after restarting `sensor-reconciler` can produce false negatives.
- **TODO (Jules)**:
  - Add a 10-second polling retry loop with exponential backoff before declaring the metrics health check failed.
  - Ensure `node_exporter` is formally checked as an active systemd service on the sensor before inspecting port 9100.

---

## 5. Edge Sensor `reconciler.json` Hardcoded `cmp_url` Fallback
- **Location**: `/etc/sensor/reconciler.json` & [`sensor/install.sh`](file:///data/Open_Network_Experience/sensor/install.sh) & [`sensor/reconciler/reconciler.py`](file:///data/Open_Network_Experience/sensor/reconciler/reconciler.py)
- **Status**: Discovered on Bench Sensors `10.98.2.105` and `10.98.2.141`
- **Context**: Both bench sensors had `"cmp_url": "http://localhost:8000/api/v1"`, causing `sensor-reconciler` to poll `localhost:8000` instead of the CMP host (`10.98.2.125:8000`), failing with `[Errno 111] Connection refused`.
- **TODO (Jules)**:
  - Update [`scripts/deploy_bench.sh`](file:///data/Open_Network_Experience/scripts/deploy_bench.sh) to automatically rewrite `cmp_url` in `/etc/sensor/reconciler.json` to `http://${CMP_HOST}:8000/api/v1`.
  - In `sensor/install.sh` and USB staging kit generator, ensure the current host's reachable IP is never defaulted to `localhost` when generating sensor bundles for remote appliances.

---

## 6. Docker Image Registry & `open-ux/playwright-runner:latest` on Sensors
- **Location**: [`sensor/playwright-runner/`](file:///data/Open_Network_Experience/sensor/playwright-runner/) & [`server/state.py`](file:///data/Open_Network_Experience/server/state.py)
- **Status**: Discovered during live bench deployment
- **Context**: The CMP's default `target_config` includes a `browser-transaction-tester` container using image `open-ux/playwright-runner:latest`. Edge sensors attempt to `docker pull open-ux/playwright-runner:latest`, which fails (non-zero exit 1) because the image is not hosted on a public registry (Docker Hub) and is not automatically built on the edge sensors during bench deployment.
- **TODO (Jules)**:
  - Add build step in `deploy_bench.sh` to build `sensor/playwright-runner/Dockerfile` on sensors, or export via `docker save | docker load` over SSH.
  - Or configure CMP server to host an internal lightweight container registry (e.g. registry:2 in docker-compose.yml) or push images to an official GitHub Container Registry (`ghcr.io/open-ux/...`).
  - In `reconciler.py`, catch `docker pull` failures gracefully for local images if the image already exists in local Docker cache.

---

## 7. Python stdout Line Buffering in Systemd Daemon
- **Location**: [`sensor/reconciler/reconciler.py`](file:///data/Open_Network_Experience/sensor/reconciler/reconciler.py) & [`sensor/reconciler/sensor-reconciler.service`](file:///data/Open_Network_Experience/sensor/reconciler/sensor-reconciler.service)
- **Status**: Fixed in `reconciler.py` via `sys.stdout.reconfigure(line_buffering=True)`
- **Context**: When running under systemd as a non-TTY service, standard Python block-buffers stdout, causing `journalctl -u sensor-reconciler -f` to show zero logs until 4KB buffer fills.
- **TODO (Jules)**:
  - Standardize `Environment=PYTHONUNBUFFERED=1` across all systemd service templates in `sensor/` and `install.sh`.

---

## 8. Database Schema Missing `ip_address` Column on `sensors` Table
- **Location**: [`server/db/__init__.py`](file:///data/Open_Network_Experience/server/db/__init__.py#L31-L45) & [`server/db/sensors.py`](file:///data/Open_Network_Experience/server/db/sensors.py) & [`server/routers/sensor_telemetry.py`](file:///data/Open_Network_Experience/server/routers/sensor_telemetry.py#L207)
- **Status**: Resolved & Deployed to Bench CMP
- **Context**: In SQLite, the `sensors` table schema defines `hostname`, `mac_address`, `os`, `campus_id`, etc., but was missing an `ip_address TEXT` column. As a result, when `cmp-server` restarted or reloaded from SQLite, physical sensor IP addresses reverted to `null`. Furthermore, `reconcile_sensor` (`POST /api/v1/sensors/reconcile`) did not accept `req: Request` to extract client IP from incoming TCP sockets or `X-Forwarded-For`.
- **Resolution**:
  - Added `ip_address TEXT` to `CREATE TABLE IF NOT EXISTS sensors` and migration `ALTER TABLE sensors ADD COLUMN ip_address TEXT;` in `server/db/__init__.py`.
  - Updated `server/db/sensors.py` (`load_all_sensors`, `load_sensor`, `save_sensor`, `batch_save_sensors`) to persist and retrieve `ip_address`.
  - Added `req: Request` parameter in `server/routers/sensor_telemetry.py` to continuously record client IP from `X-Forwarded-For` or `req.client.host` upon reconcile heartbeats.
  - Deployed to CMP test bench (`10.98.2.125`).

---

## 9. Frontend ES Module Migration & Window Event Handler Scoping
- **Location**: [`server/static/js/modules/`](file:///data/Open_Network_Experience/server/static/js/modules/) & [`server/templates/dashboard.html`](file:///data/Open_Network_Experience/server/templates/dashboard.html)
- **Status**: Discovered during test bench verification; Hotfixed & Deployed
- **Context**: When the frontend JavaScript was modularized into ES modules (`main.js`, `charts.js`, `sensors.js`, `api.js`, etc.) loaded via `<script type="module" src="...">`, inline HTML `onclick` attributes (e.g., `switchView()`, `togglePlayPause()`, `goToSlide()`, `toggleTheme()`) failed to resolve because top-level functions in ES modules are scoped to the module and not bound to `window` by default. Additionally, syntax errors during the split (`async export function`, unclosed functions/braces in `sensors.js`, `charts.js`, `main.js`) halted module execution completely before window bindings could execute.
- **TODO (Jules)**:
  - Eliminate all inline HTML event handlers (e.g. `onclick="..."`) in `dashboard.html` in favor of declarative `data-action` attributes and standard `addEventListener` delegation in `main.js`.
  - Add an automated frontend CI linting and bundling step (e.g. `esbuild`, `eslint`, or Playwright headless tests) to catch syntax errors, missing exports, and unbound handlers before deploying.

---

## 10. Diagnostic Probe Runner `ADMIN_KEY` Undefined Scope Error
- **Location**: [`server/static/js/modules/sensors.js`](file:///data/Open_Network_Experience/server/static/js/modules/sensors.js#L932) & [`server/static/js/modules/main.js`](file:///data/Open_Network_Experience/server/static/js/modules/main.js#L96)
- **Status**: Discovered on Bench CMP; Hotfixed & Deployed
- **Reported Error**:
  ```text
  > Connecting to edge sensor 'chromebook-dev-e7573882-80d0-4bec-ab68-4e1f98afd22f'...
  > Spawning on-demand probe 'vlan_isolation' (Target Override: Default)...
  > Streaming live output...

  [ERROR] Failed to execute diagnostic: ReferenceError: ADMIN_KEY is not defined
  ```
- **Context**: In `sensors.js`, multiple API operations (`runDiagnosticOnSensor`, `triggerOTAUpgrade`, `triggerPcap`, `approveSensor`, `rejectSensor`, `fetchEvidence`) include headers `{ 'X-API-Key': ADMIN_KEY }`. However, `ADMIN_KEY` was defined as a local variable inside `main.js` and was neither exported nor imported into `sensors.js`. When any on-demand diagnostic probe or sensor management action was clicked, the browser threw `ReferenceError: ADMIN_KEY is not defined`.
- **Hotfix Applied**:
  - Exported `ADMIN_KEY` in `main.js` and assigned `window.ADMIN_KEY = ADMIN_KEY;`.
  - Defined fallback `export const ADMIN_KEY = window.ADMIN_KEY || "admin-noc-key-change-me";` in `sensors.js`.
  - Deployed updated JS modules to the CMP (`10.98.2.125`).
- **TODO (Jules)**:
  - Consolidate all API client fetch calls into a dedicated `api.js` client module that manages authentication tokens, headers, session refreshing, and error handling in one central location.
  - Implement dynamic API key configuration retrieved from a user profile or cookie rather than hardcoded global constants in the frontend bundle.


