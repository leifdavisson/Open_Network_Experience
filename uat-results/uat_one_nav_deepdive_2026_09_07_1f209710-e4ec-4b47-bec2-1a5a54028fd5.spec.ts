
import { test } from '@playwright/test';
import { expect } from '@playwright/test';

test('UAT-ONE-NAV-DEEPDIVE-2026-09-07_2026-09-08', async ({ page, context }) => {
  
    // Navigate to URL
    await page.goto('http://10.98.2.125:8000/');

    // Take screenshot
    await page.screenshot({ path: 'NAV-DEEPDIVE - Before Test.png' });

    // Click element
    await page.click('#btn-play-pause');

    // Take screenshot
    await page.screenshot({ path: 'Carousel - Confirmed Paused.png' });

    // Take screenshot
    await page.screenshot({ path: 'NAV - INITIAL SCAN - 2026-09-07.png', { fullPage: true } });
});