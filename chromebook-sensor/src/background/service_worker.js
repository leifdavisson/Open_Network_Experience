/**
 * Open Network Experience (ONE) - Chromebook Sensor
 * Manifest V3 Background Service Worker
 * Manages periodic alarms, offscreen probers, telemetry gathering, and CMP synchronization.
 * License: GNU AGPLv3
 */

import { logger } from "../utils/logger.js";
import { configManager } from "./config_manager.js";
import { resolveSensorIdentity, getSystemHardwareTelemetry } from "./device_telemetry.js";
import { getActiveWifiTelemetry, onWifiRoam } from "./network_private.js";
import { runSyntheticHttpSuite } from "../probes/http_synthetic.js";
import { checkCaptivePortal } from "../probes/captive_portal.js";
import { wifiHealthAnalyzer } from "../probes/wifi_health_analyzer.js";
import { probeGatewayReachability, deriveGatewayIp } from "../probes/gateway_probe.js";
import { runDualStackDnsBenchmark } from "../probes/dual_stack_dns.js";
import { measureMicroBurstThroughput } from "../probes/bandwidth_bufferbloat.js";
import { runEdtechFilterSuite } from "../probes/edtech_filter_probe.js";
import { buildReportPayload, sendTelemetryReport } from "../utils/reporter.js";
import { offlineStorage } from "../db/indexed_db.js";
import { flushOfflineBuffer } from "./storage_sync.js";

// Listen for roaming events to feed AP thrashing analyzer
onWifiRoam((roamEvent) => {
  wifiHealthAnalyzer.recordTransition(roamEvent.newBssid, roamEvent.ssid, roamEvent.timestamp);
});

const ALARM_NAME = "one_sensor_periodic_probe";
const OFFSCREEN_DOCUMENT_PATH = "src/offscreen/offscreen.html";

let cmpDynamicTargets = [];
let latestSnapshot = {
  last_run_timestamp: 0,
  sensor_identity: null,
  wifi: null,
  wifi_diagnostics: null,
  captive_portal: null,
  synthetic_http: [],
  webrtc: null,
  buffered_count: 0,
  status: "INITIALIZING"
};

/**
 * Ensures the Offscreen Document is active for WebRTC STUN measurement.
 */
async function ensureOffscreenDocument() {
  if (typeof chrome === "undefined" || !chrome.offscreen) return false;

  try {
    const existingContexts = await chrome.runtime.getContexts({
      contextTypes: ["OFFSCREEN_DOCUMENT"],
      documentUrls: [chrome.runtime.getURL(OFFSCREEN_DOCUMENT_PATH)]
    });

    if (existingContexts.length > 0) {
      return true;
    }

    await chrome.offscreen.createDocument({
      url: OFFSCREEN_DOCUMENT_PATH,
      reasons: ["WEB_RTC", "DOM_SCRAPING"],
      justification: "Synthetically measure WebRTC STUN latency, jitter, and MOS score for district Wi-Fi"
    });
    return true;
  } catch (err) {
    if (err.message && err.message.includes("Only a single offscreen document may be created")) {
      return true;
    }
    logger.warn("Failed to create offscreen document:", err);
    return false;
  }
}

/**
 * Executes WebRTC STUN probe by messaging the Offscreen Document.
 */
async function executeOffscreenWebRtcProbe(stunServers) {
  const hasOffscreen = await ensureOffscreenDocument();
  if (!hasOffscreen) {
    return {
      success: false,
      error: "Offscreen document unavailable (offscreen API not enabled or supported)"
    };
  }

  return new Promise((resolve) => {
    chrome.runtime.sendMessage(
      {
        target: "offscreen",
        type: "RUN_WEBRTC_PROBE",
        stunServers: stunServers || ["stun:stun.l.google.com:19302"],
        timeoutMs: 6000
      },
      (response) => {
        if (chrome.runtime.lastError) {
          logger.warn("Offscreen probe message error:", chrome.runtime.lastError.message);
          resolve({ success: false, error: chrome.runtime.lastError.message });
        } else if (response && response.data) {
          resolve(response.data);
        } else {
          resolve({ success: false, error: response?.error || "Unknown offscreen response" });
        }
      }
    );
  });
}

