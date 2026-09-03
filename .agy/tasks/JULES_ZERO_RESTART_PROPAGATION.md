# Gemini Jules Task: Implement Zero-Restart Live Configuration Propagation

## Objective
The goal is to ensure that when a network administrator modifies a Custom Probe, a Unified Schedule, or a Wi-Fi setting via the REST APIs (in `probes.py`, `schedules.py`, or `sensors.py`), those changes are immediately propagated into the `target_config` of all active sensors in `SENSORS_DB`. This enables the `reconciler.py` on the edge sensors to pick up the changes dynamically during their next poll without requiring manual daemon restarts.

---

## Scope of Work

### Part 1: Server-Side Propagation (REST API -> `SENSORS_DB`)
- **Audit Update Endpoints**: Look at `server/routers/probes.py` (`save_custom_probe`), `server/routers/schedules.py` (`save_schedule_endpoint`), and Wi-Fi configuration updates.
- **Problem**: When a probe or schedule is created/updated, it currently saves to `PROBES_DB` or `SCHEDULES_DB`, but it **does not actively update** the `target_config.custom_probes` or `target_config.schedules` arrays inside active sensors within `SENSORS_DB`. Thus, running sensors never see the updated configurations during their reconcile poll unless they do a full manual sync.
- **Implementation**:
  - In `save_custom_probe` and `delete_custom_probe`, add logic to iterate over `SENSORS_DB.values()`. If the sensor is a physical edge node (not a Chromebook), replace its `target_config.custom_probes` with the newly updated `list(PROBES_DB.values())` and call `db.save_sensor(s)`.
  - Repeat the exact same pattern for `save_schedule_endpoint` and `delete_schedule_endpoint` in `schedules.py`, updating `target_config.unified_schedules`.
  - Repeat the pattern for `update_sensor_config` in `sensors.py` (which currently *does* update `target_config`, but double check it properly calls `db.save_sensor`).

### Part 2: Client-Side Reconciler Process Management (`reconciler.py`)
- **Location**: `sensor/reconciler/reconciler.py` (`reconcile_custom_probes` and `reconcile_unified_schedules`)
- **Problem**: The reconciler currently executes `subprocess.Popen(["python3", runner_script...])` *every time* it sees a new configuration file. If the configuration changes frequently, this could leak orphaned background processes because it never terminates the previous runner script instances.
- **Implementation**:
  - Store the `Popen` process handle globally (e.g. `_active_probe_runner_proc`).
  - Before spawning a new `python3 custom_probe_runner.py`, explicitly check if `_active_probe_runner_proc` exists and is running. If so, call `.terminate()` or `.kill()` on it to prevent zombie process leaks.
  - The same logic applies to any schedule runners triggered inside `reconciler.py`.

---

## Acceptance Criteria
- [ ] Modifying a custom probe via API immediately updates `target_config` for all physical sensors.
- [ ] Modifying a schedule via API immediately updates `target_config` for all physical sensors.
- [ ] `reconciler.py` gracefully terminates old probe runners before spawning new ones to prevent process leakage, successfully achieving zero-restart propagation.
