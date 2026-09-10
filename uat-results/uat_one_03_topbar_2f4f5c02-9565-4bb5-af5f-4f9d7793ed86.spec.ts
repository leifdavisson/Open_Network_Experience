
import { test } from '@playwright/test';
import { expect } from '@playwright/test';

test('UAT-ONE-03-Topbar_2026-09-08', async ({ page, context }) => {

    // Navigate to URL
    await page.goto('http://10.98.2.125:8000/');

    // Take screenshot
    await page.screenshot({ path: 'Topbar - Before Test.png' });

    // Click element
    await page.click('#btn-play-pause');

    // Take screenshot
    await page.screenshot({ path: 'Carousel - Confirmed Paused.png' });

    // Take screenshot
    await page.screenshot({ path: 'INITIAL SCAN - 2026-09-07.png', { fullPage: true } });

    // Fill input field
    await page.fill('#global-search', 'Kernville');

    // Take screenshot
    await page.screenshot({ path: 'Topbar - Global Search Input - Positive Result.png' });

    // Fill input field
    await page.fill('#global-search', '');

    // Fill input field
    await page.fill('#global-search', '@@@@999999');

    // Fill input field
    await page.fill('#global-search', 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA');

    // Fill input field
    await page.fill('#global-search', '<script>alert('XSS')</script>');

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

    // Click element
    await page.click('#theme-btn');

    // Take screenshot
    await page.screenshot({ path: 'Topbar - Theme Button - Negative Result.png' });

    // Click element
    await page.click('#grafana-link');

    // Navigate to URL
    await page.goto('http://10.98.2.125:3000');

    // Take screenshot
    await page.screenshot({ path: 'Grafana External Link - Destination Verified.png' });

    // Navigate to URL
    await page.goto('http://10.98.2.125:8000/');

    // Take screenshot
    await page.screenshot({ path: 'Topbar - Grafana External Link - Positive Result.png' });

    // Take screenshot
    await page.screenshot({ path: 'Topbar - Grafana External Link - Negative Result.png' });

    // Click element
    await page.click('header.topbar a[href="/docs"]');

    // Navigate to URL
    await page.goto('http://10.98.2.125:8000/docs');

    // Take screenshot
    await page.screenshot({ path: 'Swagger Documentation Link - Destination Verified.png' });

    // Navigate to URL
    await page.goto('http://10.98.2.125:8000/');

    // Take screenshot
    await page.screenshot({ path: 'Topbar - Swagger Documentation Link - Positive Result.png' });

    // Take screenshot
    await page.screenshot({ path: 'Topbar - Swagger Documentation Link - Negative Result.png' });
});
