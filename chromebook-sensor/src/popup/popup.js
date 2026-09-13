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

  // Wi-Fi Diagnostics & Captive Portal
  const diag = snapshot.wifi_diagnostics;
  const portal = snapshot.captive_portal;

  if (portal) {
    const portalEl = document.getElementById("val-portal");
    if (portalEl) {
      if (portal.is_captive_portal) {
        portalEl.textContent = "BLOCKED (Portal Detected)";
        portalEl.style.color = "#ef4444";
      } else {
        portalEl.textContent = "Clear (Internet Open)";
        portalEl.style.color = "#10b981";
      }
    }
  }

  if (diag) {
    const healthTag = document.getElementById("health-tag");
    if (healthTag) {
      healthTag.textContent = diag.signal_health || "OK";
      healthTag.className = `tag ${diag.signal_health === "EXCELLENT" || diag.signal_health === "GOOD" ? "badge-green" : diag.signal_health === "FAIR" ? "badge-info" : "badge-amber"}`;
    }

    const flappingEl = document.getElementById("val-flapping");
    if (flappingEl) {
      if (diag.is_flapping) {
        flappingEl.textContent = `FLAPPING (${diag.roam_transitions_last_min} switches/min)`;
        flappingEl.style.color = "#ef4444";
      } else {
        flappingEl.textContent = `Stable (${diag.roam_transitions_last_min} roams/min)`;
        flappingEl.style.color = "#10b981";
      }
    }

    const recEl = document.getElementById("val-wifi-recommendation");
    if (recEl) {
      recEl.textContent = diag.recommendation || "Wi-Fi running nominally";
    }
  }

  // Gateway Probe UI Binding
  const gw = snapshot.gateway_probe;
  const gwEl = document.getElementById("val-gateway");
  if (gw && gwEl) {
    if (gw.reachable) {
      gwEl.textContent = `Reachable (${gw.rtt_ms} ms to ${gw.gateway_ip || 'GW'})`;
      gwEl.style.color = "#10b981";
    } else {
      gwEl.textContent = `UNREACHABLE (${gw.error || gw.status})`;
      gwEl.style.color = "#ef4444";
    }
  }

  // DNS Benchmark UI Binding
  const dns = snapshot.dns_benchmark;
  const dnsEl = document.getElementById("val-dns");
  if (dns && dnsEl) {
    if (dns.dns_health === "HEALTHY") {
      dnsEl.textContent = `Healthy (${dns.doh_google?.latency_ms || 0}ms DoH / ${dns.local_dns?.latency_ms || 0}ms Local)`;
      dnsEl.style.color = "#10b981";
    } else {
      dnsEl.textContent = `${dns.dns_health}: ${dns.recommendation.slice(0, 45)}...`;
      dnsEl.style.color = dns.dns_health === "DEGRADED_LATENCY" ? "#f59e0b" : "#ef4444";
    }
  }

  // Bandwidth & Bufferbloat UI Binding
  const bw = snapshot.bandwidth_bufferbloat;
  const bwEl = document.getElementById("val-bandwidth");
  if (bw && bwEl) {
    if (bw.success) {
      bwEl.textContent = `${bw.throughput_mbps} Mbps (Grade ${bw.grade?.split(' ')[0] || 'A'}, +${bw.bufferbloat_delta_ms}ms)`;
      bwEl.style.color = bw.bufferbloat_delta_ms <= 60 ? "#10b981" : bw.bufferbloat_delta_ms <= 150 ? "#f59e0b" : "#ef4444";
    } else {
      bwEl.textContent = bw.error ? `Failed (${bw.error.slice(0, 30)})` : "Unmeasured";
      bwEl.style.color = "#ef4444";
    }
  }

  // EdTech Filter & Student Safety UI Binding
  const filter = snapshot.edtech_filter;
  const filterEl = document.getElementById("val-filter");
  if (filter && filterEl) {
    if (filter.collision_detected) {
      filterEl.textContent = `COLLISION (${filter.detected_agents.join(" + ")})`;
      filterEl.style.color = "#ef4444";
    } else if (filter.health_status === "SSL_INSPECTION_FAILED") {
      filterEl.textContent = "SSL CERT FAILED (MITM Error)";
      filterEl.style.color = "#ef4444";
    } else if (filter.health_status === "CLASSROOM_BLOCKED") {
      const blocked = filter.classroom_whitelist?.services?.filter(s => !s.reachable)?.map(s => s.name) || ["LMS"];
      filterEl.textContent = `LMS BLOCKED (${blocked.join(", ")})`;
      filterEl.style.color = "#ef4444";
    } else if (filter.health_status === "CLOUD_UNREACHABLE") {
      filterEl.textContent = "FILTER CLOUD UNREACHABLE";
      filterEl.style.color = "#ef4444";
    } else if (filter.health_status === "DEGRADED_LATENCY") {
      filterEl.textContent = `High Overhead (+${filter.filter_overhead_ms}ms)`;
      filterEl.style.color = "#f59e0b";
    } else {
      const activeLabel = filter.detected_agents.length > 0 ? filter.detected_agents[0] : (filter.fastest_provider || "Nominal");
      filterEl.textContent = `Healthy (${activeLabel}, +${filter.filter_overhead_ms}ms)`;
      filterEl.style.color = "#10b981";
    }
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
