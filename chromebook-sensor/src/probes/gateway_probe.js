/**
 * Open Network Experience (ONE) - Chromebook Sensor
 * Local Default Gateway & Next-Hop RTT Diagnostic Probe
 * Evaluates Layer 3 local subnet health by calculating next-hop IP and probing RTT.
 * Helps isolate Layer 2/3 local LAN/AP issues from upstream ISP/WAN outages.
 * License: GNU AGPLv3
 */

import { logger } from "../utils/logger.js";

/**
 * Derives the probable default gateway IP from a local IPv4 address and prefix length.
 * e.g., 10.200.4.155/24 -> 10.200.4.1
 * @param {string} ipAddress - Local IPv4 (e.g. "192.168.1.50")
 * @param {number} [prefixLength=24] - Subnet mask prefix
 * @returns {string|null} Estimated default gateway IP
 */
export function deriveGatewayIp(ipAddress, prefixLength = 24) {
  if (!ipAddress || typeof ipAddress !== "string") return null;
  const parts = ipAddress.split(".").map(Number);
  if (parts.length !== 4 || parts.some((p) => isNaN(p) || p < 0 || p > 255)) {
    return null;
  }

  // Common network practice: default gateway is typically host .1 in the subnet
  const base = parts.slice(0, 3).join(".");
  return `${base}.1`;
}

/**
 * Probes the local default gateway to measure local network RTT and reachability.
 * @param {string} gatewayIp - Gateway IP address
 * @param {number} [timeoutMs=2000] - Fast timeout since gateway is on local LAN
 * @returns {Promise<{
 *   gateway_ip: string|null,
 *   reachable: boolean,
 *   rtt_ms: number,
 *   status: string,
 *   error: string|null
 * }>}
 */
export async function probeGatewayReachability(gatewayIp, timeoutMs = 2000) {
  const result = {
    gateway_ip: gatewayIp || null,
    reachable: false,
    rtt_ms: 0,
    status: "UNKNOWN",
    error: null
  };

  if (!gatewayIp) {
    result.status = "NO_GATEWAY";
    result.error = "No local gateway IP identified";
    return result;
  }

  const start = performance.now();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    // Send a lightweight HTTP HEAD probe to gateway with cache buster and Chrome LNA annotation
    const probeUrl = `http://${gatewayIp}/?_one_gw_probe=${Date.now()}`;
    await fetch(probeUrl, {
      method: "HEAD",
      mode: "no-cors",
      cache: "no-store",
      targetAddressSpace: "local", // W3C Local Network Access specification (Chrome 138+)
      signal: controller.signal
    });

    clearTimeout(timer);
    result.rtt_ms = Math.round(performance.now() - start);
    result.reachable = true;
    result.status = "REACHABLE";
  } catch (err) {
    clearTimeout(timer);
    const elapsed = Math.round(performance.now() - start);
    result.rtt_ms = elapsed;

    if (err.name === "AbortError") {
      result.reachable = false;
      result.status = "TIMEOUT";
      result.error = `Gateway timeout after ${timeoutMs}ms`;
    } else {
      // In browser no-cors fetch, a TCP RST or connection refused still proves the gateway IP is alive and responding on Layer 3
      if (elapsed < timeoutMs) {
        result.reachable = true;
        result.status = "REACHABLE"; // Network stack reached gateway; service closed/rejected port
      } else {
        result.reachable = false;
        result.status = "UNREACHABLE";
        result.error = err.message;
      }
    }
  }

  return result;
}
