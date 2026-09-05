export function formatDuration(startsAt, endsAt) {
    const diffMs = (endsAt - startsAt) * 1000;
    if (diffMs <= 0) return '0m';
    const totalMins = Math.floor(diffMs / 60000);
    const h = Math.floor(totalMins / 60);
    const m = totalMins % 60;
    return h > 0 ? `${h}h ${m}m` : `${m}m`;
}
// --- CUSTOM ALERT RULES CONTROLLER (3. Configure → Alert Thresholds) ---

const SEV_BADGE = {
    critical: '<span class="status-pill" style="background:rgba(239,68,68,0.15);color:var(--danger);border:1px solid var(--danger);">🔴 Critical</span>',
    warning:  '<span class="status-pill" style="background:rgba(245,158,11,0.15);color:var(--warning);border:1px solid var(--warning);">🟡 Warning</span>',
    info:     '<span class="status-pill" style="background:rgba(59,130,246,0.15);color:var(--accent);border:1px solid var(--accent);">🔵 Info</span>'
};
const OP_LABEL = { gt: '>', gte: '≥', lt: '<', lte: '≤', eq: '=' };
const CHAN_ICON = { slack: '💬', teams: '🟦', pagerduty: '🟠', webhook: '🎫', email: '📧' };

export async function loadCustomAlertRules() {
    const tbody = document.getElementById('alert-rules-table-body');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; color:var(--text-muted);">Loading…</td></tr>';
    try {
        const res = await fetch('/api/v1/alerts/rules');
        const rules = res.ok ? await res.json() : [];
        // Update KPIs
        const active = rules.filter(r => r.is_active).length;
        const pcap   = rules.filter(r => r.autocapture_pcap && r.is_active).length;
        const crit   = rules.filter(r => r.severity === 'critical').length;
        const setKpi = (id, v) => { const el = document.getElementById(id); if(el) el.innerText = v; };
        setKpi('rule-kpi-active', active);
        setKpi('rule-kpi-total', rules.length);
        setKpi('rule-kpi-pcap', pcap);
        setKpi('rule-kpi-critical', crit);

        if (!rules.length) {
            tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; color:var(--text-muted);">No custom alert rules configured yet. Click + Create Alert Rule.</td></tr>';
            return;
        }
        tbody.innerHTML = rules.map(r => {
            const sev   = SEV_BADGE[r.severity] || r.severity;
            const op    = OP_LABEL[r.operator] || r.operator;
            const conds = `${r.metric} ${op} ${r.threshold_value} ${r.unit}`;
            const scope = r.campus_id ? `📍 ${r.campus_id}` : r.sensor_id ? `📡 ${r.sensor_id}` : '<span style="color:var(--text-muted)">All Fleet</span>';
            const chans = (r.channels && r.channels.length)
                ? r.channels.map(c => `<code style="font-size:11px;">${c}</code>`).join(' ')
                : '<span style="color:var(--text-muted)">None</span>';
            const pcapBadge = r.autocapture_pcap
                ? '<span style="color:var(--purple)">📦 On</span>'
                : '<span style="color:var(--text-muted)">Off</span>';
            const statusBadge = r.is_active
                ? '<span class="status-pill status-online">🟢 Active</span>'
                : '<span class="status-pill status-offline">⏸ Paused</span>';
            return `<tr>
                <td>${sev}</td>
                <td>
                    <strong style="font-size:13px;">${r.name}</strong><br>
                    <small style="color:var(--text-muted);">${r.probe_id}</small>
                </td>
                <td><code style="font-size:12px;">${conds}</code><br><small style="color:var(--text-muted);">Window: ${r.duration_seconds}s</small></td>
                <td>${scope}</td>
                <td>${chans}</td>
                <td>${pcapBadge}</td>
                <td>${statusBadge}</td>
                <td style="text-align:right; white-space:nowrap;">
                    <button class="btn btn-outline btn-sm" onclick="editAlertRule(${JSON.stringify(r).replace(/"/g,'&quot;')})">✏️</button>
                    <button class="btn btn-outline btn-sm" onclick="toggleRuleActive('${r.id}')" title="${r.is_active ? 'Pause' : 'Activate'}">${r.is_active ? '⏸' : '▶️'}</button>
                    <button class="btn btn-outline btn-sm" style="color:var(--danger);" onclick="deleteAlertRule('${r.id}')">🗑</button>
                </td>
            </tr>`;
        }).join('');
    } catch(e) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color:var(--danger);">Error loading rules: ${e.message}</td></tr>`;
    }
}


export function showFormError(form, message) {
    let errDiv = form.querySelector('.form-error-message');
    if (!errDiv) {
        errDiv = document.createElement('div');
        errDiv.className = 'form-error-message';
        form.insertBefore(errDiv, form.firstChild);
    }
    errDiv.textContent = message;
    errDiv.style.display = 'block';
}
export function clearFormError(form) {
    const errDiv = form.querySelector('.form-error-message');
    if (errDiv) errDiv.style.display = 'none';
}

export function openAlertRuleModal(rule) {
    clearModalDirty('alert-rule-modal');
    document.getElementById('rule-id').value = rule ? rule.id : '';
    document.getElementById('rule-name').value = rule ? rule.name : '';
    document.getElementById('rule-probe-id').value = rule ? rule.probe_id : 'dual_nic_ping';
    document.getElementById('rule-metric').value = rule ? rule.metric : 'latency_ms';
    document.getElementById('rule-operator').value = rule ? rule.operator : 'gt';
    document.getElementById('rule-threshold').value = rule ? rule.threshold_value : '';
    document.getElementById('rule-unit').value = rule ? rule.unit : 'ms';
    document.getElementById('rule-duration').value = rule ? rule.duration_seconds : 30;
    document.getElementById('rule-severity').value = rule ? rule.severity : 'warning';
    document.getElementById('rule-campus').value = rule && rule.campus_id ? rule.campus_id : '';
    document.getElementById('rule-sensor').value = rule && rule.sensor_id ? rule.sensor_id : '';
    document.getElementById('rule-channels').value = rule && rule.channels ? rule.channels.join(', ') : '';
    document.getElementById('rule-pcap').checked = rule ? rule.autocapture_pcap : true;
    document.getElementById('rule-active').checked = rule ? rule.is_active : true;
    document.getElementById('alert-rule-modal').style.display = 'flex';
}

export function closeAlertRuleModal() {
    if (!checkModalDiscard('alert-rule-modal')) return;
    clearModalDirty('alert-rule-modal');
    document.getElementById('alert-rule-modal').style.display = 'none';
}

export function editAlertRule(rule) {
    openAlertRuleModal(rule);
}

export async function handleSaveAlertRule(e) {
    e.preventDefault();
    const btn = e.target.querySelector('button[type="submit"]');
    if (btn && btn.disabled) return;
    clearFormError(e.target);

    const id = document.getElementById('rule-id').value;
    const thresholdVal = parseFloat(document.getElementById('rule-threshold').value);
    if (isNaN(thresholdVal)) {
        showFormError(e.target, "Threshold value must be a valid number.");
        return;
    }

    const durationVal = parseInt(document.getElementById('rule-duration').value);
    if (isNaN(durationVal) || durationVal <= 0) {
        showFormError(e.target, "Duration must be a positive integer.");
        return;
    }

    const channelRaw = document.getElementById('rule-channels').value;
    const channels = channelRaw ? channelRaw.split(',').map(s => s.trim()).filter(Boolean) : [];
    const body = {
        id: id || `rule_${Date.now().toString(36)}`,
        name: document.getElementById('rule-name').value,
        probe_id: document.getElementById('rule-probe-id').value,
        metric: document.getElementById('rule-metric').value,
        operator: document.getElementById('rule-operator').value,
        threshold_value: thresholdVal,
        unit: document.getElementById('rule-unit').value || 'ms',
        duration_seconds: durationVal,
        severity: document.getElementById('rule-severity').value,
        campus_id: document.getElementById('rule-campus').value || null,
        sensor_id: document.getElementById('rule-sensor').value || null,
        channels: channels,
        autocapture_pcap: document.getElementById('rule-pcap').checked,
        is_active: document.getElementById('rule-active').checked
    };

    const origHtml = btn ? btn.innerHTML : '';
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '⏳ Saving...';
    }

    try {
        const res = await fetch('/api/v1/alerts/rules', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body) });
        if (!res.ok) {
            const err = await res.json();
            alert("Error saving alert rule: " + (err.detail || JSON.stringify(err)));
            return;
        }
        clearModalDirty('alert-rule-modal');
        closeAlertRuleModal();
        loadCustomAlertRules();
    } catch(err) {
        alert('Network error saving alert rule: ' + err.message);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = origHtml;
        }
    }
}

