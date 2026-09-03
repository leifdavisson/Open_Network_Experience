# Gemini Jules Task: Chromebook Fleet UI Identity Rendering

## Objective
The Chromebook Fleet UI currently hardcodes "DEV-SIM-SERIAL" and "DEV-SIM-ASSET" for all Chromebooks instead of rendering the actual serial numbers, hostnames, and MAC addresses populated by the telemetry payload. Refactor the UI rendering loop to display dynamic, accurate identity metadata for Chromebooks.

---

## Scope of Work

### Update `dashboard.html` Rendering Logic
- **Audit `cbList.forEach` block in `server/templates/dashboard.html`:**
  - The variables representing the Chromebook's serial number, asset ID, hostname, and MAC address are currently missing or hardcoded.
  - The API schema (`ChromebookFleetItemResponse`) already includes `serial_number`, `asset_id`, `hostname`, and `mac_address` which are returned by `list_chromebook_fleet` in `server/routers/sensors.py`.
- **Implement Dynamic HTML Replacement:**
  - Locate the HTML string template inside `cbList.forEach` where table rows are generated.
  - Update the first column (`Serial / Asset ID`) to display `${cb.serial_number || 'UNTAGGED'}` and `${cb.asset_id || 'UNTAGGED-ASSET'}`.
  - Update the second column (`Assigned User / Room`) to include `${cb.hostname || 'chromebook-agent'}` alongside the annotated location/user.
  - If a MAC address (`cb.mac_address`) is available, display it in a small, muted monospace font beneath the location.

---

## Acceptance Criteria
- [ ] The Chromebook table in the WebUI accurately displays the `serial_number`, `asset_id`, and `hostname` supplied by the backend API.
- [ ] Fallbacks to 'UNTAGGED' and 'chromebook-agent' are gracefully handled for unmanaged/dev devices.
- [ ] UI maintains visual alignment and styling with the existing layout.
