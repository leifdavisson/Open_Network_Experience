/**
 * Open Network Experience (ONE) - Chromebook Sensor
 * DNS-over-HTTPS (DoH) & Resolution Latency Probe
 * License: GNU AGPLv3
 */

import { logger } from "../utils/logger.js";

const DOH_PROVIDERS = [
  { name: "Google DNS", url: "https://dns.google/resolve" },
  { name: "Cloudflare DNS", url: "https://cloudflare-dns.com/dns-query" }
];

/**
 * Performs DoH resolution check for target domain.
 * @param {string} domain - Domain to resolve (e.g. "classroom.google.com")
 * @param {string} dohEndpoint - DoH endpoint URL
 * @returns {Promise<object>}
 */
export async function probeDnsResolution(domain = "google.com", dohEndpoint = "https://dns.google/resolve") {
  const start = performance.now();
  const result = {
    domain,
    provider: dohEndpoint.includes("google") ? "Google DoH" : "Cloudflare DoH",
    success: false,
    resolution_time_ms: 0,
    ip_addresses: [],
    status: "ERROR",
    error: null
  };

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 4000);

  try {
    const url = `${dohEndpoint}?name=${encodeURIComponent(domain)}&type=A`;
    const response = await fetch(url, {
      method: "GET",
      headers: { Accept: "application/dns-json" },
      signal: controller.signal
    });

    clearTimeout(timer);
    const end = performance.now();
    result.resolution_time_ms = Math.round(end - start);

    if (response.ok) {
      const data = await response.json();
      result.status = data.Status === 0 ? "NOERROR" : `RCODE_${data.Status}`;
      if (data.Answer && Array.isArray(data.Answer)) {
        result.ip_addresses = data.Answer.filter((a) => a.type === 1).map((a) => a.data);
      }
      result.success = data.Status === 0;
    } else {
      result.error = `HTTP ${response.status}`;
    }
  } catch (err) {
    clearTimeout(timer);
    result.resolution_time_ms = Math.round(performance.now() - start);
    result.error = err.message;
  }

  return result;
}