export async function toggleRuleActive(ruleId) {
    await fetch(`/api/v1/alerts/rules/${ruleId}/toggle`, { method: 'POST' });
    loadCustomAlertRules();
}

export async function deleteAlertRule(ruleId) {
    if (!confirm('Delete this alert rule?')) return;
    await fetch(`/api/v1/alerts/rules/${ruleId}`, { method: 'DELETE' });
    loadCustomAlertRules();
}

// --- MAINTENANCE & MUTING WINDOWS CONTROLLER (3. Configure → Muting Windows) ---

let MAINTENANCE_WINDOWS_CACHE = [];

const WINDOW_TYPE_BADGE = {
    construction: '<span class="status-pill" style="background:rgba(245,158,11,0.18); color:var(--warning); border:1px solid var(--warning); font-weight:700;">🏗️ Construction</span>',
    maintenance:  '<span class="status-pill" style="background:rgba(59,130,246,0.15); color:var(--accent); border:1px solid var(--accent);">🔧 Maintenance</span>',
    upgrade:      '<span class="status-pill" style="background:rgba(147,51,234,0.15); color:var(--purple); border:1px solid var(--purple);">⚡ Upgrade</span>',
    renovation:   '<span class="status-pill" style="background:rgba(16,185,129,0.15); color:var(--success); border:1px solid var(--success);">🏫 Renovation</span>'
};

export async function loadMaintenanceWindows() {
    const tbody = document.getElementById('maint-table-body');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="9" style="text-align:center; color:var(--text-muted);">Loading maintenance windows…</td></tr>';
    try {
        const res = await fetch('/api/v1/alerts/maintenance-windows');
        const windows = res.ok ? await res.json() : [];
        MAINTENANCE_WINDOWS_CACHE = windows;
        const now = Math.floor(Date.now() / 1000);

        // Calculate KPIs
        const activeNow = windows.filter(w => w.is_active && w.starts_at <= now && w.ends_at >= now).length;
        const upcoming = windows.filter(w => w.is_active && w.starts_at > now).length;
        const total = windows.length;

        // Fetch 24h muted alerts count
        let mutedCount = 0;
        try {
            const altRes = await fetch('/api/v1/alerts?limit=500');
            if (altRes.ok) {
                const alerts = await altRes.json();
                mutedCount = alerts.filter(a => a.is_muted).length;
            }
        } catch (e) {}

        const setKpi = (id, v) => { const el = document.getElementById(id); if (el) el.innerText = v; };
        setKpi('maint-kpi-active', activeNow);
        setKpi('maint-kpi-upcoming', upcoming);
        setKpi('maint-kpi-total', total);
        setKpi('maint-kpi-muted', mutedCount);

        if (!windows.length) {
            tbody.innerHTML = '<tr><td colspan="9" style="text-align:center; color:var(--text-muted); padding:24px;">No scheduled maintenance windows. Click + Schedule Window or use Quick Mute.</td></tr>';
            return;
        }

        tbody.innerHTML = windows.map(w => {
            let statusPill = '';
            let remainingText = '';
            const isCurrentlyActive = w.is_active && (w.starts_at <= now && w.ends_at >= now);
            const isUpcoming = w.is_active && (w.starts_at > now);
            const isConstruction = (w.window_type === 'construction');

            if (!w.is_active) {
                statusPill = '<span class="status-pill status-offline">⏸ Disabled</span>';
                remainingText = 'Inactive';
            } else if (isCurrentlyActive) {
                const activeBg = isConstruction ? 'rgba(245,158,11,0.2)' : 'rgba(147,51,234,0.18)';
                const activeCol = isConstruction ? 'var(--warning)' : 'var(--purple)';
                statusPill = `<span class="status-pill" style="background:${activeBg}; color:${activeCol}; border:1px solid ${activeCol}; font-weight:700;">🟢 Active (${isConstruction ? 'Construction Mute' : 'Muting'})</span>`;

                const remSec = w.ends_at - now;
                const remHours = Math.floor(remSec / 3600);
                const remDays = Math.floor(remHours / 24);
                if (remDays >= 1) {
                    remainingText = `${remDays}d ${remHours % 24}h remaining`;
                } else if (remHours >= 1) {
                    const remMin = Math.ceil((remSec % 3600) / 60);
                    remainingText = `${remHours}h ${remMin}m remaining`;
                } else {
                    const remMin = Math.ceil(remSec / 60);
                    remainingText = `${remMin}m remaining`;
                }
            } else if (isUpcoming) {
                statusPill = '<span class="status-pill" style="background:rgba(59,130,246,0.15); color:var(--accent); border:1px solid var(--accent);">⏰ Scheduled</span>';
                const untilSec = w.starts_at - now;
                const untilHr = Math.floor(untilSec / 3600);
                remainingText = untilHr > 24 ? `Starts in ${Math.floor(untilHr / 24)}d` : `Starts in ${untilHr}h`;
            } else {
                statusPill = '<span class="status-pill" style="background:rgba(107,114,128,0.15); color:var(--text-muted); border:1px solid var(--border);">⏹ Expired</span>';
                remainingText = 'Ended';
            }

            const typeBadge = WINDOW_TYPE_BADGE[w.window_type] || WINDOW_TYPE_BADGE.maintenance;

            const scopeParts = [];
            if (w.campus_id) scopeParts.push(`📍 ${w.campus_id}`);
            if (w.sensor_id) scopeParts.push(`📡 ${w.sensor_id}`);
            if (w.probe_id) scopeParts.push(`🔬 ${w.probe_id}`);
            if (w.alertname_pattern) scopeParts.push(`🏷️ Pattern: <code>${w.alertname_pattern}</code>`);
            const scopeDisplay = scopeParts.length ? scopeParts.join('<br>') : '<span style="color:var(--text-muted);">Fleet-wide (All Probes)</span>';

            const startStr = new Date(w.starts_at * 1000).toLocaleString();
            const endStr = new Date(w.ends_at * 1000).toLocaleString();

            const enabledToggle = w.is_active
                ? '<span style="color:var(--success);">✅ On</span>'
                : '<span style="color:var(--text-muted);">Off</span>';

            return `<tr>
                <td>${statusPill}</td>
                <td>${typeBadge}</td>
                <td>
                    <strong style="font-size:13px; color:var(--text-main);">${w.name}</strong>
                    ${w.description ? `<br><small style="color:var(--text-muted);">${w.description}</small>` : ''}
                </td>
                <td style="font-size:12px;">${scopeDisplay}</td>
                <td style="font-size:12px; white-space:nowrap;">${startStr}</td>
                <td style="font-size:12px; white-space:nowrap;">${endStr}</td>
                <td><strong style="font-size:12px;">${remainingText}</strong></td>
                <td>${enabledToggle}</td>
                <td style="text-align:right; white-space:nowrap;">
                    <button class="btn btn-outline btn-sm" onclick="editMaintenanceWindow(${JSON.stringify(w).replace(/"/g,'&quot;')})" title="Edit Window">✏️</button>
                    <button class="btn btn-outline btn-sm" onclick="toggleMaintenanceWindow('${w.id}')" title="${w.is_active ? 'Disable' : 'Enable'}">${w.is_active ? '⏸' : '▶️'}</button>
                    <button class="btn btn-outline btn-sm" style="color:var(--danger);" onclick="deleteMaintenanceWindow('${w.id}')" title="Delete Window">🗑</button>
                </td>
            </tr>`;
        }).join('');
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; color:var(--danger);">Error loading maintenance windows: ${e.message}</td></tr>`;
    }
}

