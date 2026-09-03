# Gemini Jules Task: Fix Chromebook Settings Lock Re-Evaluation Logic

## Objective
Fix a bug where locking/unlocking the Chromebook Fleet in the WebUI doesn't successfully re-evaluate the local state in the Chromebook extension's `options.js` panel without a full browser reload. Also ensure that the backend provides the current fleet-wide lock state explicitly so the UI correctly reflects it instead of assuming default states.

---

## Scope of Work

### Part 1: Chromebook Extension Options UI Re-Evaluation
- **Audit `options.js` Initialization & Listeners:**
  - `options.js` reads `config.settings_locked` on `DOMContentLoaded`.
  - The `service_worker.js` actively polls the CMP and dynamically updates `chrome.storage.local` with the newest `settings_locked` and `helpdesk_pin` values.
  - However, `options.js` does not actively listen for changes to `chrome.storage.local` while it is open. If an admin locks/unlocks the fleet centrally, the open options page on a Chromebook does not reflect the change until the user manually refreshes it.
- **Implement Live Configuration Listeners:**
  - Use `chrome.storage.onChanged.addListener` inside `options.js` to listen for changes to `settings_locked`.
  - When `settings_locked` changes dynamically, call `setFormLockedState(locked)` automatically without requiring a reload, making the transition seamless and instantaneous when the service worker fetches the update.

### Part 2: CMP Backend Accuracy
- **Audit Fleet Lock Status Endpoint:**
  - `get_chromebook_fleet_settings` in `server/routers/sensors.py` returns the lock state correctly.
  - However, the `ChromebookLockUpdateRequest` logic in `update_chromebook_fleet_settings` correctly modifies existing sensors, but new sensors connecting after a fleet unlock will still default to the schema's `settings_locked: True` default, creating inconsistency.
- **Implement Global Fleet State:**
  - Add a persistent fleet-wide configuration object or system setting to track the *intended* fleet lock state, so when a new Chromebook checks in, it inherits the intended global fleet state rather than just updating currently known active sensors.

---

## Acceptance Criteria
- [ ] `options.js` immediately updates its locked/unlocked banner state when the service worker receives a state change from the CMP.
- [ ] The global fleet lock state accurately inherits for new Chromebooks joining the network.
- [ ] No manual extension restarts or page reloads are required to reflect lock state changes.
