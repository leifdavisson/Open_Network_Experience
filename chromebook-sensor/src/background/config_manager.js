/**
 * Open Network Experience (ONE) - Chromebook Sensor
 * Configuration Manager
 * Resolves configuration from Google Workspace Admin Console (chrome.storage.managed),
 * local storage overrides, or built-in defaults.
 * License: GNU AGPLv3
 */

import { logger } from "../utils/logger.js";

export const DEFAULT_CONFIG = {
  cmp_server_url: "http://localhost:8000",
  api_key: "",
  campus_id: "CAMPUS-CHROMEBOOK-FLEET",
  probe_interval_seconds: 60,
  stun_servers: [
    "stun:stun.l.google.com:19302",
    "stun:stun1.l.google.com:19302"
  ],
  synthetic_http_targets: [
    {
      name: "Google Classroom & Workspace",
      url: "https://classroom.google.com",
      category: "Google Workspace",
      timeout_ms: 5000
    },
    {
      name: "CAASPP / Cambium TDS Portal",
      url: "https://caaspp.org",
      category: "Testing",
      timeout_ms: 5000
    },
    {
      name: "Clever K-12 Identity",
      url: "https://clever.com",
      category: "Identity",
      timeout_ms: 5000
    },
    {
      name: "Lightspeed Filter Portal",
      url: "https://relay.lightspeedsystems.com",
      category: "Security / Filter",
      timeout_ms: 5000
    }
  ],
  enable_webrtc_probing: true,
  enable_offline_buffer: true,
  max_offline_records: 1000
};

class ConfigManager {
  constructor() {
    this.config = { ...DEFAULT_CONFIG };
    this.listeners = [];
  }

  /**
   * Load managed configuration from Google Workspace Admin Console policy,
   * merging with local overrides and defaults.
   */
  async loadConfig() {
    let managed = {};
    let local = {};

    if (typeof chrome !== "undefined" && chrome.storage) {
      if (chrome.storage.managed) {
        try {
          managed = await new Promise((resolve) => {
            chrome.storage.managed.get(null, (items) => {
              if (chrome.runtime.lastError) {
                logger.debug("No managed policy loaded:", chrome.runtime.lastError.message);
                resolve({});
              } else {
                resolve(items || {});
              }
            });
          });
        } catch (e) {
          logger.debug("chrome.storage.managed not accessible:", e);
        }
      }

      if (chrome.storage.local) {
        try {
          local = await new Promise((resolve) => {
            chrome.storage.local.get(null, (items) => {
              if (chrome.runtime.lastError) {
                resolve({});
              } else {
                resolve(items || {});
              }
            });
          });
        } catch (e) {
          logger.debug("chrome.storage.local not accessible:", e);
        }
      }
    }

    this.config = {
      ...DEFAULT_CONFIG,
      ...local,
      ...managed // Managed policy from Admin Console takes highest precedence
    };

    logger.info("Active configuration loaded. CMP URL:", this.config.cmp_server_url);
    this._notifyListeners();
    return this.config;
  }

  get() {
    return this.config;
  }

  async updateLocal(updates) {
    if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
      await new Promise((resolve) => chrome.storage.local.set(updates, resolve));
    }
    return this.loadConfig();
  }

  subscribe(callback) {
    this.listeners.push(callback);
    return () => {
      this.listeners = this.listeners.filter((cb) => cb !== callback);
    };
  }

  _notifyListeners() {
    for (const listener of this.listeners) {
      try {
        listener(this.config);
      } catch (err) {
        logger.error("Error in config listener:", err);
      }
    }
  }
}

export const configManager = new ConfigManager();
