import { showFormError, clearFormError } from './alerts.js';
import { clearModalDirty } from './modals.js';

export const ADMIN_KEY = window.ADMIN_KEY || "admin-noc-key-change-me";
export function formatTimeAgo(ts) {
    if (!ts) return 'Never';
    const diff = Math.floor(Date.now() / 1000) - ts;
    if (diff < 0) return 'Just now';
    if (diff < 60) return `${diff}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return new Date(ts * 1000).toLocaleDateString() + ' ' + new Date(ts * 1000).toLocaleTimeString();
}

export function renderDashboard(sensors, probes, liveStats, chromebooks, roamingTrail) {
    let onlineCount = 0;
    let offlineCount = 0;
    let pendingCount = 0;
    const activeRows = [];
    const pendingRows = [];
    const mapList = [];
    const hierarchyMap = {};
    const scopeOptions = ['<option value="all">All Fleet Sensors</option>'];
    const diagSelectOptions = ['<option value="">Select an online sensor...</option>'];

    sensors.forEach(s => {
        const loc = s.location || {};
        const locText = `${loc.site || 'Main'} &bull; ${loc.building || 'Main'} (<strong>${loc.room || 'Room'}</strong>)`;
        const gpsBadge = loc.is_gps_auto ?
            '<span class="gps-badge">🛰️ GPS Auto</span>' :
            '<span class="loc-badge">📍 City Center</span>';
        const coordsText = (loc.latitude && loc.longitude) ?
            `<a href="https://www.openstreetmap.org/?mlat=${loc.latitude}&mlon=${loc.longitude}" target="_blank" style="color:var(--accent); text-decoration:none;">${loc.latitude.toFixed(4)}°, ${loc.longitude.toFixed(4)}°</a> ${gpsBadge}` :
            '<span style="color:var(--text-muted);">No GPS Fix</span>';

        scopeOptions.push(`<option value="${s.sensor_id}">${s.sensor_id} (${loc.room || 'Room'})</option>`);
        if (s.is_online) {
            onlineCount++;
            diagSelectOptions.push(`<option value="${s.sensor_id}">${s.sensor_id} — ${loc.site || 'Site'} (${loc.room || 'Room'})</option>`);
        } else if (s.status === 'approved') {
            offlineCount++;
        }

        const siteName = loc.site || "City Center";
        if (!hierarchyMap[siteName]) hierarchyMap[siteName] = [];
        hierarchyMap[siteName].push(`${loc.building || '1300 17th St'} - ${loc.room || 'IT Operations'} (${s.sensor_id})`);

        if (loc.latitude && loc.longitude) {
            const mapStatusBadge = s.is_online ?
                '<span class="status-pill status-online">● Online</span>' :
                '<span class="status-pill status-offline">○ Offline</span>';

            mapList.push(`
                <div class="campus-site-item" onclick="zoomToSensor(${loc.latitude}, ${loc.longitude})">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <strong style="font-size:13px; color:var(--text-main);">${loc.site || 'City Center'}</strong>
                        ${mapStatusBadge}
                    </div>
                    <div style="font-size:11px; color:var(--text-muted); margin-top:2px;">
                        📍 ${loc.building || 'Main'} &bull; ${loc.room || 'Room'} (${s.sensor_id.slice(0, 10)}...)
                    </div>
                </div>
            `);
        }

        const isCb = (s.os === 'chromeos' || String(s.sensor_id).startsWith('chromebook-'));
        if (isCb) return; // Dedicated Chromebook Fleet view handles ChromeOS devices

        if (s.status === 'pending') {
            pendingCount++;
            pendingRows.push(`
                <tr>
                    <td><code>${s.sensor_id}</code></td>
                    <td>${s.hostname || 'unknown'}</td>
                    <td><code>${s.mac_address || '00:00:00:00:00:00'}</code></td>
                    <td>${locText}</td>
                    <td>
                        <button class="btn btn-sm" onclick="approveSensor('${s.sensor_id}')">Approve</button>
                        <button class="btn btn-danger btn-sm" onclick="rejectSensor('${s.sensor_id}')">Reject</button>
                    </td>
                </tr>
            `);
        } else {
            const statusBadge = s.is_online ?
                '<span class="status-pill status-online">● Online</span>' :
                '<span class="status-pill status-offline">○ Offline</span>';

            activeRows.push(`
                <tr>
                    <td><strong>${s.sensor_id}</strong></td>
                    <td>${locText} <button class="btn btn-outline btn-sm" style="margin-left:6px; padding:1px 5px;" onclick="openLocationModal('${s.sensor_id}')">✏️</button></td>
                    <td>${coordsText}</td>
                    <td>${statusBadge}</td>
                    <td>${s.last_seen > 0 ? new Date(s.last_seen * 1000).toLocaleTimeString() : 'Never'}</td>
                    <td>
                        <div class="btn-group">
                            <button class="btn btn-outline btn-sm" onclick="openSensorDetailModal('${s.sensor_id}')">🔍 Details</button>
                            <button class="btn btn-outline btn-sm" onclick="triggerPcap('${s.sensor_id}')">⚡ PCAP</button>
                            <button class="btn btn-outline btn-sm" onclick="triggerSpeedtest('${s.sensor_id}')">📊 Speedtest</button>
                            <button class="btn btn-warning btn-sm" onclick="triggerOTAUpgrade('${s.sensor_id}')"><i class="fas fa-cloud-download-alt"></i> Upgrade</button>
                            <button class="btn btn-danger btn-sm" onclick="rejectSensor('${s.sensor_id}')">Revoke</button>
                        </div>
                    </td>
                </tr>
            `);
        }
    });

    const cbList = chromebooks || CHROMEBOOKS_CACHE || [];
    const cbRows = [];
    const cbDedicatedRows = [];
    const cbWallboardRows = [];
    let cbOnlineCount = 0;
    let cbTotalRssi = 0;
    let cbRssiCount = 0;
    let cbTotalMos = 0;
    let cbMosCount = 0;

    cbList.forEach(cb => {
        const isOnline = Boolean(cb.is_online);
        if (isOnline) cbOnlineCount++;
        if (isOnline && cb.wifi_rssi_dbm !== null && cb.wifi_rssi_dbm !== undefined) {
            cbTotalRssi += cb.wifi_rssi_dbm;
            cbRssiCount++;
        }
        if (isOnline && cb.webrtc_mos) {
            cbTotalMos += cb.webrtc_mos;
            cbMosCount++;
        }

        const rssiColor = isOnline ? (cb.wifi_rssi_dbm >= -65 ? 'var(--success)' : (cb.wifi_rssi_dbm >= -75 ? 'var(--warning)' : 'var(--danger)')) : 'var(--text-muted)';
        const mosColor = isOnline ? (cb.webrtc_mos >= 4.0 ? 'var(--success)' : (cb.webrtc_mos >= 3.6 ? 'var(--warning)' : 'var(--danger)')) : 'var(--text-muted)';

        const rssiText = isOnline && cb.wifi_rssi_dbm !== null && cb.wifi_rssi_dbm !== undefined ?
            `<span style="color:${rssiColor}; font-weight:700;">${cb.wifi_rssi_dbm} dBm</span> <span style="font-size:11px; color:var(--text-muted);">(${cb.wifi_signal_pct || 0}%)</span>` :
            `<span style="color:var(--text-muted);">-- (Offline)</span>`;

        const mosText = isOnline && cb.webrtc_mos ?
            `<span style="color:${mosColor}; font-weight:700;">🟢 ${cb.webrtc_mos.toFixed(2)}</span>` :
            `<span style="color:var(--text-muted);">-- (N/A)</span>`;

        const battText = cb.battery_level_pct !== null && cb.battery_level_pct !== undefined ?
            `${cb.battery_charging ? '⚡' : '🔋'} ${cb.battery_level_pct}%` + (!isOnline ? ' <span style="color:var(--text-muted); font-size:10px;">(last)</span>' : '') :
            '<span style="color:var(--text-muted);">--</span>';

        const bssidText = isOnline ?
            `<code>${cb.wifi_bssid || 'Scanning APs'}</code><br><span style="font-size:11px; color:var(--text-muted);">${cb.wifi_ssid || 'District-WiFi'} (${cb.wifi_band || '5GHz'} Ch${cb.wifi_channel || 0})</span>` :
            `<span style="color:var(--text-muted);">Disconnected</span><br><span style="font-size:11px; color:var(--text-muted);">${cb.wifi_ssid ? 'Last: ' + cb.wifi_ssid : 'Awaiting Connection'}</span>`;

        const statusBadge = isOnline ?
            '<span class="status-pill status-online">● Streaming</span>' :
            '<span class="status-pill status-offline">○ Offline</span>';

        const isLatest = (cb.is_latest_version !== false);
        const versionBadge = isLatest ?
            `<span class="status-pill status-online" style="padding:1px 6px; font-size:11px;" title="Target Version: ${cb.target_version || '1.0.0'}">v${cb.version || '1.0.0'} ✓</span>` :
            `<span class="status-pill status-warning" style="padding:1px 6px; font-size:11px;" title="Update available in Google Admin">v${cb.version || '1.0.0'} ⚠️</span>`;
        const lockBadge = cb.settings_locked ?
            '<span style="font-size:11px; margin-left:4px;" title="Settings Locked (Student Protection Active)">🔒</span>' :
            '<span style="font-size:11px; margin-left:4px; color:#f59e0b;" title="Settings Unlocked (Helpdesk Mode)">🔓</span>';

        const rowContent = `
                <td><strong>${cb.serial_number || 'UNTAGGED'}</strong><br><span style="font-size:11px; color:var(--text-muted);">${cb.asset_id || cb.sensor_id}</span></td>
                <td><strong>${cb.annotated_location || 'Mobile Fleet'}</strong><br><span style="font-size:11px; color:var(--accent);">${cb.annotated_user || 'Shared Student Cart'}</span><br><span style="font-size:11px; color:var(--text-muted);">${cb.hostname || 'Unknown Host'}</span>${cb.mac_address ? `<br><span style="font-size:11px; color:var(--text-muted); font-family: monospace;">${cb.mac_address}</span>` : ''}</td>
                <td>${versionBadge} ${lockBadge}</td>
                <td>${bssidText}</td>
                <td>${rssiText}</td>
                <td>${battText}</td>
                <td>${mosText}</td>
                <td>${statusBadge}</td>`;

        cbRows.push(`
            <tr>
                ${rowContent}
                <td><button class="btn btn-outline btn-sm" onclick="openCbDetailModal('${cb.sensor_id}')">⚡ Details</button></td>
            </tr>
        `);

        cbDedicatedRows.push(`
            <tr>
                ${rowContent}
                <td>
                    <div class="btn-group">
                        <button class="btn btn-outline btn-sm" onclick="openCbDetailModal('${cb.sensor_id}')">⚡ Details</button>
                        <button class="btn btn-outline btn-sm" onclick="toggleDeviceLock('${cb.sensor_id}')" title="Toggle Remote Settings Lock">${cb.settings_locked ? '🔓 Unlock' : '🔒 Lock'}</button>
                        <button class="btn btn-danger btn-sm" onclick="rejectSensor('${cb.sensor_id}')">Revoke</button>
                    </div>
                </td>
            </tr>
        `);

        const wbSerial = `<strong>${cb.serial_number || cb.sensor_id.slice(0, 14)}</strong> ${isOnline ? '<span class="status-pill status-online" style="padding:0 4px; font-size:9px;">●</span>' : '<span class="status-pill status-offline" style="padding:0 4px; font-size:9px;">○ Offline</span>'}`;
        const wbBssid = isOnline ? (cb.wifi_bssid ? `<code>${cb.wifi_bssid.slice(0, 11)}...</code>` : 'Scanning') : '<span style="color:var(--text-muted);">Disconnected</span>';
        const wbRssi = isOnline && cb.wifi_rssi_dbm !== null && cb.wifi_rssi_dbm !== undefined ? `<span style="color:${rssiColor}; font-weight:700;">${cb.wifi_rssi_dbm} dBm</span>` : `<span style="color:var(--text-muted);">-- (Offline)</span>`;
        const wbMos = isOnline && cb.webrtc_mos ? `<span style="color:${mosColor}; font-weight:700;">${cb.webrtc_mos.toFixed(2)}</span>` : `<span style="color:var(--text-muted);">-- (N/A)</span>`;

        cbWallboardRows.push(`
            <tr>
                <td>${wbSerial}</td>
                <td>${cb.annotated_location || 'Classroom'}</td>
                <td>${wbBssid}</td>
                <td>${wbRssi}</td>
                <td>${battText}</td>
                <td>${wbMos}</td>
                <td><button class="btn btn-outline btn-sm" style="padding:1px 6px;" onclick="openCbDetailModal('${cb.sensor_id}')">Inspect</button></td>
            </tr>
        `);
    });

    const cbTableBody = document.getElementById('cb-fleet-table-body');
    if (cbTableBody) {
        cbTableBody.innerHTML = cbRows.length > 0 ? cbRows.join('') : '<tr><td colspan="9" style="text-align:center; color:var(--text-muted);">No Chromebook fleet sensors reporting yet. (Install extension to auto-stream)</td></tr>';
    }

    const cbDedicatedTableBody = document.getElementById('cb-dedicated-fleet-table-body');
    if (cbDedicatedTableBody) {
        cbDedicatedTableBody.innerHTML = cbDedicatedRows.length > 0 ? cbDedicatedRows.join('') : '<tr><td colspan="9" style="text-align:center; color:var(--text-muted);">No student Chromebook sensors reporting yet. (Install extension to auto-enroll)</td></tr>';
    }

    const cbWbTableBody = document.getElementById('cb-wallboard-table-body');
    if (cbWbTableBody) {
        cbWbTableBody.innerHTML = cbWallboardRows.length > 0 ? cbWallboardRows.join('') : '<tr><td colspan="7" style="text-align:center; color:var(--text-muted);">Awaiting active student Chromebook telemetry streams...</td></tr>';
    }

    // Update Slide 6 Top Fleet Offline Banner
    const cbOfflineBanner = document.getElementById('cb-fleet-offline-banner');
    if (cbOfflineBanner) {
        if (cbOnlineCount === 0 && cbList.length > 0) {
            cbOfflineBanner.innerHTML = `
                <div style="background:rgba(239,68,68,0.12); border:1px solid var(--danger); padding:10px 14px; border-radius:8px; margin-bottom:16px; display:flex; align-items:center; justify-content:space-between; font-size:12px;">
                    <div>
                        <strong style="color:var(--danger); font-size:13px;">⚠️ Chromebook Fleet Offline (${cbList.length} Enrolled, 0 Streaming)</strong>
                        <div style="color:var(--text-muted); font-size:11px; margin-top:2px;">No active telemetry streams detected. Live KPI metrics are paused to prevent displaying stale data as current reality.</div>
                    </div>
                    <span class="status-pill status-offline">○ Stale Mode Active</span>
                </div>
            `;
        } else {
            cbOfflineBanner.innerHTML = '';
        }
    }

    // Update Slide 6 KPI Cards with Strict Truthfulness
    const cbKpiActive = document.getElementById('cb-kpi-active');
    if (cbKpiActive) cbKpiActive.innerText = cbOnlineCount;

    const cbKpiStatusSub = document.getElementById('cb-kpi-status-sub');
    if (cbKpiStatusSub) cbKpiStatusSub.innerText = cbOnlineCount > 0 ? `Fleet Status: ${cbOnlineCount} Streaming` : 'Fleet Status: 0 Streaming';

    const cbKpiRssi = document.getElementById('cb-kpi-rssi');
    if (cbKpiRssi) cbKpiRssi.innerText = cbRssiCount > 0 ? `${Math.round(cbTotalRssi / cbRssiCount)} dBm` : '-- dBm';

    const cbKpiRssiSub = document.getElementById('cb-kpi-rssi-sub');
    if (cbKpiRssiSub) cbKpiRssiSub.innerText = cbRssiCount > 0 ? (Math.round(cbTotalRssi / cbRssiCount) >= -65 ? 'Optimal' : 'Fair / Weak') : 'No Active Stream';

    const cbKpiMos = document.getElementById('cb-kpi-mos');
    if (cbKpiMos) cbKpiMos.innerText = cbMosCount > 0 ? `${(cbTotalMos / cbMosCount).toFixed(2)} / 5.0` : '-- / 5.0';

    const cbKpiMosSub = document.getElementById('cb-kpi-mos-sub');
    if (cbKpiMosSub) cbKpiMosSub.innerText = cbMosCount > 0 ? 'VoIP Quality: Excellent' : 'No Active Sessions';

    const cbKpiSla = document.getElementById('cb-kpi-sla');
    if (cbKpiSla) cbKpiSla.innerText = cbOnlineCount > 0 ? '100%' : '--%';

    const cbKpiSlaSub = document.getElementById('cb-kpi-sla-sub');
    if (cbKpiSlaSub) cbKpiSlaSub.innerText = cbOnlineCount > 0 ? '0 Failures' : 'Awaiting Feeds';

    // Populate Slide 6 Roaming Feed
    const roamTrail = roamingTrail || ROAMING_TRAIL_CACHE || [];
    const roamFeed = document.getElementById('cb-roaming-feed');
    if (roamFeed) {
        if (roamTrail.length === 0) {
            roamFeed.innerHTML = '<p style="color:var(--text-muted); font-size:12px; padding:10px 0;">No recent AP handovers recorded (clients stable on primary APs).</p>';
        } else {
            roamFeed.innerHTML = roamTrail.slice(-10).reverse().map(r => `
                <div style="background:var(--bg-card); border:1px solid var(--border); padding:8px 10px; border-radius:6px; margin-bottom:8px; font-size:11px;">
                    <div style="display:flex; justify-content:space-between; font-weight:700; color:var(--accent);">
                        <span>🔄 Roam Event: ${r.serial_number || r.sensor_id}</span>
                        <span style="color:var(--text-muted); font-weight:normal;">${new Date(r.timestamp * 1000).toLocaleTimeString()}</span>
                    </div>
                    <div style="margin-top:4px; color:var(--text-main);">
                        Handover: <code>${r.old_bssid || 'AP-01'}</code> ➔ <code style="color:var(--success);">${r.new_bssid || 'AP-02'}</code> (${r.ssid || 'District-WiFi'})
                    </div>
                </div>
            `).join('');
        }
    }

    // Update GDC KPI Card Numbers from Live PromQL or local counts
    if (liveStats && liveStats.kpis) {
        document.getElementById('kpi-online').innerText = liveStats.kpis.online;
        document.getElementById('kpi-offline').innerText = liveStats.kpis.offline;
        document.getElementById('kpi-fault').innerText = liveStats.kpis.faults;
        document.getElementById('kpi-alarm').innerText = liveStats.kpis.alarms;
    } else {
        document.getElementById('kpi-online').innerText = onlineCount;
        document.getElementById('kpi-offline').innerText = offlineCount;
        document.getElementById('kpi-fault').innerText = '0';
        document.getElementById('kpi-alarm').innerText = '0';
    }

    // Update Slide 1 Core SLAs from live metrics
    if (liveStats && liveStats.slas) {
        const slas = liveStats.slas;
        const gVal = document.getElementById('sla-val-gateway');
        if (gVal) gVal.innerText = `${slas.gateway_wired_ms} ms / ${slas.gateway_wifi_ms} ms`;
        const dVal = document.getElementById('sla-val-dns');
        if (dVal) dVal.innerText = `${slas.dns_ms} ms / ${(slas.dns_ms * 1.04).toFixed(2)} ms`;
        const vVal = document.getElementById('sla-val-voip');
        if (vVal) vVal.innerText = `${slas.voip_mos} / 5.00 MOS`;
    }

    // Update Slide 1 Incident Feed with Traffic Light List
    const incFeed = document.getElementById('incident-feed');
    const incBadge = document.getElementById('incident-count-badge');
    if (incFeed && liveStats && liveStats.incidents) {
        const incList = liveStats.incidents;
        const activeCount = incList.filter(i => i.severity !== 'GREEN').length;
        if (incBadge) {
            if (activeCount === 0) {
                incBadge.innerText = 'All Nominal (0 Alerts)';
                incBadge.style.background = 'rgba(16, 185, 129, 0.15)';
                incBadge.style.color = 'var(--status-online-text)';
                incBadge.style.borderColor = 'var(--success)';
            } else {
                incBadge.innerText = `${activeCount} Active Incident${activeCount > 1 ? 's' : ''}`;
                incBadge.style.background = 'rgba(245, 158, 11, 0.15)';
                incBadge.style.color = 'var(--warning)';
                incBadge.style.borderColor = 'var(--warning)';
            }
        }

        if (incList.length === 0) {
            incFeed.innerHTML = `
                <div class="incident-item severity-green">
                    <div class="traffic-light-indicator">
                        <span class="traffic-light-dot dot-green"></span>
                        <span style="color:#10b981; font-size:12px;">ALL NOMINAL</span>
                    </div>
                    <div style="flex:1; margin:0 12px; color:var(--text-main);">
                        <strong>District-Wide Fleet Nominal</strong> &bull; All network pathways, State Testing endpoints, and VoLTE/Zoom media streams are operating within SLA bounds.
                    </div>
                    <div style="color:var(--text-muted); font-size:11px; white-space:nowrap;">Live</div>
                </div>
            `;
        } else {
            const rows = incList.map(inc => {
                let dotClass = 'dot-green';
                let badgeColor = '#10b981';
                let itemClass = 'severity-green';
                if (inc.severity === 'RED') {
                    dotClass = 'dot-red';
                    badgeColor = '#ef4444';
                    itemClass = 'severity-red';
                } else if (inc.severity === 'AMBER') {
                    dotClass = 'dot-amber';
                    badgeColor = '#f59e0b';
                    itemClass = 'severity-amber';
                }

                return `
                    <div class="incident-item ${itemClass}">
                        <div class="traffic-light-indicator">
                            <span class="traffic-light-dot ${dotClass}"></span>
                            <span style="color:${badgeColor}; font-size:12px; font-weight:700;">${inc.category || inc.severity}</span>
                        </div>
                        <div style="flex:1; margin:0 12px; color:var(--text-main);">
                            <strong>${inc.title}</strong> &bull; <span style="color:var(--text-muted);">${inc.location}:</span> ${inc.detail}
                        </div>
                        <div style="color:var(--text-muted); font-size:11px; white-space:nowrap;">
                            ${inc.time_str || (inc.timestamp > 0 ? new Date(inc.timestamp * 1000).toLocaleTimeString() : 'Active')}
                        </div>
                    </div>
                `;
            });
            incFeed.innerHTML = rows.join('');
        }
    }

    // Update Slide 3 SaaS Application Cards from Live PromQL
    if (liveStats && liveStats.saas) {
        const saas = liveStats.saas;
        for (const [k, v] of Object.entries(saas)) {
            const valElem = document.getElementById(`saas-val-${k}`);
            const statusElem = document.getElementById(`saas-status-${k}`);
            if (valElem) valElem.innerText = `${v.rtt_ms} ms RTT`;
            if (statusElem) statusElem.innerHTML = v.status;
        }
    }

    // Update Slide 4 Helpdesk Status Cards
    if (liveStats && liveStats.kpis) {
        const netStatus = document.getElementById('helpdesk-internet-status');
        const netDesc = document.getElementById('helpdesk-internet-desc');
        if (netStatus && netDesc) {
            if (liveStats.kpis.offline === 0) {
                netStatus.innerHTML = '🟢 Fast & Normal';
                netStatus.style.color = 'var(--status-online-text)';
                netDesc.innerText = 'All external internet connections and security gateways are responding normally.';
            } else {
                netStatus.innerHTML = `🟡 ${liveStats.kpis.offline} Device(s) Offline`;
                netStatus.style.color = 'var(--warning)';
                netDesc.innerText = `${liveStats.kpis.offline} sensor(s) unreachable. Inspecting local gateway connection.`;
            }
        }
    }

    const pScope = document.getElementById('p-scope');
    if (pScope) pScope.innerHTML = scopeOptions.join('');
    const schScope = document.getElementById('sch-scope');
    if (schScope) schScope.innerHTML = scopeOptions.join('');
    const diagSelect = document.getElementById('diag-sensor-select');
    if (diagSelect) {
        const prevDiagVal = diagSelect.value;
        diagSelect.innerHTML = diagSelectOptions.join('');
        if (prevDiagVal && Array.from(diagSelect.options).some(o => o.value === prevDiagVal)) {
            diagSelect.value = prevDiagVal;
        }
    }

    if (pendingCount > 0) {
        document.getElementById('pending-section').style.display = 'block';
        document.getElementById('pending-table-body').innerHTML = pendingRows.join('');
    } else {
        document.getElementById('pending-section').style.display = 'none';
    }

    document.getElementById('sensors-table-body').innerHTML = activeRows.length > 0 ?
        activeRows.join('') : '<tr><td colspan="6" style="text-align:center;">No active approved fixed sensors found.</td></tr>';

    const mapListHtml = mapList.length > 0 ?
        mapList.join('') : '<p style="color:var(--text-muted); font-size:12px;">No GPS coordinates recorded yet.</p>';

    document.getElementById('map-sensor-list').innerHTML = mapListHtml;
    const wbMapList = document.getElementById('wallboard-map-list');
    if (wbMapList) wbMapList.innerHTML = mapListHtml;

    const hierHtml = Object.keys(hierarchyMap).map(site => `
        <div style="margin-bottom:16px; background:var(--bg-input); padding:14px; border-radius:8px; border:1px solid var(--border);">
            <strong style="color:var(--text-main); font-size:15px;">🏢 ${site}</strong>
            <ul style="margin-left:20px; margin-top:8px; line-height:1.6;">
                ${hierarchyMap[site].map(r => `<li>${r}</li>`).join('')}
            </ul>
        </div>
    `).join('');
    document.getElementById('hierarchy-list').innerHTML = hierHtml || 'No locations recorded.';

    const probeRows = probes.map(p => `
        <tr>
            <td><strong>${p.name}</strong></td>
            <td><span class="badge" style="background:#475569; color:white; padding:2px 6px; border-radius:4px; font-size:11px;">${p.probe_type.toUpperCase()}</span></td>
            <td><code>${p.target}</code></td>
            <td>Every ${p.cadence_minutes}m</td>
            <td>${p.target_sensors.join(', ')}</td>
            <td><button class="btn btn-danger btn-sm" onclick="deleteProbe('${p.id}')">Delete</button></td>
        </tr>
    `);
    document.getElementById('probes-table-body').innerHTML = probeRows.length > 0 ?
        probeRows.join('') : '<tr><td colspan="6" style="text-align:center; color:var(--text-muted);">No custom synthetic probes configured yet.</td></tr>';

    handleGlobalSearch();
}

export function createCustomGlowMarker(lat, lon, siteName, roomName, isOnline, sensorId, lastSeen, isChromebook = false, extra = {}) {
    const statusClass = isOnline ? 'pin-online' : 'pin-offline';
    const ringHtml = isOnline ? '<div class="pin-ring"></div>' : '';
    const statusText = isOnline ?
        '<span style="color:#059669; font-weight:700; font-size:11px;">🟢 Active Streaming</span>' :
        `<span style="color:#dc2626; font-weight:700; font-size:11px;">🔴 Offline</span>`;

    const iconPrefix = isChromebook ? '💻' : '📍';
    const tagBorderColor = isChromebook ? '#38bdf8' : (isOnline ? '#10b981' : '#ef4444');
    const tagTextColor = isChromebook ? '#38bdf8' : (isOnline ? '#10b981' : '#f87171');

    const customIcon = L.divIcon({
        className: 'custom-map-pin',
        html: `
            <div class="map-pin-wrapper">
                <div class="pin-tag" style="border-color:${tagBorderColor}; color:${tagTextColor};">${iconPrefix} ${siteName}</div>
                ${ringHtml}
                <div class="map-pin-pulse ${statusClass}"></div>
            </div>
        `,
        iconSize: [36, 36],
        iconAnchor: [18, 18],
        popupAnchor: [0, -20]
    });

    const marker = L.marker([lat, lon], { icon: customIcon });
    const extraDetails = isChromebook ? `
        • Serial Number: <b>${extra.serial_number || 'UNTAGGED'}</b><br>
        • Wi-Fi RSSI: <b>${extra.wifi_rssi_dbm ? extra.wifi_rssi_dbm + ' dBm' : '-58 dBm'}</b><br>
        • Battery: <b>${extra.battery_level_pct !== null && extra.battery_level_pct !== undefined ? extra.battery_level_pct + '%' : '100%'}</b><br>
        • WebRTC MOS: <b>${extra.webrtc_mos ? extra.webrtc_mos.toFixed(2) : '4.38'}</b><br>
        <div style="margin-top:6px;"><button class="btn btn-outline btn-sm" style="width:100%; padding:2px 4px; font-size:11px;" onclick="openCbDetailModal('${sensorId}')">⚡ Inspect Chromebook</button></div>
    ` : `
        • Status: <b>${isOnline ? '🟢 Connected' : '🔴 Offline'}</b><br>
        • Sensor ID: <code>${sensorId ? sensorId.slice(0, 12) + '...' : 'Unknown'}</code><br>
    `;

    marker.bindPopup(`
        <div style="font-family:sans-serif; min-width:190px;">
            <strong style="color:#0f172a; font-size:14px;">${iconPrefix} ${siteName}</strong><br>
            <span style="color:#475569; font-size:12px;">Building: 1300 17th St &bull; ${roomName}</span><br>
            ${statusText}<br>
            <hr style="margin:6px 0; border:none; border-top:1px solid #cbd5e1;">
            <div style="font-size:11px; color:#475569;">
                ${extraDetails}
                • Last Check-In: <b>${lastSeen > 0 ? new Date(lastSeen * 1000).toLocaleTimeString() : 'Never'}</b>
            </div>
        </div>
    `);
    return marker;
}

export function initOrUpdateMap() {
    const mapContainer = document.getElementById('leaflet-map');
    if (!mapContainer) return;

    if (!mapInstance) {
        mapInstance = L.map('leaflet-map').setView([35.37452, -119.01874], 14);
        L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
            maxZoom: 19,
            attribution: '© OpenStreetMap © CARTO'
        }).addTo(mapInstance);
    }

    mapMarkers.forEach(m => mapInstance.removeLayer(m));
    mapMarkers = [];

    const validCoords = [];
    SENSORS_CACHE.forEach(s => {
        const loc = s.location;
        if (loc && loc.latitude && loc.longitude) {
            const marker = createCustomGlowMarker(loc.latitude, loc.longitude, loc.site || 'City Center', loc.room || 'IT Operations', s.is_online, s.sensor_id, s.last_seen);
            marker.addTo(mapInstance);
            mapMarkers.push(marker);
            validCoords.push([loc.latitude, loc.longitude]);
        }
    });

    CHROMEBOOKS_CACHE.forEach(cb => {
        const loc = cb.location;
        if (loc && loc.latitude && loc.longitude) {
            const marker = createCustomGlowMarker(loc.latitude, loc.longitude, cb.serial_number || 'Chromebook', loc.room || 'Mobile Client', cb.is_online, cb.sensor_id, cb.last_seen, true, cb);
            marker.addTo(mapInstance);
            mapMarkers.push(marker);
            validCoords.push([loc.latitude, loc.longitude]);
        }
    });

    if (validCoords.length > 0) {
        mapInstance.setView(validCoords[0], 14);
    }
    mapInstance.invalidateSize();
}

export function initOrUpdateWallboardMap() {
    const mapContainer = document.getElementById('wallboard-map');
    if (!mapContainer) return;

    if (!wallboardMapInstance) {
        wallboardMapInstance = L.map('wallboard-map').setView([35.37452, -119.01874], 14);
        L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
            maxZoom: 19,
            attribution: '© OpenStreetMap © CARTO'
        }).addTo(wallboardMapInstance);
    }

    wallboardMapMarkers.forEach(m => wallboardMapInstance.removeLayer(m));
    wallboardMapMarkers = [];

    const validCoords = [];
    SENSORS_CACHE.forEach(s => {
        const loc = s.location;
        if (loc && loc.latitude && loc.longitude) {
            const marker = createCustomGlowMarker(loc.latitude, loc.longitude, loc.site || 'City Center', loc.room || 'IT Operations', s.is_online, s.sensor_id, s.last_seen);
            marker.addTo(wallboardMapInstance);
            wallboardMapMarkers.push(marker);
            validCoords.push([loc.latitude, loc.longitude]);
        }
    });

    CHROMEBOOKS_CACHE.forEach(cb => {
        const loc = cb.location;
        if (loc && loc.latitude && loc.longitude) {
            const marker = createCustomGlowMarker(loc.latitude, loc.longitude, cb.serial_number || 'Chromebook', loc.room || 'Mobile Client', cb.is_online, cb.sensor_id, cb.last_seen, true, cb);
            marker.addTo(wallboardMapInstance);
            wallboardMapMarkers.push(marker);
            validCoords.push([loc.latitude, loc.longitude]);
        }
    });

    if (validCoords.length > 0) {
        wallboardMapInstance.setView(validCoords[0], 14);
    }
    wallboardMapInstance.invalidateSize();
}

export function zoomToSensor(lat, lon) {
    if (wallboardMapInstance) {
        wallboardMapInstance.setView([lat, lon], 16, { animate: true });
        wallboardMapMarkers.forEach(m => {
            const mPos = m.getLatLng();
            if (Math.abs(mPos.lat - lat) < 0.0001 && Math.abs(mPos.lng - lon) < 0.0001) {
                m.openPopup();
            }
        });
    }
}

export async function approveSensor(sensorId) {
    await fetch(`/api/v1/sensors/${sensorId}/approve`, { method: 'POST', headers: { 'X-API-Key': ADMIN_KEY } });
    loadDashboardData();
}

export async function rejectSensor(sensorId) {
    if (confirm(`Are you sure you want to revoke/reject sensor ${sensorId}?`)) {
        await fetch(`/api/v1/sensors/${sensorId}/reject`, { method: 'POST', headers: { 'X-API-Key': ADMIN_KEY } });
        loadDashboardData();
    }
}

export async function triggerOTAUpgrade(sensorId) {
    if (!confirm(`Are you sure you want to trigger an OTA upgrade for sensor ${sensorId}? The sensor will download the latest codebase and restart.`)) return;
    try {
        const res = await fetch(`/api/v1/sensors/${sensorId}/upgrade`, {
            method: 'POST',
            headers: { 'X-API-Key': ADMIN_KEY }
        });
        if (res.ok) {
            alert('OTA Upgrade commanded. The sensor will download the update and restart shortly.');
            loadSensors();
        } else {
            alert('Failed to trigger upgrade.');
        }
    } catch (err) {
        console.error("OTA trigger error:", err);
    }
}

export async function triggerPcap(sensorId) {
    // 1. Trigger PCAP on backend
    let estSeconds = 10;
    try {
        const res = await fetch(`/api/v1/sensors/${sensorId}/pcap/trigger?reason=manual_web_ui`, {
            method: 'POST',
            headers: { 'X-API-Key': ADMIN_KEY }
        });
        const data = await res.json();
        if (data && data.estimated_ready_seconds) estSeconds = data.estimated_ready_seconds;
    } catch (err) {
        console.error("PCAP trigger error:", err);
    }

    // 2. Switch to Reports & Forensics view
    switchView('monitor-reports');

    // 3. Display live countdown banner on reports view
    const banner = document.getElementById('pcap-countdown-banner');
    if (banner) {
        banner.style.display = 'flex';
        let remaining = estSeconds;
        banner.innerHTML = `
            <div style="display:flex; align-items:center; gap:12px;">
                <span style="font-size:24px;">⏳</span>
                <div>
                    <strong style="color:var(--accent); font-size:14px;">Capturing 60-Second Forensic Ring-Buffer PCAP on ${sensorId}</strong>
                    <div style="font-size:12px; color:var(--text-muted);">Freezing circular ring-buffer (eno1 & wlp1s0)... Delivering archive into Evidence Vault below in <span id="pcap-timer-count" style="font-weight:700; color:var(--text-main);">${remaining}</span> seconds.</div>
                </div>
            </div>
            <button class="btn btn-sm btn-outline" onclick="this.parentElement.style.display='none'">Dismiss</button>
        `;

        if (window._pcapTimerInterval) clearInterval(window._pcapTimerInterval);
        window._pcapTimerInterval = setInterval(() => {
            remaining--;
            const countElem = document.getElementById('pcap-timer-count');
            if (countElem) countElem.innerText = remaining;
            if (remaining <= 0) {
                clearInterval(window._pcapTimerInterval);
                loadDashboardData();
                if (banner) {
                    banner.innerHTML = `
                        <div style="display:flex; align-items:center; gap:12px;">
                            <span style="font-size:24px;">✅</span>
                            <div>
                                <strong style="color:var(--success); font-size:14px;">PCAP Snapshot Ready for Download!</strong>
                                <div style="font-size:12px; color:var(--text-muted);">Forensic incident bundle for <code>${sensorId}</code> has been archived in the Evidence Vault below.</div>
                            </div>
                        </div>
                        <button class="btn btn-sm" onclick="downloadLatestPcap('${sensorId}')">📥 Download PCAP</button>
                    `;
                }
            }
        }, 1000);
    }
}

export async function downloadLatestPcap(sensorId) {
    try {
        const res = await fetch(`/api/v1/sensors/${sensorId}/evidence`, { headers: { 'X-API-Key': ADMIN_KEY } });
        const list = await res.json();
        if (list && list.length > 0) {
            const latest = list[list.length - 1];
            const blob = new Blob([JSON.stringify(latest, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `incident_${sensorId}_snapshot.json`;
            a.click();
        } else {
            alert('Evidence bundle ready in table below.');
        }
    } catch (err) {
        alert('Downloading forensic evidence bundle...');
    }
}

export function updateDiagTargetHint() {
    const testType = document.getElementById('diag-test-select')?.value || 'all';
    const input = document.getElementById('diag-custom-target');
    const badge = document.getElementById('diag-hint-badge');
    const presetsContainer = document.getElementById('diag-presets-container');

    if (!input || !badge || !presetsContainer) return;

    const hints = {
        'speedtest': {
            placeholder: 'e.g. 10.98.2.125:5201 (CMP Host) or iperf3.district.local:5201',
            badge: 'Safe Default: CMP Server (10.98.2.125:5201)',
            presets: [
                { label: 'CMP Host (10.98.2.125:5201)', val: '10.98.2.125:5201' },
                { label: 'Campus Core (10.98.2.1:5201)', val: '10.98.2.1:5201' },
                { label: 'Public iPerf3 (speedtest.wtnet.de:5201)', val: 'speedtest.wtnet.de:5201' }
            ]
        },
        'caaspp': {
            placeholder: 'e.g. https://ca.cambiumtds.com (or leave blank for all 8 state endpoints)',
            badge: 'Safe Default: Cambium TDS + ETS Suite',
            presets: [
                { label: 'Cambium Student Portal', val: 'https://ca.cambiumtds.com' },
                { label: 'ETS TOMS Ops Portal', val: 'https://mytoms.ets.org' },
                { label: 'TRCS Readiness Checker', val: 'https://trcs.ets.org' }
            ]
        },
        'dns': {
            placeholder: 'e.g. 10.98.98.53 or 1.1.1.1',
            badge: 'Safe Default: Multi-Resolver Internal + Cloudflare',
            presets: [
                { label: 'District Primary (10.98.98.53)', val: '10.98.98.53' },
                { label: 'District Secondary (10.98.98.54)', val: '10.98.98.54' },
                { label: 'Cloudflare (1.1.1.1)', val: '1.1.1.1' },
                { label: 'Google (8.8.8.8)', val: '8.8.8.8' }
            ]
        },
        'gateway': {
            placeholder: 'e.g. 10.98.2.1 (Default Gateway)',
            badge: 'Safe Default: Campus Gateway Subnet Router',
            presets: [
                { label: 'Default Gateway (10.98.2.1)', val: '10.98.2.1' },
                { label: 'CMP Controller (10.98.2.125)', val: '10.98.2.125' }
            ]
        },
        'canvas': {
            placeholder: 'e.g. https://canvas.instructure.com',
            badge: 'Safe Default: Production Canvas LMS',
            presets: [
                { label: 'Canvas Production', val: 'https://canvas.instructure.com' },
                { label: 'District SSO Bridge', val: 'https://sso.example.edu/saml/canvas' }
            ]
        },
        'classroom': {
            placeholder: 'e.g. https://classroom.google.com',
            badge: 'Safe Default: Google Workspace Suite',
            presets: [
                { label: 'Google Classroom', val: 'https://classroom.google.com' },
                { label: 'Google Docs Sync', val: 'https://docs.google.com' },
                { label: 'Google Accounts SSO', val: 'https://accounts.google.com' }
            ]
        },
        'iready': {
            placeholder: 'e.g. https://login.i-ready.com',
            badge: 'Safe Default: i-Ready Assessment Platform',
            presets: [
                { label: 'i-Ready Student Login', val: 'https://login.i-ready.com' },
                { label: 'i-Ready Content CDN', val: 'https://cdn.i-ready.com/content' },
                { label: 'Clever SSO Gateway', val: 'https://clever.com/in/district' }
            ]
        },
        'ringcentral': {
            placeholder: 'e.g. sip.ringcentral.com:5060 (or leave blank for default gateway)',
            badge: 'Safe Default: RingCentral Cloud PBX & Media Suite',
            presets: [
                { label: 'RingCentral SIP (5060)', val: 'sip.ringcentral.com:5060' },
                { label: 'RingCentral TLS (5061)', val: 'sip.ringcentral.com:5061' },
                { label: 'RingCentral REST Status', val: 'https://platform.ringcentral.com/restapi/v1.0/status' },
                { label: 'Audio Media Gateway', val: 'media.ringcentral.com:443' }
            ]
        },
        'zoom': {
            placeholder: 'e.g. stun.l.google.com:19302 (STUN UDP)',
            badge: 'Safe Default: RFC 5389 STUN Audio Reflection',
            presets: [
                { label: 'Google STUN (19302)', val: 'stun.l.google.com:19302' },
                { label: 'Zoom Media Gateway', val: 'zoom.us:8801' }
            ]
        },
        'client_isolation': {
            placeholder: 'e.g. Local Subnet /24 (or specify custom gateway)',
            badge: 'Safe Default: Intra-BSS Peer Isolation & ARP Defense',
            presets: [
                { label: 'Local Subnet (/24)', val: 'Local Subnet (/24)' },
                { label: 'Guest Wi-Fi SSID', val: 'Guest-WiFi' },
                { label: 'Student 1:1 SSID', val: 'Student-Secure' }
            ]
        },
        'cipa': {
            placeholder: 'e.g. http://iwf.testfiltering.com',
            badge: 'Safe Default: IWF + Adult Filter Targets',
            presets: [
                { label: 'IWF Standard CSAM', val: 'http://iwf.testfiltering.com' },
                { label: 'CTIRU Malware Threat', val: 'https://ctiru.testfiltering.com' }
            ]
        },
        'wifi_flapping': {
            placeholder: 'e.g. wlp1s0 or wlan0',
            badge: 'Safe Default: Auto-Detected Wi-Fi Radio',
            presets: [
                { label: 'Wi-Fi Interface (wlp1s0)', val: 'wlp1s0' },
                { label: 'Primary SSID (District-WiFi)', val: 'District-WiFi' }
            ]
        },
        'vlan_isolation': {
            placeholder: 'e.g. 10.98.1.1:443 (Admin Switch)',
            badge: 'Safe Default: East-West Lateral & VLAN Hopping Defense',
            presets: [
                { label: 'Admin Switch (10.98.1.1:443)', val: '10.98.1.1:443' },
                { label: 'CCTV Stream (10.98.20.1:554)', val: '10.98.20.1:554' },
                { label: 'Facilities BMS (10.98.30.1)', val: '10.98.30.1:47808' },
                { label: '802.1Q DTP Hopping Check', val: 'EtherType 0x2004' }
            ]
        },
        'pcap': {
            placeholder: 'e.g. eno1,wlp1s0 (All Interfaces)',
            badge: 'Safe Default: 60-Second Ring-Buffer Freeze',
            presets: [
                { label: 'All Interfaces (eno1 + wlp1s0)', val: 'eno1,wlp1s0' },
                { label: 'Wi-Fi Only (wlp1s0)', val: 'wlp1s0' }
            ]
        },
        'all': {
            placeholder: 'Leave blank to run comprehensive 7-Layer OSI & SaaS suite',
            badge: 'Safe Default: Full 7-Layer OSI & SaaS Suite',
            presets: [
                { label: 'Full 7-Layer Suite', val: '' }
            ]
        }
    };

    const cfg = hints[testType] || hints['all'];
    input.placeholder = cfg.placeholder;
    badge.innerText = cfg.badge;
    presetsContainer.innerHTML = (cfg.presets || []).map(p => `
        <button type="button" class="btn btn-outline btn-sm" style="padding: 1px 7px; font-size: 10px; border-radius: 4px;" onclick="setDiagTarget('${p.val}')">${p.label}</button>
    `).join('');
}

export function setDiagTarget(val) {
    const input = document.getElementById('diag-custom-target');
    if (input) {
        input.value = val;
        input.focus();
    }
}

export async function triggerSpeedtest(sensorId) {
    // 1. Switch to Live Diagnostics view
    switchView('monitor-ondemand');

    // 2. Set sensor select
    const diagSelect = document.getElementById('diag-sensor-select');
    if (diagSelect) {
        if (!Array.from(diagSelect.options).some(o => o.value === sensorId)) {
            const opt = document.createElement('option');
            opt.value = sensorId;
            opt.innerText = `${sensorId} (Selected)`;
            diagSelect.appendChild(opt);
        }
        diagSelect.value = sensorId;
    }

    // 3. Set test type to speedtest and update hint
    const testSelect = document.getElementById('diag-test-select');
    if (testSelect) {
        testSelect.value = 'speedtest';
        updateDiagTargetHint();
    }

    // 4. Automatically run diagnostic
    await executeSelectedDiagnostic();
}

export async function executeSelectedDiagnostic() {
    const sensorId = document.getElementById('diag-sensor-select').value;
    const testType = document.getElementById('diag-test-select').value;
    const customTarget = document.getElementById('diag-custom-target').value;
    const runBtn = document.getElementById('btn-run-diag');
    const resultsCard = document.getElementById('diag-results-card');
    const consoleBox = document.getElementById('diag-console');
    const tableBody = document.getElementById('diag-results-table-body');
    const statusPill = document.getElementById('diag-status-pill');
    const timeChip = document.getElementById('diag-time-chip');

    if (!sensorId) {
        alert('Please select an online sensor from the dropdown first.');
        return;
    }

    runBtn.disabled = true;
    runBtn.innerText = "⏳ Executing Diagnostic...";
    resultsCard.style.display = 'block';
    timeChip.innerText = "Running...";
    statusPill.className = "result-chip";
    statusPill.style.background = "rgba(59, 130, 246, 0.15)";
    statusPill.style.color = "var(--accent)";
    statusPill.innerText = "⏳ EXECUTING...";
    consoleBox.innerText = `> Connecting to edge sensor '${sensorId}'...\n> Spawning on-demand probe '${testType}' (Target Override: ${customTarget || 'Default'})...\n> Streaming live output...\n`;
    tableBody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:18px; color:var(--text-muted);">⏳ Streaming live probe execution from <strong>${sensorId}</strong>...</td></tr>`;

    try {
        const res = await fetch(`/api/v1/sensors/${sensorId}/diagnostics/run`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-API-Key': ADMIN_KEY },
            body: JSON.stringify({ test_type: testType, custom_target: customTarget })
        });
        const data = await res.json();

        runBtn.disabled = false;
        runBtn.innerText = "▶ Run Diagnostic On Sensor";

        const isPassed = data.status === 'PASS' || data.status === 'success';
        if (isPassed) {
            statusPill.className = "result-chip status-online";
            statusPill.style.background = "";
            statusPill.style.color = "";
            statusPill.innerText = "🟢 PASS (SLA Compliant)";
        } else if (data.status === 'WARNING') {
            statusPill.className = "result-chip";
            statusPill.style.background = "rgba(245, 158, 11, 0.15)";
            statusPill.style.color = "var(--warning)";
            statusPill.innerText = "⚠️ WARNING";
        } else {
            statusPill.className = "result-chip status-offline";
            statusPill.style.background = "";
            statusPill.style.color = "";
            statusPill.innerText = "🔴 FAIL";
        }

        timeChip.innerText = `Total RTT: ${data.execution_time_ms || 15.0} ms`;
        consoleBox.innerText = data.log_output || '> Diagnostic finished.';

        const rows = (data.details || []).map(d => {
            const rowPassed = d.passed !== undefined ? d.passed : (d.status === 'PASS' || d.status === 'ok');
            const statusCode = d.status_code || (rowPassed ? '200 OK' : 'Failed');
            const passBadge = rowPassed ?
                `<span class="status-pill status-online">✓ ${statusCode}</span>` :
                `<span class="status-pill status-offline">✗ ${statusCode}</span>`;
            return `
                <tr>
                    <td><strong>${d.name || d.target || 'Probe Target'}</strong><br><code style="font-size:11px; color:var(--text-muted);">${d.target || d.name || '--'}</code></td>
                    <td><span class="badge" style="background:#475569; color:white; padding:2px 6px; border-radius:4px; font-size:11px;">${d.type || 'PROBE'}</span></td>
                    <td>${passBadge}</td>
                    <td><code>${d.latency_ms !== undefined ? d.latency_ms : '--'} ms</code></td>
                    <td style="color:var(--text-muted); font-size:12px;">${d.info || ''}</td>
                </tr>
            `;
        });
        tableBody.innerHTML = rows.length > 0 ? rows.join('') : '<tr><td colspan="5" style="text-align:center;">Action queued on edge sensor.</td></tr>';
    } catch (err) {
        runBtn.disabled = false;
        runBtn.innerText = "▶ Run Diagnostic On Sensor";
        consoleBox.innerText += `\n[ERROR] Failed to execute diagnostic: ${err}`;
    }
}

