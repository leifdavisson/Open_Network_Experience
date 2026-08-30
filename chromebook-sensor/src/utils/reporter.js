/**
 * Open Network Experience (ONE) - Chromebook Sensor
 * Telemetry Ingestion Client & Payload Serializer
 * Posts telemetry to CMP (/api/v1/sensors/report).
 * License: GNU AGPLv3
 */

import { logger } from "./logger.js";

/**
 * Builds a standardized Chromebook Sensor Telemetry Report payload.
 */
export function buildReportPayload({
  sensorIdentity,
  wifiTelemetry,
  hardwareTelemetry,
  syntheticHttpResults,
  webrtcResult,
  campusId
}) {
  return {
    sensor_id: sensorIdentity.sensor_id,
    sensor_type: "chromebook",
    os: "ChromeOS",
    timestamp: Math.floor(Date.now() / 1000),
    campus_id: campusId || "CAMPUS-CHROMEBOOK-FLEET",
    device_info: {
      serial_number: sensorIdentity.serial_number,
      asset_id: sensorIdentity.asset_id,
      annotated_location: sensorIdentity.location,
      annotated_user: sensorIdentity.annotated_user || null,
      directory_device_id: sensorIdentity.directory_device_id || null,
      hostname: sensorIdentity.hostname,
      mac_address: sensorIdentity.mac_address || null,
      is_managed: sensorIdentity.is_managed,
      user_agent: typeof navigator !== "undefined" ? navigator.userAgent : "ChromeOS/ONE-Sensor"
    },
    location: {
      district: "Default District",
      site: campusId || "District Chromebook Fleet",
      building: "Mobile Fleet",
      room: sensorIdentity.location || "Mobile Client"
    },
    wifi: {
      connected: wifiTelemetry.connected,
      ssid: wifiTelemetry.ssid,
      bssid: wifiTelemetry.bssid,
      rssi_dbm: wifiTelemetry.rssi_dbm,
      signal_strength_pct: wifiTelemetry.signal_strength_pct,
      frequency_mhz: wifiTelemetry.frequency_mhz,
      channel: wifiTelemetry.channel,
      band: wifiTelemetry.band,
      security: wifiTelemetry.security,
      roamed_recently: wifiTelemetry.roamed_recently
    },
    hardware: {
      cpu: hardwareTelemetry?.cpu || null,
      memory: hardwareTelemetry?.memory || null,
      storage: hardwareTelemetry?.storage || null,
      display: hardwareTelemetry?.display || null,
      battery: hardwareTelemetry?.battery || null,
      os_info: hardwareTelemetry?.os_info || null,
      interfaces: hardwareTelemetry?.interfaces || []
    },
    probes: {
      synthetic_http: syntheticHttpResults || [],
      webrtc: webrtcResult || null
    }
  };
}

/**
 * Submits report to CMP FastAPI backend.
 * @param {string} cmpUrl - Base CMP URL
 * @param {string} apiKey - Sensor / Enrollment API Key
 * @param {object} payload - Standard report payload
 * @param {number} timeoutMs
 * @returns {Promise<{ success: boolean, statusCode: number, error?: string }>}
 */
export async function sendTelemetryReport(cmpUrl, apiKey, payload, timeoutMs = 8000) {
  const endpoint = `${cmpUrl.replace(/\/+$/, "")}/api/v1/sensors/report`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const headers = {
      "Content-Type": "application/json",
      "User-Agent": "ONE-Chromebook-Sensor/1.0"
    };

    if (apiKey) {
      headers["X-API-Key"] = apiKey;
    }

    const response = await fetch(endpoint, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
      signal: controller.signal
    });

    clearTimeout(timer);

    if (response.ok) {
      const data = await response.json().catch(() => null);
      logger.info(`Telemetry report successfully ingested by CMP (${response.status})`);
      return { success: true, statusCode: response.status, data };
    }

    const errText = await response.text().catch(() => "");
    logger.warn(`CMP ingestion rejected (${response.status}):`, errText);
    return { success: false, statusCode: response.status, error: `HTTP ${response.status}: ${errText}` };
  } catch (err) {
    clearTimeout(timer);
    const isTimeout = err.name === "AbortError";
    const msg = isTimeout ? `Network timeout after ${timeoutMs}ms` : err.message;
    logger.debug("Failed to deliver telemetry to CMP (will buffer offline):", msg);
    return { success: false, statusCode: 0, error: msg };
  }
}
