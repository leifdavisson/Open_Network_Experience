# Gemini Jules Task: Remove Remaining Mock Data & Placeholders from Dashboard WebUI

## Objective
The WebUI (`dashboard.html`) contains several remaining hardcoded simulation placeholders in the "Simulate Alert" developer modal and pre-filled form fields. Refactor the template to eliminate hardcoded assumptions (like `pi5-science-01` or `CAMPUS-WEST-HIGH`) and replace them with contextual dropdowns or empty states, ensuring mock data does not accidentally bleed into production database records.

---

## Scope of Work

### Clean up Simulated Alarm Rules Modal (`dashboard.html`)
- **Location**: `server/templates/dashboard.html` (`#simulate-alert-modal`)
- **Problem**: The form inputs have hardcoded default values:
  - `sim-alertname`: `CAASPPUntrustedCertificate`
  - `sim-title`: `CAASPP Secure Browser SSL Certificate Interception Detected`
  - `sim-desc`: `Untrusted MITM certificate detected during pre-flight synthetic TLS probe to Cambium TDS.`
  - `sim-campus`: `CAMPUS-WEST-HIGH`
  - `sim-sensor`: `pi5-science-01`
  - `sim-probe`: `caaspp_readiness`
- **Implementation**:
  - Do **NOT** remove the modal entirely (it is needed for QA and CI tests, such as in `server/test_alerts.py`).
  - Clear the `value="..."` attributes from the HTML inputs. Use `placeholder="..."` attributes instead to give the user hints without pre-filling the form.
  - In `applySimulatePreset(presetKey)`, you may keep the preset injections (like `CAASPP Untrusted SSL Certificate`), but ensure the title explicitly prepends `[SIMULATED]` so they are unmistakably test artifacts if submitted.

---

## Acceptance Criteria
- [ ] No HTML `input` elements in the `simulate-alert-modal` have default `value="..."` attributes containing hardcoded mock strings.
- [ ] The Javascript `applySimulatePreset` function prefixes injected titles with `[SIMULATED]`.
- [ ] Pytest integration tests (`server/test_ui_comprehensive.py` and `server/test_alerts.py`) still pass without failing due to missing modal IDs.
