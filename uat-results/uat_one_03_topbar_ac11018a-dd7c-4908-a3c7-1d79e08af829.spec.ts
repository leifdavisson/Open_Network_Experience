
import { test } from '@playwright/test';
import { expect } from '@playwright/test';

test('UAT-ONE-03-Topbar_2026-09-07', async ({ page, context }) => {

    // Navigate to URL
    await page.goto('http://10.98.2.125:8000/');

    // Take screenshot
    await page.screenshot({ path: 'Topbar - Before Test.png' });

    // Fill input field
    await page.fill('#global-search', 'Kernville');

    // Take screenshot
    await page.screenshot({ path: 'Topbar - Global Search Input - Positive Result.png' });

    // Fill input field
    await page.fill('#global-search', '@@@@999999');

    // Take screenshot
    await page.screenshot({ path: 'Topbar - Global Search Input - Negative Result.png' });

    // Fill input field
    await page.fill('#global-search', '');

    // Click element
    await page.click('#theme-btn');

    // Take screenshot
    await page.screenshot({ path: 'Topbar - Theme Button - Positive Result.png' });

    // Click element
    await page.click('#theme-btn');

    // Click element
    await page.click('#theme-btn');

    // Take screenshot
    await page.screenshot({ path: 'Topbar - Theme Button - Negative Result.png' });

    // Click element
    await page.click('#grafana-link');

    // Take screenshot
    await page.screenshot({ path: 'Topbar - Grafana External Link - Positive Result.png' });

    // Take screenshot
    await page.screenshot({ path: 'Topbar - Grafana External Link - Negative Result.png' });

    // Click element
    await page.click('header.topbar a[href="/docs"]');

    // Take screenshot
    await page.screenshot({ path: 'Topbar - Swagger Documentation Link - Positive Result.png' });

    // Take screenshot
    await page.screenshot({ path: 'Topbar - Swagger Documentation Link - Negative Result.png' });
});
