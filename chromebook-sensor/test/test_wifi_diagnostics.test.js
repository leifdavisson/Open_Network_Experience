import test from "node:test";
import assert from "node:assert";
import { checkCaptivePortal } from "../src/probes/captive_portal.js";
import { WifiHealthAnalyzer } from "../src/probes/wifi_health_analyzer.js";
import { verifies } from "./helpers/rtm.js";

test("Captive Portal Probe - Identifies genuine HTTP 204 as open internet", verifies("REQ-PRB-001", "Identifies genuine HTTP 204 as open internet")(async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url) => ({
    status: 204,
    url
  });

  try {
    const result = await checkCaptivePortal("http://connectivitycheck.gstatic.com/generate_204");
    assert.strictEqual(result.is_captive_portal, false);
    assert.strictEqual(result.authenticated, true);
    assert.strictEqual(result.status_code, 204);
  } finally {
    globalThis.fetch = originalFetch;
  }
}));

test("Captive Portal Probe - Identifies HTTP 302 redirect / HTTP 200 splash page as captive portal", verifies("REQ-PRB-001", "Identifies HTTP 302 redirect / HTTP 200 splash page as captive portal")(async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url) => ({
    status: 200,
    url: "https://wifi-login.district.org/guest/s/default/"
  });

  try {
    const result = await checkCaptivePortal("http://connectivitycheck.gstatic.com/generate_204");
    assert.strictEqual(result.is_captive_portal, true);
    assert.strictEqual(result.authenticated, false);
    assert.strictEqual(result.status_code, 200);
    assert.strictEqual(result.redirect_url, "https://wifi-login.district.org/guest/s/default/");
  } finally {
    globalThis.fetch = originalFetch;
  }
}));

test("Wi-Fi Health Analyzer - Evaluates signal classification correctly", verifies("REQ-PRB-002", "Evaluates signal classification correctly")(() => {
  const analyzer = new WifiHealthAnalyzer();

  const excellent = analyzer.analyze({ connected: true, rssi_dbm: -55, band: "5GHz" });
  assert.strictEqual(excellent.signal_health, "EXCELLENT");
  assert.strictEqual(excellent.is_sticky_client, false);

  const good = analyzer.analyze({ connected: true, rssi_dbm: -65, band: "5GHz" });
  assert.strictEqual(good.signal_health, "GOOD");

  const fair = analyzer.analyze({ connected: true, rssi_dbm: -73, band: "5GHz" });
  assert.strictEqual(fair.signal_health, "FAIR");

  const poor = analyzer.analyze({ connected: true, rssi_dbm: -80, band: "5GHz" });
  assert.strictEqual(poor.signal_health, "POOR");
  assert.strictEqual(poor.is_sticky_client, true);
}));

test("Wi-Fi Health Analyzer - Detects Sticky Client on 2.4 GHz", verifies("REQ-PRB-002", "Detects Sticky Client on 2.4 GHz")(() => {
  const analyzer = new WifiHealthAnalyzer();

  const sticky = analyzer.analyze({
    connected: true,
    rssi_dbm: -74,
    band: "2.4GHz",
    frequency_mhz: 2437
  });

  assert.strictEqual(sticky.is_sticky_client, true);
  assert.strictEqual(sticky.is_suboptimal_band, true);
  assert.match(sticky.recommendation, /band-steering/);
}));

test("Wi-Fi Health Analyzer - Detects AP Flapping / Thrashing", verifies("REQ-PRB-002", "Detects AP Flapping / Thrashing")(() => {
  const analyzer = new WifiHealthAnalyzer();
  const now = Date.now();

  // Rapidly flip between two AP BSSIDs in the last 30 seconds
  analyzer.recordTransition("00:11:22:33:44:01", "District-Staff", now - 25000);
  analyzer.recordTransition("00:11:22:33:44:02", "District-Staff", now - 18000);
  analyzer.recordTransition("00:11:22:33:44:01", "District-Staff", now - 10000);
  analyzer.recordTransition("00:11:22:33:44:02", "District-Staff", now - 2000);

  const report = analyzer.analyze({ connected: true, rssi_dbm: -64, band: "5GHz" });
  assert.strictEqual(report.is_flapping, true);
  assert.strictEqual(report.roam_transitions_last_min, 4);
  assert.strictEqual(report.recent_flaps.length, 2);
  assert.match(report.recommendation, /AP Flapping detected/);
}));