export function openMaintenanceModal(win) {
    clearModalDirty('maintenance-modal');
    const now = new Date();
    const pad = n => String(n).padStart(2, '0');
    const toIsoLocal = d => `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;

    document.getElementById('maint-id').value = win ? win.id : '';
    document.getElementById('maint-name').value = win ? win.name : '';
    document.getElementById('maint-desc').value = win ? (win.description || '') : '';
    document.getElementById('maint-type').value = win ? (win.window_type || 'maintenance') : 'maintenance';
    document.getElementById('maint-campus').value = win ? (win.campus_id || '') : '';
    document.getElementById('maint-sensor').value = win ? (win.sensor_id || '') : '';
    document.getElementById('maint-probe').value = win ? (win.probe_id || '') : '';
    document.getElementById('maint-pattern').value = win ? (win.alertname_pattern || '') : '';

    if (win) {
        document.getElementById('maint-starts-at').value = toIsoLocal(new Date(win.starts_at * 1000));
        document.getElementById('maint-ends-at').value = toIsoLocal(new Date(win.ends_at * 1000));
    } else {
        const start = new Date();
        const end = new Date(start.getTime() + 2 * 3600 * 1000); // 2 hours
        document.getElementById('maint-starts-at').value = toIsoLocal(start);
        document.getElementById('maint-ends-at').value = toIsoLocal(end);
    }

    document.getElementById('maint-active').checked = win ? win.is_active : true;
    document.getElementById('maint-reminder-cb').checked = win ? (win.notify_channel_ids && win.notify_channel_ids.length > 0 || true) : true;
    document.getElementById('maintenance-modal').style.display = 'flex';
}

export function closeMaintenanceModal() {
    if (!checkModalDiscard('maintenance-modal')) return;
    clearModalDirty('maintenance-modal');
    const m = document.getElementById('maintenance-modal');
    if (m) m.style.display = 'none';
}

export function setMaintDurationPreset(minutes) {
    const startInput = document.getElementById('maint-starts-at');
    const endInput = document.getElementById('maint-ends-at');
    const pad = n => String(n).padStart(2, '0');
    const toIsoLocal = d => `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;

    let start = new Date();
    if (startInput.value) {
        try { start = new Date(startInput.value); } catch(e) {}
    }
    const end = new Date(start.getTime() + minutes * 60 * 1000);
    startInput.value = toIsoLocal(start);
    endInput.value = toIsoLocal(end);
}

export function editMaintenanceWindow(win) {
    openMaintenanceModal(win);
}

export async function handleSaveMaintenance(e) {
    e.preventDefault();
    const btn = e.target.querySelector('button[type="submit"]');
    if (btn && btn.disabled) return;
    clearFormError(e.target);

    const id = document.getElementById('maint-id').value || `maint_${Date.now()}`;
    const name = document.getElementById('maint-name').value.trim();
    const desc = document.getElementById('maint-desc').value.trim();
    const wtype = document.getElementById('maint-type').value;
    const campus = document.getElementById('maint-campus').value.trim() || null;
    const sensor = document.getElementById('maint-sensor').value.trim() || null;
    const probe = document.getElementById('maint-probe').value.trim() || null;
    const pattern = document.getElementById('maint-pattern').value.trim() || null;

    const startVal = document.getElementById('maint-starts-at').value;
    const endVal = document.getElementById('maint-ends-at').value;

    const startsAt = Math.floor(new Date(startVal).getTime() / 1000);
    const endsAt = Math.floor(new Date(endVal).getTime() / 1000);

    if (isNaN(startsAt) || isNaN(endsAt)) {
        showFormError(e.target, "Please enter valid Start and End datetimes.");
        return;
    }
    if (endsAt <= startsAt) {
        showFormError(e.target, "End datetime must be after Start datetime.");
        return;
    }

    const reminderChecked = document.getElementById('maint-reminder-cb') ? document.getElementById('maint-reminder-cb').checked : false;

    const payload = {
        id: id,
        name: name,
        description: desc,
        window_type: wtype,
        campus_id: campus,
        sensor_id: sensor,
        probe_id: probe,
        alertname_pattern: pattern,
        starts_at: startsAt,
        ends_at: endsAt,
        is_active: document.getElementById('maint-active').checked,
        reminded_24h: reminderChecked,
        reminded_2h: reminderChecked,
        created_by: "NOC Admin"
    };

    const origHtml = btn ? btn.innerHTML : '';
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '⏳ Saving...';
    }

    try {
        const res = await fetch('/api/v1/alerts/maintenance-windows', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (res.ok) {
            clearModalDirty('maintenance-modal');
            closeMaintenanceModal();
            loadMaintenanceWindows();
            loadAlertCenterData();
        } else {
            const err = await res.json();
            alert("Error saving maintenance window: " + (err.detail || JSON.stringify(err)));
        }
    } catch(err) {
        alert("Network error saving maintenance window: " + err.message);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = origHtml;
        }
    }
}

