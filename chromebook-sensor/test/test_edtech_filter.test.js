/**
 * Open Network Experience (ONE) - Chromebook Sensor
 * Unit tests for EdTech Filter & Student Safety Agent Diagnostic Probe
 * Verifies REQ-PRB-006
 * License: GNU AGPLv3
 */

import test from "node:test";
import assert from "node:assert";
import {
  probeFilterEndpoint,
  runEdtechFilterSuite,
  verifyClassroomWhitelists,
  probeSslInterceptionHealth,
  KNOWN_EDTECH_AGENTS
} from "../src/probes/edtech_filter_probe.js";
import { verifies } from "./helpers/rtm.js";

test("EdTech Filter Probe - Probes individual filter cloud endpoint successfully", verifies("REQ-PRB-006", "Probes individual filter cloud endpoint successfully")(async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, opts) => {
    assert.strictEqual(opts.method, "HEAD");
    return { ok: true, status: 200 };
  };

  try {
    const res = await probeFilterEndpoint("https://www.securly.com/generate_204", 2000);
    assert.strictEqual(res.reachable, true);
    assert.strictEqual(res.status, 200);
    assert.strictEqual(res.error, null);
    assert.ok(typeof res.rtt_ms === "number");
  } finally {
    globalThis.fetch = originalFetch;
  }
}));

test("EdTech Filter Probe - Handles probe timeout gracefully", verifies("REQ-PRB-006", "Handles probe timeout gracefully")(async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => {
    const err = new Error("The operation was aborted");
    err.name = "AbortError";
    throw err;
  };

  try {
    const res = await probeFilterEndpoint("https://service.blocksi.net", 100);
    assert.strictEqual(res.reachable, false);
    assert.strictEqual(res.status, null);
    assert.match(res.error, /Timeout/);
  } finally {
    globalThis.fetch = originalFetch;
  }
}));

test("EdTech Filter Suite - Evaluates healthy filter cloud latency and detects fastest provider", verifies("REQ-PRB-006", "Evaluates healthy filter cloud latency and detects fastest provider")(async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url) => {
    // If probing chrome-extension internal assets in Node environment, reject
    if (url.startsWith("chrome-extension://")) {
      throw new Error("Chrome extension protocol unavailable in test");
    }
    // Simulate low-latency filter response
    return { ok: true, status: 200 };
  };

  try {
    const result = await runEdtechFilterSuite(25, 2000);
    assert.strictEqual(result.collision_detected, false);
    assert.strictEqual(result.health_status, "HEALTHY");
    assert.ok(result.fastest_provider !== null);
    assert.ok(result.filter_endpoints.securly.reachable);
    assert.ok(result.filter_endpoints.lightspeed.reachable);
    assert.ok(result.filter_endpoints.blocksi.reachable);
    assert.ok(result.filter_endpoints.goguardian.reachable);
  } finally {
    globalThis.fetch = originalFetch;
  }
}));

test("EdTech Filter Suite - Flags multi-agent collision when multiple filters are detected", verifies("REQ-PRB-006", "Flags multi-agent collision when multiple filters are detected")(async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url) => {
    // Simulate detecting Securly AND Lightspeed manifests in browser
    if (url.includes("jhegagklnjemlaccpdjdiogomgeapbcl") || url.includes("adkcpkpaleahmbngficnbneflipohmnj")) {
      return { ok: true, status: 200, type: "basic" };
    }
    if (url.startsWith("chrome-extension://")) {
      throw new Error("Not installed");
    }
    return { ok: true, status: 200 };
  };

  try {
    const result = await runEdtechFilterSuite(20, 2000);
    assert.strictEqual(result.collision_detected, true);
    assert.strictEqual(result.health_status, "COLLISION_DETECTED");
    assert.ok(result.detected_agents.includes("Securly Filter"));
    assert.ok(result.detected_agents.includes("Lightspeed Systems Relay"));
    assert.match(result.recommendation, /Multiple filtering agents detected/);
  } finally {
    globalThis.fetch = originalFetch;
  }
}));

