
import { test } from '@playwright/test';
import { expect } from '@playwright/test';

test('UAT-ONE-ALL-PAGES_2026-09-08', async ({ page, context }) => {
  
    // Navigate to URL
    await page.goto('http://10.98.2.125:8000/');

    // Take screenshot
    await page.screenshot({ path: 'ALL-PAGES - Before Test.png' });

    // Take screenshot
    await page.screenshot({ path: 'Carousel - Confirmed Paused.png' });
});