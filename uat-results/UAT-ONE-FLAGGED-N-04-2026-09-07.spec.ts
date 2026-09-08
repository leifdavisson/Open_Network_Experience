import { test, expect } from '@playwright/test';

test('UAT-ONE-FLAGGED-N-04-2026-09-07: Reports & Forensics Evidence Vault Authentication and Polling Inspection', async ({ page }) => {
    const consoleErrors: string[] = [];
    const unauthenticatedEvidenceCalls: string[] = [];

    page.on('console', msg => {
        if (msg.type() === 'error') {
            consoleErrors.push(msg.text());
        }
    });

    page.on('request', request => {
        if (request.url().includes('/api/v1/evidence')) {
            const headers = request.headers();
            if (!headers['x-api-key']) {
                unauthenticatedEvidenceCalls.push(request.url());
            }
        }
    });

    // 1. Navigate to target URL
    await page.goto('http://10.98.2.125:8000/');

    // 2. Pause carousel to prevent background rotation during investigation
    await page.click('#btn-play-pause');
    await page.screenshot({ path: 'uat-results/N-04 - Initial Landing & Paused Carousel.png' });

    // 3. Navigate to Reports & Forensics
    await page.click('#nav-monitor-reports');
    await expect(page.locator('#view-monitor-reports')).toBeVisible();
    await page.screenshot({ path: 'uat-results/N-04 - Reports & Forensics View.png' });

    // 4. Verify initial unauthenticated evidence table state
    const tableBody = page.locator('#evidence-table-body');
    await expect(tableBody).toBeVisible();

    // 5. Navigate to Slide 5 (Grafana NOC Wallboard Embed)
    await page.click('#nav-monitor-noc');
    await page.evaluate(() => {
        if (typeof (window as any).goToSlide === 'function') {
            (window as any).goToSlide(4);
        }
    });
    const grafanaFrame = page.locator('#grafana-embed-frame');
    await expect(grafanaFrame).toBeVisible();
    await page.screenshot({ path: 'uat-results/N-04 - Slide 5 Grafana Embed.png' });

    // 6. Return to Reports & Forensics
    await page.click('#nav-monitor-reports');
    await expect(page.locator('#view-monitor-reports')).toBeVisible();

    // 7. Verify whether background polling sent unauthenticated /api/v1/evidence requests
    console.log('Unauthenticated /api/v1/evidence requests intercepted:', unauthenticatedEvidenceCalls.length);
});
