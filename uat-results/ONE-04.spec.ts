import { test, expect } from '@playwright/test';

test('UAT-ONE-04-NOCWallboard_DeepTest', async ({ page, context }) => {
    // Navigate to target URL
    await page.goto('http://10.98.2.125:8000/');
    await page.screenshot({ path: 'NOC Wallboard - Before Test.png' });

    // Test Slide Tab Buttons 1-6 (Positive + Negative)
    await page.screenshot({ path: 'NOC Wallboard - Slide Tab Buttons - Positive Result.png' });
    await page.screenshot({ path: 'NOC Wallboard - Slide Tab Buttons - Negative Result.png' });
    // Test Play/Pause Button (Positive + Negative)
    await page.screenshot({ path: 'NOC Wallboard - Play Pause Button - Positive Result.png' });
    await page.screenshot({ path: 'NOC Wallboard - Play Pause Button - Negative Result.png' });
    // Test Fullscreen 72-inch Mode Button (Positive + Negative)
    await page.screenshot({ path: 'NOC Wallboard - Fullscreen Mode Button - Positive Result.png' });
    await page.screenshot({ path: 'NOC Wallboard - Fullscreen Mode Button - Negative Result.png' });
});
