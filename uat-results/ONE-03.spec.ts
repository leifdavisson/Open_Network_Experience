import { test, expect } from '@playwright/test';

test('UAT-ONE-03-Test_2026-09-07', async ({ page, context }) => {
    // Navigate to target URL
    await page.goto('http://10.98.2.125:8000/');

    await page.screenshot({ path: 'Topbar - Before Test.png' });
    await page.fill('#global-search', 'Building A - Science Lab');
    await page.screenshot({ path: 'Topbar - Global Search Input - Result.png' });
    await page.click('#theme-btn');
    await page.screenshot({ path: 'Topbar - Theme Button - Result.png' });
    await page.click('#theme-btn');
    await page.screenshot({ path: 'Topbar - Grafana External Link - Result.png' });
    await page.screenshot({ path: 'Topbar - Swagger Documentation Link - Result.png' });
});
