/**
 * Open Network Experience (ONE) - Chromebook Sensor
 * ITU-T G.107 E-Model Mean Opinion Score (MOS) Calculator
 * Evaluates VoIP, Google Meet, and Zoom call quality on ChromeOS fleets.
 * License: GNU AGPLv3
 */

/**
 * Calculates ITU-T G.107 E-Model MOS score and rating based on RTT, jitter, and packet loss.
 *
 * @param {number} rttMs - Round trip time in milliseconds
 * @param {number} jitterMs - Inter-packet jitter in milliseconds
 * @param {number} packetLossFraction - Packet loss (0.0 to 1.0 or percentage 0-100)
 * @returns {object} { mos: number, rFactor: number, qualityGrade: string, effectiveLatencyMs: number }
 */
export function calculateVoipMos(rttMs = 0, jitterMs = 0, packetLossFraction = 0) {
  // Normalize packet loss to fraction 0.0 - 1.0
  const lossFraction = packetLossFraction > 1.0 ? packetLossFraction / 100.0 : Math.max(0, packetLossFraction);

  // One-way delay estimate
  const oneWayDelayMs = Math.max(0, rttMs / 2.0);

  // Effective latency accounting for jitter buffer delay (ITU-T G.107)
  const effectiveLatencyMs = oneWayDelayMs + (2.0 * jitterMs) + 10.0;

  // Delay Impairment factor (Id)
  let id = 0;
  if (effectiveLatencyMs < 160) {
    id = effectiveLatencyMs / 40.0;
  } else {
    id = (effectiveLatencyMs - 120.0) / 10.0;
  }

  // Equipment / Packet Loss Impairment factor (Ie)
  // For Opus / G.711 with standard PLC (Packet Loss Concealment)
  const ie = 30.0 * Math.log(1.0 + (15.0 * lossFraction));

  // Basic Transmission Rating Factor R (Base = 93.2 for wideband codecs / 94 for G.711)
  let rFactor = 93.2 - id - ie;
  rFactor = Math.max(0, Math.min(100, rFactor));

  // Convert R-factor to Mean Opinion Score (MOS) [1.0 to 4.5]
  let mos = 1.0;
  if (rFactor <= 0) {
    mos = 1.0;
  } else if (rFactor >= 100) {
    mos = 4.5;
  } else {
    mos = 1.0 + (0.035 * rFactor) + (rFactor * (rFactor - 60.0) * (100.0 - rFactor) * 0.000007);
    mos = Math.max(1.0, Math.min(4.5, mos));
  }

  // Round to 2 decimal places
  mos = Math.round(mos * 100) / 100;
  rFactor = Math.round(rFactor * 10) / 10;

  let qualityGrade = "Bad";
  if (mos >= 4.34) {
    qualityGrade = "Excellent";
  } else if (mos >= 4.03) {
    qualityGrade = "Good";
  } else if (mos >= 3.60) {
    qualityGrade = "Fair";
  } else if (mos >= 3.10) {
    qualityGrade = "Poor";
  } else {
    qualityGrade = "Bad";
  }

  return {
    mos,
    rFactor,
    qualityGrade,
    effectiveLatencyMs: Math.round(effectiveLatencyMs * 10) / 10,
    rttMs: Math.round(rttMs * 10) / 10,
    jitterMs: Math.round(jitterMs * 10) / 10,
    packetLossPercent: Math.round(lossFraction * 10000) / 100
  };
}
