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

  // Active Network RF & Interface Info
  const wifi = snapshot.wifi;
  const ifaces = snapshot.hardware?.interfaces || [];
  const hasActiveWifiIface = ifaces.some(i => /^(wlan|wl|wifi)/i.test(i.name) && !i.address.startsWith("127."));
  const hasActiveEthIface = ifaces.some(i => /^(eth|en|eno|enp)/i.test(i.name) && !i.address.startsWith("127."));

  // Only consider connection as Ethernet if:
  // 1) wifi explicitly indicates ethernet or virtual bssid, OR
  // 2) an active eth/en interface exists AND no active wlan interface exists
  const isEthernet = wifi?.interface_type === "ethernet" ||
    (wifi?.bssid && (wifi.bssid.includes("Virtual") || wifi.bssid.includes("Ethernet"))) ||
    (hasActiveEthIface && !hasActiveWifiIface && !wifi?.bssid && !wifi?.channel);

  const hasRfMetrics = Boolean(wifi?.bssid || wifi?.channel || wifi?.rssi_dbm);

  const titleRfCard = document.getElementById("title-rf-card");
  const titleHealthCard = document.getElementById("title-health-card");
  const rowFlapping = document.getElementById("row-flapping");
  const colRssi = document.getElementById("col-rssi");
  const colChannel = document.getElementById("col-channel");

  if (isEthernet) {
    if (titleRfCard) titleRfCard.textContent = "🔌 Active Network State (Wired / Ethernet)";
    if (titleHealthCard) titleHealthCard.textContent = "🩺 Network Health & Diagnostics";
    if (rowFlapping) rowFlapping.style.display = "none";
    if (colRssi) colRssi.style.display = "none";
    if (colChannel) colChannel.style.display = "none";
  } else {
    if (titleRfCard) titleRfCard.textContent = hasRfMetrics ? "📶 Active Wi-Fi RF State" : "📶 Active Network State (Managed Policy Restricted)";
    if (titleHealthCard) titleHealthCard.textContent = hasRfMetrics ? "🩺 Wi-Fi Health & Diagnostics" : "🩺 Network Health & Diagnostics";
    if (rowFlapping) rowFlapping.style.display = hasRfMetrics ? "flex" : "none";
    if (colRssi) colRssi.style.display = "block";
    if (colChannel) colChannel.style.display = "block";
  }

  if (wifi) {
    let defaultSsid = "Connected Network";
    if (isEthernet) {
      defaultSsid = "Wired Ethernet Connection";
    } else if (wifi.connected) {
      defaultSsid = wifi.ssid || (hasActiveWifiIface ? "Wi-Fi Connected (Unmanaged)" : "Wi-Fi Connected");
    } else {
      defaultSsid = "Disconnected";
    }

    let defaultBssid = isEthernet ? "Ethernet Interface" : "Not supported (Requires Managed ChromeOS)";
    document.getElementById("val-ssid").textContent = defaultSsid;
    document.getElementById("val-bssid").textContent = wifi.bssid || defaultBssid;

    if (!isEthernet) {
      const rssiEl = document.getElementById("val-rssi");
      const chanEl = document.getElementById("val-channel");
      if (wifi.rssi_dbm) {
        rssiEl.textContent = `${wifi.rssi_dbm} dBm (${wifi.signal_strength_pct || '--'}%)`;
        rssiEl.style.color = "#fff";
      } else {
        rssiEl.textContent = "Not supported (Unmanaged)";
        rssiEl.style.color = "#94a3b8";
      }

      if (wifi.channel) {
        chanEl.textContent = `Ch ${wifi.channel} (${wifi.frequency_mhz || '--'} MHz)`;
        chanEl.style.color = "#fff";
      } else {
        chanEl.textContent = "Not supported (Unmanaged)";
        chanEl.style.color = "#94a3b8";
      }
    }
    document.getElementById("band-tag").textContent = isEthernet ? "Ethernet" : (wifi.band || (wifi.connected ? "Wi-Fi" : "Offline"));
  }

  // Local Host IP Binding
  const localIp = snapshot.local_ip || wifi?.ip_address || (snapshot.hardware?.interfaces?.find(i => i.address && !i.address.startsWith("127."))?.address) || "--";
  const ipEl = document.getElementById("val-ip");
  if (ipEl) {
    ipEl.textContent = localIp;
  }

  // Diagnostics & Captive Portal
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
      healthTag.textContent = isEthernet ? "ONLINE" : (diag.signal_health || "OK");
      healthTag.className = `tag ${diag.signal_health === "EXCELLENT" || diag.signal_health === "GOOD" || isEthernet ? "badge-green" : diag.signal_health === "FAIR" ? "badge-info" : "badge-amber"}`;
    }

    const flappingEl = document.getElementById("val-flapping");
    if (flappingEl && !isEthernet) {
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
      if (isEthernet) {
        recEl.textContent = "Wired Ethernet connection healthy";
      } else if (!hasRfMetrics) {
        recEl.textContent = "Network healthy (RF signal telemetry requires Managed ChromeOS device)";
      } else {
        recEl.textContent = diag.recommendation || "Wi-Fi running nominally";
      }
    }
  }

  // Gateway Probe UI Binding (Transparent Sandboxing & No Guessing)
  const gw = snapshot.gateway_probe;
  const gwEl = document.getElementById("val-gateway");
  const gwRow = document.getElementById("row-gateway");
  if (gw && gwEl && gwRow) {
    if (gw.reachable) {
      gwEl.textContent = `Reachable (${gw.rtt_ms} ms to ${gw.gateway_ip})`;
      gwEl.style.color = "#10b981";
      gwRow.style.display = "flex";
    } else if (gw.status === "NO_GATEWAY" || !gw.gateway_ip) {
      // Don't guess. Be honest about Chrome security sandboxing
      gwEl.innerHTML = 'Restricted by Chrome Sandbox (<a href="https://developer.chrome.com/docs/extensions/mv3/intro/" target="_blank" style="color: #94a3b8; text-decoration: underline;">Learn more</a>)';
      gwEl.style.color = "#94a3b8";
      gwRow.style.display = "flex";
    } else {
      gwEl.textContent = `UNREACHABLE (${gw.error || gw.status})`;
      gwEl.style.color = "#ef4444";
      gwRow.style.display = "flex";
    }
  }

  // DNS Benchmark UI Binding (Clearer Details)
  const dns = snapshot.dns_benchmark;
  const dnsEl = document.getElementById("val-dns");
  if (dns && dnsEl) {
    if (dns.dns_health === "HEALTHY") {
      const dohLatency = dns.doh_google?.latency_ms ?? dns.doh_cloudflare?.latency_ms ?? 0;
      const localLatency = dns.local_dns?.latency_ms ?? 0;
      dnsEl.textContent = `Healthy (DoH: ${dohLatency}ms | Local: ${localLatency}ms)`;
      dnsEl.style.color = "#10b981";
    } else if (dns.dns_health === "DEGRADED_LATENCY") {
      const maxLat = Math.max(dns.local_dns?.latency_ms || 0, dns.doh_google?.latency_ms || 0);
      dnsEl.textContent = `High Latency (${maxLat}ms - Web pages may feel sluggish)`;
      dnsEl.style.color = "#f59e0b";
    } else {
      dnsEl.textContent = `${dns.dns_health}: ${dns.recommendation.slice(0, 45)}...`;
      dnsEl.style.color = "#ef4444";
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
    if (ident.is_managed && ident.serial_number) {
      document.getElementById("val-device").textContent = `${ident.serial_number} / ${ident.asset_id || 'LOCAL'}`;
    } else {
      document.getElementById("val-device").textContent = `Unmanaged Device (${ident.sensor_id.slice(0, 18)}...)`;
    }
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

  // Check if opened as standalone tab or popout window
  const urlParams = new URLSearchParams(window.location.search);
  if (urlParams.get("mode") === "popout" || window.innerWidth > 450) {
    document.body.classList.add("popout-mode");
    const popoutBtn = document.getElementById("btn-popout");
    if (popoutBtn) popoutBtn.style.display = "none";
  }

  const popoutBtn = document.getElementById("btn-popout");
  if (popoutBtn) {
    popoutBtn.addEventListener("click", () => {
      const popoutUrl = chrome.runtime?.getURL ? chrome.runtime.getURL("src/popup/popup.html?mode=popout") : "popup.html?mode=popout";
      if (chrome.windows && chrome.windows.create) {
        chrome.windows.create({
          url: popoutUrl,
          type: "popup",
          width: 580,
          height: 750
        });
        window.close();
      } else if (chrome.tabs && chrome.tabs.create) {
        chrome.tabs.create({ url: popoutUrl });
        window.close();
      } else {
        window.open(popoutUrl, "_blank", "width=580,height=750");
      }
    });
  }

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

  // Auto-refresh snapshot when online/offline network events fire
  window.addEventListener("online", () => refreshSnapshot());
  window.addEventListener("offline", () => refreshSnapshot());

  // Poll for background snapshot updates every 3 seconds while popup / popout is visible
  const pollInterval = setInterval(() => {
    refreshSnapshot();
  }, 3000);

  window.addEventListener("unload", () => {
    clearInterval(pollInterval);
  });
});
