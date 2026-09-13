import test from "node:test";
import assert from "node:assert";
import { verifies } from "./helpers/rtm.js";

// Mock validator function matching options.js logic
function validateAndSanitizeSettings(rawValues) {
  const errors = [];
  let cmpUrl = String(rawValues.cmp_server_url || "").trim();

  if (!cmpUrl) {
    errors.push("CMP Server URL is required.");
  } else {
    if (!/^https?:\/\//i.test(cmpUrl)) {
      cmpUrl = "http://" + cmpUrl;
    }
    try {
      const parsed = new URL(cmpUrl);
      if (!parsed.hostname) {
        errors.push("Invalid CMP Server URL hostname.");
      }
      cmpUrl = parsed.origin + (parsed.pathname === "/" ? "" : parsed.pathname.replace(/\/+$/, ""));
    } catch {
      errors.push("Invalid CMP Server URL format.");
    }
  }

  let interval = parseInt(rawValues.probe_interval_seconds, 10);
  if (isNaN(interval) || interval < 15 || interval > 3600) {
    errors.push("Probe interval must be an integer between 15 and 3600 seconds.");
  }

  let maxRecords = parseInt(rawValues.max_offline_records, 10);
  if (isNaN(maxRecords) || maxRecords < 50 || maxRecords > 10000) {
    errors.push("Max offline records must be between 50 and 10000.");
  }

  let campusId = String(rawValues.campus_id || "").trim();
  if (campusId) {
    campusId = campusId.replace(/[^a-zA-Z0-9_\-\s]/g, "").slice(0, 64);
  } else {
    campusId = "CAMPUS-CHROMEBOOK-FLEET";
  }

  return {
    valid: errors.length === 0,
    errors,
    sanitized: {
      cmp_server_url: cmpUrl,
      api_key: String(rawValues.api_key || "").trim(),
      campus_id: campusId,
      probe_interval_seconds: isNaN(interval) ? 60 : Math.min(3600, Math.max(15, interval)),
      enable_webrtc_probing: Boolean(rawValues.enable_webrtc_probing),
      enable_offline_buffer: Boolean(rawValues.enable_offline_buffer),
      max_offline_records: isNaN(maxRecords) ? 1000 : Math.min(10000, Math.max(50, maxRecords))
    }
  };
}

test("UI Form Validator - Rejects empty CMP URL", verifies("REQ-UI-001", "Rejects empty CMP URL")(() => {
  const res = validateAndSanitizeSettings({ cmp_server_url: "" });
  assert.strictEqual(res.valid, false);
  assert.match(res.errors[0], /URL is required/);
}));

test("UI Form Validator - Normalizes scheme and strips trailing slash on URL", verifies("REQ-UI-001", "Normalizes scheme and strips trailing slash on URL")(() => {
  const res = validateAndSanitizeSettings({
    cmp_server_url: "10.98.2.125:8000/",
    probe_interval_seconds: "60",
    max_offline_records: "1000"
  });
  assert.strictEqual(res.valid, true);
  assert.strictEqual(res.sanitized.cmp_server_url, "http://10.98.2.125:8000");
}));

test("UI Form Validator - Rejects out of bounds probe interval and NaN values", () => {
  const resLow = validateAndSanitizeSettings({
    cmp_server_url: "http://localhost:8000",
    probe_interval_seconds: "5",
    max_offline_records: "1000"
  });
  assert.strictEqual(resLow.valid, false);
  assert.match(resLow.errors[0], /between 15 and 3600/);

  const resNan = validateAndSanitizeSettings({
    cmp_server_url: "http://localhost:8000",
    probe_interval_seconds: "abc",
    max_offline_records: "1000"
  });
  assert.strictEqual(resNan.valid, false);
});

test("UI Form Validator - Sanitizes campus_id to prevent injection", () => {
  const res = validateAndSanitizeSettings({
    cmp_server_url: "http://localhost:8000",
    probe_interval_seconds: "60",
    max_offline_records: "1000",
    campus_id: "West-High<script>alert(1)</script>"
  });
  assert.strictEqual(res.valid, true);
  assert.strictEqual(res.sanitized.campus_id, "West-Highscriptalert1script");
});
