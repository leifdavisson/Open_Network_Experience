import test from "node:test";
import assert from "node:assert";
import { calculateVoipMos } from "../src/probes/mos_calculator.js";

test("MOS Calculator - Excellent Toll Quality", () => {
  // Low latency (20ms RTT), low jitter (2ms), zero loss
  const res = calculateVoipMos(20, 2, 0);
  assert.ok(res.mos >= 4.3, `Expected MOS >= 4.3, got ${res.mos}`);
  assert.strictEqual(res.qualityGrade, "Excellent");
  assert.ok(res.rFactor > 90);
});

test("MOS Calculator - Good Quality (Standard Classroom Call)", () => {
  // 60ms RTT, 8ms jitter, 0.5% packet loss
  const res = calculateVoipMos(60, 8, 0.005);
  assert.ok(res.mos >= 4.0 && res.mos < 4.4, `Expected Good MOS, got ${res.mos}`);
  assert.strictEqual(res.qualityGrade, "Good");
});

test("MOS Calculator - Fair Quality (Noticeable delay / moderate packet loss)", () => {
  // 180ms RTT, 45ms jitter, 2.5% packet loss
  const res = calculateVoipMos(180, 45, 0.025);
  assert.ok(res.mos >= 3.6 && res.mos < 4.1, `Expected Fair MOS, got ${res.mos}`);
  assert.strictEqual(res.qualityGrade, "Fair");
});

test("MOS Calculator - Poor Quality (High delay & packet loss)", () => {
  // 240ms RTT, 50ms jitter, 4.5% packet loss
  const res = calculateVoipMos(240, 50, 0.045);
  assert.ok(res.mos >= 3.1 && res.mos < 3.6, `Expected Poor MOS, got ${res.mos}`);
  assert.strictEqual(res.qualityGrade, "Poor");
});

test("MOS Calculator - Bad / Unusable Quality (Severe Packet Loss & Outage)", () => {
  // 450ms RTT, 120ms jitter, 20% packet loss
  const res = calculateVoipMos(450, 120, 0.20);
  assert.ok(res.mos < 3.1, `Expected Bad MOS, got ${res.mos}`);
  assert.strictEqual(res.qualityGrade, "Bad");
});

test("MOS Calculator - Edge cases and bounding", () => {
  const zero = calculateVoipMos(0, 0, 0);
  assert.ok(zero.mos <= 4.5);
  assert.ok(zero.mos >= 4.0);

  const extreme = calculateVoipMos(5000, 1000, 1.0);
  assert.strictEqual(extreme.mos, 1.0);
  assert.strictEqual(extreme.rFactor, 0);
  assert.strictEqual(extreme.qualityGrade, "Bad");
});