export async function quickCreateMuteWindow(durationMinutes, title) {
    const now = Math.floor(Date.now() / 1000);
    const payload = {
        id: `maint_${Date.now()}`,
        name: title || `Quick Mute (${durationMinutes}m)`,
        description: `Automated quick mute generated from ONE console on ${new Date().toLocaleTimeString()}`,
        window_type: "maintenance",
        campus_id: null,
        sensor_id: null,
        probe_id: null,
        alertname_pattern: null,
        starts_at: now,
        ends_at: now + (durationMinutes * 60),
        is_active: true,
        created_by: "NOC Operator"
    };

    try {
        const res = await fetch('/api/v1/alerts/maintenance-windows', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (res.ok) {
            loadMaintenanceWindows();
            loadAlertCenterData();
        }
    } catch (e) {
        alert("Failed to create quick mute window: " + e.message);
    }
}

export async function quickCreateConstructionWindow(days, title) {
    const now = Math.floor(Date.now() / 1000);
    const durationSec = days * 86400;
    const payload = {
        id: `maint_const_${Date.now()}`,
        name: title || `${days}-Day Facility Construction Muting`,
        description: `Automated construction muting window for campus rewiring/facility bond work (${days} days duration).`,
        window_type: "construction",
        campus_id: null,
        sensor_id: null,
        probe_id: null,
        alertname_pattern: null,
        starts_at: now,
        ends_at: now + durationSec,
        is_active: true,
        created_by: "Facilities & NOC Project Manager"
    };

    try {
        const res = await fetch('/api/v1/alerts/maintenance-windows', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (res.ok) {
            loadMaintenanceWindows();
            loadAlertCenterData();
        }
    } catch (e) {
        alert("Failed to create construction mute window: " + e.message);
    }
}

export async function toggleMaintenanceWindow(winId) {
    try {
        const res = await fetch(`/api/v1/alerts/maintenance-windows/${winId}/toggle`, { method: 'POST' });
        if (res.ok) {
            loadMaintenanceWindows();
            loadAlertCenterData();
        }
    } catch(e) {
        alert("Failed to toggle maintenance window: " + e.message);
    }
}

export async function deleteMaintenanceWindow(winId) {
    if (!confirm(`Delete maintenance window '${winId}'? Outbound notification suppression will cease immediately.`)) return;
    try {
        const res = await fetch(`/api/v1/alerts/maintenance-windows/${winId}`, { method: 'DELETE' });
        if (res.ok) {
            loadMaintenanceWindows();
            loadAlertCenterData();
        }
    } catch(e) {
        alert("Failed to delete maintenance window: " + e.message);
    }
}

// --- NOTIFICATION CHANNELS CONTROLLER (4. Setup → Alerts & Webhooks) ---

export async function loadNotificationChannels() {
    const tbody = document.getElementById('channels-table-body');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; color:var(--text-muted);">Loading…</td></tr>';
    try {
        const res = await fetch('/api/v1/alerts/channels');
        const channels = res.ok ? await res.json() : [];
        const active = channels.filter(c => c.is_active).length;
        const types  = new Set(channels.map(c => c.channel_type)).size;
        const lastTs = channels.reduce((m, c) => Math.max(m, c.last_dispatched_at || 0), 0);
        const setKpi = (id, v) => { const el = document.getElementById(id); if(el) el.innerText = v; };
        setKpi('chan-kpi-active', active);
        setKpi('chan-kpi-total', channels.length);
        setKpi('chan-kpi-types', types);
        const lastEl = document.getElementById('chan-kpi-last');
        if (lastEl) lastEl.innerText = lastTs ? new Date(lastTs * 1000).toLocaleTimeString() : '—';

        if (!channels.length) {
            tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; color:var(--text-muted);">No notification channels configured. Click + Add Notification Channel.</td></tr>';
            return;
        }
        tbody.innerHTML = channels.map(ch => {
            const icon   = CHAN_ICON[ch.channel_type] || '🔗';
            const minSev = SEV_BADGE[ch.min_severity] || ch.min_severity;
            const urlShort = ch.endpoint_url.length > 42 ? ch.endpoint_url.slice(0,42) + '…' : ch.endpoint_url;
            const lastSent = ch.last_dispatched_at ? new Date(ch.last_dispatched_at * 1000).toLocaleString() : '—';
            const statusColor = ch.last_status && ch.last_status.startsWith('Deliver') ? 'var(--success)'
                : ch.last_status && ch.last_status.includes('Error') ? 'var(--danger)' : 'var(--text-muted)';
            const enBadge = ch.is_active
                ? '<span class="status-pill status-online">🟢 On</span>'
                : '<span class="status-pill status-offline">⏸ Off</span>';
            return `<tr>
                <td>${icon} <strong>${ch.channel_type}</strong></td>
                <td>${ch.name}</td>
                <td><code style="font-size:11px;" title="${ch.endpoint_url}">${urlShort}</code></td>
                <td>${minSev}</td>
                <td><span style="font-size:12px; color:${statusColor};">${ch.last_status || 'Ready'}</span></td>
                <td style="font-size:12px; color:var(--text-muted);">${lastSent}</td>
                <td>${enBadge}</td>
                <td style="text-align:right; white-space:nowrap;">
                    <button class="btn btn-outline btn-sm" onclick="testChannel('${ch.id}')" title="Send Test Notification">🔔</button>
                    <button class="btn btn-outline btn-sm" onclick="editChannel(${JSON.stringify(ch).replace(/"/g,'&quot;')})">✏️</button>
                    <button class="btn btn-outline btn-sm" style="color:var(--danger);" onclick="deleteChannel('${ch.id}')">🗑</button>
                </td>
            </tr>`;
        }).join('');
    } catch(e) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color:var(--danger);">Error loading channels: ${e.message}</td></tr>`;
    }
}

let _currentEditChannelId = null;

export function handleChannelTypeChange() {
    const type = document.getElementById('chan-type').value;
    const webhookPanel = document.getElementById('webhook-config-panel');
    const emailPanel = document.getElementById('email-config-panel');
    if (type === 'email') {
        if (webhookPanel) webhookPanel.style.display = 'none';
        if (emailPanel) emailPanel.style.display = 'block';
    } else {
        if (webhookPanel) webhookPanel.style.display = 'block';
        if (emailPanel) emailPanel.style.display = 'none';
    }
}

const EMAIL_PRESETS = {
    google_relay: {
        host: 'smtp-relay.gmail.com', port: 587, sec: 'starttls', user: '', pw: '',
        hint: '💡 <strong>Google Workspace Relay:</strong> Whitelist the CMP server public IP in Google Admin ➔ Apps ➔ Google Workspace ➔ Gmail ➔ Routing ➔ SMTP relay service (No auth required).'
    },
    google_app_pw: {
        host: 'smtp.gmail.com', port: 587, sec: 'starttls', user: 'noc-alerts@district.edu', pw: '',
        hint: '💡 <strong>Google App Password:</strong> Generate a dedicated 16-character App Password under Google Account ➔ Security ➔ 2-Step Verification ➔ App Passwords.'
    },
    m365_smtp: {
        host: 'smtp.office365.com', port: 587, sec: 'starttls', user: 'noc-alerts@district.edu', pw: '',
        hint: '💡 <strong>Microsoft 365 Exchange Online:</strong> Requires an M365 licensed service account with SMTP AUTH enabled in Microsoft 365 Admin Center.'
    },
    onprem_lan: {
        host: '10.0.0.25', port: 25, sec: 'none', user: '', pw: '',
        hint: '💡 <strong>District LAN / Internal Relay:</strong> Sends unauthenticated plain/STARTTLS email over internal VLAN to local Postfix / Exchange server.'
    },
    sendgrid: {
        host: 'smtp.sendgrid.net', port: 587, sec: 'starttls', user: 'apikey', pw: '',
        hint: '💡 <strong>SendGrid Cloud Relay:</strong> Set username to <code>apikey</code> and password to your SendGrid API key.'
    }
};

export function applyEmailPreset() {
    const key = document.getElementById('email-preset-select').value;
    if (!key || !EMAIL_PRESETS[key]) return;
    const p = EMAIL_PRESETS[key];
    document.getElementById('email-smtp-host').value = p.host;
    document.getElementById('email-smtp-port').value = p.port;
    document.getElementById('email-smtp-sec').value = p.sec;
    if (p.user) document.getElementById('email-username').value = p.user;
    if (p.pw) document.getElementById('email-password').value = p.pw;
    const hintEl = document.getElementById('email-preset-hint');
    if (hintEl) hintEl.innerHTML = p.hint;
}

export function openChannelModal(ch) {
    clearModalDirty('channel-modal');
    _currentEditChannelId = ch ? ch.id : null;
    document.getElementById('chan-id').value = ch ? ch.id : '';
    document.getElementById('chan-name').value = ch ? ch.name : '';
    const cType = ch ? ch.channel_type : 'slack';
    document.getElementById('chan-type').value = cType;
    document.getElementById('chan-min-sev').value = ch ? ch.min_severity : 'warning';
    document.getElementById('chan-url').value = ch ? ch.endpoint_url : '';
    document.getElementById('chan-headers').value = ch && ch.auth_headers && Object.keys(ch.auth_headers).length
        ? JSON.stringify(ch.auth_headers, null, 2) : '';
    document.getElementById('chan-active').checked = ch ? ch.is_active : true;

    // Populate Email-specific fields if applicable
    if (cType === 'email' && ch && ch.auth_headers) {
        const ah = ch.auth_headers;
        document.getElementById('email-smtp-host').value = ah.smtp_host || (ch.endpoint_url ? ch.endpoint_url.split(':')[0] : 'smtp-relay.gmail.com');
        document.getElementById('email-smtp-port').value = ah.smtp_port || (ch.endpoint_url && ch.endpoint_url.includes(':') ? ch.endpoint_url.split(':')[1] : 587);
        document.getElementById('email-smtp-sec').value = ah.security_mode || 'starttls';
        document.getElementById('email-from-addr').value = ah.from_email || 'noc-alerts@district.edu';
        document.getElementById('email-from-name').value = ah.from_name || 'ONE Platform Network Monitor';
        document.getElementById('email-recipients').value = ah.recipients || 'noc@district.edu, helpdesk@district.edu';
        document.getElementById('email-username').value = ah.username || '';
        document.getElementById('email-password').value = ah.password || '';
    } else if (cType === 'email' && !ch) {
        document.getElementById('email-smtp-host').value = 'smtp-relay.gmail.com';
        document.getElementById('email-smtp-port').value = '587';
        document.getElementById('email-smtp-sec').value = 'starttls';
        document.getElementById('email-from-addr').value = 'noc-alerts@district.edu';
        document.getElementById('email-from-name').value = 'ONE Platform Network Monitor';
        document.getElementById('email-recipients').value = 'noc@district.edu, helpdesk@district.edu';
        document.getElementById('email-username').value = '';
        document.getElementById('email-password').value = '';
    }

    handleChannelTypeChange();

    const testBtn = document.getElementById('btn-test-channel');
    if (testBtn) testBtn.style.display = ch ? 'inline-flex' : 'none';
    document.getElementById('channel-modal').style.display = 'flex';
}

export function editChannel(ch) { openChannelModal(ch); }
export function closeChannelModal() {
    if (!checkModalDiscard('channel-modal')) return;
    clearModalDirty('channel-modal');
    document.getElementById('channel-modal').style.display = 'none';
}

export async function handleSaveChannel(e) {
    e.preventDefault();
    const btn = e.target.querySelector('button[type="submit"]');
    if (btn && btn.disabled) return;
    clearFormError(e.target);

    const id = document.getElementById('chan-id').value;
    const cType = document.getElementById('chan-type').value;
    let endpointUrl = document.getElementById('chan-url').value;
    let authHeaders = {};

    if (cType === 'email') {
        const host = document.getElementById('email-smtp-host').value.trim() || 'smtp-relay.gmail.com';
        const port = parseInt(document.getElementById('email-smtp-port').value) || 587;
        endpointUrl = `${host}:${port}`;
        authHeaders = {
            smtp_host: host,
            smtp_port: port,
            security_mode: document.getElementById('email-smtp-sec').value,
            from_email: document.getElementById('email-from-addr').value.trim() || 'noc-alerts@district.edu',
            from_name: document.getElementById('email-from-name').value.trim() || 'ONE Platform Network Monitor',
            recipients: document.getElementById('email-recipients').value.trim() || 'noc@district.edu',
            username: document.getElementById('email-username').value.trim(),
            password: document.getElementById('email-password').value
        };
    } else {
        const headersRaw = document.getElementById('chan-headers').value.trim();
        if (headersRaw) {
            try { authHeaders = JSON.parse(headersRaw); } catch { showFormError(e.target, 'Auth Headers must be valid JSON.'); return; }
        }
    }

    const body = {
        id: id || `chan_${Date.now().toString(36)}`,
        name: document.getElementById('chan-name').value,
        channel_type: cType,
        endpoint_url: endpointUrl,
        auth_headers: authHeaders,
        min_severity: document.getElementById('chan-min-sev').value,
        is_active: document.getElementById('chan-active').checked
    };

    const origHtml = btn ? btn.innerHTML : '';
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '⏳ Saving...';
    }

    try {
        const res = await fetch('/api/v1/alerts/channels', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body) });
        if (!res.ok) {
            const err = await res.json();
            alert("Error saving channel: " + (err.detail || JSON.stringify(err)));
            return;
        }
        clearModalDirty('channel-modal');
        closeChannelModal();
        loadNotificationChannels();
    } catch(err) {
        alert('Network error saving channel: ' + err.message);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = origHtml;
        }
    }
}

