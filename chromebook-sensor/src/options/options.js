import { configManager } from "../background/config_manager.js";

let isUnlockedSession = false;
let managedKeys = [];
let isFormDirty = false;

function setFormLockedState(locked) {
  const form = document.getElementById('settings-form');
  const lockBanner = document.getElementById('lock-banner');
  const lockTitle = document.getElementById('lock-banner-title');
  const lockDesc = document.getElementById('lock-banner-desc');
  const toggleBtn = document.getElementById('btn-toggle-lock');
  const lockBadge = document.getElementById('badge-lock');
  const saveBtn = document.getElementById('save-btn');

  const fieldsets = form.querySelectorAll('fieldset');
  fieldsets.forEach((fs) => {
    fs.disabled = locked;
  });

  // Re-disable any keys that are strictly managed by Google Workspace policy
  if (!locked) {
    managedKeys.forEach((k) => {
      if (form.elements[k]) form.elements[k].disabled = true;
    });
  }

  saveBtn.disabled = locked;

  if (locked) {
    lockBanner.className = 'banner banner-locked';
    lockTitle.textContent = '🔒 Student Protection Active: Settings Locked';
    lockDesc.textContent = 'Local modifications are restricted. IT technicians can enter the Helpdesk PIN to make manual adjustments.';
    toggleBtn.textContent = '🔑 Unlock for Helpdesk';
    toggleBtn.className = 'btn btn-secondary';
    lockBadge.textContent = '🔒 Locked';
    lockBadge.className = 'badge badge-locked';
  } else {
    lockBanner.className = 'banner banner-unlocked';
    lockTitle.textContent = '🔓 Helpdesk Edit Mode Active';
    lockDesc.textContent = 'You have unlocked local configuration for this Chromebook. Remember to relock when finished.';
    toggleBtn.textContent = '🔒 Relock Settings';
    toggleBtn.className = 'btn btn-outline';
    lockBadge.textContent = '🔓 Unlocked';
    lockBadge.className = 'badge badge-unlocked';
  }
}

/**
 * Validates and sanitizes settings inputs according to schema and security boundaries.
 */
function validateAndSanitizeSettings(rawValues) {
  const errors = [];
  let cmpUrl = String(rawValues.cmp_server_url || "").trim();

  // 1. CMP Server URL validation & normalization
  if (!cmpUrl) {
    errors.push("CMP Server URL is required.");
  } else {
    if (!/^https?:\/\//i.test(cmpUrl)) {
      cmpUrl = "http://" + cmpUrl; // Default to HTTP if scheme omitted
    }
    try {
      const parsed = new URL(cmpUrl);
      if (!parsed.hostname) {
        errors.push("Invalid CMP Server URL hostname.");
      }
      cmpUrl = parsed.origin + (parsed.pathname === "/" ? "" : parsed.pathname.replace(/\/+$/, ""));
    } catch {
      errors.push("Invalid CMP Server URL format.");
    }
  }

  // 2. Probe Interval (clamped to 15-3600)
  let interval = parseInt(rawValues.probe_interval_seconds, 10);
  if (isNaN(interval) || interval < 15 || interval > 3600) {
    errors.push("Probe interval must be an integer between 15 and 3600 seconds.");
  }

  // 3. Max Offline Records (clamped to 50-10000)
  let maxRecords = parseInt(rawValues.max_offline_records, 10);
  if (isNaN(maxRecords) || maxRecords < 50 || maxRecords > 10000) {
    errors.push("Max offline records must be between 50 and 10000.");
  }

  // 4. Campus ID sanitization (alphanumeric, dashes, underscores, spaces)
  let campusId = String(rawValues.campus_id || "").trim();
  if (campusId) {
    campusId = campusId.replace(/[^a-zA-Z0-9_\-\s]/g, "").slice(0, 64);
  } else {
    campusId = "CAMPUS-CHROMEBOOK-FLEET";
  }

  return {
    valid: errors.length === 0,
    errors,
    sanitized: {
      cmp_server_url: cmpUrl,
      api_key: String(rawValues.api_key || "").trim(),
      campus_id: campusId,
      probe_interval_seconds: isNaN(interval) ? 60 : Math.min(3600, Math.max(15, interval)),
      enable_webrtc_probing: Boolean(rawValues.enable_webrtc_probing),
      enable_offline_buffer: Boolean(rawValues.enable_offline_buffer),
      max_offline_records: isNaN(maxRecords) ? 1000 : Math.min(10000, Math.max(50, maxRecords))
    }
  };
}

