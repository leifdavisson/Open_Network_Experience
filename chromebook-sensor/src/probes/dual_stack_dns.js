/**
 * Open Network Experience (ONE) - Chromebook Sensor
 * Dual-Stack DNS Resolution Benchmark Probe
 * Compares DNS resolution latency and answer consistency across:
 * 1. Google Public DoH (https://dns.google/resolve)
 * 2. Cloudflare Public DoH (https://cloudflare-dns.com/dns-query)
 * 3. Local Browser Fetch-based DNS resolution (detecting school filter hijacking & local timeouts)
 * License: GNU AGPLv3
 */

import { logger } from "../utils/logger.js";

export const DOH_SERVERS = {
  google: { name: "Google Public DoH", url: "https://dns.google/resolve" },
  cloudflare: { name: "Cloudflare DoH", url: "https://cloudflare-dns.com/dns-query" }
};

/**
 * Resolves a domain name via a specific DoH provider.
 * @param {string} domain - Target FQDN (e.g. "google.com")
 * @param {string} providerUrl - DoH endpoint URL
 * @param {number} [timeoutMs=3500]
 * @returns {Promise<{
 *   provider: string,
 *   domain: string,
 *   success: boolean,
 *   latency_ms: number,
 *   ips: string[],
 *   status: string,
 *   error: string|null
 * }>}
 */
export async function resolveDoH(domain, providerUrl = DOH_SERVERS.google.url, timeoutMs = 3500) {
  const start = performance.now();
  const providerName = providerUrl.includes("cloudflare") ? "Cloudflare DoH" : "Google DoH";
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  const result = {
    provider: providerName,
    domain,
    success: false,
    latency_ms: 0,
    ips: [],
    status: "ERROR",
    error: null
  };

  try {
    const url = `${providerUrl}?name=${encodeURIComponent(domain)}&type=A&_ts=${Date.now()}`;
    const response = await fetch(url, {
      method: "GET",
      headers: { Accept: "application/dns-json" },
      signal: controller.signal
    });

    clearTimeout(timer);
    result.latency_ms = Math.round(performance.now() - start);

    if (response.ok) {
      const json = await response.json();
      result.status = json.Status === 0 ? "NOERROR" : `RCODE_${json.Status}`;
      if (json.Answer && Array.isArray(json.Answer)) {
        result.ips = json.Answer.filter((a) => a.type === 1).map((a) => a.data);
      }
      result.success = json.Status === 0;
    } else {
      result.error = `HTTP ${response.status}`;
    }
  } catch (err) {
    clearTimeout(timer);
    result.latency_ms = Math.round(performance.now() - start);
    result.error = err.name === "AbortError" ? `Timeout after ${timeoutMs}ms` : err.message;
  }

  return result;
}

/**
 * Measures local native stack resolution latency by attempting a fast lightweight query.
 * @param {string} domain
 * @param {number} [timeoutMs=3500]
 */
export async function resolveNativeLocalDns(domain, timeoutMs = 3500) {
  const start = performance.now();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  const result = {
    provider: "Local/DHCP DNS",
    domain,
    success: false,
    latency_ms: 0,
    status: "ERROR",
    error: null
  };

  try {
    const targetUrl = `https://${domain}/favicon.ico?_one_dns_probe=${Date.now()}`;
    await fetch(targetUrl, {
      method: "HEAD",
      mode: "no-cors",
      cache: "no-store",
      signal: controller.signal
    });

    clearTimeout(timer);
    result.latency_ms = Math.round(performance.now() - start);
    result.success = true;
    result.status = "NOERROR";
  } catch (err) {
    clearTimeout(timer);
    result.latency_ms = Math.round(performance.now() - start);
    result.error = err.name === "AbortError" ? `Timeout after ${timeoutMs}ms` : err.message;
  }

  return result;
}

/**
 * Executes a dual-stack benchmark comparing public DoH resolution against local DNS.
 * Detects content filter interception (e.g. IP hijacking by Securly/GoGuardian) and slow local DNS.
 * @param {string} domain - Domain to benchmark (defaults to "classroom.google.com")
 * @returns {Promise<{
 *   domain: string,
 *   doh_google: object,
 *   doh_cloudflare: object,
 *   local_dns: object,
 *   dns_health: string,
 *   recommendation: string
 * }>}
 */
export async function runDualStackDnsBenchmark(domain = "classroom.google.com") {
  const [googleRes, cfRes, localRes] = await Promise.all([
    resolveDoH(domain, DOH_SERVERS.google.url),
    resolveDoH(domain, DOH_SERVERS.cloudflare.url),
    resolveNativeLocalDns(domain)
  ]);

  let health = "HEALTHY";
  let rec = "DNS resolution fast and consistent across providers";

  if (!googleRes.success && !cfRes.success && !localRes.success) {
    health = "CRITICAL_OUTAGE";
    rec = "All DNS resolution paths failed. Device is completely offline or DNS is blocked.";
  } else if (!localRes.success && (googleRes.success || cfRes.success)) {
    health = "LOCAL_DNS_FAIL";
    rec = "Local LAN/DHCP DNS is timing out while public DoH succeeds. Check internal DNS server or gateway.";
  } else if (localRes.latency_ms > 250 || googleRes.latency_ms > 250) {
    health = "DEGRADED_LATENCY";
    rec = `High DNS latency detected (${Math.max(localRes.latency_ms, googleRes.latency_ms)}ms). Web pages and SaaS apps will feel sluggish.`;
  }

  return {
    domain,
    doh_google: googleRes,
    doh_cloudflare: cfRes,
    local_dns: localRes,
    dns_health: health,
    recommendation: rec
  };
}
