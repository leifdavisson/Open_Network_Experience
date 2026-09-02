# Gemini Jules Task: Automated Discovery & Managed WebUI Propagation Pipeline

## Objective
Audit and refactor the Open Network Experience (ONE) codebase to transition static/hardcoded system parameters into native dynamic discovery queries (hardware, network interfaces, default gateways, subnets), while establishing an interactive, validated WebUI configuration management pipeline with live downstream propagation to sensors and probes.

---

## Scope of Work

### Part 1: Automated Discovery & Native System Introspection
- **Audit Hardcoded Fallbacks & Probes:**
  - Audit fallback IPs and gateway assumptions across `server/routers/sensors.py`, `sensor/client_isolation_probe.py`, `sensor/segmentation_prober.py`, and `sensor/reconciler/reconciler.py`.
  - Replace static fallback gateway `10.98.2.1` or subnet definitions with dynamic kernel routing table queries (`ip route show default`, `netifaces`, `/proc/net/route`).
- **Implement Native Dynamic Queries:**
  - Enhance sensor hardware/network discovery to query interface names (`eno1`, `wlp1s0`, `eth0`), active IP addresses, gateway IPs, and DNS resolvers directly from OS sysfs/sockets.
- **Graceful Degradation Pattern:**
  - If dynamic discovery fails (e.g. restricted container environment or missing kernel privileges), fallback to asking or displaying user-editable parameters in the WebUI.

### Part 2: Managed WebUI Configuration Pipeline & Live Propagation
- **WebUI Configuration Management:**
  - Ensure all operational parameters (probe intervals, target gateways, DNS resolvers, STUN servers, maintenance windows, muting rules) are inspectable and modifiable via dedicated UI forms.
- **Live Downstream Push Pipeline:**
  - Ensure updates submitted in the WebUI propagate immediately to edge sensors during next reconciliation cycles (`/api/v1/sensors/{id}/reconcile`) without requiring manual service restarts.
- **Strict State Validation Gate:**
  - Enforce Pydantic validation on all incoming UI updates (IP address format checking, CIDR boundary validation, port bounds 1-65535, cron syntax validation).
  - Reject malformed payloads with descriptive 400/422 status codes and structured UI error toasts.

---

## Detailed Jules Tasks

### Task 1: Edge Sensor Network Discovery & Gateway Dynamic Resolution
- **Title:** Dynamic Gateway, Interface & Subnet Discovery on Physical Edge Sensors
- **Description:** Replace hardcoded gateway fallbacks in `sensor/client_isolation_probe.py` and `server/routers/sensors.py` with runtime discovery using `/proc/net/route` and `ip route` parsing.
- **Acceptance Criteria:**
  1. `get_default_gateway_and_ip()` dynamically identifies default gateway, interface, and local IP on any Linux distro.
  2. No hardcoded `10.98.2.1` strings exist as runtime defaults.
  3. If discovery fails, query CMP for campus-assigned gateway configuration as fallback.
  4. Unit tests in `sensor/test_client_isolation_probe.py` updated and passing.
- **Context Files:**
  - `sensor/client_isolation_probe.py`
  - `sensor/test_client_isolation_probe.py`
  - `server/routers/sensors.py`
- **Dependencies:** None

### Task 2: Pydantic Validation Gate for Managed WebUI Submissions
- **Title:** Strict Input Validation Schema & Error Gate for Fleet & Probe Configs
- **Description:** Implement strict Pydantic validators on `CustomProbeSpec`, `WifiSpec`, and `UnifiedScheduleSpec` to validate IP addresses, URLs, cron strings, and port ranges before saving to SQLite database or dispatching to sensors.
- **Acceptance Criteria:**
  1. Validate `target` in `CustomProbeSpec` according to `probe_type` (URL format for `http`/`api`, IPv4/IPv6 for `dns`/`ping`, host:port for `tcp`).
  2. Validate `cron_expr` against 5-field cron standard syntax in `UnifiedScheduleSpec`.
  3. Return clear, localized error messages on validation failure.
  4. Unit tests in `server/test_security_hardening.py` verifying invalid inputs are blocked.
- **Context Files:**
  - `server/schemas.py`
  - `server/routers/probes.py`
  - `server/routers/sensors.py`
  - `server/test_security_hardening.py`
- **Dependencies:** None

### Task 3: Zero-Restart Downstream Configuration Propagation
- **Title:** Downstream Reconciliation Engine for Dynamic Fleet Parameter Sync
- **Description:** Wire UI-submitted probe/wifi/schedule modifications into `SensorReconcileResponse` so sensors pick up and apply configuration deltas on-the-fly during their periodic poll without service restarts.
- **Acceptance Criteria:**
  1. Modifying a probe or Wi-Fi setting in the WebUI updates the sensor's `target_config` in `SENSORS_DB`.
  2. The next poll to `/api/v1/sensors/{id}/reconcile` returns the new config.
  3. `reconciler.py` updates in-memory probe runner and config files without triggering a daemon restart unless binary has changed.
  4. Integration tests in `server/test_integration.py` verify live propagation flow.
- **Context Files:**
  - `server/routers/sensors.py`
  - `sensor/reconciler/reconciler.py`
  - `server/test_integration.py`
- **Dependencies:** Task 2
