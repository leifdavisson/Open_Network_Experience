/**
 * Open Network Experience (ONE) - Chromebook Sensor
 * Wi-Fi RF & Health Analyzer
 * Detects "Sticky Client" syndrome, sub-optimal band steering,
 * AP thrashing/flapping, and excessive roam latency.
 * License: GNU AGPLv3
 */

import { logger } from "../utils/logger.js";

export class WifiHealthAnalyzer {
  constructor() {
    this.roamHistory = []; // Array of { bssid: string, ssid: string, timestamp: number }
    this.maxHistory = 20;
  }

  /**
   * Records an AP roam or state observation.
   * @param {string} bssid
   * @param {string} ssid
   * @param {number} timestamp
   */
  recordTransition(bssid, ssid, timestamp = Date.now()) {
    if (!bssid) return;
    this.roamHistory.push({ bssid, ssid, timestamp });
    if (this.roamHistory.length > this.maxHistory) {
      this.roamHistory.shift();
    }
  }

  /**
   * Analyzes active Wi-Fi telemetry for performance anomalies.
   * @param {object} wifi - Active Wi-Fi telemetry from network_private.js
   * @param {number} [windowMs=60000] - Time window for flap detection (defaults to 60s)
   * @returns {object} Health diagnostic report
   */
  analyze(wifi, windowMs = 60000) {
    const report = {
      is_sticky_client: false,
      is_suboptimal_band: false,
      is_flapping: false,
      signal_health: "GOOD", // "EXCELLENT", "GOOD", "FAIR", "POOR", "CRITICAL"
      recommendation: "Wi-Fi connection healthy",
      roam_transitions_last_min: 0,
      recent_flaps: []
    };

    if (!wifi || !wifi.connected) {
      report.signal_health = "DISCONNECTED";
      report.recommendation = "No active Wi-Fi connection detected";
      return report;
    }

    const rssi = wifi.rssi_dbm;
    const band = wifi.band || "";
    const is24G = band.includes("2.4GHz") || (wifi.frequency_mhz && wifi.frequency_mhz < 3000);

    // 1. Signal Health Classification (Enterprise Wi-Fi standards)
    if (rssi !== null && rssi !== undefined) {
      if (rssi >= -60) {
        report.signal_health = "EXCELLENT";
      } else if (rssi >= -67) {
        report.signal_health = "GOOD"; // Minimum standard for VoIP/WebRTC
      } else if (rssi >= -75) {
        report.signal_health = "FAIR"; // Adequate for basic web browsing
      } else if (rssi >= -82) {
        report.signal_health = "POOR";
      } else {
        report.signal_health = "CRITICAL";
      }
    }

    // 2. "Sticky Client" & Sub-optimal Band Steering
    // A client stuck on 2.4 GHz with poor signal (< -75 dBm) or clinging to an AP when coverage is degraded
    if (is24G && rssi !== null && rssi <= -72) {
      report.is_sticky_client = true;
      report.is_suboptimal_band = true;
      report.recommendation = "Client is connected to 2.4 GHz with weak signal. AP roaming or band-steering to 5/6 GHz recommended.";
    } else if (rssi !== null && rssi < -78) {
      report.is_sticky_client = true;
      report.recommendation = "Critical Wi-Fi signal attenuation (< -78 dBm). Client failed to roam to a closer AP.";
    }

    // 3. AP Thrashing / Flapping Detection
    // Checks if the client has switched between APs multiple times within windowMs
    const now = Date.now();
    const recentRoams = this.roamHistory.filter((r) => now - r.timestamp <= windowMs);
    report.roam_transitions_last_min = recentRoams.length;

    if (recentRoams.length >= 3) {
      // Check for bouncing back and forth between identical BSSIDs
      const bssids = recentRoams.map((r) => r.bssid);
      const uniqueBssids = new Set(bssids);
      if (uniqueBssids.size < bssids.length) {
        report.is_flapping = true;
        report.recent_flaps = Array.from(uniqueBssids);
        report.recommendation = `AP Flapping detected: Client switched APs ${recentRoams.length} times in past minute. Investigate overlapping AP cell boundaries or co-channel interference.`;
        logger.warn(report.recommendation);
      }
    }

    return report;
  }
}

export const wifiHealthAnalyzer = new WifiHealthAnalyzer();