/**
 * Executes a full synthetic telemetry collection cycle.
 */
export async function executeDiagnosticCycle() {
  const config = configManager.get();
  logger.info("Starting diagnostic probe cycle...");
  latestSnapshot.status = "PROBING";

  try {
    // 1. Resolve Identity & Hardware Info
    const sensorIdentity = await resolveSensorIdentity();
    const hardwareTelemetry = await getSystemHardwareTelemetry();

    // 2. Fetch Active Wi-Fi Telemetry & Health Analytics
    logger.debug("Inspecting Wi-Fi interface and RF characteristics...");
    const wifiTelemetry = await getActiveWifiTelemetry();
    const wifiDiagnostics = wifiHealthAnalyzer.analyze(wifiTelemetry);

    // 3. Captive Portal & Walled Garden Check
    logger.debug("Running captive portal verification (generate_204)...");
    const captivePortalResult = await checkCaptivePortal();

    // 4. Default Gateway & Subnet RTT Probe
    const clientIp = wifiTelemetry.ip_address || (hardwareTelemetry.interfaces[0] ? hardwareTelemetry.interfaces[0].address : null);
    const estimatedGatewayIp = deriveGatewayIp(clientIp);
    logger.debug(`Probing local default gateway [${estimatedGatewayIp || "None"}]...`);
    const gatewayProbeResult = await probeGatewayReachability(estimatedGatewayIp);

    // 5. Dual-Stack DNS Resolution Benchmark
    logger.debug("Running Dual-Stack DNS Benchmark (DoH vs Local)...");
    const dualStackDnsResult = await runDualStackDnsBenchmark();

    // 6. Micro-Burst Bandwidth & Bufferbloat Probe
    logger.debug("Running Micro-Burst Bandwidth & Bufferbloat probe...");
    const bandwidthBufferbloatResult = await measureMicroBurstThroughput();

    // 7. EdTech Filter & Student Safety Agent Diagnostic (Securly, Lightspeed, Blocksi, GoGuardian)
    logger.debug("Running EdTech Filter & Safety Agent diagnostic suite...");
    const baselineRtt = gatewayProbeResult?.rtt_ms || 30;
    const edtechFilterResult = await runEdtechFilterSuite(baselineRtt);

    // 8. Run Synthetic HTTP Probes
    logger.debug("Running Synthetic HTTP application probes...");
    const targetsToProbe = cmpDynamicTargets.length > 0 ? cmpDynamicTargets : config.synthetic_http_targets;
    const httpResults = await runSyntheticHttpSuite(targetsToProbe);

    // 9. Run WebRTC Offscreen Prober (if enabled)
    let webrtcResult = null;
    if (config.enable_webrtc_probing) {
      logger.debug("Triggering Offscreen WebRTC STUN Latency & MOS evaluation...");
      webrtcResult = await executeOffscreenWebRtcProbe(config.stun_servers);
    }

    // 10. Build Standardized Ingestion Payload
    const reportPayload = buildReportPayload({
      sensorIdentity,
      wifiTelemetry,
      wifiDiagnostics,
      captivePortalResult,
      gatewayProbeResult,
      dualStackDnsResult,
      bandwidthBufferbloatResult,
      edtechFilterResult,
      hardwareTelemetry,
      syntheticHttpResults: httpResults,
      webrtcResult,
      campusId: config.campus_id
    });

    // 7. Submit to CMP
    const sendResult = await sendTelemetryReport(
      config.cmp_server_url,
      config.api_key,
      reportPayload
    );

    if (sendResult.success && sendResult.data) {
      if (sendResult.data.custom_probes) {
        // Dynamically sync custom probes created in CMP Web UI, filtering for supported HTTP/API probes
        cmpDynamicTargets = sendResult.data.custom_probes
          .filter(p => !p.probe_type || p.probe_type === "http" || p.probe_type === "api")
          .map((p) => {
            let targetUrl = p.target || p.target_url;
            if (targetUrl && !/^https?:\/\//i.test(targetUrl)) {
                targetUrl = "https://" + targetUrl; // Default to HTTPS if missing schema
            }
            return {
              name: p.name,
              url: targetUrl,
              category: p.category || p.probe_type || "CMP Custom",
              timeout_ms: p.timeout_seconds ? p.timeout_seconds * 1000 : 5000
            };
          });
        logger.info(`Synchronized ${cmpDynamicTargets.length} active custom probes from CMP.`);
      }

      if (typeof sendResult.data.settings_locked === "boolean") {
        configManager.updateLocal({ settings_locked: sendResult.data.settings_locked });
        logger.info(`Server mandated settings_locked state: ${sendResult.data.settings_locked}`);
      }

      if (sendResult.data.helpdesk_pin && sendResult.data.helpdesk_pin !== config.helpdesk_pin) {
        configManager.updateLocal({
          previous_helpdesk_pin: config.helpdesk_pin || "4357",
          helpdesk_pin: sendResult.data.helpdesk_pin
        });
        logger.info(`Synchronized updated Helpdesk PIN from CMP server.`);
      }
    }

    if (!sendResult.success && config.enable_offline_buffer) {
      logger.info("CMP unreachable; buffering report into IndexedDB offline queue");
      await offlineStorage.enqueue(reportPayload, config.max_offline_records);
    } else if (sendResult.success && config.enable_offline_buffer) {
      // If report succeeded and we are online, flush any pending backlog
      await flushOfflineBuffer(config.cmp_server_url, config.api_key);
    }

    // 8. Update Snapshot for UI / Diagnostics
    const count = await offlineStorage.count();
    let computedStatus = "HEALTHY";
    if (captivePortalResult && captivePortalResult.is_captive_portal) {
      computedStatus = "CAPTIVE_PORTAL";
    } else if (edtechFilterResult && edtechFilterResult.collision_detected) {
      computedStatus = "FILTER_COLLISION";
    } else if (edtechFilterResult && edtechFilterResult.health_status === "SSL_INSPECTION_FAILED") {
      computedStatus = "SSL_INSPECTION_FAILED";
    } else if (edtechFilterResult && edtechFilterResult.health_status === "CLASSROOM_BLOCKED") {
      computedStatus = "CLASSROOM_BLOCKED";
    } else if (wifiDiagnostics && wifiDiagnostics.is_flapping) {
      computedStatus = "AP_FLAPPING";
    } else if (wifiDiagnostics && wifiDiagnostics.is_sticky_client) {
      computedStatus = "STICKY_CLIENT";
    } else if (edtechFilterResult && edtechFilterResult.health_status === "CLOUD_UNREACHABLE") {
      computedStatus = "FILTER_OFFLINE";
    } else if (webrtcResult && webrtcResult.mos && webrtcResult.mos < 3.5) {
      computedStatus = "DEGRADED";
    }

    latestSnapshot = {
      last_run_timestamp: Date.now(),
      sensor_identity: sensorIdentity,
      wifi: wifiTelemetry,
      wifi_diagnostics: wifiDiagnostics,
      captive_portal: captivePortalResult,
      gateway_probe: gatewayProbeResult,
      dns_benchmark: dualStackDnsResult,
      bandwidth_bufferbloat: bandwidthBufferbloatResult,
      edtech_filter: edtechFilterResult,
      synthetic_http: httpResults,
      webrtc: webrtcResult,
      buffered_count: count,
      status: computedStatus
    };

    logger.info("Diagnostic probe cycle completed successfully.");
    return latestSnapshot;
  } catch (err) {
    logger.error("Error during diagnostic cycle:", err);
    latestSnapshot.status = "ERROR";
    return latestSnapshot;
  }
}

