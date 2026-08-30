/**
 * Open Network Experience (ONE) - Chromebook Sensor
 * Synthetic HTTP & Application Timing Probe
 * Evaluates district web applications with DNS, TCP, TLS, TTFB, and latency breakdowns.
 * License: GNU AGPLv3
 */

import { logger } from "../utils/logger.js";

/**
 * Runs a synthetic HTTP probe against a single target URL.
 * @param {object} target - { name: string, url: string, category: string, timeout_ms?: number }
 * @returns {Promise<object>}
 */
export async function probeHttpTarget(target) {
  const { name, url, category = "General", timeout_ms = 5000 } = target;
  const startTime = performance.now();
  const result = {
    name,
    url,
    category,
    status_code: 0,
    success: false,
    latency_ms: 0,
    dns_ms: 0,
    tcp_ms: 0,
    tls_ms: 0,
    ttfb_ms: 0,
    error: null,
    timestamp: Date.now()
  };

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout_ms);

  try {
    const fetchUrl = `${url}${url.includes("?") ? "&" : "?"}_one_cb_probe=${Date.now()}`;
    const response = await fetch(fetchUrl, {
      method: "HEAD", // Prefer lightweight HEAD request to minimize bandwidth
      signal: controller.signal,
      cache: "no-store",
      mode: "no-cors" // Supports cross-origin probing without CORS failures
    });

    clearTimeout(timer);
    const endTime = performance.now();
    result.latency_ms = Math.round(endTime - startTime);
    result.status_code = response.status || 200; // opaque no-cors responses return status 0
    result.success = true;

    // Inspect PerformanceResourceTiming if available in execution context
    if (typeof performance.getEntriesByName === "function") {
      const entries = performance.getEntriesByName(fetchUrl);
      if (entries && entries.length > 0) {
        const perf = entries[entries.length - 1];
        if (perf.domainLookupEnd && perf.domainLookupStart) {
          result.dns_ms = Math.round(perf.domainLookupEnd - perf.domainLookupStart);
        }
        if (perf.connectEnd && perf.connectStart) {
          result.tcp_ms = Math.round(perf.connectEnd - perf.connectStart);
        }
        if (perf.secureConnectionStart && perf.connectEnd) {
          result.tls_ms = Math.round(perf.connectEnd - perf.secureConnectionStart);
        }
        if (perf.responseStart && perf.requestStart) {
          result.ttfb_ms = Math.round(perf.responseStart - perf.requestStart);
        }
        // Clean up performance buffer
        if (typeof performance.clearResourceTimings === "function") {
          performance.clearResourceTimings();
        }
      }
    }
  } catch (err) {
    clearTimeout(timer);
    const endTime = performance.now();
    result.latency_ms = Math.round(endTime - startTime);
    result.success = false;
    result.error = err.name === "AbortError" ? `Timeout after ${timeout_ms}ms` : err.message;
    logger.warn(`Synthetic probe failed for [${name}] (${url}):`, result.error);
  }

  return result;
}

/**
 * Runs synthetic probes across all configured district application targets.
 * @param {Array<object>} targets
 * @returns {Promise<Array<object>>}
 */
export async function runSyntheticHttpSuite(targets = []) {
  if (!targets || targets.length === 0) return [];
  const results = await Promise.all(targets.map((t) => probeHttpTarget(t)));
  return results;
}
