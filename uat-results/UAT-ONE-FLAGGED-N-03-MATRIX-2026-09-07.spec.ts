
import { test } from '@playwright/test';
import { expect } from '@playwright/test';

test('Test_2026-09-08', async ({ page, context }) => {

    // Navigate to URL
    await page.goto('http://10.98.2.125:8000/');

    // Click element
    await page.click('#nav-monitor-ondemand');

    // Take screenshot
    await page.screenshot({ path: '/data/Open_Network_Experience/uat-results/N-03-Matrix-View-Loaded.png' });

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
    await page.screenshot({ path: '/data/Open_Network_Experience/uat-results/N-03-Chromebook-Speedtest-Success.png' });

    // Select option
    await page.selectOption('#diag-sensor-select', '0320589c63904502bd820cb0c321a1b2');

    // Select option
    await page.selectOption('#diag-test-select', 'zoom');

    // Click element
    await page.click('#btn-run-diag');

    // Take screenshot
    await page.screenshot({ path: '/data/Open_Network_Experience/uat-results/N-03-Zoom-MOS-Success.png' });

    // Select option
    await page.selectOption('#diag-test-select', 'vlan_isolation');

    // Click element
    await page.click('#btn-run-diag');

    // Take screenshot
    await page.screenshot({ path: '/data/Open_Network_Experience/uat-results/N-03-VLAN-Isolation-Success.png' });

    // Select option
    await page.selectOption('#diag-test-select', 'canvas');

    // Click element
    await page.click('#btn-run-diag');

    // Take screenshot
    await page.screenshot({ path: '/data/Open_Network_Experience/uat-results/N-03-Canvas-Fail-State.png' });

    // Select option
    await page.selectOption('#diag-test-select', 'pcap');

    // Click element
    await page.click('#btn-run-diag');

    // Take screenshot
    await page.screenshot({ path: '/data/Open_Network_Experience/uat-results/N-03-PCAP-Trigger-Success.png' });
});

// ============================================================
// REGRESSION ASSERTIONS
// Bug: BUG-N-03-MATRIX-2026-09-07
// View: Live Diagnostics (On-Demand Action Center)
// Generated: 2026-09-07 by agy-cli UAT Agent
// Instructions: Uncomment after applying the recommended fix.
//               Run with: npx playwright test uat-results/ --grep 'regression'
// ============================================================
//
// test('BUG-N-03-MATRIX regression — Live Diagnostics executes all 16 probes cleanly across sensors', async ({ page }) => {
//   const consoleErrors: string[] = [];
//   page.on('console', msg => {
//     if (msg.type() === 'error') consoleErrors.push(msg.text());
//   });
//
//   await page.goto('http://10.98.2.125:8000/');
//   await page.click('#nav-monitor-ondemand');
//   await page.waitForTimeout(1000);
//
//   // Verify CIPA probe execution
//   await page.selectOption('#diag-sensor-select', 'f10325921e2b43b2b5fcf33cadad864b');
//   await page.selectOption('#diag-test-select', 'cipa');
//   await page.click('#btn-run-diag');
//   await page.waitForTimeout(2000);
//   const cipaPill = page.locator('#diag-status-pill');
//   await expect(cipaPill).toHaveText(/PASS/);
//
//   // Verify DHCP lease probe execution
//   await page.selectOption('#diag-test-select', 'dhcp');
//   await page.click('#btn-run-diag');
//   await page.waitForTimeout(2000);
//   const dhcpPill = page.locator('#diag-status-pill');
//   await expect(dhcpPill).toHaveText(/PASS/);
//
//   // Verify External Core SaaS HTTP Probe succeeds in Full Suite
//   await page.selectOption('#diag-test-select', 'all');
//   await page.click('#btn-run-diag');
//   await page.waitForTimeout(2000);
//   const allPill = page.locator('#diag-status-pill');
//   await expect(allPill).toHaveText(/PASS/);
//
//   expect(consoleErrors).toHaveLength(0);
// });
