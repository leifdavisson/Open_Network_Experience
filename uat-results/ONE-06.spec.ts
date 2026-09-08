import { test, expect } from '@playwright/test';

test('UAT-ONE-06-ChartsSection_DeepTest', async ({ page, context }) => {
    // Navigate to target URL
    await page.goto('http://10.98.2.125:8000/');
    await page.screenshot({ path: 'Charts Section - Before Test.png' });

    // Test Fault Situation Chart (Positive + Negative)
    await page.screenshot({ path: 'Charts Section - Fault Situation Chart - Positive Result.png' });
    await page.screenshot({ path: 'Charts Section - Fault Situation Chart - Negative Result.png' });
    // Test WAN Latency Trend Analysis Chart (Positive + Negative)
    await page.screenshot({ path: 'Charts Section - WAN Latency Trend - Positive Result.png' });
    await page.screenshot({ path: 'Charts Section - WAN Latency Trend - Negative Result.png' });
});
