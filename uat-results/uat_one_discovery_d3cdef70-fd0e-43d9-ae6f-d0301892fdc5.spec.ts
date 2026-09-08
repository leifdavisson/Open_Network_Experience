
import { test } from '@playwright/test';
import { expect } from '@playwright/test';

test('UAT-ONE-Discovery_2026-09-07', async ({ page, context }) => {
  
    // Navigate to URL
    await page.goto('http://10.98.2.125:8000/');

    // Take screenshot
    await page.screenshot({ path: 'DISCOVERY - Initial State.png', { fullPage: true } });

    // Take screenshot
    await page.screenshot({ path: 'DISCOVERY - Full Page.png', { fullPage: true } });
});