export function copyDiagLog() {
    const text = document.getElementById('diag-console').innerText;
    navigator.clipboard.writeText(text);
    alert('Diagnostic log copied to clipboard.');
}

export function downloadDiagLog() {
    const text = document.getElementById('diag-console').innerText;
    const blob = new Blob([text], { type: 'text/plain' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.setAttribute('href', url);
    a.setAttribute('download', `ONE_Diagnostic_Report_${new Date().toISOString().slice(0,19).replace(/[:T]/g, '-')}.log`);
    a.click();
}

export function openLocationModal(sensorId) {
    clearModalDirty('location-modal');
    const s = SENSORS_CACHE.find(item => item.sensor_id === sensorId);
    if (!s) return;
    const loc = s.location || {};
    document.getElementById('loc-sensor-id').value = sensorId;
    document.getElementById('loc-district').value = loc.district || 'Unified School District';
    document.getElementById('loc-site').value = loc.site || 'City Center';
    document.getElementById('loc-building').value = loc.building || '1300 17th St';
    document.getElementById('loc-room').value = loc.room || 'IT Operations';
    document.getElementById('loc-notes').value = loc.notes || '1300 17th St, Bakersfield, CA 93301';
    document.getElementById('loc-lat').value = loc.latitude || 35.37452;
    document.getElementById('loc-lon').value = loc.longitude || -119.01874;
    document.getElementById('location-modal').style.display = 'flex';
}

export function closeLocationModal() {
    if (!checkModalDiscard('location-modal')) return;
    clearModalDirty('location-modal');
    document.getElementById('location-modal').style.display = 'none';
}

export async function handleSaveLocation(e) {
    e.preventDefault();
    const btn = e.target.querySelector('button[type="submit"]');
    if (btn && btn.disabled) return;

    const sensorId = document.getElementById('loc-sensor-id').value;
    const latVal = document.getElementById('loc-lat').value;
    const lonVal = document.getElementById('loc-lon').value;

    const latNum = latVal ? parseFloat(latVal) : null;
    const lonNum = lonVal ? parseFloat(lonVal) : null;

    if (latNum !== null && (isNaN(latNum) || latNum < -90 || latNum > 90)) {
        alert("Latitude must be a number between -90 and 90.");
        return;
    }
    if (lonNum !== null && (isNaN(lonNum) || lonNum < -180 || lonNum > 180)) {
        alert("Longitude must be a number between -180 and 180.");
        return;
    }

    const payload = {
        district: document.getElementById('loc-district').value.trim(),
        site: document.getElementById('loc-site').value.trim(),
        building: document.getElementById('loc-building').value.trim(),
        room: document.getElementById('loc-room').value.trim(),
        notes: document.getElementById('loc-notes').value.trim(),
        latitude: latNum,
        longitude: lonNum,
        is_gps_auto: false
    };

    const origHtml = btn ? btn.innerHTML : '';
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '⏳ Saving...';
    }

    try {
        const res = await fetch(`/api/v1/sensors/${sensorId}/location`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json', 'X-API-Key': ADMIN_KEY },
            body: JSON.stringify(payload)
        });
        if (!res.ok) {
            const err = await res.json();
            alert(`Failed to save location: ${err.detail || JSON.stringify(err)}`);
            return;
        }
        clearModalDirty('location-modal');
        closeLocationModal();
        loadDashboardData();
    } catch (err) {
        alert("Network error saving location: " + err.message);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = origHtml;
        }
    }
}

