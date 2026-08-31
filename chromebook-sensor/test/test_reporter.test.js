import test from "node:test";
import assert from "node:assert";
import { setupChromeMock } from "./mocks/chrome_mock.js";
import { buildReportPayload, sendTelemetryReport } from "../src/utils/reporter.js";

test("Reporter - Builds standardized Chromebook Sensor payload with full hardware & serial info", () => {
  setupChromeMock();

  const sensorIdentity = {
    sensor_id: "chromebook-sn-5cd9440abc",
    serial_number: "5CD9440ABC",
    asset_id: "ASSET-CB-90210",
    location: "West High Room 204",
    annotated_user: "student.jdoe@example.edu",
    directory_device_id: "dir-dev-12345",
    hostname: "cb-student-204-01",
    mac_address: "00:1A:2B:3C:4D:5E",
    is_managed: true
  };

  const wifiTelemetry = {
    connected: true,
    ssid: "District-Secure-WiFi",
    bssid: "00:1A:2B:3C:4D:5E",
    rssi_dbm: -58,
    signal_strength_pct: 85,
    frequency_mhz: 5240,
    channel: 48,
    band: "5GHz",
    security: "WPA-Enterprise",
    roamed_recently: false
  };

  const hardwareTelemetry = {
    cpu: { arch: "x86_64", model_name: "Intel(R) Celeron(R) N4500", usage_percent: 18.5 },
    memory: { capacity_bytes: 8589934592, available_bytes: 4294967296, usage_percent: 50.0 },
    storage: { total_capacity_bytes: 68719476736 },
    display: { primary_resolution: "1366x768" },
    battery: { charging: true, level_percent: 94 },
    interfaces: [{ name: "wlan0", address: "10.200.4.155" }]
  };

  const syntheticHttpResults = [
    { name: "Google Classroom", url: "https://classroom.google.com", latency_ms: 45, success: true },
    { name: "CAASPP Testing", url: "https://caaspp.org", latency_ms: 80, success: true }
  ];

  const webrtcResult = {
    success: true,
    rtt_ms: 24,
    jitter_ms: 2,
    packet_loss_percent: 0,
    mos: 4.38,
    mos_grade: "Excellent"
  };

  const payload = buildReportPayload({
    sensorIdentity,
    wifiTelemetry,
    hardwareTelemetry,
    syntheticHttpResults,
    webrtcResult,
    campusId: "CAMPUS-WEST-HIGH"
  });

  assert.strictEqual(payload.sensor_id, "chromebook-sn-5cd9440abc");
  assert.strictEqual(payload.sensor_type, "chromebook");
  assert.strictEqual(payload.os, "ChromeOS");
  assert.strictEqual(payload.campus_id, "CAMPUS-WEST-HIGH");
  assert.strictEqual(payload.device_info.serial_number, "5CD9440ABC");
  assert.strictEqual(payload.device_info.asset_id, "ASSET-CB-90210");
  assert.strictEqual(payload.device_info.annotated_user, "student.jdoe@example.edu");
  assert.strictEqual(payload.device_info.directory_device_id, "dir-dev-12345");
  assert.strictEqual(payload.hardware.cpu.usage_percent, 18.5);
  assert.strictEqual(payload.hardware.battery.level_percent, 94);
  assert.strictEqual(payload.wifi.bssid, "00:1A:2B:3C:4D:5E");
  assert.strictEqual(payload.wifi.rssi_dbm, -58);
  assert.strictEqual(payload.probes.synthetic_http.length, 2);
  assert.strictEqual(payload.probes.webrtc.mos, 4.38);
});

test("Reporter - sendTelemetryReport handles network error gracefully", async () => {
  const origFetch = global.fetch;
  global.fetch = async () => {
    throw new Error("Failed to fetch (offline)");
  };

  try {
    const res = await sendTelemetryReport("http://invalid-cmp-url:8000", "dummy-key", {});
    assert.strictEqual(res.success, false);
    assert.ok(res.error.includes("offline"));
  } finally {
    global.fetch = origFetch;
  }
});
