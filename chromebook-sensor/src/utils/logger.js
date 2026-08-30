/**
 * Open Network Experience (ONE) - Chromebook Sensor
 * Structured Logger
 * License: GNU AGPLv3
 */

const PREFIX = "[ONE-Chromebook-Sensor]";

export const LogLevel = {
  DEBUG: 0,
  INFO: 1,
  WARN: 2,
  ERROR: 3,
};

let currentLevel = LogLevel.DEBUG;

export function setLogLevel(level) {
  currentLevel = level;
}

export const logger = {
  debug: (...args) => {
    if (currentLevel <= LogLevel.DEBUG) {
      console.debug(PREFIX, `[DEBUG] [${new Date().toISOString()}]`, ...args);
    }
  },
  info: (...args) => {
    if (currentLevel <= LogLevel.INFO) {
      console.info(PREFIX, `[INFO] [${new Date().toISOString()}]`, ...args);
    }
  },
  warn: (...args) => {
    if (currentLevel <= LogLevel.WARN) {
      console.warn(PREFIX, `[WARN] [${new Date().toISOString()}]`, ...args);
    }
  },
  error: (...args) => {
    if (currentLevel <= LogLevel.ERROR) {
      console.error(PREFIX, `[ERROR] [${new Date().toISOString()}]`, ...args);
    }
  }
};