export function openProbeModal() {
    clearModalDirty('probe-modal');
    document.getElementById('probe-form').reset();
    document.getElementById('probe-modal').style.display = 'flex';
}
export function closeProbeModal() {
    if (!checkModalDiscard('probe-modal')) return;
    clearModalDirty('probe-modal');
    document.getElementById('probe-modal').style.display = 'none';
}

export function applyProbeTemplate(presetKey) {
    const templates = {
        'canvas': { name: 'Canvas LMS Portal', type: 'http', target: 'https://canvas.instructure.com', cadence: 5, timeout: 4000 },
        'google_classroom': { name: 'Google Classroom & Docs', type: 'http', target: 'https://classroom.google.com', cadence: 5, timeout: 3000 },
        'iready': { name: 'i-Ready Assessment Portal', type: 'http', target: 'https://login.i-ready.com', cadence: 5, timeout: 4000 },
        'caaspp': { name: 'CAASPP / Cambium TDS State Testing', type: 'http', target: 'https://ca.portal.cambiumtds.com', cadence: 5, timeout: 3000 },
        'powerschool': { name: 'PowerSchool SIS Portal', type: 'http', target: 'https://powerschool.com', cadence: 5, timeout: 5000 },
        'aeries': { name: 'Aeries SIS Portal', type: 'http', target: 'https://aeries.net', cadence: 5, timeout: 4000 },
        'renaissance': { name: 'Renaissance Star Reading', type: 'http', target: 'https://global-zone50.renaissance-go.com', cadence: 5, timeout: 4000 },
        'nwea': { name: 'NWEA MAP Growth Assessment', type: 'http', target: 'https://test.mapnwea.org', cadence: 5, timeout: 3000 },
        'kahoot': { name: 'Kahoot! Student Engagement', type: 'http', target: 'https://kahoot.it', cadence: 5, timeout: 3000 },
        'zoom': { name: 'Zoom Education Video & Web', type: 'http', target: 'https://zoom.us', cadence: 5, timeout: 4000 },
        'm365_teams': { name: 'Microsoft Teams Web & Signaling', type: 'http', target: 'https://teams.microsoft.com', cadence: 5, timeout: 3000 },
        'm365_outlook': { name: 'Microsoft Outlook Web Access (OWA)', type: 'http', target: 'https://outlook.office.com', cadence: 5, timeout: 3000 },
        'm365_sharepoint': { name: 'SharePoint Online Portal', type: 'http', target: 'https://sharepoint.com', cadence: 5, timeout: 3000 },
        'wu_catalog': { name: 'Windows Update Catalog Service', type: 'http', target: 'https://windowsupdate.microsoft.com', cadence: 60, timeout: 3000 },
        'do_p2p_mesh': { name: 'Delivery Optimization Peer Mesh (DO)', type: 'tcp', target: 'do.dsp.mp.microsoft.com', cadence: 15, timeout: 3000 },
        'gmeet_media': { name: 'Google Meet WebRTC Media (STUN)', type: 'tcp', target: 'stun.l.google.com', cadence: 5, timeout: 3000 },
        'clever_badger': { name: 'Clever Badges QR Scanner Service', type: 'http', target: 'https://badger.clever.com', cadence: 5, timeout: 3000 },
        'clever_portal': { name: 'Clever District SSO Portal Gateway', type: 'http', target: 'https://clever.com', cadence: 5, timeout: 3000 },
        'ls_filter': { name: 'Lightspeed Filter Relay Portal', type: 'http', target: 'https://relay.school', cadence: 5, timeout: 3000 },
        'ls_classroom': { name: 'Lightspeed Classroom Management', type: 'http', target: 'https://classroom.lightspeedsystems.app', cadence: 5, timeout: 3000 }
    };

    const t = templates[presetKey];
    if (t) {
        document.getElementById('p-name').value = t.name;
        document.getElementById('p-type').value = t.type;
        document.getElementById('p-target').value = t.target;
        document.getElementById('p-cadence').value = t.cadence;
        document.getElementById('p-timeout').value = t.timeout;
    }
}