document.addEventListener('DOMContentLoaded', async () => {
  const form = document.getElementById('settings-form');
  const statusMessage = document.getElementById('status-message');
  const managedWarning = document.getElementById('managed-warning');
  const toggleLockBtn = document.getElementById('btn-toggle-lock');
  const pinModal = document.getElementById('pin-modal');
  const pinInput = document.getElementById('input-pin');
  const pinError = document.getElementById('pin-error');
  const btnCancelPin = document.getElementById('btn-cancel-pin');
  const btnSubmitPin = document.getElementById('btn-submit-pin');
  const saveBtn = document.getElementById('save-btn');

  // Load current configuration
  const config = await configManager.loadConfig();

  // Check if managed policies exist
  if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.managed) {
    chrome.storage.managed.get(null, (managedItems) => {
      if (managedItems && Object.keys(managedItems).length > 0) {
        managedWarning.classList.remove('hidden');
        managedKeys = Object.keys(managedItems);
      }
    });
  }

  // Populate form values
  form.elements['cmp_server_url'].value = config.cmp_server_url || '';
  form.elements['api_key'].value = config.api_key || '';
  form.elements['campus_id'].value = config.campus_id || '';
  form.elements['probe_interval_seconds'].value = config.probe_interval_seconds || 60;
  form.elements['enable_webrtc_probing'].checked = config.enable_webrtc_probing !== false;
  form.elements['enable_offline_buffer'].checked = config.enable_offline_buffer !== false;
  form.elements['max_offline_records'].value = config.max_offline_records || 1000;

  // Track dirty state for unsaved changes guard
  form.addEventListener('input', () => {
    isFormDirty = true;
  });

  window.addEventListener('beforeunload', (e) => {
    if (isFormDirty) {
      e.preventDefault();
      e.returnValue = 'You have unsaved configuration changes. Are you sure you want to discard them?';
      return e.returnValue;
    }
  });

  // Initialize lock state
  const isServerLocked = (config.settings_locked !== false);
  setFormLockedState(isServerLocked && !isUnlockedSession);

  // Dynamically monitor settings_locked property changes
  if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.onChanged) {
    chrome.storage.onChanged.addListener((changes) => {
      if (changes.settings_locked) {
        const newLocked = changes.settings_locked.newValue !== false;
        config.settings_locked = changes.settings_locked.newValue;
        setFormLockedState(newLocked && !isUnlockedSession);
      }
    });
  }

  function closePinModal() {
    pinModal.classList.add('hidden');
    pinInput.value = '';
    pinError.classList.add('hidden');
  }

  // Toggle Lock Button (Unlock with PIN / Relock)
  toggleLockBtn.addEventListener('click', () => {
    if (isUnlockedSession) {
      // Relock
      isUnlockedSession = false;
      setFormLockedState(true);
      statusMessage.textContent = 'Settings locked.';
      statusMessage.className = 'status';
      setTimeout(() => { statusMessage.textContent = ''; }, 2500);
    } else {
      // Open PIN modal
      pinInput.value = '';
      pinError.classList.add('hidden');
      pinModal.classList.remove('hidden');
      pinInput.focus();
    }
  });

  // Cancel PIN modal
  btnCancelPin.addEventListener('click', closePinModal);

  // Backdrop click dismisses PIN modal
  pinModal.addEventListener('click', (e) => {
    if (e.target === pinModal) {
      closePinModal();
    }
  });

  // Global Escape key closes PIN modal
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !pinModal.classList.contains('hidden')) {
      closePinModal();
    }
  });

  // Verify PIN Submission
  async function submitPin() {
    const pin = pinInput.value.trim();
    if (!pin) return;

    if (typeof chrome !== "undefined" && chrome.runtime) {
      btnSubmitPin.disabled = true;
      btnSubmitPin.textContent = 'Verifying...';

      chrome.runtime.sendMessage({ target: "background", type: "VERIFY_HELPDESK_PIN", pin }, (res) => {
        btnSubmitPin.disabled = false;
        btnSubmitPin.textContent = 'Unlock';

        if (res && res.verified) {
          isUnlockedSession = true;
          closePinModal();
          setFormLockedState(false);
          statusMessage.textContent = 'Helpdesk unlock verified.';
          statusMessage.className = 'status success';
          setTimeout(() => { statusMessage.textContent = ''; }, 3000);
        } else {
          pinError.textContent = res?.error || 'Invalid Helpdesk PIN';
          pinError.classList.remove('hidden');
          pinInput.select();
        }
      });
    } else {
      // Fallback in non-extension environment
      if (pin === (config.helpdesk_pin || "4357")) {
        isUnlockedSession = true;
        closePinModal();
        setFormLockedState(false);
      } else {
        pinError.classList.remove('hidden');
      }
    }
  }

  btnSubmitPin.addEventListener('click', submitPin);
  pinInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') submitPin();
  });

  // Handle Save
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!isUnlockedSession && config.settings_locked !== false) {
      statusMessage.textContent = 'Cannot save while settings are locked.';
      statusMessage.className = 'status error';
      return;
    }

    const rawValues = {
      cmp_server_url: form.elements['cmp_server_url'].value,
      api_key: form.elements['api_key'].value,
      campus_id: form.elements['campus_id'].value,
      probe_interval_seconds: form.elements['probe_interval_seconds'].value,
      enable_webrtc_probing: form.elements['enable_webrtc_probing'].checked,
      enable_offline_buffer: form.elements['enable_offline_buffer'].checked,
      max_offline_records: form.elements['max_offline_records'].value
    };

    const validation = validateAndSanitizeSettings(rawValues);
    if (!validation.valid) {
      statusMessage.textContent = validation.errors[0];
      statusMessage.className = 'status error';
      return;
    }

    const updates = validation.sanitized;

    // Reflect sanitized values back to UI
    form.elements['cmp_server_url'].value = updates.cmp_server_url;
    form.elements['campus_id'].value = updates.campus_id;
    form.elements['probe_interval_seconds'].value = updates.probe_interval_seconds;
    form.elements['max_offline_records'].value = updates.max_offline_records;

    // Mutex debounce: Lock button during save
    saveBtn.disabled = true;
    saveBtn.textContent = '💾 Saving...';

    const finishSave = (success, msg) => {
      saveBtn.disabled = false;
      saveBtn.textContent = 'Save Settings';
      if (success) {
        isFormDirty = false;
        statusMessage.textContent = msg || 'Settings saved successfully.';
        statusMessage.className = 'status success';
      } else {
        statusMessage.textContent = msg || 'Error saving settings.';
        statusMessage.className = 'status error';
      }
      setTimeout(() => { statusMessage.textContent = ''; }, 3500);
    };

    // Send update message to background worker
    if (typeof chrome !== "undefined" && chrome.runtime) {
      chrome.runtime.sendMessage({ target: "background", type: "UPDATE_LOCAL_CONFIG", updates }, (response) => {
        if (response && response.success) {
          finishSave(true, 'Settings saved successfully.');
        } else {
          finishSave(false, 'Error saving settings to storage.');
        }
      });
    } else {
      await configManager.updateLocal(updates);
      finishSave(true, 'Settings saved locally.');
    }
  });
});
