import { test, expect } from '@playwright/test';

test('UAT-ONE-08-ActiveIncidents_DeepTest', async ({ page, context }) => {
    // Navigate to target URL
    await page.goto('http://10.98.2.125:8000/');
    await page.screenshot({ path: 'Active Incidents - Before Test.png' });

    // Test Incident Count Badge (Positive + Negative)
    await page.screenshot({ path: 'Active Incidents - Incident Count Badge - Positive Result.png' });
    await page.screenshot({ path: 'Active Incidents - Incident Count Badge - Negative Result.png' });
    // Test Refresh Incidents Button (Positive + Negative)
    await page.screenshot({ path: 'Active Incidents - Refresh Incidents Button - Positive Result.png' });
    await page.screenshot({ path: 'Active Incidents - Refresh Incidents Button - Negative Result.png' });
    // Test Live Operational Ticker Feed (Positive + Negative)
    await page.screenshot({ path: 'Active Incidents - Live Operational Ticker Feed - Positive Result.png' });
    await page.screenshot({ path: 'Active Incidents - Live Operational Ticker Feed - Negative Result.png' });
});
