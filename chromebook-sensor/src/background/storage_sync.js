/**
 * Open Network Experience (ONE) - Chromebook Sensor
 * Offline Buffer Synchronization Manager
 * Drains and replays offline IndexedDB metrics to CMP upon connectivity restoration.
 * License: GNU AGPLv3
 */

import { offlineStorage } from "../db/indexed_db.js";
import { sendTelemetryReport } from "../utils/reporter.js";
import { logger } from "../utils/logger.js";

let isSyncing = false;

/**
 * Attempts to flush buffered offline records to CMP.
 * @param {string} cmpUrl
 * @param {string} apiKey
 * @param {number} batchSize
 * @returns {Promise<number>} Count of flushed records
 */
export async function flushOfflineBuffer(cmpUrl, apiKey, batchSize = 25) {
  if (isSyncing) {
    logger.debug("Offline flush already in progress, skipping concurrent run");
    return 0;
  }

  isSyncing = true;
  let totalFlushed = 0;

  try {
    const queueCount = await offlineStorage.count();
    if (queueCount === 0) {
      isSyncing = false;
      return 0;
    }

    logger.info(`Flushing ${queueCount} buffered offline telemetry events to CMP...`);

    while (true) {
      const batch = await offlineStorage.peekBatch(batchSize);
      if (!batch || batch.length === 0) break;

      const successfulIds = [];

      for (const item of batch) {
        const result = await sendTelemetryReport(cmpUrl, apiKey, item.payload, 5000);
        if (result.success) {
          successfulIds.push(item.id);
          totalFlushed++;
        } else {
          // If network is still unreachable, abort current sync cycle
          logger.debug("Sync paused due to delivery failure, retaining remaining offline buffer");
          if (successfulIds.length > 0) {
            await offlineStorage.deleteBatch(successfulIds);
          }
          isSyncing = false;
          return totalFlushed;
        }
      }

      if (successfulIds.length > 0) {
        await offlineStorage.deleteBatch(successfulIds);
      }

      // If less than batch size was returned, we're done
      if (batch.length < batchSize) break;
    }
  } catch (err) {
    logger.error("Error during offline buffer flush:", err);
  } finally {
    isSyncing = false;
  }

  return totalFlushed;
}
