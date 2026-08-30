/**
 * Open Network Experience (ONE) - Chromebook Sensor
 * Offscreen Document Message Handler
 * License: GNU AGPLv3
 */

import { measureWebRtcQuality } from "./webrtc_prober.js";

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.target !== "offscreen") return;

  if (message.type === "RUN_WEBRTC_PROBE") {
    measureWebRtcQuality(message.stunServers, message.timeoutMs)
      .then((data) => sendResponse({ success: true, data }))
      .catch((err) => sendResponse({ success: false, error: err.message }));
    return true; // Keep message channel open for async response
  }
});