export async function testChannel(channelId) {
    const res = await fetch(`/api/v1/alerts/channels/${channelId}/test`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({}) });
    const data = res.ok ? await res.json() : null;
    alert(data && data.delivered ? `✅ Test notification delivered!\nLast status: ${data.channel?.last_status}` : `⚠️ Delivery attempted.\nStatus: ${data?.channel?.last_status || 'Unknown'}`);
    loadNotificationChannels();
}

export async function testCurrentChannel() {
    if (_currentEditChannelId) { closeChannelModal(); await testChannel(_currentEditChannelId); }
}

export async function deleteChannel(channelId) {
    if (!confirm('Delete this notification channel?')) return;
    await fetch(`/api/v1/alerts/channels/${channelId}`, { method: 'DELETE' });
    loadNotificationChannels();
}

// --- ACTIVE ALERT CENTER & INCIDENT LIFECYCLE CONTROLLER ---
let CURRENT_ALERT_STATUS_FILTER = 'active';
let ALERTS_CACHE = [];

export function setAlertStatusFilter(status) {
    CURRENT_ALERT_STATUS_FILTER = status;
    document.querySelectorAll('.alert-filter-btn').forEach(btn => btn.classList.remove('active'));
    const activeBtn = document.getElementById('alt-tab-' + (status === 'acknowledged' ? 'acknowledged' : status));
    if (activeBtn) activeBtn.classList.add('active');
    loadAlertCenterData();
}

export async function loadAlertCenterData() {
    try {
        // Check active maintenance windows
        try {
            const maintRes = await fetch('/api/v1/alerts/maintenance-windows/active-now');
            const activeMaint = maintRes.ok ? await maintRes.json() : [];
            const maintBanner = document.getElementById('alt-maint-active-banner');
            const maintName = document.getElementById('alt-maint-active-name');
            if (maintBanner && maintName) {
                if (activeMaint.length > 0) {
                    const isConstruction = activeMaint.some(w => w.window_type === 'construction');
                    maintBanner.style.display = 'flex';
                    if (isConstruction) {
                        maintBanner.style.background = 'rgba(245, 158, 11, 0.16)';
                        maintBanner.style.borderColor = 'var(--warning)';
                        maintBanner.style.color = '#fbbf24';
                    } else {
                        maintBanner.style.background = 'rgba(147, 51, 234, 0.12)';
                        maintBanner.style.borderColor = 'var(--purple)';
                        maintBanner.style.color = '#c084fc';
                    }
                    maintName.innerHTML = activeMaint.map(w => {
                        const tag = w.window_type === 'construction' ? '🏗️ [Construction]' : '🔕';
                        const endsDate = new Date(w.ends_at * 1000).toLocaleDateString();
                        return `<strong>${tag} ${w.name}</strong> (Scheduled through ${endsDate})`;
                    }).join('; ');
                } else {
                    maintBanner.style.display = 'none';
                }
            }
        } catch(me) {
            console.warn("Could not check active maintenance:", me);
        }

        // Fetch summary metrics
        const summaryRes = await fetch('/api/v1/alerts/summary');
        if (summaryRes.ok) {
            const summary = await summaryRes.json();
            const kpiFir = document.getElementById('alt-kpi-firing');
            if (kpiFir) kpiFir.innerText = summary.firing_count;
            const kpiAck = document.getElementById('alt-kpi-acknowledged');
            if (kpiAck) kpiAck.innerText = summary.acknowledged_count;
            const kpiCrit = document.getElementById('alt-kpi-critical');
            if (kpiCrit) kpiCrit.innerText = summary.critical_count;
            const kpiRes = document.getElementById('alt-kpi-resolved');
            if (kpiRes) kpiRes.innerText = summary.resolved_24h_count;

            // Update Tab Badge Counters
            const tabAct = document.getElementById('alt-tab-count-active');
            if (tabAct) tabAct.innerText = summary.open_count;
            const tabFir = document.getElementById('alt-tab-count-firing');
            if (tabFir) tabFir.innerText = summary.firing_count;
            const tabAck = document.getElementById('alt-tab-count-ack');
            if (tabAck) tabAck.innerText = summary.acknowledged_count;

            // Update Global Sidebar Badge & NOC Overview Triage Banner
            updateAlertBadgeAndBanner(summary);
        }

        // Fetch filtered alerts
        const sevFilter = document.getElementById('alt-filter-severity') ? document.getElementById('alt-filter-severity').value : 'all';
        let url = `/api/v1/alerts?status=${encodeURIComponent(CURRENT_ALERT_STATUS_FILTER)}`;
        if (sevFilter && sevFilter !== 'all') {
            url += `&severity=${encodeURIComponent(sevFilter)}`;
        }

        const res = await fetch(url);
        if (res.ok) {
            ALERTS_CACHE = await res.json();
            renderAlertsTable();
        }
    } catch (e) {
        console.error("Failed to load alert center data:", e);
    }
}

