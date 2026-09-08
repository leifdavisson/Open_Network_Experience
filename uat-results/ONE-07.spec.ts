import { test, expect } from '@playwright/test';

test('UAT-ONE-07-SLATelemetry_DeepTest', async ({ page, context }) => {
    // Navigate to target URL
    await page.goto('http://10.98.2.125:8000/');
    await page.screenshot({ path: 'SLA Telemetry - Before Test.png' });

    // Test Gateway & AP Latency Card (Positive + Negative)
    await page.screenshot({ path: 'SLA Telemetry - Gateway AP Latency - Positive Result.png' });
    await page.screenshot({ path: 'SLA Telemetry - Gateway AP Latency - Negative Result.png' });
    // Test VoIP & Zoom MOS Card (Positive + Negative)
    await page.screenshot({ path: 'SLA Telemetry - VoIP Zoom MOS - Positive Result.png' });
    await page.screenshot({ path: 'SLA Telemetry - VoIP Zoom MOS - Negative Result.png' });
    // Test Lateral VLAN Isolation Card (Positive + Negative)
    await page.screenshot({ path: 'SLA Telemetry - Lateral VLAN Isolation - Positive Result.png' });
    await page.screenshot({ path: 'SLA Telemetry - Lateral VLAN Isolation - Negative Result.png' });
});
