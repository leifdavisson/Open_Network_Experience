/**
 * Open Network Experience (ONE) - Chromebook Sensor
 * Test Mock for Chrome Extension and ChromeOS Enterprise APIs
 * License: GNU AGPLv3
 */

export function setupChromeMock(overrides = {}) {
  const managedStore = overrides.managed || {
    cmp_server_url: "https://cmp-test.district.edu:8000",
    api_key: "test-noc-key",
    campus_id: "CAMPUS-NORTH-HIGH",
    probe_interval_seconds: 30
  };

  const localStore = overrides.local || {};

  const globalScope = typeof global !== "undefined" ? global : window;

  if (typeof navigator !== "undefined") {
    try {
      Object.defineProperty(navigator, "getBattery", {
        value: async () => ({
          charging: true,
          level: 0.94,
          dischargingTime: Infinity
        }),
        configurable: true,
        writable: true
      });
    } catch (e) {
      // Ignore if navigator is non-extensible
    }
  }

  globalScope.chrome = {
    runtime: {
      lastError: null,
      getURL: (path) => `chrome-extension://mock-id/${path}`,
      getContexts: async () => overrides.contexts || [],
      sendMessage: (msg, callback) => {
        if (callback) callback({ success: true, data: { mos: 4.38, rtt_ms: 22.5 } });
      },
      onMessage: {
        addListener: () => {}
      },
      onInstalled: {
        addListener: () => {}
      },
      onStartup: {
        addListener: () => {}
      }
    },
    storage: {
      managed: {
        get: (keys, callback) => {
          callback(managedStore);
        }
      },
      local: {
        get: (keys, callback) => {
          if (typeof keys === "string") {
            callback({ [keys]: localStore[keys] });
          } else if (Array.isArray(keys)) {
            const out = {};
            keys.forEach((k) => (out[k] = localStore[k]));
            callback(out);
          } else {
            callback(localStore);
          }
        },
        set: (items, callback) => {
          Object.assign(localStore, items);
          if (callback) callback();
        }
      }
    },
    enterprise: {
      deviceAttributes: {
        getDirectoryDeviceId: (cb) => cb("dir-dev-12345"),
        getDeviceSerialNumber: (cb) => cb("5CD9440ABC"),
        getDeviceAssetId: (cb) => cb("ASSET-CB-90210"),
        getDeviceAnnotatedLocation: (cb) => cb("West High Room 204"),
        getDeviceAnnotatedUser: (cb) => cb("student.jdoe@district.edu"),
        getDeviceHostname: (cb) => cb("cb-student-204-01")
      },
      networkingAttributes: {
        getNetworkDetails: (cb) =>
          cb({
            macAddress: "00:1A:2B:3C:4D:5E",
            ipv4: "10.200.4.155"
          })
      }
    },
    networkingPrivate: {
      getNetworks: (filter, callback) => {
        callback([
          {
            ConnectionState: "Connected",
            Name: "District-Secure-WiFi",
            WiFi: {
              SSID: "District-Secure-WiFi",
              BSSID: "00:1A:2B:3C:4D:5E",
              SignalStrength: 85,
              SignalStrengthDbm: -58,
              Frequency: 5240,
              Channel: 48,
              Security: "WPA-Enterprise"
            }
          }
        ]);
      }
    },
    system: {
      cpu: {
        getInfo: (cb) =>
          cb({
            archName: "x86_64",
            modelName: "Intel(R) Celeron(R) N4500",
            numOfProcessors: 2,
            processors: [
              { usage: { user: 100, kernel: 50, idle: 850, total: 1000 } },
              { usage: { user: 120, kernel: 60, idle: 820, total: 1000 } }
            ]
          })
      },
      memory: {
        getInfo: (cb) =>
          cb({
            capacity: 8589934592,
            availableCapacity: 4294967296
          })
      },
      storage: {
        getInfo: (cb) =>
          cb([
            {
              id: "internal-emmc-0",
              name: "eMMC Internal Storage",
              type: "fixed",
              capacity: 68719476736
            }
          ])
      },
      display: {
        getInfo: (cb) =>
          cb([
            {
              id: "display-internal",
              name: "Internal LCD Panel",
              isPrimary: true,
              isInternal: true,
              bounds: { width: 1366, height: 768 }
            }
          ])
      },
      network: {
        getNetworkInterfaces: (cb) =>
          cb([
            {
              name: "wlan0",
              address: "10.200.4.155",
              prefixLength: 24
            }
          ])
      }
    },
    alarms: {
      create: () => {},
      onAlarm: {
        addListener: () => {}
      }
    },
    offscreen: {
      createDocument: async () => true,
      closeDocument: async () => true
    }
  };

  return globalScope.chrome;
}