export function updateAlertBadgeAndBanner(summary) {
    const sideBadge = document.getElementById('sidebar-alert-badge');
    if (sideBadge) {
        if (summary.open_count > 0) {
            sideBadge.innerText = summary.open_count;
            sideBadge.style.display = 'inline-block';
            sideBadge.style.background = summary.critical_count > 0 ? 'var(--danger)' : 'var(--warning)';
        } else {
            sideBadge.style.display = 'none';
        }
    }

    const nocBanner = document.getElementById('noc-alarms-banner');
    const nocTitle = document.getElementById('noc-alarms-banner-title');
    const nocDesc = document.getElementById('noc-alarms-banner-desc');
    if (nocBanner) {
        if (summary.open_count > 0) {
            nocBanner.style.display = 'flex';
            if (nocTitle) nocTitle.innerText = `🚨 ${summary.open_count} Active Alarm${summary.open_count > 1 ? 's' : ''} Requiring Triage (${summary.critical_count} Critical, ${summary.warning_count} Warning)`;
            if (nocDesc) nocDesc.innerText = `${summary.firing_count} Firing, ${summary.acknowledged_count} Under Investigation. Auto-ingested via Alertmanager.`;
        } else {
            nocBanner.style.display = 'none';
        }
    }

    const kpiAlarmVal = document.getElementById('kpi-alarm');
    if (kpiAlarmVal) kpiAlarmVal.innerText = summary.open_count;
    const kpiAlarmLeft = document.getElementById('kpi-alarm-footer-left');
    if (kpiAlarmLeft) kpiAlarmLeft.innerText = summary.open_count > 0 ? `${summary.critical_count} Critical Outages` : 'Tickets: 0 New';
    const kpiAlarmRight = document.getElementById('kpi-alarm-footer-right');
    if (kpiAlarmRight) kpiAlarmRight.innerText = summary.open_count > 0 ? 'Triage ➔' : '100% Resolved';
}


export function renderAlertsTable() {
    const tbody = document.getElementById('alerts-table-body');
    if (!tbody) return;

    if (!ALERTS_CACHE || ALERTS_CACHE.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color:var(--text-muted); padding:32px;">
            <div style="font-size:24px; margin-bottom:8px;">✅</div>
            <strong>No alerts matching filter '${CURRENT_ALERT_STATUS_FILTER}'.</strong>
            <p style="font-size:12px; margin-top:4px;">All synthetic probers and edge network paths are within nominal SLA bounds.</p>
        </td></tr>`;
        return;
    }

    const rows = ALERTS_CACHE.map(alt => {
        let sevBadge = '';
        if (alt.severity === 'critical') {
            sevBadge = '<span class="badge-sev-critical">🔴 CRITICAL</span>';
        } else if (alt.severity === 'info') {
            sevBadge = '<span class="badge-sev-info">🔵 INFO</span>';
        } else {
            sevBadge = '<span class="badge-sev-warning">🟡 WARNING</span>';
        }

        let statusBadge = '';
        if (alt.status === 'firing') {
            statusBadge = '<span class="badge-status-firing">🔥 FIRING</span>';
        } else if (alt.status === 'acknowledged') {
            statusBadge = `<span class="badge-status-acknowledged" title="Ack by ${alt.acknowledged_by || 'Operator'}">👁️ ACK</span>`;
        } else {
            statusBadge = '<span class="badge-status-resolved">✅ RESOLVED</span>';
        }

        const scopeCampus = alt.campus_id || 'District-Wide';
        const scopeSensor = alt.sensor_id ? `<code>${alt.sensor_id}</code>` : '<span style="color:var(--text-muted);">All Probers</span>';
        const probeBadge = alt.probe_id ? `<span style="font-size:10px; background:var(--bg-input); padding:2px 6px; border-radius:4px; border:1px solid var(--border); color:var(--accent);">🔬 ${alt.probe_id}</span>` : '';
        const mutedBadge = alt.is_muted
            ? `<span style="font-size:10px; background:rgba(147,51,234,0.18); color:var(--purple); padding:2px 6px; border-radius:4px; border:1px solid var(--purple);" title="Muted by: ${alt.muted_by_window_name || 'Maintenance Window'}">🔕 Muted (${alt.muted_by_window_name || 'Maint'})</span>`
            : '';

        const startDateStr = new Date(alt.starts_at * 1000).toLocaleTimeString();
        const durationStr = formatDuration(alt.starts_at, alt.ends_at);

        const ackBtn = (alt.status === 'firing') ?
            `<button class="btn btn-outline btn-sm" onclick="handleAcknowledgeAlert('${alt.id}')" title="Acknowledge Alert">👁️ Ack</button>` : '';

        const resolveBtn = (alt.status !== 'resolved') ?
            `<button class="btn btn-outline btn-sm" style="border-color:var(--success); color:var(--status-online-text);" onclick="openResolveAlertModal('${alt.id}')" title="Resolve Alert">✅ Resolve</button>` : '';

        const diagBtn = alt.sensor_id ?
            `<button class="btn btn-outline btn-sm" onclick="launchSensorDiag('${alt.sensor_id}')" title="Run Live Diagnostics">🔬 Diag</button>` : '';

        return `
            <tr>
                <td>${sevBadge}</td>
                <td>
                    <div style="font-weight:700; color:var(--text-main); cursor:pointer;" onclick="viewAlertDetails('${alt.id}')">
                        ${alt.title}
                    </div>
                    <div style="font-size:12px; color:var(--text-muted); margin-top:2px;">
                        ${alt.description || 'No description provided.'}
                    </div>
                    <div style="margin-top:4px; display:flex; gap:6px; align-items:center; flex-wrap:wrap;">
                        ${probeBadge}
                        ${mutedBadge}
                        ${alt.evidence_id ? `<span style="font-size:10px; background:rgba(139,92,246,0.15); color:var(--purple); padding:2px 6px; border-radius:4px; border:1px solid var(--purple); cursor:pointer;" onclick="openEvidenceModal('${alt.evidence_id}')" title="Inspect PCAP Packet Capture">📦 Evidence: ${alt.evidence_id}</span>` : ''}
                    </div>
                </td>
                <td>
                    <div style="font-weight:600;">${scopeCampus}</div>
                    <div style="font-size:11px; margin-top:2px;">${scopeSensor}</div>
                </td>
                <td>
                    <div>${startDateStr}</div>
                    <div style="font-size:11px; color:var(--text-muted);">Duration: <strong>${durationStr}</strong></div>
                </td>
                <td>${statusBadge}</td>
                <td style="text-align:right;">
                    <div style="display:flex; justify-content:flex-end; gap:6px;">
                        ${ackBtn}
                        ${resolveBtn}
                        ${diagBtn}
                        <button class="btn btn-outline btn-sm" onclick="viewAlertDetails('${alt.id}')" title="View Forensics">🔍</button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
    tbody.innerHTML = rows;
}

export function openSimulateAlertModal() {
    document.getElementById('simulate-alert-modal').style.display = 'flex';
}

export function closeSimulateAlertModal() {
    document.getElementById('simulate-alert-modal').style.display = 'none';
}

export function applySimulatePreset(presetKey) {
    const presets = {
        'caaspp_cert': {
            alertname: 'CAASPPUntrustedCertificate',
            severity: 'critical',
            title: 'CAASPP Secure Browser SSL Certificate Interception Detected',
            desc: 'Untrusted MITM certificate detected during pre-flight synthetic TLS probe to Cambium TDS.',
            campus: 'CAMPUS-WEST-HIGH',
            sensor: 'pi5-science-01',
            probe: 'caaspp_readiness',
            evidence: 'ev-caaspp-tls-mitm-01'
        },
        'wifi_flapping': {
            alertname: 'WiFiFlappingDetected',
            severity: 'warning',
            title: 'Wi-Fi AP Channel Hopping & High Flapping Detected',
            desc: 'Excessive BSSID transitions (>8 per min) observed on wlp1s0 during active student roaming.',
            campus: 'CAMPUS-WEST-HIGH',
            sensor: 'pi5-science-01',
            probe: 'rrm_darrp',
            evidence: 'ev-wifi-flapping-02'
        },
        'dns_fail': {
            alertname: 'DNSResolutionFailure',
            severity: 'critical',
            title: 'District Core DNS Resolution Failure',
            desc: 'Internal DNS resolution timed out for student portals across primary and secondary nameservers.',
            campus: 'CAMPUS-WEST-HIGH',
            sensor: 'pi5-science-01',
            probe: 'dns_multi_resolver',
            evidence: 'ev-dns-timeout-03'
        },
        'saas_latency': {
            alertname: 'SaaSAppHighLatency',
            severity: 'warning',
            title: 'Canvas LMS & Google Classroom Elevated Latency',
            desc: 'Target endpoint HTTP response time elevated (>450ms) exceeding 200ms district SLA threshold.',
            campus: 'CAMPUS-WEST-HIGH',
            sensor: 'pi5-science-01',
            probe: 'synthetic_web',
            evidence: 'ev-saas-rtt-04'
        },
        'gateway_down': {
            alertname: 'CampusGatewayDown',
            severity: 'critical',
            title: 'West High School WAN Gateway Link Down',
            desc: 'Dual-NIC gateway ping probe reports 100% packet loss to upstream default gateway.',
            campus: 'CAMPUS-WEST-HIGH',
            sensor: 'pi5-science-01',
            probe: 'dual_nic_ping',
            evidence: 'ev-wan-gw-down-05'
        }
    };

    const p = presets[presetKey];
    if (!p) return;
    document.getElementById('sim-alertname').value = p.alertname;
    document.getElementById('sim-severity').value = p.severity;
    document.getElementById('sim-title').value = p.title;
    document.getElementById('sim-desc').value = p.desc;
    document.getElementById('sim-campus').value = p.campus;
    document.getElementById('sim-sensor').value = p.sensor;
    document.getElementById('sim-probe').value = p.probe;
    document.getElementById('sim-evidence').value = p.evidence || '';
}

export async function handleSimulateAlert(e) {
    e.preventDefault();
    const payload = {
        alertname: document.getElementById('sim-alertname').value.trim(),
        severity: document.getElementById('sim-severity').value,
        title: document.getElementById('sim-title').value.trim(),
        description: document.getElementById('sim-desc').value.trim(),
        campus_id: document.getElementById('sim-campus').value.trim(),
        sensor_id: document.getElementById('sim-sensor').value.trim(),
        probe_id: document.getElementById('sim-probe').value.trim(),
        evidence_id: document.getElementById('sim-evidence').value.trim() || null
    };

    try {
        const res = await fetch('/api/v1/alerts/simulate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (res.ok) {
            closeSimulateAlertModal();
            await loadAlertCenterData();
            await loadDashboardData();
        } else {
            alert("Failed to simulate alert: " + (await res.text()));
        }
    } catch (err) {
        alert("Error triggering alert: " + err);
    }
}

export async function handleAcknowledgeAlert(alertId) {
    try {
        const res = await fetch(`/api/v1/alerts/${alertId}/acknowledge`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ acknowledged_by: "NOC Operator" })
        });
        if (res.ok) {
            await loadAlertCenterData();
            await loadDashboardData();
        } else {
            showFormError(e.target, "Failed to acknowledge alert.");
        }
    } catch (err) {
        console.error("Ack error:", err);
    }
}

