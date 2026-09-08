
import { test } from '@playwright/test';
import { expect } from '@playwright/test';

test('Test_2026-09-08', async ({ page, context }) => {
  
    // Navigate to URL
    await page.goto('http://10.98.2.125:8000/');

    // Take screenshot
    await page.screenshot({ path: 'GIS Campus Map - Investigation Start.png' });

    // Click element
    await page.click('#btn-play-pause');

    // Take screenshot
    await page.screenshot({ path: 'Carousel - Confirmed Paused.png' });

    // Click element
    await page.click('#nav-monitor-map');

    // Take screenshot
    await page.screenshot({ path: 'GIS Campus Map - After Navigation.png' });

    // Take screenshot
    await page.screenshot({ path: 'GIS Campus Map - Full State.png' });

    // Take screenshot
    await page.screenshot({ path: 'GIS Campus Map - Bottom State.png' });

    // Click element
    await page.click('#nav-monitor-noc');

    // Click element
    await page.click('#nav-monitor-map');

    // Take screenshot
    await page.screenshot({ path: 'GIS Campus Map - Second Load.png' });

    // Take screenshot
    await page.screenshot({ path: 'GIS Campus Map - Deep Investigation.png' });

    // Take screenshot
    await page.screenshot({ path: 'GIS Campus Map - Boundary Map Missing.png' });
});