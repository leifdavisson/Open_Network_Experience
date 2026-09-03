# Gemini Jules Task: Remove Hardcoded "DEV-SIM-SERIAL" Identities and Refactor Mock Data

## Objective
Identify and remove all hardcoded "DEV-SIM-SERIAL" and "DEV-SIM-ASSET" placeholder values generated within the telemetry collector. Instead, telemetry fallbacks should dynamically map to unique, meaningful strings. Refactor the UI template to use proper, dynamic bindings while gracefully handling missing data without fake hardcoded placeholders.

---

## Scope of Work

### Part 1: Fix Chromebook Extension Identity Telemetry (`device_telemetry.js`)
- **Location**: `chromebook-sensor/src/background/device_telemetry.js:resolveSensorIdentity()`
- **Problem**: When a Chromebook is unmanaged or the `chrome.enterprise` API fails, it falls back to hardcoding `serial_number: "DEV-SIM-SERIAL"` and `asset_id: "DEV-SIM-ASSET"`. This is what is feeding the mocked data into the database and displaying on the WebUI.
- **Implementation**:
  - Remove the static `"DEV-SIM-SERIAL"` and `"DEV-SIM-ASSET"`.
  - Instead, return `null` for `serial_number` and `asset_id` when the device is truly unmanaged.
  - Return `hostname` dynamically based on the generated UUID, e.g., `hostname: \`cb-unmanaged-${storedUuid.slice(-6)}\``.

### Part 2: Fix Dashboard WebUI Templating (`dashboard.html`)
- **Location**: `server/templates/dashboard.html` (`cbList.forEach` and `wallboardMapMarkers.forEach`)
- **Problem**: The UI must dynamically display whatever the backend provides and fall back gracefully to "Unknown Serial" instead of relying on the backend to spit out fake "SIM" IDs.
- **Implementation**:
  - Check the `cbList.forEach` and map pop-ups in `dashboard.html`.
  - Ensure that `cb.serial_number` falls back to `'Unknown Serial'` rather than `'UNTAGGED'`.
  - Ensure `cb.asset_id` falls back to `'Unmanaged Device'` rather than `'UNTAGGED'`.
  - Display the `cb.hostname` in the second column alongside the user/location string.

### Part 3: Clean up Simulated Alarm Rules Modal (`dashboard.html`)
- **Location**: `server/templates/dashboard.html`
- **Problem**: There are simulated alarm UI modals (e.g. `sim-alertname`, `sim-title`, `sim-desc`) containing hardcoded placeholder strings for generating fake test alerts. These are acceptable but should clearly indicate they are test artifacts.
- **Implementation**:
  - Prepend `[TEST]` to the default values of `sim-title` and `sim-desc` in the HTML so users explicitly know they are interacting with a test simulator and it does not bleed into production logs ambiguously.

---

## Acceptance Criteria
- [ ] No telemetry payloads emit the string "DEV-SIM-SERIAL" or "DEV-SIM-ASSET".
- [ ] Unmanaged Chromebooks show "Unknown Serial" and "Unmanaged Device" gracefully in the UI.
- [ ] The `cb.hostname` is visible in the UI table.
