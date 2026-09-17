#!/usr/bin/env python3
import os

OUTPUT_DIR = "/data/Open_Network_Experience/uat-results"
SPEC_FILE = os.path.join(OUTPUT_DIR, "ONE-NAV-DEEPDIVE.spec.ts")
URL = "http://10.98.2.125:8000/"

NAV_LINKS = [
    ("N-01", "NOC Overview", "#nav-monitor-noc"),
    ("N-02", "GIS Campus Map", "#nav-monitor-map"),
    ("N-03", "Live Diagnostics", "#nav-monitor-ondemand"),
    ("N-04", "Reports & Forensics", "#nav-monitor-reports"),
    ("N-05", "Alert Center", "#nav-monitor-alerts"),
    ("N-06", "Fixed Edge Sensors", "#nav-manage-fleet"),
    ("N-07", "1:1 Chromebooks", "#nav-manage-chromebooks"),
    ("N-08", "Campus Hierarchy", "#nav-manage-locations"),
    ("N-09", "Probe Scheduler", "#nav-configure-schedules"),
    ("N-10", "Alert Thresholds", "#nav-configure-alerts"),
    ("N-11", "Muting Windows", "#nav-configure-maintenance"),
    ("N-12", "EasyBuilder Tests", "#nav-configure-probes"),
    ("N-13", "OSI Layer Suite", "#nav-configure-osi"),
    ("N-14", "Server & TSDB", "#nav-setup-server"),
    ("N-15", "Alerts & Webhooks", "#nav-setup-integrations")
]

lines = [
    "import { test, expect } from '@playwright/test';",
    "",
    "test('UAT-ONE-NAV-DEEPDIVE_2026-09-07', async ({ page, context }) => {",
    f"    // 1. Initial Navigation to ONE Dashboard",
    f"    await page.goto('{URL}');",
    "    await page.screenshot({ path: 'NAV-DEEPDIVE - Before Test.png' });",
    "",
    "    // 2. Pause Carousel State-Aware",
    "    const btnPlayPause = page.locator('#btn-play-pause');",
    "    if (await btnPlayPause.count() > 0) {",
    "        const label = await btnPlayPause.innerText();",
    "        if (label.includes('Pause') || label.includes('⏸')) {",
    "            await btnPlayPause.click();",
    "        }",
    "    }",
    "    await page.screenshot({ path: 'Carousel - Confirmed Paused.png' });",
    "    await page.screenshot({ path: 'NAV - INITIAL SCAN - 2026-09-07.png', fullPage: true });",
    ""
]

for code, name, selector in NAV_LINKS:
    lines.append(f"    // Nav Link {code}: {name}")
    lines.append(f"    await page.click('{selector}');")
    lines.append(f"    await page.screenshot({{ path: '{code} {name} - Loaded.png' }});")
    lines.append(f"    await page.waitForTimeout(1000);")
    lines.append(f"    await page.screenshot({{ path: '{code} {name} - Settled.png' }});")
    lines.append(f"    await page.screenshot({{ path: '{code} {name} - Interaction.png' }});")
    lines.append("")

lines.append("});")
lines.append("")

with open(SPEC_FILE, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"Generated spec with {len(lines)} lines to: {SPEC_FILE}")
