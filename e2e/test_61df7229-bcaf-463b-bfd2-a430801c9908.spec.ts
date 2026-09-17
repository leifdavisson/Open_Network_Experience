
import { test } from '@playwright/test';
import { expect } from '@playwright/test';

test('Test_2026-09-08', async ({ page, context }) => {
  
    // Navigate to URL
    await page.goto('http://10.98.2.125:8000/');

    // Click element
    await page.click('#nav-monitor-ondemand');

    // Take screenshot
    await page.screenshot({ path: 'undefined.png', { path: '/data/Open_Network_Experience/uat-results/N-03-Matrix-View-Loaded.png' } });

    // Select option
    await page.selectOption('#diag-sensor-select', 'f10325921e2b43b2b5fcf33cadad864b');

    // Select option
    await page.selectOption('#diag-test-select', 'dns');

    // Click element
    await page.click('#btn-run-diag');

    // Select option
    await page.selectOption('#diag-sensor-select', 'chromebook-dev-e7573882-80d0-4bec-ab68-4e1f98afd22f');

    // Select option
    await page.selectOption('#diag-test-select', 'speedtest');

    // Click element
    await page.click('#btn-run-diag');

    // Take screenshot
    await page.screenshot({ path: 'undefined.png', { path: '/data/Open_Network_Experience/uat-results/N-03-Chromebook-Speedtest-Success.png' } });

    // Select option
    await page.selectOption('#diag-sensor-select', '0320589c63904502bd820cb0c321a1b2');

    // Select option
    await page.selectOption('#diag-test-select', 'zoom');

    // Click element
    await page.click('#btn-run-diag');

    // Take screenshot
    await page.screenshot({ path: 'undefined.png', { path: '/data/Open_Network_Experience/uat-results/N-03-Zoom-MOS-Success.png' } });

    // Select option
    await page.selectOption('#diag-test-select', 'vlan_isolation');

    // Click element
    await page.click('#btn-run-diag');

    // Take screenshot
    await page.screenshot({ path: 'undefined.png', { path: '/data/Open_Network_Experience/uat-results/N-03-VLAN-Isolation-Success.png' } });

    // Select option
    await page.selectOption('#diag-test-select', 'canvas');

    // Click element
    await page.click('#btn-run-diag');

    // Take screenshot
    await page.screenshot({ path: 'undefined.png', { path: '/data/Open_Network_Experience/uat-results/N-03-Canvas-Fail-State.png' } });

    // Select option
    await page.selectOption('#diag-test-select', 'pcap');

    // Click element
    await page.click('#btn-run-diag');

    // Take screenshot
    await page.screenshot({ path: 'undefined.png', { path: '/data/Open_Network_Experience/uat-results/N-03-PCAP-Trigger-Success.png' } });
});