test("EdTech Filter Suite - Detects high filtering proxy overhead latency degradation", verifies("REQ-PRB-006", "Detects high filtering proxy overhead latency degradation")(async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url) => {
    if (url.startsWith("chrome-extension://")) {
      throw new Error("Not installed");
    }
    // Simulate 160ms filter proxy latency
    await new Promise((r) => setTimeout(r, 160));
    return { ok: true, status: 200 };
  };

  try {
    const result = await runEdtechFilterSuite(15, 2000);
    assert.strictEqual(result.collision_detected, false);
    assert.strictEqual(result.health_status, "DEGRADED_LATENCY");
    assert.ok(result.filter_overhead_ms > 120);
    assert.match(result.recommendation, /High filtering proxy latency overhead/);
  } finally {
    globalThis.fetch = originalFetch;
  }
}));

test("EdTech Filter Suite - Flags CLOUD_UNREACHABLE when all filter endpoints fail", verifies("REQ-PRB-006", "Flags CLOUD_UNREACHABLE when all filter endpoints fail")(async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => {
    throw new Error("Network unreachable");
  };

  try {
    const result = await runEdtechFilterSuite(20, 1000);
    assert.strictEqual(result.health_status, "CLOUD_UNREACHABLE");
    assert.match(result.recommendation, /filtering cloud endpoints are unreachable/);
  } finally {
    globalThis.fetch = originalFetch;
  }
}));

test("Classroom Safe-List Probe - All educational endpoints reachable", verifies("REQ-PRB-007", "All educational endpoints reachable")(async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, opts) => {
    assert.strictEqual(opts.method, "HEAD");
    return { ok: true, status: 200 };
  };

  try {
    const res = await verifyClassroomWhitelists();
    assert.strictEqual(res.all_passed, true);
    assert.strictEqual(res.blocked_count, 0);
    assert.strictEqual(res.services.length, 4);
    assert.ok(res.services.every(s => s.reachable));
  } finally {
    globalThis.fetch = originalFetch;
  }
}));

test("Classroom Safe-List Probe - Detects blocked or timing out educational tools", verifies("REQ-PRB-007", "Detects blocked or timing out educational tools")(async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url) => {
    if (url.includes("canvas.instructure.com")) {
      const err = new Error("The operation was aborted");
      err.name = "AbortError";
      throw err;
    }
    return { ok: true, status: 200 };
  };

  try {
    const res = await verifyClassroomWhitelists();
    assert.strictEqual(res.all_passed, false);
    assert.strictEqual(res.blocked_count, 1);
    const canvas = res.services.find(s => s.name === "Canvas LMS");
    assert.strictEqual(canvas.reachable, false);
    assert.match(canvas.error, /Timeout/);
  } finally {
    globalThis.fetch = originalFetch;
  }
}));

test("SSL Interception Health - Detects valid TLS handshake and flags MITM cert failure", verifies("REQ-PRB-007", "Detects valid TLS handshake and flags MITM cert failure")(async () => {
  const originalFetch = globalThis.fetch;

  // 1. Valid handshake
  globalThis.fetch = async () => ({ ok: true, status: 204 });
  let sslRes = await probeSslInterceptionHealth();
  assert.strictEqual(sslRes.ssl_valid, true);
  assert.strictEqual(sslRes.error, null);

  // 2. Failed MITM handshake (e.g. invalid local root CA)
  globalThis.fetch = async () => {
    throw new TypeError("Failed to fetch (ERR_CERT_AUTHORITY_INVALID)");
  };
  sslRes = await probeSslInterceptionHealth();
  assert.strictEqual(sslRes.ssl_valid, false);
  assert.match(sslRes.error, /ERR_CERT_AUTHORITY_INVALID/);

  globalThis.fetch = originalFetch;
}));

test("EdTech Filter Suite - Flags CLASSROOM_BLOCKED and SSL_INSPECTION_FAILED statuses", verifies("REQ-PRB-007", "Flags CLASSROOM_BLOCKED and SSL_INSPECTION_FAILED statuses")(async () => {
  const originalFetch = globalThis.fetch;

  // Test SSL Failure in Full Suite
  globalThis.fetch = async (url) => {
    if (url.startsWith("chrome-extension://")) throw new Error("Not installed");
    if (url.includes("google.com/generate_204")) {
      throw new Error("ERR_CERT_COMMON_NAME_INVALID");
    }
    return { ok: true, status: 200 };
  };

  try {
    const res = await runEdtechFilterSuite(20, 2000);
    assert.strictEqual(res.health_status, "SSL_INSPECTION_FAILED");
    assert.match(res.recommendation, /SSL inspection handshake failed/);
  } finally {
    globalThis.fetch = originalFetch;
  }
}));

