/**
 * Open Network Experience (ONE) - Chromebook Sensor
 * ChromeOS Wi-Fi & Network Private Telemetry
 * Captures active SSID, BSSID, RSSI dBm, Frequency, Channel, and Roaming events.
 * License: GNU AGPLv3
 */

import { logger } from "../utils/logger.js";

let lastKnownBssid = null;
let lastKnownSsid = null;
const roamingListeners = [];

/**
 * Register callback for Wi-Fi AP Roaming events (BSSID transition).
 * @param {function({ oldBssid: string, newBssid: string, ssid: string, timestamp: number })} callback
 */
export function onWifiRoam(callback) {
  roamingListeners.push(callback);
}

/**
 * Calculates Wi-Fi channel from frequency in MHz (2.4 GHz, 5 GHz, 6 GHz).
 * @param {number} freqMhz
 * @returns {number|null} Channel number
 */
export function frequencyToChannel(freqMhz) {
  if (!freqMhz || isNaN(freqMhz)) return null;
  // 2.4 GHz (802.11b/g/n/ax)
  if (freqMhz === 2484) return 14;
  if (freqMhz >= 2412 && freqMhz <= 2472) {
    return Math.floor((freqMhz - 2407) / 5);
  }
  // 5 GHz (802.11a/n/ac/ax)
  if (freqMhz >= 5170 && freqMhz <= 5825) {
    return Math.floor((freqMhz - 5000) / 5);
  }
  // 6 GHz (Wi-Fi 6E / 7, 802.11ax/be)
  if (freqMhz >= 5955 && freqMhz <= 7115) {
    return Math.floor((freqMhz - 5950) / 5);
  }
  return null;
}

/**
 * Converts ChromeOS signal strength (0-100%) to estimated RSSI dBm if raw dBm is absent.
 * @param {number} signalStrengthPercent
 * @returns {number} Estimated RSSI in dBm
 */
export function percentToRssiDbm(signalStrengthPercent) {
  if (signalStrengthPercent === undefined || signalStrengthPercent === null) return -99;
  // Standard linear approximation: 0% = -100 dBm, 100% = -50 dBm
  const dbm = -100 + Math.min(100, Math.max(0, signalStrengthPercent)) * 0.5;
  return Math.round(dbm);
}

/**
 * Retrieves full active Wi-Fi and network interface telemetry.
 */
export async function getActiveWifiTelemetry() {
  const result = {
    connected: false,
    ssid: null,
    bssid: null,
    rssi_dbm: null,
    signal_strength_pct: null,
    frequency_mhz: null,
    channel: null,
    band: null, // "2.4GHz", "5GHz", "6GHz"
    security: null,
    gateway_ip: null,
    ip_address: null,
    mac_address: null,
    effective_type: null,
    estimated_rtt_ms: null,
    downlink_mbps: null,
    captive_portal_detected: false,
    roamed_recently: false
  };

  // 1. Browser Network Information API (Standard Web API)
  if (typeof navigator !== "undefined") {
    result.connected = navigator.onLine;
    if (navigator.connection) {
      result.effective_type = navigator.connection.effectiveType || null;
      result.estimated_rtt_ms = navigator.connection.rtt || null;
      result.downlink_mbps = navigator.connection.downlink || null;
    }
  }

  // 2. chrome.networkingPrivate API (ChromeOS Enterprise / Force-Installed)
  if (typeof chrome !== "undefined" && chrome.networkingPrivate) {
    try {
      const networks = await new Promise((resolve) => {
        chrome.networkingPrivate.getNetworks(
          { networkType: "WiFi", visible: true, configured: true },
          (nets) => {
            if (chrome.runtime.lastError) {
              logger.debug("networkingPrivate.getNetworks error:", chrome.runtime.lastError.message);
              resolve([]);
            } else {
              resolve(nets || []);
            }
          }
        );
      });

      const activeNet = networks.find(
        (n) => n.ConnectionState === "Connected" || n.ConnectionState === "Online"
      );

      if (activeNet) {
        result.connected = true;
        result.ssid = activeNet.WiFi?.SSID || activeNet.Name || null;
        result.bssid = activeNet.WiFi?.BSSID || activeNet.BSSID || null;
        result.signal_strength_pct = activeNet.WiFi?.SignalStrength ?? activeNet.SignalStrength ?? null;
        result.rssi_dbm = activeNet.WiFi?.SignalStrengthDbm ?? percentToRssiDbm(result.signal_strength_pct);
        result.frequency_mhz = activeNet.WiFi?.Frequency || null;
        result.channel = activeNet.WiFi?.Channel || frequencyToChannel(result.frequency_mhz);
        result.security = activeNet.WiFi?.Security || "WPA-Enterprise/PSK";

        if (result.frequency_mhz) {
          if (result.frequency_mhz > 5900) result.band = "6GHz (Wi-Fi 6E/7)";
          else if (result.frequency_mhz > 4900) result.band = "5GHz";
          else result.band = "2.4GHz";
        }

        // Check if BSSID changed (Roaming detected)
        if (lastKnownBssid && result.bssid && lastKnownBssid !== result.bssid) {
          result.roamed_recently = true;
          logger.info(`Wi-Fi Roaming detected: AP [${lastKnownBssid}] -> [${result.bssid}] on SSID [${result.ssid}]`);

          const roamEvent = {
            oldBssid: lastKnownBssid,
            newBssid: result.bssid,
            ssid: result.ssid,
            timestamp: Date.now()
          };
          for (const cb of roamingListeners) {
            try { cb(roamEvent); } catch (e) { logger.error("Roam listener error:", e); }
          }
        }

        if (result.bssid) {
          lastKnownBssid = result.bssid;
        }
        if (result.ssid) {
          lastKnownSsid = result.ssid;
        }
      }
    } catch (err) {
      logger.debug("Error reading chrome.networkingPrivate:", err);
    }
  }

  // 3. Fallback: Query system.network for local IP
  if (typeof chrome !== "undefined" && chrome.system && chrome.system.network) {
    try {
      const ifaces = await new Promise((resolve) => {
        chrome.system.network.getNetworkInterfaces((items) => resolve(items || []));
      });
      const activeIface = ifaces.find((i) => i.prefixLength && !i.address.startsWith("127."));
      if (activeIface) {
        result.ip_address = activeIface.address;
      }
    } catch (e) {
      // Ignored
    }
  }

  return result;
}
