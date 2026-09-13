/**
 * Open Network Experience (ONE) - Chromebook Sensor
 * EdTech Filter & Safety Agent Diagnostic Probe
 * Evaluates latency, cloud edge reachability, and conflicts for K-12 agents:
 * Securly, Lightspeed Systems (Relay), Blocksi, and GoGuardian.
 * License: GNU AGPLv3
 */

import { logger } from "../utils/logger.js";

// Known K-12 Filter Agent Fingerprints and Cloud Edge Probing Targets
export const KNOWN_EDTECH_AGENTS = {
  securly: {
    name: "Securly Filter",
    extension_ids: [
      "jhegagklnjemlaccpdjdiogomgeapbcl", // Securly Chrome Extension
      "iheobagjkfkfllikgdpflaikfdhaegpn"  // Securly Classroom
    ],
    probe_url: "https://www.securly.com/generate_204",
    fallback_url: "https://useast-www.securly.com"
  },
  lightspeed: {
    name: "Lightspeed Systems Relay",
    extension_ids: [
      "adkcpkpaleahmbngficnbneflipohmnj" // Lightspeed Filter
    ],
    probe_url: "https://production-relay.lsfilter.com",
    fallback_url: "https://relay.school"
  },
  blocksi: {
    name: "Blocksi (Bloxy)",
    extension_ids: [
      "pgbdhkoplegmpdohnhehomnmgebcmcld" // Blocksi Enterprise Extension
    ],
    probe_url: "https://service.blocksi.net",
    fallback_url: "https://api.blocksi.net"
  },
  goguardian: {
    name: "GoGuardian",
    extension_ids: [
      "haldlgldplgnggkjaafhelgiaglafanh", // GoGuardian App
      "niggcflpbflnglnejclfdipfbnillall"  // GoGuardian License
    ],
    probe_url: "https://kpreporting.goguardian.com",
    fallback_url: "https://panoptes.goguardian.com"
  },
  linewize: {
    name: "Linewize (FamilyZone)",
    extension_ids: [
      "ddhabbgageeajjegnejocgdmkpkflpeb", // Linewize Connect
      "ifinpabiejihfljipfdhaegpnkmfgkba"  // FamilyZone School Manager
    ],
    probe_url: "https://linewize.io/generate_204",
    fallback_url: "https://api.familyzone.com"
  },
  contentkeeper: {
    name: "ContentKeeper",
    extension_ids: [
      "jknokgflnhncfdgnnhomngnbekecclgd" // ContentKeeper Chrome Extension
    ],
    probe_url: "https://ckauth.contentkeeper.com",
    fallback_url: "https://cloud.contentkeeper.com"
  },
  cisco_umbrella: {
    name: "Cisco Umbrella",
    extension_ids: [
      "jpfjjagjollfdabfpacfmfaphenmgomi" // Cisco Umbrella Chromebook Client
    ],
    probe_url: "https://disthost.umbrella.com/generate_204",
    fallback_url: "https://resolver.umbrella.com"
  }
};

/**
 * Checks reachability and round-trip time (RTT) to an external filter cloud gateway.
 * Uses HEAD request with no-cache and abort controller.
 * 
 * @param {string} url - Target URL to probe
 * @param {number} timeoutMs - Timeout limit in milliseconds
 * @returns {Promise<{ reachable: boolean, rtt_ms: number, status: number|null, error: string|null }>}
 */
export async function probeFilterEndpoint(url, timeoutMs = 4000) {
  const start = performance.now();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(url, {
      method: "HEAD",
      cache: "no-store",
      mode: "no-cors",
      signal: controller.signal
    });
    clearTimeout(timer);
    const rtt = Math.round(performance.now() - start);
    return {
      reachable: true,
      rtt_ms: rtt,
      status: res.status || 200,
      error: null
    };
  } catch (err) {
    clearTimeout(timer);
    const rtt = Math.round(performance.now() - start);
    const isTimeout = err.name === "AbortError";
    return {
      reachable: false,
      rtt_ms: rtt,
      status: null,
      error: isTimeout ? `Timeout after ${timeoutMs}ms` : err.message
    };
  }
}

/**
 * Detects presence of known K-12 filtering extensions via internal resource probing.
 * If running outside Chrome extension environment, returns an empty array.
 * 
 * @returns {Promise<Array<{ key: string, name: string, extension_id: string, detected: boolean }>>}
 */
