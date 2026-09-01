/**
 * Open Network Experience (ONE) - Chromebook Sensor
 * Popup Dashboard UI Controller
 * License: GNU AGPLv3
 */

function updateUI(snapshot, config) {
  if (!snapshot) return;

  // Status Badge
  const badge = document.getElementById("badge-status");
  if (badge) {
    badge.textContent = snapshot.status || "IDLE";
    badge.className = `badge ${snapshot.status === "HEALTHY" ? "badge-green" : snapshot.status === "PROBING" ? "badge-info" : "badge-amber"}`;
  }

  // Wi-Fi RF Info
  const wifi = snapshot.wifi;
  if (wifi) {
    document.getElementById("val-ssid").textContent = wifi.ssid || (wifi.connected ? "Connected" : "Disconnected");
    document.getElementById("val-bssid").textContent = wifi.bssid || "N/A (Virtual/Ethernet)";
    document.getElementById("val-rssi").textContent = wifi.rssi_dbm ? `${wifi.rssi_dbm} dBm (${wifi.signal_strength_pct || '--'}%)` : "--";
    document.getElementById("val-channel").textContent = wifi.channel ? `Ch ${wifi.channel} (${wifi.frequency_mhz || '--'} MHz)` : "--";
    document.getElementById("band-tag").textContent = wifi.band || (wifi.connected ? "Active" : "Offline");
  }

  // WebRTC / MOS
  const webrtc = snapshot.webrtc;
  if (webrtc && webrtc.mos) {
    document.getElementById("val-mos").textContent = webrtc.mos.toFixed(1);
    document.getElementById("val-grade").textContent = webrtc.mos_grade || "Good";
    document.getElementById("val-rtt").textContent = `${webrtc.rtt_ms || 0} ms`;
    document.getElementById("val-jitter").textContent = `${webrtc.jitter_ms || 0} ms`;
  }

  // App Latency List
  const appsList = document.getElementById("apps-list");
  if (appsList && snapshot.synthetic_http && snapshot.synthetic_http.length > 0) {
    appsList.innerHTML = "";
    snapshot.synthetic_http.forEach((app) => {
      const row = document.createElement("div");
      row.className = `app-row ${app.success ? "" : "fail"}`;
      row.innerHTML = `
        <div class="app-info">
          <span class="app-name">${app.name}</span>
          <span class="app-cat">${app.category}</span>
        </div>
        <span class="app-latency" style="color: ${app.success ? '#10b981' : '#ef4444'}">
          ${app.success ? `${app.latency_ms} ms` : 'FAIL'}
        </span>
      `;
      appsList.appendChild(row);
    });
  }

  // Device Info
  const ident = snapshot.sensor_identity;
  if (ident) {
    document.getElementById("val-device").textContent = `${ident.serial_number || 'DEV'} / ${ident.asset_id || 'LOCAL'}`;
  }
  document.getElementById("val-buffer").textContent = `${snapshot.buffered_count || 0} events queued`;

  if (config) {
    document.getElementById("val-cmp").textContent = config.cmp_server_url || "Configured";
    const isLocked = config.settings_locked !== false;
    const lockEl = document.getElementById("badge-lock-status");
    if (lockEl) {
      lockEl.textContent = isLocked ? "🔒" : "🔓";
      lockEl.title = isLocked ? "Settings Locked (Student Protection Active)" : "Settings Unlocked";
    }
  }

  if (snapshot.last_run_timestamp) {
    document.getElementById("last-updated").textContent = `Updated: ${new Date(snapshot.last_run_timestamp).toLocaleTimeString()}`;
  }
}

function refreshSnapshot() {
  if (typeof chrome === "undefined" || !chrome.runtime) return;

  chrome.runtime.sendMessage({ target: "background", type: "GET_LATEST_SNAPSHOT" }, (response) => {
    if (response && response.snapshot) {
      updateUI(response.snapshot, response.config);
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  refreshSnapshot();

  const settingsBtn = document.getElementById("btn-open-settings");
  if (settingsBtn) {
    settingsBtn.addEventListener("click", () => {
      if (typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.openOptionsPage) {
        chrome.runtime.openOptionsPage();
      } else {
        window.open("../options/options.html");
      }
    });
  }

  const btn = document.getElementById("btn-run-probe");
  if (btn) {
    btn.addEventListener("click", () => {
      btn.disabled = true;
      btn.textContent = "⏳ Running Diagnostic Probes...";
      chrome.runtime.sendMessage({ target: "background", type: "TRIGGER_ON_DEMAND_PROBE" }, (response) => {
        btn.disabled = false;
        btn.textContent = "⚡ Run Diagnostic Sweep Now";
        if (response && response.snapshot) {
          updateUI(response.snapshot);
        }
      });
    });
  }
});
