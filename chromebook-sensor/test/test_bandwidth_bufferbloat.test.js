/**
 * Open Network Experience (ONE) - Chromebook Sensor
 * Unit tests for Micro-Burst Downlink Bandwidth & Bufferbloat Probe
 * Verifies REQ-PRB-005
 * License: GNU AGPLv3
 */

import test from "node:test";
import assert from "node:assert";
import { measureMicroBurstThroughput } from "../src/probes/bandwidth_bufferbloat.js";
import { verifies } from "./helpers/rtm.js";

test("Micro-Burst Bandwidth - Computes downlink throughput and Grade A bufferbloat", verifies("REQ-PRB-005", "Computes downlink throughput and Grade A bufferbloat")(async () => {
  const originalFetch = globalThis.fetch;
  const mockPayload = new Uint8Array(1048576); // 1MB

  globalThis.fetch = async (url, opts) => {
    if (opts && opts.method === "HEAD") {
      return { ok: true, status: 204 };
    }
    return {
      ok: true,
      status: 200,
      arrayBuffer: async () => mockPayload.buffer
    };
  };

  try {
    const result = await measureMicroBurstThroughput("https://mock-speed.cloudflare.com/test", 1048576, 5000);
    assert.strictEqual(result.success, true);
    assert.ok(result.throughput_mbps > 0, "Throughput should be greater than 0 Mbps");
    assert.strictEqual(result.bytes_downloaded, 1048576);
    assert.ok(typeof result.bufferbloat_delta_ms === "number");
    assert.ok(result.grade.startsWith("A") || result.grade.startsWith("B"), `Expected Grade A or B, got ${result.grade}`);
    assert.strictEqual(result.error, null);
  } finally {
    globalThis.fetch = originalFetch;
  }
}));

test("Micro-Burst Bandwidth - Correctly grades high bufferbloat latency spikes (Grade C/D/F)", verifies("REQ-PRB-005", "Correctly grades high bufferbloat latency spikes")(async () => {
  const originalFetch = globalThis.fetch;
  const mockPayload = new Uint8Array(524288); // 512KB

  let headCallCount = 0;
  globalThis.fetch = async (url, opts) => {
    if (opts && opts.method === "HEAD") {
      headCallCount++;
      if (headCallCount > 1) {
        // Simulate severe bufferbloat latency spike under load (+180ms)
        await new Promise((r) => setTimeout(r, 180));
      }
      return { ok: true, status: 204 };
    }
    return {
      ok: true,
      status: 200,
      arrayBuffer: async () => mockPayload.buffer
    };
  };

  try {
    const result = await measureMicroBurstThroughput("https://mock-speed.cloudflare.com/test", 524288, 5000);
    assert.strictEqual(result.success, true);
    assert.ok(result.bufferbloat_delta_ms >= 100, `Expected bufferbloat >= 100ms, got ${result.bufferbloat_delta_ms}`);
    assert.ok(result.grade.startsWith("C") || result.grade.startsWith("D") || result.grade.startsWith("F"), `Expected Grade C, D, or F, got ${result.grade}`);
  } finally {
    globalThis.fetch = originalFetch;
  }
}));

test("Micro-Burst Bandwidth - Gracefully handles download timeout or network failure", verifies("REQ-PRB-005", "Gracefully handles download timeout or network failure")(async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, opts) => {
    if (opts && opts.method === "HEAD") {
      return { ok: true, status: 204 };
    }
    const err = new Error("The operation was aborted");
    err.name = "AbortError";
    throw err;
  };

  try {
    const result = await measureMicroBurstThroughput("https://mock-speed.cloudflare.com/test", 1048576, 100);
    assert.strictEqual(result.success, false);
    assert.strictEqual(result.throughput_mbps, 0);
    assert.match(result.error, /timed out/i);
  } finally {
    globalThis.fetch = originalFetch;
  }
}));