/**
 * Configure periodic alarm based on active configuration cadence.
 */
function setupAlarm(intervalSeconds) {
  if (typeof chrome === "undefined" || !chrome.alarms) return;
  const periodInMinutes = Math.max(0.25, intervalSeconds / 60.0);
  chrome.alarms.create(ALARM_NAME, {
    periodInMinutes: periodInMinutes,
    delayInMinutes: 0.1
  });
  logger.info(`Probe alarm configured for every ${periodInMinutes} minutes (${intervalSeconds}s)`);
}

// Alarm Listener
if (typeof chrome !== "undefined" && chrome.alarms) {
  chrome.alarms.onAlarm.addListener((alarm) => {
    if (alarm.name === ALARM_NAME) {
      executeDiagnosticCycle();
    }
  });
}

// Roaming Handover Listener (Triggers an immediate fast probe on AP handoff)
onWifiRoam((roamEvent) => {
  logger.info("AP Handoff detected, triggering fast roaming validation sweep...");
  executeDiagnosticCycle();
});

// Runtime Message Listener (Popup UI & On-Demand Actions)
if (typeof chrome !== "undefined" && chrome.runtime) {
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.target === "background") {
      if (message.type === "GET_LATEST_SNAPSHOT") {
        sendResponse({ success: true, snapshot: latestSnapshot, config: configManager.get() });
        return false;
      } else if (message.type === "TRIGGER_ON_DEMAND_PROBE") {
        executeDiagnosticCycle().then((snapshot) => {
          sendResponse({ success: true, snapshot });
        });
        return true;
      } else if (message.type === "UPDATE_LOCAL_CONFIG") {
        configManager.updateLocal(message.updates).then((newConf) => {
          setupAlarm(newConf.probe_interval_seconds);
          sendResponse({ success: true, config: newConf });
        });
        return true;
      } else if (message.type === "VERIFY_HELPDESK_PIN") {
        const conf = configManager.get();
        const activePin = String(conf.helpdesk_pin || "4357").trim();
        const prevPin = conf.previous_helpdesk_pin ? String(conf.previous_helpdesk_pin).trim() : null;
        const masterBypass = conf.master_emergency_pin ? String(conf.master_emergency_pin).trim() : null;
        const providedPin = String(message.pin || "").trim();

        // Allows active PIN, previous PIN during rotation grace period, or master district bypass
        const isValid = (providedPin === activePin) ||
                        (prevPin !== null && providedPin === prevPin) ||
                        (masterBypass !== null && providedPin === masterBypass);

        if (isValid) {
          sendResponse({ success: true, verified: true });
        } else {
          sendResponse({ success: true, verified: false, error: "Invalid Helpdesk PIN" });
        }
        return false;
      } else if (message.type === "SET_LOCAL_LOCK_STATE") {
        configManager.updateLocal({ settings_locked: Boolean(message.locked) }).then((newConf) => {
          sendResponse({ success: true, settings_locked: newConf.settings_locked });
        });
        return true;
      }
    }
  });
}

// Lifecycle Initialization
let isInitialized = false;
async function initialize() {
  if (isInitialized) return;
  isInitialized = true;
  logger.info("Initializing Open Network Experience Chromebook Sensor Service Worker...");
  const config = await configManager.loadConfig();
  setupAlarm(config.probe_interval_seconds);

  // Run initial diagnostic sweep shortly after start
  setTimeout(() => {
    executeDiagnosticCycle();
  }, 2000);
}

if (typeof chrome !== "undefined" && chrome.runtime) {
  if (chrome.runtime.onInstalled) {
    chrome.runtime.onInstalled.addListener(() => {
      logger.info("ONE Chromebook Sensor extension installed / updated");
      initialize();
    });
  }

  if (chrome.runtime.onStartup) {
    chrome.runtime.onStartup.addListener(() => {
      logger.info("ONE Chromebook Sensor extension browser startup");
      initialize();
    });
  }
}

// Ensure initialization when service worker wakes up
initialize();
