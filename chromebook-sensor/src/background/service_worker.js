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
import { buildReportPayload, sendTelemetryReport } from "../utils/reporter.js";
import { offlineStorage } from "../db/indexed_db.js";
import { flushOfflineBuffer } from "./storage_sync.js";

const ALARM_NAME = "one_sensor_periodic_probe";
const OFFSCREEN_DOCUMENT_PATH = "src/offscreen/offscreen.html";

let cmpDynamicTargets = [];
let latestSnapshot = {
  last_run_timestamp: 0,
  sensor_identity: null,
  wifi: null,
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

    // 2. Wi-Fi & RF Telemetry
    const wifiTelemetry = await getActiveWifiTelemetry();

    // 3. Synthetic HTTP Probing (Combines policy targets + CMP dynamic custom probes)
    const combinedTargets = [...config.synthetic_http_targets, ...cmpDynamicTargets];
    const syntheticHttpResults = await runSyntheticHttpSuite(combinedTargets);

    // 4. WebRTC STUN Probing (via Offscreen Document)
    let webrtcResult = null;
    if (config.enable_webrtc_probing) {
      webrtcResult = await executeOffscreenWebRtcProbe(config.stun_servers);
    }

    // 5. Construct Payload
    const payload = buildReportPayload({
      sensorIdentity,
      wifiTelemetry,
      hardwareTelemetry,
      syntheticHttpResults,
      webrtcResult,
      campusId: config.campus_id
    });

    // 6. Submit to CMP
    const sendResult = await sendTelemetryReport(
      config.cmp_server_url,
      config.api_key,
      payload
    );

    if (sendResult.success && sendResult.data) {
      if (sendResult.data.custom_probes) {
        // Dynamically sync custom probes created in CMP Web UI
        cmpDynamicTargets = sendResult.data.custom_probes.map((p) => ({
          name: p.name,
          url: p.target_url,
          category: p.category || "CMP Custom",
          timeout_ms: p.timeout_seconds ? p.timeout_seconds * 1000 : 5000
        }));
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
      await offlineStorage.enqueue(payload, config.max_offline_records);
    } else if (sendResult.success && config.enable_offline_buffer) {
      // If report succeeded and we are online, flush any pending backlog
      await flushOfflineBuffer(config.cmp_server_url, config.api_key);
    }

    // 7. Update Snapshot for UI / Diagnostics
    const count = await offlineStorage.count();
    latestSnapshot = {
      last_run_timestamp: Date.now(),
      sensor_identity: sensorIdentity,
      wifi: wifiTelemetry,
      synthetic_http: syntheticHttpResults,
      webrtc: webrtcResult,
      buffered_count: count,
      status: "HEALTHY"
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