export async function detectInstalledFilterAgents() {
  const detectedAgents = [];

  for (const [key, agent] of Object.entries(KNOWN_EDTECH_AGENTS)) {
    let agentFound = false;
    let foundExtId = null;

    for (const extId of agent.extension_ids) {
      const probeTarget = `chrome-extension://${extId}/manifest.json`;
      try {
        const response = await fetch(probeTarget, { method: "HEAD" });
        if (response && (response.ok || response.status === 200 || response.type === "basic")) {
          agentFound = true;
          foundExtId = extId;
          break;
        }
      } catch {
        // Expected if extension is not installed or web_accessible_resources are restricted
      }
    }

    if (agentFound) {
      detectedAgents.push({
        key,
        name: agent.name,
        extension_id: foundExtId,
        detected: true
      });
    }
  }

  return detectedAgents;
}

// Critical Educational & Classroom LMS Endpoints to verify safe-list pass-through
export const CORE_CLASSROOM_ENDPOINTS = [
  { name: "Google Classroom", url: "https://classroom.google.com/favicon.ico", category: "LMS" },
  { name: "Canvas LMS", url: "https://canvas.instructure.com/favicon.ico", category: "LMS" },
  { name: "Clever SSO", url: "https://clever.com/favicon.ico", category: "Identity" },
  { name: "Kahoot", url: "https://kahoot.it/favicon.ico", category: "Learning" }
];

/**
 * Probes district LMS and educational classroom endpoints through the active filter proxy.
 * Verifies that legitimate educational services are not accidentally blocked or degraded.
 * 
 * @param {Array<{ name: string, url: string, category: string }>} [targets]
 * @param {number} [timeoutMs=3500]
 * @returns {Promise<{
 *   all_passed: boolean,
 *   blocked_count: number,
 *   services: Array<{ name: string, url: string, reachable: boolean, rtt_ms: number, status: number|null, error: string|null }>
 * }>}
 */
export async function verifyClassroomWhitelists(targets = CORE_CLASSROOM_ENDPOINTS, timeoutMs = 3500) {
  const probePromises = targets.map(async (target) => {
    const start = performance.now();
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const res = await fetch(target.url, {
        method: "HEAD",
        cache: "no-store",
        mode: "no-cors",
        signal: controller.signal
      });
      clearTimeout(timer);
      return {
        name: target.name,
        url: target.url,
        reachable: true,
        rtt_ms: Math.round(performance.now() - start),
        status: res.status || 200,
        error: null
      };
    } catch (err) {
      clearTimeout(timer);
      const isTimeout = err.name === "AbortError";
      return {
        name: target.name,
        url: target.url,
        reachable: false,
        rtt_ms: Math.round(performance.now() - start),
        status: null,
        error: isTimeout ? `Timeout after ${timeoutMs}ms` : err.message
      };
    }
  });

  const services = await Promise.all(probePromises);
  const blockedCount = services.filter(s => !s.reachable).length;

  return {
    all_passed: blockedCount === 0,
    blocked_count: blockedCount,
    services
  };
}

/**
 * Verifies TLS/SSL MITM decryption inspection and certificate validation health.
 * When school filtering proxies decrypt HTTPS traffic using installed Root CAs,
 * misconfigured or expired certs trigger handshake aborts or cert authority errors.
 * 
 * @param {number} [timeoutMs=3500]
 * @returns {Promise<{ ssl_valid: boolean, rtt_ms: number, error: string|null }>}
 */
export async function probeSslInterceptionHealth(timeoutMs = 3500) {
  const start = performance.now();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch("https://www.google.com/generate_204", {
      method: "HEAD",
      cache: "no-store",
      signal: controller.signal
    });
    clearTimeout(timer);
    return {
      ssl_valid: res.ok || res.status === 204,
      rtt_ms: Math.round(performance.now() - start),
      error: null
    };
  } catch (err) {
    clearTimeout(timer);
    return {
      ssl_valid: false,
      rtt_ms: Math.round(performance.now() - start),
      error: err.name === "AbortError" ? `Handshake timeout after ${timeoutMs}ms` : err.message
    };
  }
}

/**
 * Runs a complete EdTech Filter & Safety Agent Diagnostic Suite:
 * 1. Measures latency to all major cloud filter endpoints (Securly, Lightspeed, Blocksi, GoGuardian).
 * 2. Detects active agents and flags multi-agent collisions (e.g., Securly + Lightspeed running concurrently).
 * 3. Calculates filter latency overhead against a baseline reference.
 * 4. Determines overall filter health status and actionable recommendations for IT admins.
 * 
 * @param {number} [baselineRttMs=30] - Baseline idle gateway/WAN RTT for overhead comparison
 * @param {number} [timeoutMs=4000] - Hard safety timeout per probe
 * @returns {Promise<{
 *   detected_agents: Array<string>,
 *   collision_detected: boolean,
 *   filter_endpoints: Record<string, { reachable: boolean, rtt_ms: number, status: number|null, error: string|null }>,
 *   fastest_provider: string|null,
 *   filter_overhead_ms: number,
 *   health_status: "HEALTHY"|"DEGRADED_LATENCY"|"COLLISION_DETECTED"|"CLOUD_UNREACHABLE",
 *   recommendation: string
 * }>}
 */
