import { test, expect } from '@playwright/test';

test('UAT-ONE-05-KPICards_DeepTest', async ({ page, context }) => {
    // Navigate to target URL
    await page.goto('http://10.98.2.125:8000/');
    await page.screenshot({ path: 'KPI Cards - Before Test.png' });

    // Test Online Fleet KPI Card (Positive + Negative)
    await page.screenshot({ path: 'KPI Cards - Online Fleet Card - Positive Result.png' });
    await page.screenshot({ path: 'KPI Cards - Online Fleet Card - Negative Result.png' });
    // Test Open Alarms KPI Card (Positive + Negative)
    await page.screenshot({ path: 'KPI Cards - Open Alarms Card - Positive Result.png' });
    await page.screenshot({ path: 'KPI Cards - Open Alarms Card - Negative Result.png' });
});
