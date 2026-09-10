
import { test } from '@playwright/test';
import { expect } from '@playwright/test';

test('UAT-ONE-03-Topbar_2026-09-07', async ({ page, context }) => {

    // Navigate to URL
    await page.goto('http://10.98.2.125:8000/');

    // Take screenshot
    await page.screenshot({ path: 'BEFORE - Topbar.png' });

    // Fill input field
    await page.fill('#global-search', 'undefined');

    // Fill input field
    await page.fill('#global-search', 'Kernville');

    // Take screenshot
    await page.screenshot({ path: 'Global Search Input - Result.png' });

    // Click element
    await page.click('#theme-btn');

    // Click element
    await page.click('#theme-btn');

    // Take screenshot
    await page.screenshot({ path: 'Theme Button - Result.png' });

    // Take screenshot
    await page.screenshot({ path: 'Grafana External Link - Result.png' });

    // Take screenshot
    await page.screenshot({ path: 'Swagger Documentation Link - Result.png' });
});
