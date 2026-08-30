/**
 * Open Network Experience (ONE) - Chromebook Sensor
 * ChromeOS Dynamic Enterprise & Hardware Telemetry Engine
 * Collects enterprise attributes (Serial Number, Asset ID, Room Location),
 * dynamic CPU/Memory/Storage/Battery metrics, and network interface details.
 * License: GNU AGPLv3
 */

import { logger } from "../utils/logger.js";

// Cache for CPU utilization delta computation
let previousCpuInfo = null;

/**
 * Calculates CPU utilization percentage between consecutive samples.
 */
function calculateCpuUsage(currentProcessors, previousProcessors) {
  if (!currentProcessors || !previousProcessors || currentProcessors.length !== previousProcessors.length) {
    return 0;
  }

  let totalUserDelta = 0;
  let totalKernelDelta = 0;
  let totalIdleDelta = 0;
  let totalDelta = 0;

  for (let i = 0; i < currentProcessors.length; i++) {
    const cur = currentProcessors[i].usage;
    const prev = previousProcessors[i].usage;

    const user = cur.user - prev.user;
    const kernel = cur.kernel - prev.kernel;
    const idle = cur.idle - prev.idle;
    const total = cur.total - prev.total;

    totalUserDelta += user;
    totalKernelDelta += kernel;
    totalIdleDelta += idle;
    totalDelta += total;
  }

  if (totalDelta <= 0) return 0;
  const activeDelta = totalUserDelta + totalKernelDelta;
  const usagePercent = Math.min(100, Math.max(0, (activeDelta / totalDelta) * 100));
  return Math.round(usagePercent * 10) / 10;
}

/**
 * Promisify Chrome API callbacks with runtime.lastError safety.
 */
function callChromeApi(fn) {
  return new Promise((resolve) => {
    try {
      fn((val) => {
        if (typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.lastError) {
          resolve(null);
        } else {
          resolve(val || null);
        }
      });
    } catch (e) {
      resolve(null);
    }
  });
}

/**
 * Dynamically queries ChromeOS enterprise device attributes on every cycle.
 */
export async function getEnterpriseDeviceAttributes() {
  const result = {
    deviceId: null,
    serialNumber: null,
    assetId: null,
    annotatedLocation: null,
    annotatedUser: null,
    hostname: null,
    macAddress: null,
    ipv4Address: null,
    isEnterpriseManaged: false
  };

  if (typeof chrome === "undefined") {
    return result;
  }

  // 1. chrome.enterprise.deviceAttributes
  if (chrome.enterprise && chrome.enterprise.deviceAttributes) {
    const attrs = chrome.enterprise.deviceAttributes;
    try {
      const [deviceId, serialNumber, assetId, location, user, hostname] = await Promise.all([
        attrs.getDirectoryDeviceId ? callChromeApi(attrs.getDirectoryDeviceId) : Promise.resolve(null),
        attrs.getDeviceSerialNumber ? callChromeApi(attrs.getDeviceSerialNumber) : Promise.resolve(null),
        attrs.getDeviceAssetId ? callChromeApi(attrs.getDeviceAssetId) : Promise.resolve(null),
        attrs.getDeviceAnnotatedLocation ? callChromeApi(attrs.getDeviceAnnotatedLocation) : Promise.resolve(null),
        attrs.getDeviceAnnotatedUser ? callChromeApi(attrs.getDeviceAnnotatedUser) : Promise.resolve(null),
        attrs.getDeviceHostname ? callChromeApi(attrs.getDeviceHostname) : Promise.resolve(null)
      ]);

      result.deviceId = deviceId;
      result.serialNumber = serialNumber;
      result.assetId = assetId;
      result.annotatedLocation = location;
      result.annotatedUser = user;
      result.hostname = hostname;
      result.isEnterpriseManaged = Boolean(deviceId || serialNumber || assetId);
    } catch (err) {
      logger.debug("Error reading enterprise device attributes:", err);
    }
  }

  // 2. chrome.enterprise.networkingAttributes (if present on ChromeOS)
  if (chrome.enterprise && chrome.enterprise.networkingAttributes) {
    try {
      const netAttrs = await callChromeApi(chrome.enterprise.networkingAttributes.getNetworkDetails);
      if (netAttrs) {
        result.macAddress = netAttrs.macAddress || null;
        result.ipv4Address = netAttrs.ipv4 || null;
      }
    } catch (e) {
      logger.debug("Error reading enterprise networking attributes:", e);
    }
  }

  return result;
}

/**
 * Dynamically queries system hardware, CPU, Memory, Storage, Display, and Battery status.
 */