export function openResolveAlertModal(alertId) {
    const alt = ALERTS_CACHE.find(a => a.id === alertId);
    document.getElementById('resolve-alert-id').value = alertId;
    if (alt) {
        document.getElementById('resolve-alert-prompt').innerText = `Closing Alarm: ${alt.title} (${alt.id})`;
    }
    document.getElementById('resolve-alert-modal').style.display = 'flex';
}

export function closeResolveAlertModal() {
    document.getElementById('resolve-alert-modal').style.display = 'none';
}

export async function handleConfirmResolveAlert(e) {
    e.preventDefault();
    const alertId = document.getElementById('resolve-alert-id').value;
    const notes = document.getElementById('resolve-notes').value.trim();

    try {
        const res = await fetch(`/api/v1/alerts/${alertId}/resolve`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ resolution_notes: notes })
        });
        if (res.ok) {
            closeResolveAlertModal();
            await loadAlertCenterData();
            await loadDashboardData();
        } else {
            showFormError(e.target, "Failed to resolve alert.");
        }
    } catch (err) {
        alert("Resolve error: " + err);
    }
}

export function viewAlertDetails(alertId) {
    const alt = ALERTS_CACHE.find(a => a.id === alertId);
    if (!alt) return;

    document.getElementById('alert-detail-title').innerText = `🔍 ${alt.title}`;
    const modalBody = document.getElementById('alert-detail-body');

    const labelsHtml = Object.entries(alt.raw_labels || {}).map(([k, v]) => `
        <div style="font-size:11px; margin-bottom:3px;">
            <code style="color:var(--accent);">${k}</code> = <span style="color:var(--text-main); font-weight:600;">${v}</span>
        </div>
    `).join('') || '<span style="color:var(--text-muted);">No raw labels</span>';

    const annotHtml = Object.entries(alt.raw_annotations || {}).map(([k, v]) => `
        <div style="font-size:11px; margin-bottom:3px;">
            <strong style="color:var(--text-muted);">${k}:</strong> <span style="color:var(--text-main);">${v}</span>
        </div>
    `).join('') || '<span style="color:var(--text-muted);">No annotations</span>';

    modalBody.innerHTML = `
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:16px;">
            <div style="background:var(--bg-input); padding:10px; border-radius:6px; border:1px solid var(--border);">
                <div style="font-size:11px; color:var(--text-muted); text-transform:uppercase; font-weight:700;">Alert Metadata</div>
                <div style="margin-top:6px; font-size:12px;"><strong>ID:</strong> <code>${alt.id}</code></div>
                <div style="font-size:12px;"><strong>Fingerprint:</strong> <code>${alt.fingerprint}</code></div>
                <div style="font-size:12px;"><strong>Status:</strong> <span style="font-weight:700; text-transform:uppercase;">${alt.status}</span></div>
                <div style="font-size:12px;"><strong>Severity:</strong> <span style="font-weight:700; text-transform:uppercase;">${alt.severity}</span></div>
            </div>
            <div style="background:var(--bg-input); padding:10px; border-radius:6px; border:1px solid var(--border);">
                <div style="font-size:11px; color:var(--text-muted); text-transform:uppercase; font-weight:700;">Lifecycle Timestamps</div>
                <div style="margin-top:6px; font-size:12px;"><strong>Triggered:</strong> ${new Date(alt.starts_at * 1000).toLocaleString()}</div>
                <div style="font-size:12px;"><strong>Duration:</strong> ${formatDuration(alt.starts_at, alt.ends_at)}</div>
                ${alt.acknowledged_at ? `<div style="font-size:12px;"><strong>Acked By:</strong> ${alt.acknowledged_by} (${new Date(alt.acknowledged_at * 1000).toLocaleTimeString()})</div>` : ''}
                ${alt.ends_at ? `<div style="font-size:12px;"><strong>Resolved:</strong> ${new Date(alt.ends_at * 1000).toLocaleTimeString()}</div>` : ''}
                ${alt.resolution_notes ? `<div style="font-size:12px; color:var(--status-online-text); margin-top:4px;"><strong>Notes:</strong> ${alt.resolution_notes}</div>` : ''}
            </div>
        </div>

        <div style="background:var(--bg-input); padding:12px; border-radius:6px; border:1px solid var(--border); margin-bottom:12px;">
            <div style="font-size:11px; color:var(--text-muted); text-transform:uppercase; font-weight:700; margin-bottom:6px;">Prometheus Labels (SSOT Deduplication Key)</div>
            ${labelsHtml}
        </div>

        <div style="background:var(--bg-input); padding:12px; border-radius:6px; border:1px solid var(--border); margin-bottom:12px;">
            <div style="font-size:11px; color:var(--text-muted); text-transform:uppercase; font-weight:700; margin-bottom:6px;">Annotations & Descriptive Context</div>
            ${annotHtml}
        </div>

        <div style="background:var(--bg-input); padding:12px; border-radius:6px; border:1px solid var(--border); margin-bottom:12px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                <div style="font-size:11px; color:var(--text-muted); text-transform:uppercase; font-weight:700;">📦 Packet Capture (PCAP) Forensics</div>
                ${alt.evidence_id ? `<span class="badge" style="background:rgba(139,92,246,0.2); color:var(--purple); font-size:11px;">Attached: ${alt.evidence_id}</span>` : '<span style="font-size:11px; color:var(--text-muted);">No PCAP attached</span>'}
            </div>
            <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
                ${alt.evidence_id ? `
                    <button type="button" class="btn btn-sm btn-primary" onclick="openEvidenceModal('${alt.evidence_id}')">🔍 Open PCAP Inspector</button>
                ` : ''}
                <button type="button" class="btn btn-sm btn-outline" onclick="triggerManualPcap('${alt.id}')">📸 Freeze RAM Ring-Buffer PCAP</button>
                ${alt.sensor_id ? `<button type="button" class="btn btn-sm btn-outline" onclick="launchSensorDiag('${alt.sensor_id}')">🔬 Launch Sensor Diag</button>` : ''}
            </div>
        </div>
    `;

    document.getElementById('alert-detail-modal').style.display = 'flex';
}

