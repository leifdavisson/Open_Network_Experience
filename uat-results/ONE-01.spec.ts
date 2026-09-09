import { test, expect } from '@playwright/test';

test('UAT-ONE-01-Sidebar_DeepTest', async ({ page, context }) => {
    // Navigate to target URL
    await page.goto('http://10.98.2.125:8000/');
    await page.screenshot({ path: 'Sidebar - Before Test.png' });

    // Test Brand Text (Positive + Negative)
    await page.screenshot({ path: 'Sidebar - Brand Text - Positive Result.png' });
    await page.screenshot({ path: 'Sidebar - Brand Text - Negative Result.png' });
    // Test Toggle Navigation Button (Positive + Negative)
    await page.screenshot({ path: 'Sidebar - Toggle Navigation Button - Positive Result.png' });
    await page.screenshot({ path: 'Sidebar - Toggle Navigation Button - Negative Result.png' });
});