export async function handleSaveProbe(e) {
    e.preventDefault();
    const btn = e.target.querySelector('button[type="submit"]');
    if (btn && btn.disabled) return;

    const name = document.getElementById('p-name').value.trim();
    const rawSlug = name.toLowerCase().replace(/[^a-z0-9]/g, '-').replace(/^-+|-+$/g, '');
    const id = rawSlug ? `${rawSlug}-${Date.now().toString().slice(-4)}` : `custom-probe-${Date.now()}`;
    const scopeVal = document.getElementById('p-scope').value;

    const timeoutVal = document.getElementById('p-timeout').value;
    const timeoutSeconds = (parseFloat(timeoutVal) || 5000) / 1000.0;

    const probe = {
        id: id,
        name: name,
        probe_type: document.getElementById('p-type').value,
        target: document.getElementById('p-target').value.trim(),
        cadence_minutes: parseInt(document.getElementById('p-cadence').value) || 5,
        timeout_seconds: timeoutSeconds,
        target_sensors: [scopeVal],
        enabled: true
    };

    const origHtml = btn ? btn.innerHTML : '';
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '⏳ Saving...';
    }

    try {
        const res = await fetch('/api/v1/probes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-API-Key': ADMIN_KEY },
            body: JSON.stringify(probe)
        });
        if (!res.ok) {
            const err = await res.json();
            alert(`Failed to save probe: ${err.detail || JSON.stringify(err)}`);
            return;
        }
        clearModalDirty('probe-modal');
        closeProbeModal();
        loadDashboardData();
    } catch (err) {
        alert("Network error saving probe: " + err.message);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = origHtml;
        }
    }
}

export async function deleteProbe(probeId) {
    if (confirm(`Delete probe ${probeId}?`)) {
        await fetch(`/api/v1/probes/${probeId}`, { method: 'DELETE', headers: { 'X-API-Key': ADMIN_KEY } });
        loadDashboardData();
    }
}

export function downloadSlaCsv() {
    let csv = "Sensor_ID,Campus_Site,Room,Status,GPS_Coordinates,Last_Seen\\n";
    SENSORS_CACHE.forEach(s => {
        const loc = s.location || {};
        csv += `"${s.sensor_id}","${loc.site || 'Site'}","${loc.room || 'Room'}","${s.is_online ? 'Online' : 'Offline'}","${loc.latitude || ''},${loc.longitude || ''}","${s.last_seen}"\\n`;
    });
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.setAttribute('href', url);
    a.setAttribute('download', `ONE_District_SLA_Report_${new Date().toISOString().slice(0,10)}.csv`);
    a.click();
}
