/**
 * Open Network Experience (ONE) - Chromebook Sensor
 * Offline Telemetry Storage via IndexedDB
 * Caches metrics during Wi-Fi roaming, AP handoffs, and network disconnects.
 * License: GNU AGPLv3
 */

import { logger } from "../utils/logger.js";

const DB_NAME = "one_chromebook_sensor_db";
const DB_VERSION = 1;
const STORE_NAME = "offline_telemetry_queue";

class OfflineStorageManager {
  constructor() {
    this.db = null;
    this.memFallback = [];
  }

  async openDb() {
    if (this.db) return this.db;
    if (typeof indexedDB === "undefined") {
      logger.warn("IndexedDB not supported in current environment; using in-memory fallback queue");
      return null;
    }

    return new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION);

      request.onupgradeneeded = (event) => {
        const db = event.target.result;
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          const store = db.createObjectStore(STORE_NAME, { keyPath: "id", autoIncrement: true });
          store.createIndex("timestamp", "timestamp", { unique: false });
        }
      };

      request.onsuccess = (event) => {
        this.db = event.target.result;
        resolve(this.db);
      };

      request.onerror = (event) => {
        logger.error("Failed to open IndexedDB:", event.target.error);
        reject(event.target.error);
      };
    });
  }

  /**
   * Enqueue a telemetry payload into offline storage.
   * @param {object} payload
   * @param {number} maxRecords
   */
  async enqueue(payload, maxRecords = 1000) {
    const db = await this.openDb().catch(() => null);
    const item = {
      timestamp: Date.now(),
      payload: payload
    };

    if (!db) {
      this.memFallback.push(item);
      if (this.memFallback.length > maxRecords) {
        this.memFallback.shift(); // Evict oldest
      }
      return true;
    }

    return new Promise((resolve, reject) => {
      const tx = db.transaction([STORE_NAME], "readwrite");
      const store = tx.objectStore(STORE_NAME);

      store.add(item);

      // Check and enforce max record count FIFO eviction
      const countReq = store.count();
      countReq.onsuccess = () => {
        const count = countReq.result;
        if (count > maxRecords) {
          const excess = count - maxRecords;
          const openCursor = store.openCursor();
          let deleted = 0;
          openCursor.onsuccess = (e) => {
            const cursor = e.target.result;
            if (cursor && deleted < excess) {
              cursor.delete();
              deleted++;
              cursor.continue();
            }
          };
        }
      };

      tx.oncomplete = () => resolve(true);
      tx.onerror = (e) => {
        logger.error("IndexedDB enqueue error:", e.target.error);
        reject(e.target.error);
      };
    });
  }

  /**
   * Peek next batch of items up to limit.
   * @param {number} limit
   * @returns {Promise<Array<{id: number, timestamp: number, payload: object}>>}
   */
  async peekBatch(limit = 50) {
    const db = await this.openDb().catch(() => null);
    if (!db) {
      return this.memFallback.slice(0, limit).map((it, idx) => ({ id: idx, ...it }));
    }

    return new Promise((resolve, reject) => {
      const tx = db.transaction([STORE_NAME], "readonly");
      const store = tx.objectStore(STORE_NAME);
      const items = [];

      const cursorReq = store.openCursor();
      cursorReq.onsuccess = (e) => {
        const cursor = e.target.result;
        if (cursor && items.length < limit) {
          items.push(cursor.value);
          cursor.continue();
        } else {
          resolve(items);
        }
      };

      cursorReq.onerror = (e) => reject(e.target.error);
    });
  }

  /**
   * Delete batch of items by IDs.
   * @param {Array<number>} ids
   */
  async deleteBatch(ids) {
    if (!ids || ids.length === 0) return;
    const db = await this.openDb().catch(() => null);
    if (!db) {
      this.memFallback = this.memFallback.filter((_, idx) => !ids.includes(idx));
      return;
    }

    return new Promise((resolve, reject) => {
      const tx = db.transaction([STORE_NAME], "readwrite");
      const store = tx.objectStore(STORE_NAME);

      for (const id of ids) {
        store.delete(id);
      }

      tx.oncomplete = () => resolve(true);
      tx.onerror = (e) => reject(e.target.error);
    });
  }

  /**
   * Return the total number of buffered records.
   */
  async count() {
    const db = await this.openDb().catch(() => null);
    if (!db) return this.memFallback.length;

    return new Promise((resolve) => {
      const tx = db.transaction([STORE_NAME], "readonly");
      const store = tx.objectStore(STORE_NAME);
      const req = store.count();
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => resolve(0);
    });
  }

  /**
   * Clear all records in the queue.
   */
  async clear() {
    const db = await this.openDb().catch(() => null);
    if (!db) {
      this.memFallback = [];
      return;
    }

    return new Promise((resolve) => {
      const tx = db.transaction([STORE_NAME], "readwrite");
      const store = tx.objectStore(STORE_NAME);
      store.clear();
      tx.oncomplete = () => resolve(true);
    });
  }
}

export const offlineStorage = new OfflineStorageManager();
