import { configManager } from "../background/config_manager.js";

let isUnlockedSession = false;
let managedKeys = [];

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

  // Initialize lock state
  const isServerLocked = (config.settings_locked !== false);
  setFormLockedState(isServerLocked && !isUnlockedSession);

  // Dynamically monitor settings_locked property changes
  if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.onChanged) {
    chrome.storage.onChanged.addListener((changes, namespace) => {
      if (changes.settings_locked) {
        const newLocked = changes.settings_locked.newValue !== false;
        config.settings_locked = changes.settings_locked.newValue;
        setFormLockedState(newLocked && !isUnlockedSession);
      }
    });
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
  btnCancelPin.addEventListener('click', () => {
    pinModal.classList.add('hidden');
  });

  // Verify PIN Submission
  async function submitPin() {
    const pin = pinInput.value.trim();
    if (!pin) return;

    if (typeof chrome !== "undefined" && chrome.runtime) {
      chrome.runtime.sendMessage({ target: "background", type: "VERIFY_HELPDESK_PIN", pin }, (res) => {
        if (res && res.verified) {
          isUnlockedSession = true;
          pinModal.classList.add('hidden');
          setFormLockedState(false);
          statusMessage.textContent = 'Helpdesk unlock verified.';
          statusMessage.className = 'status success';
          setTimeout(() => { statusMessage.textContent = ''; }, 3000);
        } else {
          pinError.textContent = res?.error || 'Invalid Helpdesk PIN';
          pinError.classList.remove('hidden');
        }
      });
    } else {
      // Fallback in non-extension environment (e.g. testing)
      if (pin === (config.helpdesk_pin || "4357")) {
        isUnlockedSession = true;
        pinModal.classList.add('hidden');
        setFormLockedState(false);
      } else {
        pinError.classList.remove('hidden');
      }
    }
  }

  btnSubmitPin.addEventListener('click', submitPin);
  pinInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') submitPin();
    else if (e.key === 'Escape') pinModal.classList.add('hidden');
  });

  // Handle Save
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!isUnlockedSession && config.settings_locked !== false) {
      statusMessage.textContent = 'Cannot save while settings are locked.';
      statusMessage.className = 'status error';
      return;
    }

    const updates = {
      cmp_server_url: form.elements['cmp_server_url'].value,
      api_key: form.elements['api_key'].value,
      campus_id: form.elements['campus_id'].value,
      probe_interval_seconds: parseInt(form.elements['probe_interval_seconds'].value, 10),
      enable_webrtc_probing: form.elements['enable_webrtc_probing'].checked,
      enable_offline_buffer: form.elements['enable_offline_buffer'].checked,
      max_offline_records: parseInt(form.elements['max_offline_records'].value, 10)
    };

    // Send update message to background worker
    if (typeof chrome !== "undefined" && chrome.runtime) {
      chrome.runtime.sendMessage({ target: "background", type: "UPDATE_LOCAL_CONFIG", updates }, (response) => {
        if (response && response.success) {
          statusMessage.textContent = 'Settings saved successfully.';
          statusMessage.className = 'status success';
          setTimeout(() => { statusMessage.textContent = ''; }, 3000);
        } else {
          statusMessage.textContent = 'Error saving settings.';
          statusMessage.className = 'status error';
        }
      });
    } else {
      await configManager.updateLocal(updates);
      statusMessage.textContent = 'Settings saved locally.';
      statusMessage.className = 'status success';
    }
  });
});
