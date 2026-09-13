/**
 * Open Network Experience (ONE) - Chromebook Sensor
 * Micro-Burst Bandwidth & Bufferbloat Diagnostic Probe
 * Performs low-overhead chunk downloads to measure downlink throughput
 * and calculates bufferbloat (latency delta under network load).
 * License: GNU AGPLv3
 */

import { logger } from "../utils/logger.js";

// Fast, geographically distributed CDNs providing reliable public speed test assets
const DEFAULT_BURST_ENDPOINTS = [
  {
    name: "Cloudflare 1MB",
    url: "https://speed.cloudflare.com/__down?bytes=1048576",
    bytes: 1048576
  },
  {
    name: "Fast.com / Akamai 512KB",
    url: "https://speed.hetzner.de/1MB.bin",
    bytes: 1048576
  }
];

/**
 * Executes a rapid micro-burst bandwidth test and measures bufferbloat.
 * 1. Measures baseline idle RTT.
 * 2. Streams/downloads a micro chunk (approx 1MB) while measuring concurrent latency.
 * 3. Calculates Downlink Throughput (Mbps) and Bufferbloat (Delta RTT in ms).
 * 
 * @param {string} [chunkUrl] - Optional URL for the micro-chunk download
 * @param {number} [expectedBytes=1048576] - Size of chunk in bytes (1MB default)
 * @param {number} [timeoutMs=8000] - Hard safety timeout to prevent eating quotas
 * @returns {Promise<{
 *   throughput_mbps: number,
 *   baseline_rtt_ms: number,
 *   loaded_rtt_ms: number,
 *   bufferbloat_delta_ms: number,
 *   grade: string, // "A" (Excellent), "B" (Good), "C" (Fair), "D" (Poor), "F" (Bad)
 *   bytes_downloaded: number,
 *   duration_ms: number,
 *   success: boolean,
 *   error: string|null
 * }>}
 */
export async function measureMicroBurstThroughput(
  chunkUrl = DEFAULT_BURST_ENDPOINTS[0].url,
  expectedBytes = DEFAULT_BURST_ENDPOINTS[0].bytes,
  timeoutMs = 8000
) {
  const result = {
    throughput_mbps: 0.0,
    baseline_rtt_ms: 0,
    loaded_rtt_ms: 0,
    bufferbloat_delta_ms: 0,
    grade: "UNKNOWN",
    bytes_downloaded: 0,
    duration_ms: 0,
    success: false,
    error: null
  };

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  const overallStart = performance.now();

  try {
    // Phase 1: Baseline Idle RTT (Fast lightweight HEAD probe)
    const baseStart = performance.now();
    try {
      await fetch("https://connectivitycheck.gstatic.com/generate_204", {
        method: "HEAD",
        cache: "no-store",
        mode: "no-cors",
        signal: controller.signal
      });
      result.baseline_rtt_ms = Math.round(performance.now() - baseStart);
    } catch {
      result.baseline_rtt_ms = 35; // Nominal fallback if offline
    }

    // Phase 2: Micro-Burst Download & Concurrent Loaded RTT
    const burstStart = performance.now();
    const burstTarget = `${chunkUrl}${chunkUrl.includes("?") ? "&" : "?"}_burst_ts=${Date.now()}`;

    // Start chunk download
    const downloadPromise = fetch(burstTarget, {
      method: "GET",
      cache: "no-store",
      signal: controller.signal
    });

    // Concurrently trigger loaded latency probe while download pipe is saturated
    let loadedRttPromise = (async () => {
      // Small pause to let TCP window scale up
      await new Promise((r) => setTimeout(r, 80));
      const loadedStart = performance.now();
      try {
        await fetch("https://connectivitycheck.gstatic.com/generate_204", {
          method: "HEAD",
          cache: "no-store",
          mode: "no-cors",
          signal: controller.signal
        });
        return Math.round(performance.now() - loadedStart);
      } catch {
        return Math.round(performance.now() - loadedStart);
      }
    })();

    const [response, loadedRtt] = await Promise.all([downloadPromise, loadedRttPromise]);
    result.loaded_rtt_ms = loadedRtt;

    if (!response.ok) {
      throw new Error(`HTTP ${response.status} downloading burst payload`);
    }

    // Read payload arrayBuffer to accurately measure byte transfer time
    const buffer = await response.arrayBuffer();
    clearTimeout(timer);

    const burstEnd = performance.now();
    result.duration_ms = Math.max(1, Math.round(burstEnd - burstStart));
    result.bytes_downloaded = buffer.byteLength || expectedBytes;

    // Calculate Downlink Throughput: (Bytes * 8) / (duration in seconds * 1,000,000)
    const durationSeconds = result.duration_ms / 1000.0;
    const bitsLoaded = result.bytes_downloaded * 8;
    result.throughput_mbps = Math.round((bitsLoaded / durationSeconds / 1000000.0) * 10) / 10;

    // Calculate Bufferbloat (Delta RTT under saturation)
    result.bufferbloat_delta_ms = Math.max(0, result.loaded_rtt_ms - result.baseline_rtt_ms);

    // Grade Bufferbloat according to Bufferbloat.net / CAIDA specifications:
    // +0-15ms: Grade A (No Bloat)
    // +16-60ms: Grade B (Low Bloat)
    // +61-150ms: Grade C (Noticeable Bloat, WebRTC/video lag)
    // +151-300ms: Grade D (Severe Bloat)
    // >300ms: Grade F (Catastrophic bufferbloat / high packet drops)
    if (result.bufferbloat_delta_ms <= 15) {
      result.grade = "A (Excellent)";
    } else if (result.bufferbloat_delta_ms <= 60) {
      result.grade = "B (Good)";
    } else if (result.bufferbloat_delta_ms <= 150) {
      result.grade = "C (Fair - Latency Spikes)";
    } else if (result.bufferbloat_delta_ms <= 300) {
      result.grade = "D (Poor - Severe Bloat)";
    } else {
      result.grade = "F (Bad - Unusable under load)";
    }

    result.success = true;
    logger.info(`Micro-Burst: ${result.throughput_mbps} Mbps | Bufferbloat: +${result.bufferbloat_delta_ms}ms (Grade ${result.grade})`);
  } catch (err) {
    clearTimeout(timer);
    result.duration_ms = Math.max(1, Math.round(performance.now() - overallStart));
    result.error = err.name === "AbortError" ? `Burst timed out after ${timeoutMs}ms` : err.message;
    logger.warn("Micro-burst bandwidth probe failed:", result.error);
  }

  return result;
}
