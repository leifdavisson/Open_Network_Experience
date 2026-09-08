import { test, expect } from '@playwright/test';

test('UAT-ONE-NAV-DEEPDIVE_2026-09-07', async ({ page, context }) => {
    // 1. Initial Navigation to ONE Dashboard
    await page.goto('http://10.98.2.125:8000/');
    await page.screenshot({ path: 'NAV-DEEPDIVE - Before Test.png' });

    // 2. Pause Carousel State-Aware
    const btnPlayPause = page.locator('#btn-play-pause');
    if (await btnPlayPause.count() > 0) {
        const label = await btnPlayPause.innerText();
        if (label.includes('Pause') || label.includes('⏸')) {
            await btnPlayPause.click();
        }
    }
    await page.screenshot({ path: 'Carousel - Confirmed Paused.png' });
    await page.screenshot({ path: 'NAV - INITIAL SCAN - 2026-09-07.png', fullPage: true });

    // Nav Link N-01: NOC Overview
    await page.click('#nav-monitor-noc');
    await page.screenshot({ path: 'N-01 NOC Overview - Loaded.png' });
    await page.waitForTimeout(1000);
    await page.screenshot({ path: 'N-01 NOC Overview - Settled.png' });
    await page.screenshot({ path: 'N-01 NOC Overview - Interaction.png' });

    // Nav Link N-02: GIS Campus Map
    await page.click('#nav-monitor-map');
    await page.screenshot({ path: 'N-02 GIS Campus Map - Loaded.png' });
    await page.waitForTimeout(1000);
    await page.screenshot({ path: 'N-02 GIS Campus Map - Settled.png' });
    await page.screenshot({ path: 'N-02 GIS Campus Map - Interaction.png' });

    // Nav Link N-03: Live Diagnostics
    await page.click('#nav-monitor-ondemand');
    await page.screenshot({ path: 'N-03 Live Diagnostics - Loaded.png' });
    await page.waitForTimeout(1000);
    await page.screenshot({ path: 'N-03 Live Diagnostics - Settled.png' });
    await page.screenshot({ path: 'N-03 Live Diagnostics - Interaction.png' });

    // Nav Link N-04: Reports & Forensics
    await page.click('#nav-monitor-reports');
    await page.screenshot({ path: 'N-04 Reports & Forensics - Loaded.png' });
    await page.waitForTimeout(1000);
    await page.screenshot({ path: 'N-04 Reports & Forensics - Settled.png' });
    await page.screenshot({ path: 'N-04 Reports & Forensics - Interaction.png' });

    // Nav Link N-05: Alert Center
    await page.click('#nav-monitor-alerts');
    await page.screenshot({ path: 'N-05 Alert Center - Loaded.png' });
    await page.waitForTimeout(1000);
    await page.screenshot({ path: 'N-05 Alert Center - Settled.png' });
    await page.screenshot({ path: 'N-05 Alert Center - Interaction.png' });

    // Nav Link N-06: Fixed Edge Sensors
    await page.click('#nav-manage-fleet');
    await page.screenshot({ path: 'N-06 Fixed Edge Sensors - Loaded.png' });
    await page.waitForTimeout(1000);
    await page.screenshot({ path: 'N-06 Fixed Edge Sensors - Settled.png' });
    await page.screenshot({ path: 'N-06 Fixed Edge Sensors - Interaction.png' });

    // Nav Link N-07: 1:1 Chromebooks
    await page.click('#nav-manage-chromebooks');
    await page.screenshot({ path: 'N-07 1:1 Chromebooks - Loaded.png' });
    await page.waitForTimeout(1000);
    await page.screenshot({ path: 'N-07 1:1 Chromebooks - Settled.png' });
    await page.screenshot({ path: 'N-07 1:1 Chromebooks - Interaction.png' });

    // Nav Link N-08: Campus Hierarchy
    await page.click('#nav-manage-locations');
    await page.screenshot({ path: 'N-08 Campus Hierarchy - Loaded.png' });
    await page.waitForTimeout(1000);
    await page.screenshot({ path: 'N-08 Campus Hierarchy - Settled.png' });
    await page.screenshot({ path: 'N-08 Campus Hierarchy - Interaction.png' });

    // Nav Link N-09: Probe Scheduler
    await page.click('#nav-configure-schedules');
    await page.screenshot({ path: 'N-09 Probe Scheduler - Loaded.png' });
    await page.waitForTimeout(1000);
    await page.screenshot({ path: 'N-09 Probe Scheduler - Settled.png' });
    await page.screenshot({ path: 'N-09 Probe Scheduler - Interaction.png' });

    // Nav Link N-10: Alert Thresholds
    await page.click('#nav-configure-alerts');
    await page.screenshot({ path: 'N-10 Alert Thresholds - Loaded.png' });
    await page.waitForTimeout(1000);
    await page.screenshot({ path: 'N-10 Alert Thresholds - Settled.png' });
    await page.screenshot({ path: 'N-10 Alert Thresholds - Interaction.png' });

    // Nav Link N-11: Muting Windows
    await page.click('#nav-configure-maintenance');
    await page.screenshot({ path: 'N-11 Muting Windows - Loaded.png' });
    await page.waitForTimeout(1000);
    await page.screenshot({ path: 'N-11 Muting Windows - Settled.png' });
    await page.screenshot({ path: 'N-11 Muting Windows - Interaction.png' });

    // Nav Link N-12: EasyBuilder Tests
    await page.click('#nav-configure-probes');
    await page.screenshot({ path: 'N-12 EasyBuilder Tests - Loaded.png' });
    await page.waitForTimeout(1000);
    await page.screenshot({ path: 'N-12 EasyBuilder Tests - Settled.png' });
    await page.screenshot({ path: 'N-12 EasyBuilder Tests - Interaction.png' });

    // Nav Link N-13: OSI Layer Suite
    await page.click('#nav-configure-osi');
    await page.screenshot({ path: 'N-13 OSI Layer Suite - Loaded.png' });
    await page.waitForTimeout(1000);
    await page.screenshot({ path: 'N-13 OSI Layer Suite - Settled.png' });
    await page.screenshot({ path: 'N-13 OSI Layer Suite - Interaction.png' });

    // Nav Link N-14: Server & TSDB
    await page.click('#nav-setup-server');
    await page.screenshot({ path: 'N-14 Server & TSDB - Loaded.png' });
    await page.waitForTimeout(1000);
    await page.screenshot({ path: 'N-14 Server & TSDB - Settled.png' });
    await page.screenshot({ path: 'N-14 Server & TSDB - Interaction.png' });

    // Nav Link N-15: Alerts & Webhooks
    await page.click('#nav-setup-integrations');
    await page.screenshot({ path: 'N-15 Alerts & Webhooks - Loaded.png' });
    await page.waitForTimeout(1000);
    await page.screenshot({ path: 'N-15 Alerts & Webhooks - Settled.png' });
    await page.screenshot({ path: 'N-15 Alerts & Webhooks - Interaction.png' });

});