export async function getSystemHardwareTelemetry() {
  const telemetry = {
    cpu: {
      model_name: "Unknown CPU",
      arch: "x86_64",
      num_processors: 2,
      usage_percent: 0.0,
      processors: []
    },
    memory: {
      capacity_bytes: 0,
      available_bytes: 0,
      used_bytes: 0,
      usage_percent: 0.0
    },
    storage: {
      units: [],
      total_capacity_bytes: 0
    },
    display: {
      displays: [],
      primary_resolution: "Unknown"
    },
    battery: {
      has_battery: false,
      charging: true,
      level_percent: 100,
      discharging_time_seconds: null
    },
    os_info: {
      platform: typeof navigator !== "undefined" ? navigator.platform : "CrOS",
      user_agent: typeof navigator !== "undefined" ? navigator.userAgent : "ChromeOS",
      online: typeof navigator !== "undefined" ? navigator.onLine : true
    },
    interfaces: []
  };

  if (typeof chrome === "undefined" || !chrome.system) {
    return telemetry;
  }

  // 1. Dynamic CPU Telemetry
  if (chrome.system.cpu) {
    try {
      const cpuInfo = await callChromeApi(chrome.system.cpu.getInfo);
      if (cpuInfo) {
        telemetry.cpu.model_name = cpuInfo.modelName || "ChromeOS CPU";
        telemetry.cpu.arch = cpuInfo.archName || "x86_64";
        telemetry.cpu.num_processors = cpuInfo.numOfProcessors || 2;
        telemetry.cpu.processors = cpuInfo.processors || [];

        if (previousCpuInfo && previousCpuInfo.processors && cpuInfo.processors) {
          telemetry.cpu.usage_percent = calculateCpuUsage(cpuInfo.processors, previousCpuInfo.processors);
        }
        previousCpuInfo = cpuInfo;
      }
    } catch (e) {
      logger.debug("CPU info error:", e);
    }
  }

  // 2. Dynamic Memory Telemetry
  if (chrome.system.memory) {
    try {
      const memInfo = await callChromeApi(chrome.system.memory.getInfo);
      if (memInfo) {
        telemetry.memory.capacity_bytes = memInfo.capacity || 0;
        telemetry.memory.available_bytes = memInfo.availableCapacity || 0;
        telemetry.memory.used_bytes = Math.max(0, memInfo.capacity - memInfo.availableCapacity);
        if (memInfo.capacity > 0) {
          telemetry.memory.usage_percent = Math.round(((telemetry.memory.used_bytes / memInfo.capacity) * 100) * 10) / 10;
        }
      }
    } catch (e) {
      logger.debug("Memory info error:", e);
    }
  }

  // 3. Dynamic Storage Telemetry
  if (chrome.system.storage) {
    try {
      const storageUnits = await callChromeApi(chrome.system.storage.getInfo);
      if (storageUnits && Array.isArray(storageUnits)) {
        telemetry.storage.units = storageUnits.map((u) => ({
          id: u.id,
          name: u.name,
          type: u.type,
          capacity_bytes: u.capacity
        }));
        telemetry.storage.total_capacity_bytes = storageUnits.reduce((acc, u) => acc + (u.capacity || 0), 0);
      }
    } catch (e) {
      logger.debug("Storage info error:", e);
    }
  }

  // 4. Dynamic Display Telemetry
  if (chrome.system.display) {
    try {
      const displays = await callChromeApi(chrome.system.display.getInfo);
      if (displays && Array.isArray(displays)) {
        telemetry.display.displays = displays.map((d) => ({
          id: d.id,
          name: d.name,
          is_primary: d.isPrimary,
          is_internal: d.isInternal,
          bounds: d.bounds
        }));
        const primary = displays.find((d) => d.isPrimary) || displays[0];
        if (primary && primary.bounds) {
          telemetry.display.primary_resolution = `${primary.bounds.width}x${primary.bounds.height}`;
        }
      }
    } catch (e) {
      logger.debug("Display info error:", e);
    }
  }

  // 5. Dynamic Battery Telemetry (Standard Web API)
  if (typeof navigator !== "undefined" && typeof navigator.getBattery === "function") {
    try {
      const battery = await navigator.getBattery();
      if (battery) {
        telemetry.battery.has_battery = true;
        telemetry.battery.charging = battery.charging;
        telemetry.battery.level_percent = Math.round(battery.level * 100);
        telemetry.battery.discharging_time_seconds = isFinite(battery.dischargingTime) ? battery.dischargingTime : null;
      }
    } catch (e) {
      logger.debug("Battery API error:", e);
    }
  }

  // 6. Network Interfaces
  if (chrome.system.network) {
    try {
      const ifaces = await callChromeApi(chrome.system.network.getNetworkInterfaces);
      if (ifaces && Array.isArray(ifaces)) {
        telemetry.interfaces = ifaces.map((i) => ({
          name: i.name,
          address: i.address,
          prefix_length: i.prefixLength
        }));
      }
    } catch (e) {
      logger.debug("Network interface info error:", e);
    }
  }

  return telemetry;
}

/**
 * Deterministically resolves sensor UUID, serial number, and hardware identity.
 */
export async function resolveSensorIdentity() {
  const ent = await getEnterpriseDeviceAttributes();

  if (ent.serialNumber) {
    return {
      sensor_id: `chromebook-sn-${ent.serialNumber.toLowerCase()}`,
      serial_number: ent.serialNumber,
      asset_id: ent.assetId || "UNTAGGED-ASSET",
      location: ent.annotatedLocation || "District Chromebook Fleet",
      annotated_user: ent.annotatedUser || null,
      directory_device_id: ent.deviceId || null,
      hostname: ent.hostname || `cb-${ent.serialNumber.slice(-6).toLowerCase()}`,
      mac_address: ent.macAddress || null,
      is_managed: ent.isEnterpriseManaged
    };
  }

  // Fallback to locally stored UUID if unmanaged / developer device
  let storedUuid = null;
  if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
    storedUuid = await new Promise((resolve) => {
      chrome.storage.local.get(["device_sensor_uuid"], (items) => {
        resolve(items ? items.device_sensor_uuid : null);
      });
    });

    if (!storedUuid) {
      storedUuid = `chromebook-dev-${crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2, 11)}`;
      chrome.storage.local.set({ device_sensor_uuid: storedUuid });
    }
  } else {
    storedUuid = `chromebook-node-${Math.random().toString(36).slice(2, 11)}`;
  }

  return {
    sensor_id: storedUuid,
    serial_number: "DEV-SIM-SERIAL",
    asset_id: "DEV-SIM-ASSET",
    location: "Unmanaged ChromeOS Device",
    annotated_user: null,
    directory_device_id: null,
    hostname: "chromebook-agent",
    mac_address: null,
    is_managed: false
  };
}
