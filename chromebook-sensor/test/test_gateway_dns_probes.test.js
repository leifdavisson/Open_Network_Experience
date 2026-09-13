import test from "node:test";
import assert from "node:assert";
import { deriveGatewayIp, probeGatewayReachability } from "../src/probes/gateway_probe.js";
import { resolveDoH, resolveNativeLocalDns, runDualStackDnsBenchmark } from "../src/probes/dual_stack_dns.js";
import { verifies } from "./helpers/rtm.js";

test("Default Gateway Probe - Derives gateway IP correctly from IPv4 address", verifies("REQ-PRB-003", "Derives gateway IP correctly from IPv4 address")(() => {
  assert.strictEqual(deriveGatewayIp("10.200.4.155"), "10.200.4.1");
  assert.strictEqual(deriveGatewayIp("192.168.1.50"), "192.168.1.1");
  assert.strictEqual(deriveGatewayIp("172.16.20.99"), "172.16.20.1");
  assert.strictEqual(deriveGatewayIp("invalid-ip"), null);
  assert.strictEqual(deriveGatewayIp(null), null);
}));

test("Default Gateway Probe - Handles reachable local gateway successfully", verifies("REQ-PRB-003", "Handles reachable local gateway successfully")(async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => ({
    ok: true,
    status: 200
  });

  try {
    const res = await probeGatewayReachability("10.200.4.1", 1000);
    assert.strictEqual(res.reachable, true);
    assert.strictEqual(res.gateway_ip, "10.200.4.1");
    assert.strictEqual(res.status, "REACHABLE");
    assert.ok(typeof res.rtt_ms === "number");
  } finally {
    globalThis.fetch = originalFetch;
  }
}));

test("Default Gateway Probe - Gracefully reports unreachable gateway on timeout", verifies("REQ-PRB-003", "Gracefully reports unreachable gateway on timeout")(async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => {
    const err = new Error("The operation was aborted");
    err.name = "AbortError";
    throw err;
  };

  try {
    const res = await probeGatewayReachability("10.200.4.1", 100);
    assert.strictEqual(res.reachable, false);
    assert.strictEqual(res.status, "TIMEOUT");
    assert.match(res.error, /timeout/);
  } finally {
    globalThis.fetch = originalFetch;
  }
}));

test("Dual-Stack DNS Benchmark - Resolves DoH successfully", verifies("REQ-PRB-004", "Resolves DoH successfully")(async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => ({
    ok: true,
    status: 200,
    json: async () => ({
      Status: 0,
      Answer: [
        { name: "google.com", type: 1, data: "142.250.190.46" },
        { name: "google.com", type: 1, data: "142.250.190.78" }
      ]
    })
  });

  try {
    const res = await resolveDoH("google.com");
    assert.strictEqual(res.success, true);
    assert.strictEqual(res.status, "NOERROR");
    assert.strictEqual(res.ips.length, 2);
    assert.strictEqual(res.ips[0], "142.250.190.46");
  } finally {
    globalThis.fetch = originalFetch;
  }
}));

test("Dual-Stack DNS Benchmark - Resolves Local DNS successfully", verifies("REQ-PRB-004", "Resolves Local DNS successfully")(async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => ({
    ok: true,
    status: 200
  });

  try {
    const res = await resolveNativeLocalDns("classroom.google.com");
    assert.strictEqual(res.success, true);
    assert.strictEqual(res.status, "NOERROR");
    assert.strictEqual(res.provider, "Local/DHCP DNS");
  } finally {
    globalThis.fetch = originalFetch;
  }
}));

test("Dual-Stack DNS Benchmark - Evaluates dual-stack health and flags local DNS timeout", verifies("REQ-PRB-004", "Evaluates dual-stack health and flags local DNS timeout")(async () => {
  const originalFetch = globalThis.fetch;
  // Mock: DoH succeeds, but local DNS throws AbortError
  globalThis.fetch = async (url) => {
    if (url.includes("dns.google") || url.includes("cloudflare-dns")) {
      return {
        ok: true,
        status: 200,
        json: async () => ({ Status: 0, Answer: [{ type: 1, data: "1.1.1.1" }] })
      };
    }
    const err = new Error("Local DNS timeout");
    err.name = "AbortError";
    throw err;
  };

  try {
    const benchmark = await runDualStackDnsBenchmark("classroom.google.com");
    assert.strictEqual(benchmark.dns_health, "LOCAL_DNS_FAIL");
    assert.match(benchmark.recommendation, /Local LAN\/DHCP DNS is timing out/);
    assert.strictEqual(benchmark.doh_google.success, true);
    assert.strictEqual(benchmark.local_dns.success, false);
  } finally {
    globalThis.fetch = originalFetch;
  }
}));