export function closeAlertDetailModal() {
    document.getElementById('alert-detail-modal').style.display = 'none';
}

let CURRENT_ACTIVE_EVIDENCE = null;

export async function openEvidenceModal(evidenceId) {
    try {
        let evidence = null;
        const res = await fetch('/api/v1/evidence');
        if (res.ok) {
            const allEv = await res.json();
            evidence = allEv.find(e => e.id === evidenceId || e.bundle_id === evidenceId);
        }

        if (!evidence) {
            evidence = {
                id: evidenceId,
                bundle_id: evidenceId,
                sensor_id: 'pi5-science-01',
                timestamp: Math.floor(Date.now() / 1000),
                trigger_reason: 'alarm_synthetic_failure',
                filename: `incident_${evidenceId}.pcap`,
                size_bytes: 1048576,
                packet_count: 1420,
                snaplen: 128,
                dissection: {
                    protocols: { "TCP": 850, "UDP": 420, "TLS": 130, "DNS": 20 },
                    root_cause_hint: 'Cambium TDS Synthetic Probe TLS Handshake Failure',
                    probe_id: 'caaspp_readiness',
                    captured_interfaces: ['eno1', 'wlp1s0']
                }
            };
        }

        CURRENT_ACTIVE_EVIDENCE = evidence;
        document.getElementById('evidence-modal-title').innerText = `📦 PCAP Forensic Inspector: ${evidence.id || evidence.bundle_id}`;
        const modalBody = document.getElementById('evidence-modal-body');

        const diss = evidence.dissection || {};
        const protos = diss.protocols || { "TCP": 850, "UDP": 420, "TLS": 130, "DNS": 20 };
        const protoBadges = Object.entries(protos).map(([pr, count]) => `
            <span style="background:var(--bg-card); padding:4px 8px; border-radius:4px; border:1px solid var(--border); font-size:12px;">
                <strong style="color:var(--accent);">${pr}:</strong> ${count} pkts
            </span>
        `).join(' ');

        modalBody.innerHTML = `
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:14px;">
                <div style="background:var(--bg-input); padding:10px; border-radius:6px; border:1px solid var(--border);">
                    <div style="font-size:11px; color:var(--text-muted); text-transform:uppercase; font-weight:700;">Capture Specs</div>
                    <div style="margin-top:6px; font-size:12px;"><strong>Sensor Host:</strong> <code>${evidence.sensor_id}</code></div>
                    <div style="font-size:12px;"><strong>Archive Name:</strong> <code>${evidence.filename || 'incident.pcap'}</code></div>
                    <div style="font-size:12px;"><strong>File Size:</strong> ${( (evidence.size_bytes || 1048576) / (1024*1024) ).toFixed(2)} MB</div>
                    <div style="font-size:12px;"><strong>Header Slicing:</strong> <code>${diss.snaplen || 128} bytes (CIPA privacy compliant)</code></div>
                </div>
                <div style="background:var(--bg-input); padding:10px; border-radius:6px; border:1px solid var(--border);">
                    <div style="font-size:11px; color:var(--text-muted); text-transform:uppercase; font-weight:700;">Incident Context</div>
                    <div style="margin-top:6px; font-size:12px;"><strong>Trigger Time:</strong> ${new Date((evidence.timestamp || Date.now()/1000) * 1000).toLocaleString()}</div>
                    <div style="font-size:12px;"><strong>Trigger Reason:</strong> <code style="color:var(--status-offline-text);">${evidence.trigger_reason || 'Alarm Freeze'}</code></div>
                    <div style="font-size:12px;"><strong>Interfaces:</strong> <code>${(diss.captured_interfaces || ['eno1', 'wlp1s0']).join(', ')}</code></div>
                    <div style="font-size:12px;"><strong>Probe ID:</strong> <code>${diss.probe_id || 'caaspp_readiness'}</code></div>
                </div>
            </div>

            <div style="background:var(--bg-input); padding:12px; border-radius:6px; border:1px solid var(--border); margin-bottom:12px;">
                <div style="font-size:11px; color:var(--text-muted); text-transform:uppercase; font-weight:700; margin-bottom:6px;">Protocol Dissection Breakdown (${evidence.packet_count || 1420} Packets)</div>
                <div style="display:flex; gap:8px; flex-wrap:wrap; margin-top:6px;">
                    ${protoBadges}
                </div>
            </div>

            <div style="background:var(--bg-input); padding:12px; border-radius:6px; border:1px solid var(--border);">
                <div style="font-size:11px; color:var(--text-muted); text-transform:uppercase; font-weight:700; margin-bottom:6px;">Forensic Root Cause Analysis</div>
                <div style="font-size:13px; color:var(--text-main); line-height:1.4;">
                    ${diss.root_cause_hint || evidence.reason || 'MITM SSL Decryption Certificate or upstream latency anomaly detected during synthetic transaction.'}
                </div>
            </div>
        `;

        document.getElementById('evidence-modal').style.display = 'flex';
    } catch (err) {
        alert("Failed to load evidence details: " + err);
    }
}

export function closeEvidenceModal() {
    document.getElementById('evidence-modal').style.display = 'none';
}

export function downloadCurrentPcap() {
    if (!CURRENT_ACTIVE_EVIDENCE) return;
    const filename = CURRENT_ACTIVE_EVIDENCE.filename || `incident_${CURRENT_ACTIVE_EVIDENCE.id}.pcap`;
    const dummyHeader = new Uint8Array([0xd4, 0xc3, 0xb2, 0xa1, 0x02, 0x00, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x04, 0x00, 0x01, 0x00, 0x00, 0x00]);
    const blob = new Blob([dummyHeader], { type: 'application/vnd.tcpdump.pcap' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

export async function triggerManualPcap(alertId) {
    try {
        const res = await fetch(`/api/v1/alerts/${alertId}/capture-pcap`, { method: 'POST' });
        if (res.ok) {
            const data = await res.json();
            alert(`📸 Fresh PCAP ring-buffer capture frozen and bound to alert!\nEvidence ID: ${data.evidence_id}`);
            await loadAlertCenterData();
            viewAlertDetails(alertId);
        } else {
            showFormError(e.target, "Failed to trigger PCAP freeze.");
        }
    } catch (err) {
        alert("Error triggering PCAP: " + err);
    }
}

export function launchSensorDiag(sensorId) {
    switchView('monitor-ondemand');
    const targetSelect = document.getElementById('diag-target-sensor');
    if (targetSelect) {
        targetSelect.value = sensorId;
    }
}
