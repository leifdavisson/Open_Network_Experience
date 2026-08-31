import test from "node:test";
import assert from "node:assert";
import { setupChromeMock } from "./mocks/chrome_mock.js";
import {
  getEnterpriseDeviceAttributes,
  getSystemHardwareTelemetry,
  resolveSensorIdentity
} from "../src/background/device_telemetry.js";
import {
  getActiveWifiTelemetry,
  frequencyToChannel,
  percentToRssiDbm
} from "../src/background/network_private.js";

test("Device Telemetry - Resolves enterprise device attributes dynamically", async () => {
  setupChromeMock();

  const attrs = await getEnterpriseDeviceAttributes();
  assert.strictEqual(attrs.isEnterpriseManaged, true);
  assert.strictEqual(attrs.serialNumber, "5CD9440ABC");
  assert.strictEqual(attrs.assetId, "ASSET-CB-90210");
  assert.strictEqual(attrs.annotatedLocation, "West High Room 204");
  assert.strictEqual(attrs.annotatedUser, "student.jdoe@example.edu");
  assert.strictEqual(attrs.hostname, "cb-student-204-01");
  assert.strictEqual(attrs.macAddress, "00:1A:2B:3C:4D:5E");
  assert.strictEqual(attrs.ipv4Address, "10.200.4.155");
});

test("Device Telemetry - Hardware CPU, Memory, Storage, Display & Battery inspection", async () => {
  setupChromeMock();

  const hw = await getSystemHardwareTelemetry();
  // CPU
  assert.ok(hw.cpu);
  assert.strictEqual(hw.cpu.arch, "x86_64");
  assert.strictEqual(hw.cpu.model_name, "Intel(R) Celeron(R) N4500");
  assert.strictEqual(hw.cpu.num_processors, 2);

  // Memory
  assert.ok(hw.memory);
  assert.strictEqual(hw.memory.capacity_bytes, 8589934592);
  assert.strictEqual(hw.memory.available_bytes, 4294967296);
  assert.strictEqual(hw.memory.used_bytes, 4294967296);
  assert.strictEqual(hw.memory.usage_percent, 50);

  // Storage
  assert.ok(hw.storage);
  assert.strictEqual(hw.storage.total_capacity_bytes, 68719476736);
  assert.strictEqual(hw.storage.units.length, 1);

  // Display
  assert.ok(hw.display);
  assert.strictEqual(hw.display.primary_resolution, "1366x768");

  // Battery
  assert.ok(hw.battery);
  assert.strictEqual(hw.battery.has_battery, true);
  assert.strictEqual(hw.battery.charging, true);
  assert.strictEqual(hw.battery.level_percent, 94);

  // Interfaces
  assert.strictEqual(hw.interfaces.length, 1);
  assert.strictEqual(hw.interfaces[0].address, "10.200.4.155");
});

test("Device Telemetry - Deterministic identity resolution", async () => {
  setupChromeMock();

  const ident = await resolveSensorIdentity();
  assert.strictEqual(ident.sensor_id, "chromebook-sn-5cd9440abc");
  assert.strictEqual(ident.serial_number, "5CD9440ABC");
  assert.strictEqual(ident.asset_id, "ASSET-CB-90210");
  assert.strictEqual(ident.location, "West High Room 204");
  assert.strictEqual(ident.annotated_user, "student.jdoe@example.edu");
  assert.strictEqual(ident.directory_device_id, "dir-dev-12345");
  assert.strictEqual(ident.mac_address, "00:1A:2B:3C:4D:5E");
});

test("Network Telemetry - Wi-Fi RF frequency to channel conversion", () => {
  assert.strictEqual(frequencyToChannel(2412), 1);
  assert.strictEqual(frequencyToChannel(2437), 6);
  assert.strictEqual(frequencyToChannel(2462), 11);
  assert.strictEqual(frequencyToChannel(5180), 36);
  assert.strictEqual(frequencyToChannel(5240), 48);
  assert.strictEqual(frequencyToChannel(5745), 149);
  assert.strictEqual(frequencyToChannel(6125), 35); // 6GHz
});

test("Network Telemetry - Signal percentage to RSSI dBm conversion", () => {
  assert.strictEqual(percentToRssiDbm(100), -50);
  assert.strictEqual(percentToRssiDbm(80), -60);
  assert.strictEqual(percentToRssiDbm(50), -75);
  assert.strictEqual(percentToRssiDbm(0), -100);
});

test("Network Telemetry - getActiveWifiTelemetry retrieves active BSSID & RSSI", async () => {
  setupChromeMock();

  const wifi = await getActiveWifiTelemetry();
  assert.strictEqual(wifi.connected, true);
  assert.strictEqual(wifi.ssid, "District-Secure-WiFi");
  assert.strictEqual(wifi.bssid, "00:1A:2B:3C:4D:5E");
  assert.strictEqual(wifi.rssi_dbm, -58);
  assert.strictEqual(wifi.channel, 48);
  assert.strictEqual(wifi.band, "5GHz");
});