export async function runEdtechFilterSuite(baselineRttMs = 30, timeoutMs = 4000) {
  logger.debug("Starting EdTech Filter & Safety Agent diagnostic suite...");

  // 1. Detect Installed Agents
  let detected = [];
  try {
    detected = await detectInstalledFilterAgents();
  } catch (err) {
    logger.debug("Agent detection skipped or unsupported:", err.message);
  }

  const detectedNames = detected.map(a => a.name);
  const collisionDetected = detectedNames.length > 1;

  // 2. Concurrently probe each vendor's cloud edge gateway
  const probePromises = Object.entries(KNOWN_EDTECH_AGENTS).map(async ([key, agent]) => {
    const res = await probeFilterEndpoint(agent.probe_url, timeoutMs);
    return [key, res];
  });

  const probeResultsArray = await Promise.all(probePromises);
  const filterEndpoints = Object.fromEntries(probeResultsArray);

  // 3. Find fastest reachable filter cloud provider & compute average RTT
  let fastestProvider = null;
  let minRtt = Infinity;
  let totalRtt = 0;
  let reachableCount = 0;

  for (const [key, res] of Object.entries(filterEndpoints)) {
    if (res.reachable && res.rtt_ms < minRtt) {
      minRtt = res.rtt_ms;
      fastestProvider = KNOWN_EDTECH_AGENTS[key].name;
    }
    if (res.reachable) {
      totalRtt += res.rtt_ms;
      reachableCount++;
    }
  }

  const avgRtt = reachableCount > 0 ? Math.round(totalRtt / reachableCount) : 0;
  const filterOverheadMs = Math.max(0, (minRtt !== Infinity ? minRtt : avgRtt) - baselineRttMs);

  // 4. District LMS & Classroom Safe-List Probe
  logger.debug("Verifying district LMS and classroom educational safe-lists...");
  const classroomWhitelistResult = await verifyClassroomWhitelists();

  // 5. SSL / MITM Interception & Root CA Handshake Health
  logger.debug("Checking SSL MITM decryption inspection and cert validation...");
  const sslHealthResult = await probeSslInterceptionHealth();

  // 6. Determine Health Status & Recommendation
  let healthStatus = "HEALTHY";
  let recommendation = "All student safety and web filtering gateways are operating with low latency.";

  if (collisionDetected) {
    healthStatus = "COLLISION_DETECTED";
    recommendation = `Multiple filtering agents detected (${detectedNames.join(", ")}). Running multiple agents causes proxy loops and device CPU exhaustion.`;
    logger.warn(recommendation);
  } else if (reachableCount === 0) {
    healthStatus = "CLOUD_UNREACHABLE";
    recommendation = "All EdTech filtering cloud endpoints are unreachable. Chromebook may fail open or block all web traffic.";
    logger.error(recommendation);
  } else if (!sslHealthResult.ssl_valid) {
    healthStatus = "SSL_INSPECTION_FAILED";
    recommendation = `SSL inspection handshake failed (${sslHealthResult.error || "Untrusted Root CA"}). Verify filter MITM certificate deployment in Google Admin Console.`;
    logger.error(recommendation);
  } else if (!classroomWhitelistResult.all_passed) {
    healthStatus = "CLASSROOM_BLOCKED";
    const blockedNames = classroomWhitelistResult.services.filter(s => !s.reachable).map(s => s.name);
    recommendation = `Core educational services are blocked or timing out: ${blockedNames.join(", ")}. Verify filtering exceptions and bypass lists.`;
    logger.error(recommendation);
  } else if (filterOverheadMs > 120) {
    healthStatus = "DEGRADED_LATENCY";
    recommendation = `High filtering proxy latency overhead (+${filterOverheadMs}ms). Inspection gateway or cloud proxy is bottlenecking web traffic.`;
    logger.warn(recommendation);
  }

  const result = {
    detected_agents: detectedNames,
    collision_detected: collisionDetected,
    filter_endpoints: filterEndpoints,
    fastest_provider: fastestProvider,
    filter_overhead_ms: filterOverheadMs,
    classroom_whitelist: classroomWhitelistResult,
    ssl_inspection: sslHealthResult,
    health_status: healthStatus,
    recommendation
  };

  logger.info(`EdTech Filter Suite: Status=${healthStatus} | Overhead=+${filterOverheadMs}ms | Collision=${collisionDetected}`);
  return result;
}
