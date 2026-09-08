import { test, expect } from '@playwright/test';

test('UAT-ONE-02-NavigationMenu_DeepTest', async ({ page, context }) => {
    // Navigate to target URL
    await page.goto('http://10.98.2.125:8000/');
    await page.screenshot({ path: 'Navigation Menu - Before Test.png' });

    // Test NOC Overview Link (Positive + Negative)
    await page.screenshot({ path: 'Navigation Menu - NOC Overview Link - Positive Result.png' });
    await page.screenshot({ path: 'Navigation Menu - NOC Overview Link - Negative Result.png' });
    // Test GIS Campus Map Link (Positive + Negative)
    await page.screenshot({ path: 'Navigation Menu - GIS Campus Map Link - Positive Result.png' });
    await page.screenshot({ path: 'Navigation Menu - GIS Campus Map Link - Negative Result.png' });
    // Test Live Diagnostics Link (Positive + Negative)
    await page.screenshot({ path: 'Navigation Menu - Live Diagnostics Link - Positive Result.png' });
    await page.screenshot({ path: 'Navigation Menu - Live Diagnostics Link - Negative Result.png' });
    // Test Alert Center Link (Positive + Negative)
    await page.screenshot({ path: 'Navigation Menu - Alert Center Link - Positive Result.png' });
    await page.screenshot({ path: 'Navigation Menu - Alert Center Link - Negative Result.png' });
});
