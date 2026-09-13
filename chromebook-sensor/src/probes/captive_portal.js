/**
 * Open Network Experience (ONE) - Chromebook Sensor
 * Captive Portal & Walled-Garden Detection Probe
 * Emulates Google Connectivity Check (generate_204) to detect splash pages,
 * hotel/school captive portals, and 802.1X interception.
 * License: GNU AGPLv3
 */

import { logger } from "../utils/logger.js";

const DEFAULT_PORTAL_ENDPOINTS = [
  "http://connectivitycheck.gstatic.com/generate_204",
  "http://clients3.google.com/generate_204"
];

/**
 * Checks whether the device is intercepted by a captive portal or walled garden.
 * @param {string} endpointUrl - Probe URL (defaults to gstatic generate_204)
 * @param {number} timeoutMs - Max timeout in ms
 * @returns {Promise<{
 *   is_captive_portal: boolean,
 *   status_code: number,
 *   redirect_url: string|null,
 *   latency_ms: number,
 *   authenticated: boolean,
 *   error: string|null
 * }>}
 */
export async function checkCaptivePortal(endpointUrl = DEFAULT_PORTAL_ENDPOINTS[0], timeoutMs = 4000) {
  const startTime = performance.now();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  const result = {
    is_captive_portal: false,
    status_code: 0,
    redirect_url: null,
    latency_ms: 0,
    authenticated: false,
    error: null
  };

  try {
    // Add cache-buster query parameter
    const targetUrl = `${endpointUrl}?_one_probe=${Date.now()}`;
    const response = await fetch(targetUrl, {
      method: "GET",
      cache: "no-store",
      signal: controller.signal,
      redirect: "follow"
    });

    clearTimeout(timer);
    result.latency_ms = Math.round(performance.now() - startTime);
    result.status_code = response.status;

    // Genuine generate_204 returns HTTP 204 No Content with empty body.
    // If status is 204, connection is direct and open.
    if (response.status === 204) {
      result.is_captive_portal = false;
      result.authenticated = true;
    } else {
      // Any HTTP 200, 302, etc. means the probe was intercepted by a splash page or proxy
      result.is_captive_portal = true;
      result.authenticated = false;
      result.redirect_url = response.url !== targetUrl ? response.url : null;
      logger.warn(`Captive portal detected! Status: ${response.status}, Redirect: ${result.redirect_url || "Local Proxy"}`);
    }
  } catch (err) {
    clearTimeout(timer);
    result.latency_ms = Math.round(performance.now() - startTime);
    result.error = err.name === "AbortError" ? `Timeout after ${timeoutMs}ms` : err.message;
    // Network completely offline or blocked
    result.authenticated = false;
  }

  return result;
}
