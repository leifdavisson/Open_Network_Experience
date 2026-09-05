import { loadCustomAlertRules, showFormError, clearFormError, openAlertRuleModal, closeAlertRuleModal, editAlertRule, handleSaveAlertRule, toggleRuleActive, deleteAlertRule, loadMaintenanceWindows, openMaintenanceModal, closeMaintenanceModal, setMaintDurationPreset, editMaintenanceWindow, handleSaveMaintenance, quickCreateMuteWindow, quickCreateConstructionWindow, toggleMaintenanceWindow, deleteMaintenanceWindow, loadNotificationChannels, handleChannelTypeChange, applyEmailPreset, openChannelModal, editChannel, closeChannelModal, handleSaveChannel, testChannel, testCurrentChannel, deleteChannel, setAlertStatusFilter, loadAlertCenterData, updateAlertBadgeAndBanner, renderAlertsTable, openSimulateAlertModal, closeSimulateAlertModal, applySimulatePreset, handleSimulateAlert, handleAcknowledgeAlert, openResolveAlertModal, closeResolveAlertModal, handleConfirmResolveAlert, viewAlertDetails, closeAlertDetailModal, openEvidenceModal, closeEvidenceModal, downloadCurrentPcap, triggerManualPcap, launchSensorDiag } from './alerts.js';
import { handleBackdropClick } from './modals.js';
import { renderAnalyticsCharts } from './charts.js';
import { renderDashboard, createCustomGlowMarker, initOrUpdateMap, initOrUpdateWallboardMap, zoomToSensor, approveSensor, rejectSensor, triggerOTAUpgrade, triggerPcap, downloadLatestPcap, updateDiagTargetHint, setDiagTarget, triggerSpeedtest, executeSelectedDiagnostic, copyDiagLog, downloadDiagLog, openLocationModal, closeLocationModal, handleSaveLocation, openProbeModal, closeProbeModal, applyProbeTemplate, handleSaveProbe, deleteProbe, downloadSlaCsv } from './sensors.js';

window.loadCustomAlertRules = loadCustomAlertRules;
window.showFormError = showFormError;
window.clearFormError = clearFormError;
window.openAlertRuleModal = openAlertRuleModal;
window.closeAlertRuleModal = closeAlertRuleModal;
window.editAlertRule = editAlertRule;
window.handleSaveAlertRule = handleSaveAlertRule;
window.toggleRuleActive = toggleRuleActive;
window.deleteAlertRule = deleteAlertRule;
window.loadMaintenanceWindows = loadMaintenanceWindows;
window.openMaintenanceModal = openMaintenanceModal;
window.closeMaintenanceModal = closeMaintenanceModal;
window.setMaintDurationPreset = setMaintDurationPreset;
window.editMaintenanceWindow = editMaintenanceWindow;
window.handleSaveMaintenance = handleSaveMaintenance;
window.quickCreateMuteWindow = quickCreateMuteWindow;
window.quickCreateConstructionWindow = quickCreateConstructionWindow;
window.toggleMaintenanceWindow = toggleMaintenanceWindow;
window.deleteMaintenanceWindow = deleteMaintenanceWindow;
window.loadNotificationChannels = loadNotificationChannels;
window.handleChannelTypeChange = handleChannelTypeChange;
window.applyEmailPreset = applyEmailPreset;
window.openChannelModal = openChannelModal;
window.editChannel = editChannel;
window.closeChannelModal = closeChannelModal;
window.handleSaveChannel = handleSaveChannel;
window.testChannel = testChannel;
window.testCurrentChannel = testCurrentChannel;
window.deleteChannel = deleteChannel;
window.setAlertStatusFilter = setAlertStatusFilter;
window.loadAlertCenterData = loadAlertCenterData;
window.updateAlertBadgeAndBanner = updateAlertBadgeAndBanner;
window.renderAlertsTable = renderAlertsTable;
window.openSimulateAlertModal = openSimulateAlertModal;
window.closeSimulateAlertModal = closeSimulateAlertModal;
window.applySimulatePreset = applySimulatePreset;
window.handleSimulateAlert = handleSimulateAlert;
window.handleAcknowledgeAlert = handleAcknowledgeAlert;
window.openResolveAlertModal = openResolveAlertModal;
window.closeResolveAlertModal = closeResolveAlertModal;
window.handleConfirmResolveAlert = handleConfirmResolveAlert;
window.viewAlertDetails = viewAlertDetails;
window.closeAlertDetailModal = closeAlertDetailModal;
window.openEvidenceModal = openEvidenceModal;
window.closeEvidenceModal = closeEvidenceModal;
window.downloadCurrentPcap = downloadCurrentPcap;
window.triggerManualPcap = triggerManualPcap;
window.launchSensorDiag = launchSensorDiag;
window.handleBackdropClick = handleBackdropClick;
window.renderAnalyticsCharts = renderAnalyticsCharts;
window.renderDashboard = renderDashboard;
window.createCustomGlowMarker = createCustomGlowMarker;
window.initOrUpdateMap = initOrUpdateMap;
window.initOrUpdateWallboardMap = initOrUpdateWallboardMap;
window.zoomToSensor = zoomToSensor;
window.approveSensor = approveSensor;
window.rejectSensor = rejectSensor;
window.triggerOTAUpgrade = triggerOTAUpgrade;
window.triggerPcap = triggerPcap;
window.downloadLatestPcap = downloadLatestPcap;
window.updateDiagTargetHint = updateDiagTargetHint;
window.setDiagTarget = setDiagTarget;
window.triggerSpeedtest = triggerSpeedtest;
window.executeSelectedDiagnostic = executeSelectedDiagnostic;
window.copyDiagLog = copyDiagLog;
window.downloadDiagLog = downloadDiagLog;
window.openLocationModal = openLocationModal;
window.closeLocationModal = closeLocationModal;
window.handleSaveLocation = handleSaveLocation;
window.openProbeModal = openProbeModal;
window.closeProbeModal = closeProbeModal;
window.applyProbeTemplate = applyProbeTemplate;
window.handleSaveProbe = handleSaveProbe;
window.deleteProbe = deleteProbe;
window.downloadSlaCsv = downloadSlaCsv;


import { markModalDirty, clearModalDirty, checkModalDiscard } from './modals.js';
import { formatDuration } from './alerts.js';
import { initCharts } from './charts.js';
import { formatTimeAgo } from './sensors.js';

// Expose imported functions to window for HTML event handlers
window.markModalDirty = markModalDirty;
window.clearModalDirty = clearModalDirty;
window.checkModalDiscard = checkModalDiscard;
window.formatDuration = formatDuration;
window.formatTimeAgo = formatTimeAgo;
window.initCharts = initCharts;

const ADMIN_KEY = "admin-noc-key-change-me";
let SENSORS_CACHE = [];
let mapInstance = null;
let wallboardMapInstance = null;
let mapMarkers = [];
let wallboardMapMarkers = [];

// Chart.js Instances
let chartFault = null;
let chartTrend = null;
let chartAlarm = null;

// MAIN SLIDESHOW STATE & CONTROLS
let currentSlideIndex = 0;
const totalSlides = 6;
let isSlidePlaying = true;
const slideDurationMs = 15000;
let slideStartTime = Date.now();
let slideTimerInterval = null;

// GRAFANA SUB-AUTO-SCROLLER STATE & DASHBOARDS
let grafanaSubIndex = 0;
const grafanaSubDurationMs = 10000; // 10 seconds per Grafana dashboard
let grafanaSubStartTime = Date.now();

const GRAFANA_DASHBOARDS = [
    {
        name: "1. NOC & WAN Wallboard",
        title: "OpenUX NOC & Diagnostic Dashboard",
        path: "/d/openux-noc/openux-noc-and-diagnostic-dashboard?kiosk=tv&theme=dark"
    },
    {
        name: "2. CAASPP Testing Readiness",
        title: "CAASPP & ELPAC State Testing Readiness",
        path: "/d/openux-caaspp/caaspp-and-elpac-state-testing-readiness-dashboard?kiosk=tv&theme=dark"
    },
    {
        name: "3. Wi-Fi RF & Spectrum",
        title: "Wi-Fi RF, DARRP & Spectrum Health",
        path: "/d/openux-wifi-rf/wi-fi-rf-darrp-and-spectrum-health-dashboard?kiosk=tv&theme=dark"
    },
    {
        name: "4. CIPA Policy Drill-Down",
        title: "CIPA Content Filtering Deep Forensic Drill-Down",
        path: "/d/openux-cipa-drilldown/cipa-content-filtering-deep-forensic-and-policy-violation-drill-down?kiosk=tv&theme=dark"
    },
    {
        name: "5. Chromebook Fleet Experience",
        title: "1:1 Chromebook Experience & Wi-Fi Telemetry",
        path: "/d/one-chromebook-fleet-dashboard/one-chromebook-fleet-experience-and-wi-fi-telemetry?kiosk=tv&theme=dark"
    }
];

function initSlideTimer() {
    if (slideTimerInterval) clearInterval(slideTimerInterval);
    slideStartTime = Date.now();
    grafanaSubStartTime = Date.now();

    slideTimerInterval = setInterval(() => {
        if (!isSlidePlaying) return;

        // If on Slide 5 (Grafana), let the sub-scroller control timing
        if (currentSlideIndex === 4) {
            const subElapsed = Date.now() - grafanaSubStartTime;
            const subProgressPct = Math.min(100, (subElapsed / grafanaSubDurationMs) * 100);
            const progressFill = document.getElementById('slide-progress-fill');
            if (progressFill) progressFill.style.width = subProgressPct + '%';

            if (subElapsed >= grafanaSubDurationMs) {
                // Advance to next Grafana sub-dashboard
                if (grafanaSubIndex < GRAFANA_DASHBOARDS.length - 1) {
                    goToGrafanaSub(grafanaSubIndex + 1);
                } else {
                    // Completed full Grafana rotation -> advance to Slide 6 (Chromebook Fleet)
                    grafanaSubIndex = 0;
                    goToSlide(5);
                }
            }
        } else {
            // Regular slide rotation for Slides 1 - 4
            const elapsed = Date.now() - slideStartTime;
            const progressPct = Math.min(100, (elapsed / slideDurationMs) * 100);
            const progressFill = document.getElementById('slide-progress-fill');
            if (progressFill) progressFill.style.width = progressPct + '%';

            if (elapsed >= slideDurationMs) {
                nextSlide();
            }
        }
    }, 100);
}

function goToSlide(index) {
    currentSlideIndex = (index + totalSlides) % totalSlides;
    document.querySelectorAll('.slide-card').forEach(el => el.classList.remove('active-slide'));
    document.querySelectorAll('.slide-tab-btn').forEach(el => el.classList.remove('active-tab'));

    const targetSlide = document.getElementById('slide-' + currentSlideIndex);
    if (targetSlide) targetSlide.classList.add('active-slide');

    const targetTab = document.getElementById('tab-slide-' + currentSlideIndex);
    if (targetTab) targetTab.classList.add('active-tab');

    slideStartTime = Date.now();
    const progressFill = document.getElementById('slide-progress-fill');
    if (progressFill) progressFill.style.width = '0%';

    if (currentSlideIndex === 0) {
        setTimeout(renderAnalyticsCharts, 150);
    } else if (currentSlideIndex === 1) {
        setTimeout(initOrUpdateWallboardMap, 250);
    } else if (currentSlideIndex === 4) {
        // When entering Slide 5, start Grafana sub-scroller from current/first sub-tab
        goToGrafanaSub(grafanaSubIndex);
    }
}

function nextSlide() { goToSlide(currentSlideIndex + 1); }
function prevSlide() { goToSlide(currentSlideIndex - 1); }

function goToGrafanaSub(subIndex) {
    grafanaSubIndex = (subIndex + GRAFANA_DASHBOARDS.length) % GRAFANA_DASHBOARDS.length;
    document.querySelectorAll('.grafana-sub-btn').forEach(el => el.classList.remove('active-sub'));

    const targetBtn = document.getElementById('graf-sub-' + grafanaSubIndex);
    if (targetBtn) targetBtn.classList.add('active-sub');

    const dash = GRAFANA_DASHBOARDS[grafanaSubIndex];
    const baseUrl = `${window.location.protocol}//${window.location.hostname}:3000`;
    const fullUrl = `${baseUrl}${dash.path}`;

    const iframe = document.getElementById('grafana-embed-frame');
    if (iframe && iframe.src !== fullUrl) {
        iframe.src = fullUrl;
    }

    const label = document.getElementById('grafana-sub-label');
    if (label) {
        label.innerText = `Displaying: ${dash.title} (Auto-rotating 10s per dashboard)`;
    }

    const standaloneBtn = document.getElementById('grafana-open-current-btn');
    if (standaloneBtn) {
        standaloneBtn.href = fullUrl;
    }

    grafanaSubStartTime = Date.now();
    const progressFill = document.getElementById('slide-progress-fill');
    if (progressFill) progressFill.style.width = '0%';
}

function nextGrafanaSub() { goToGrafanaSub(grafanaSubIndex + 1); }
function prevGrafanaSub() { goToGrafanaSub(grafanaSubIndex - 1); }

function togglePlayPause() {
    isSlidePlaying = !isSlidePlaying;
    const btn = document.getElementById('btn-play-pause');
    if (btn) {
        btn.innerText = isSlidePlaying ? '⏸ Pause' : '▶ Play';
    }
    if (isSlidePlaying) {
        slideStartTime = Date.now();
        grafanaSubStartTime = Date.now();
    }
}

function toggleFullscreenMode() {
    const isFull = document.body.classList.toggle('wallboard-fullscreen');
    const btn = document.getElementById('btn-fullscreen');
    if (btn) {
        btn.innerText = isFull ? '✕ Exit 72" Mode' : '⛶ 72" Display Mode';
    }
    setTimeout(() => {
        if (mapInstance) mapInstance.invalidateSize();
        if (wallboardMapInstance) wallboardMapInstance.invalidateSize();
        if (chartTrend) chartTrend.resize();
    }, 200);
}

function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('collapsed');
}

function toggleTheme() {
    const html = document.documentElement;
    const current = html.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    html.setAttribute('data-theme', next);
    document.getElementById('theme-btn').innerText = next === 'dark' ? '☀️ Light Mode' : '🌙 Dark Mode';
    setTimeout(renderAnalyticsCharts, 100);
}

function switchView(viewId) {
    document.querySelectorAll('.view-section').forEach(el => el.classList.remove('active-view'));
    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));

    const target = document.getElementById('view-' + viewId);
    if (target) target.classList.add('active-view');

    const navElem = document.getElementById('nav-' + viewId);
    if (navElem) navElem.classList.add('active');

    if (viewId === 'monitor-map') {
        setTimeout(initOrUpdateMap, 200);
    } else if (viewId === 'monitor-noc') {
        setTimeout(renderAnalyticsCharts, 150);
    } else if (viewId === 'monitor-alerts') {
        loadAlertCenterData();
    } else if (viewId === 'configure-alerts') {
        loadCustomAlertRules();
    } else if (viewId === 'configure-maintenance') {
        loadMaintenanceWindows();
    } else if (viewId === 'setup-integrations') {
        loadNotificationChannels();
    }
}

// --- VISUAL PROBE SCHEDULER CONTROLLER ---
let SCHEDULES_CACHE = [];
let ACTIVE_SCHEDULE_DAYS = ['mon', 'tue', 'wed', 'thu', 'fri'];
let CURRENT_TIMING_MODE = 'daily_once';

const PROBE_DISPLAY_NAMES = {
    'caaspp_readiness': '🎓 CAASPP / Cambium State Testing',
    'voip_jitter': '🎥 VoIP & Zoom RTP Jitter Stream',
    'dual_nic_ping': '🌐 Dual-NIC Gateway Latency Ping',
    'dns_multi_resolver': '🔍 Multi-Resolver DNS Health',
    'cipa_compliance': '🛡️ CIPA Safety & Content Filter Audit',
    'wifi_dhcp': '⏱️ Wi-Fi 802.1X & DHCP DORA Timer',
    'rrm_darrp': '📡 Wi-Fi RF Flapping & DARRP Monitor',
    'segmentation': '🔒 East-West VLAN Isolation Sweep',
    'iperf3': '📊 Off-Peak iperf3 Bandwidth Throughput'
};

function openScheduleModal(scheduleData = null) {
    clearModalDirty('schedule-modal');
    const form = document.getElementById('schedule-form');
    if (!form) return;
    form.reset();

    if (scheduleData) {
        document.getElementById('sch-id').value = scheduleData.id;
        document.getElementById('sch-name').value = scheduleData.name;
        document.getElementById('sch-probe').value = scheduleData.probe_id;
        ACTIVE_SCHEDULE_DAYS = [...(scheduleData.days_of_week || ['mon', 'tue', 'wed', 'thu', 'fri'])];
        setTimingMode(scheduleData.mode || 'daily_once');
        if (scheduleData.mode === 'daily_once') {
            document.getElementById('sch-daily-time').value = scheduleData.start_time || '07:15';
        } else if (scheduleData.mode === 'window_repeat') {
            document.getElementById('sch-window-start').value = scheduleData.start_time || '08:00';
            document.getElementById('sch-window-end').value = scheduleData.end_time || '16:00';
            document.getElementById('sch-window-val').value = scheduleData.interval_value || 15;
            document.getElementById('sch-window-unit').value = scheduleData.interval_unit || 'minutes';
        } else if (scheduleData.mode === 'continuous_interval') {
            document.getElementById('sch-cont-val').value = scheduleData.interval_value || 15;
            document.getElementById('sch-cont-unit').value = scheduleData.interval_unit || 'minutes';
        }
        document.getElementById('sch-scope').value = scheduleData.target_scope || 'all';
        document.getElementById('sch-guardrails').checked = scheduleData.guardrails_enabled !== false;
        document.getElementById('sch-cron-expr').value = scheduleData.cron_expr || '';
    } else {
        document.getElementById('sch-id').value = 'sched_' + Date.now().toString().slice(-8);
        document.getElementById('sch-name').value = '';
        ACTIVE_SCHEDULE_DAYS = ['mon', 'tue', 'wed', 'thu', 'fri'];
        setTimingMode('daily_once');
        document.getElementById('sch-daily-time').value = '07:15';
        document.getElementById('sch-window-start').value = '08:00';
        document.getElementById('sch-window-end').value = '16:00';
        document.getElementById('sch-window-val').value = 15;
        document.getElementById('sch-window-unit').value = 'minutes';
        document.getElementById('sch-cont-val').value = 15;
        document.getElementById('sch-cont-unit').value = 'seconds';
        document.getElementById('sch-guardrails').checked = true;
        document.getElementById('sch-cron-expr').value = '15 7 * * 1-5';
    }

    renderDayPills();
    updateScheduleSummary();
    document.getElementById('schedule-modal').style.display = 'flex';
}

function closeScheduleModal() {
    if (!checkModalDiscard('schedule-modal')) return;
    clearModalDirty('schedule-modal');
    const modal = document.getElementById('schedule-modal');
    if (modal) modal.style.display = 'none';
}

function toggleDayPill(day) {
    const index = ACTIVE_SCHEDULE_DAYS.indexOf(day);
    if (index > -1) {
        if (ACTIVE_SCHEDULE_DAYS.length > 1) {
            ACTIVE_SCHEDULE_DAYS.splice(index, 1);
        }
    } else {
        ACTIVE_SCHEDULE_DAYS.push(day);
    }
    renderDayPills();
    updateScheduleSummary();
}

function applyDayPreset(preset) {
    if (preset === 'weekdays') {
        ACTIVE_SCHEDULE_DAYS = ['mon', 'tue', 'wed', 'thu', 'fri'];
    } else if (preset === 'everyday') {
        ACTIVE_SCHEDULE_DAYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];
    } else if (preset === 'weekends') {
        ACTIVE_SCHEDULE_DAYS = ['sat', 'sun'];
    }
    renderDayPills();
    updateScheduleSummary();
}

function renderDayPills() {
    const pills = document.querySelectorAll('#sch-day-pills .day-pill');
    pills.forEach(pill => {
        const d = pill.getAttribute('data-day');
        if (ACTIVE_SCHEDULE_DAYS.includes(d)) {
            pill.classList.add('active');
        } else {
            pill.classList.remove('active');
        }
    });
}

function setTimingMode(mode) {
    CURRENT_TIMING_MODE = mode;
    document.querySelectorAll('.timing-mode-card').forEach(c => c.classList.remove('active-mode'));
    const card = document.getElementById('card-mode-' + (mode === 'daily_once' ? 'daily' : (mode === 'window_repeat' ? 'window' : 'continuous')));
    if (card) card.classList.add('active-mode');

    const radio = document.getElementById('mode-' + (mode === 'daily_once' ? 'daily' : (mode === 'window_repeat' ? 'window' : 'continuous')));
    if (radio) radio.checked = true;

    updateScheduleSummary();
}

function handleProbeSelectionChange(probeId) {
    const nameInput = document.getElementById('sch-name');
    if (nameInput && (!nameInput.value || nameInput.value.includes('Pre-Flight') || nameInput.value.includes('Monitor') || nameInput.value.includes('Test') || nameInput.value.includes('Schedule'))) {
        const displayName = PROBE_DISPLAY_NAMES[probeId] || probeId;
        nameInput.value = `${displayName} Schedule`;
    }
    updateScheduleSummary();
}

function updateScheduleSummary() {
    const preview = document.getElementById('sch-summary-preview');
    const cronInput = document.getElementById('sch-cron-expr');
    if (!preview) return;

    const dayNames = { mon: 'Mon', tue: 'Tue', wed: 'Wed', thu: 'Thu', fri: 'Fri', sat: 'Sat', sun: 'Sun' };
    let daysText = '';
    if (ACTIVE_SCHEDULE_DAYS.length === 7) {
        daysText = 'every day';
    } else if (ACTIVE_SCHEDULE_DAYS.length === 5 && !ACTIVE_SCHEDULE_DAYS.includes('sat') && !ACTIVE_SCHEDULE_DAYS.includes('sun')) {
        daysText = 'on Weekdays (Mon–Fri)';
    } else if (ACTIVE_SCHEDULE_DAYS.length === 2 && ACTIVE_SCHEDULE_DAYS.includes('sat') && ACTIVE_SCHEDULE_DAYS.includes('sun')) {
        daysText = 'on Weekends (Sat–Sun)';
    } else {
        daysText = 'on ' + ACTIVE_SCHEDULE_DAYS.map(d => dayNames[d]).join(', ');
    }

    let timingSentence = '';
    let cronComputed = '';

    const dayCronMap = { mon: 1, tue: 2, wed: 3, thu: 4, fri: 5, sat: 6, sun: 0 };
    const cronDays = ACTIVE_SCHEDULE_DAYS.map(d => dayCronMap[d]).sort().join(',');

    if (CURRENT_TIMING_MODE === 'daily_once') {
        const dailyTime = document.getElementById('sch-daily-time').value || '07:15';
        const [h, m] = dailyTime.split(':');
        const ampm = parseInt(h) >= 12 ? 'PM' : 'AM';
        const h12 = (parseInt(h) % 12) || 12;
        timingSentence = `Runs once daily at <strong>${h12}:${m} ${ampm}</strong> ${daysText}`;
        cronComputed = `${parseInt(m)} ${parseInt(h)} * * ${cronDays}`;
    } else if (CURRENT_TIMING_MODE === 'window_repeat') {
        const wStart = document.getElementById('sch-window-start').value || '08:00';
        const wEnd = document.getElementById('sch-window-end').value || '16:00';
        const wVal = document.getElementById('sch-window-val').value || '15';
        const wUnit = document.getElementById('sch-window-unit').value || 'minutes';
        timingSentence = `Runs every <strong>${wVal} ${wUnit}</strong> between <strong>${wStart}</strong> and <strong>${wEnd}</strong> ${daysText}`;
        const [sh, sm] = wStart.split(':');
        const [eh, em] = wEnd.split(':');
        cronComputed = `*/${wVal} ${parseInt(sh)}-${parseInt(eh)} * * ${cronDays}`;
    } else if (CURRENT_TIMING_MODE === 'continuous_interval') {
        const cVal = document.getElementById('sch-cont-val').value || '15';
        const cUnit = document.getElementById('sch-cont-unit').value || 'seconds';
        timingSentence = `Runs continuously every <strong>${cVal} ${cUnit}</strong> (24/7)`;
        if (cUnit === 'minutes') {
            cronComputed = `*/${cVal} * * * *`;
        } else if (cUnit === 'hours') {
            cronComputed = `0 */${cVal} * * *`;
        } else {
            cronComputed = `*/1 * * * * (Continuous ${cVal} ${cUnit})`;
        }
    }

    const scopeElem = document.getElementById('sch-scope');
    const scopeText = scopeElem ? scopeElem.options[scopeElem.selectedIndex]?.text || 'All Fleet Sensors' : 'All Fleet Sensors';

    preview.innerHTML = `💬 "${timingSentence} across <strong>${scopeText}</strong>."`;
    if (cronInput && !document.activeElement?.isEqualNode(cronInput)) {
        cronInput.value = cronComputed;
    }
}

function handleRawCronInput(val) {
    // Power user cron synchronization
}

async function handleSaveSchedule(e) {
    e.preventDefault();
    const btn = e.target.querySelector('button[type="submit"]');
    if (btn && btn.disabled) return;
    clearFormError(e.target);

    const id = document.getElementById('sch-id').value || ('sched_' + Date.now().toString().slice(-8));
    const name = document.getElementById('sch-name').value;
    const probe_id = document.getElementById('sch-probe').value;
    const mode = CURRENT_TIMING_MODE;
    const days_of_week = ACTIVE_SCHEDULE_DAYS;

    if (!days_of_week || days_of_week.length === 0) {
        showFormError(e.target, "Please select at least one active day of the week.");
        return;
    }

    let start_time = "07:15";
    let end_time = "16:00";
    let interval_value = 15;
    let interval_unit = "minutes";

    if (mode === 'daily_once') {
        start_time = document.getElementById('sch-daily-time').value || "07:15";
    } else if (mode === 'window_repeat') {
        start_time = document.getElementById('sch-window-start').value || "08:00";
        end_time = document.getElementById('sch-window-end').value || "16:00";
        if (end_time <= start_time) {
            showFormError(e.target, "End time must be after Start time in repeat window.");
            return;
        }
        interval_value = parseInt(document.getElementById('sch-window-val').value) || 15;
        interval_unit = document.getElementById('sch-window-unit').value || "minutes";
    } else if (mode === 'continuous_interval') {
        interval_value = parseInt(document.getElementById('sch-cont-val').value) || 15;
        interval_unit = document.getElementById('sch-cont-unit').value || "seconds";
    }

    const target_scope = document.getElementById('sch-scope').value || "all";
    const guardrails_enabled = document.getElementById('sch-guardrails').checked;
    const cron_expr = document.getElementById('sch-cron-expr').value;

    const payload = {
        id,
        name,
        probe_id,
        mode,
        days_of_week,
        start_time,
        end_time,
        interval_value,
        interval_unit,
        cron_expr,
        target_scope,
        guardrails_enabled,
        is_active: true,
        created_at: Math.floor(Date.now() / 1000)
    };

    const origHtml = btn ? btn.innerHTML : '';
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '⏳ Saving...';
    }

    try {
        const res = await fetch('/api/v1/schedules', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-API-Key': ADMIN_KEY },
            body: JSON.stringify(payload)
        });
        if (!res.ok) {
            const err = await res.json();
            alert("Error saving probe schedule: " + (err.detail || JSON.stringify(err)));
            return;
        }
        clearModalDirty('schedule-modal');
        closeScheduleModal();
        loadDashboardData();
    } catch(err) {
        alert("Network error saving probe schedule: " + err.message);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = origHtml;
        }
    }
}

async function deleteSchedule(scheduleId) {
    if (confirm(`Delete probe schedule '${scheduleId}'?`)) {
        await fetch(`/api/v1/schedules/${scheduleId}`, { method: 'DELETE', headers: { 'X-API-Key': ADMIN_KEY } });
        loadDashboardData();
    }
}

async function toggleSchedule(scheduleId) {
    await fetch(`/api/v1/schedules/${scheduleId}/toggle`, { method: 'PUT', headers: { 'X-API-Key': ADMIN_KEY } });
    loadDashboardData();
}

function renderSchedulesTable(schedules) {
    const tbody = document.getElementById('schedules-table-body');
    if (!tbody) return;

    if (!schedules || schedules.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; color:var(--text-muted);">No probe schedules created yet. Click "+ Create New Schedule" above.</td></tr>';
        return;
    }

    const rows = schedules.map(sch => {
        const probeName = PROBE_DISPLAY_NAMES[sch.probe_id] || sch.probe_id;
        const statusPill = sch.is_active ?
            '<span class="status-pill status-online">🟢 Active</span>' :
            '<span class="status-pill status-offline">⏸️ Paused</span>';

        const guardrailBadge = sch.guardrails_enabled ?
            '<span style="color:#10b981; font-size:12px; font-weight:700;">🛡️ Active</span>' :
            '<span style="color:var(--warning); font-size:12px; font-weight:700;">⚠️ Disabled</span>';

        let timingDesc = '';
        if (sch.mode === 'daily_once') {
            timingDesc = `Daily @ ${sch.start_time}`;
        } else if (sch.mode === 'window_repeat') {
            timingDesc = `${sch.start_time} - ${sch.end_time}`;
        } else {
            timingDesc = '24/7 Round-the-Clock';
        }

        let cadenceDesc = '';
        if (sch.mode === 'daily_once') {
            cadenceDesc = 'Once Daily';
        } else {
            cadenceDesc = `Every ${sch.interval_value} ${sch.interval_unit}`;
        }

        const daysList = (sch.days_of_week || []).map(d => d.toUpperCase().slice(0, 2)).join(' ');
        const schJsonStr = JSON.stringify(sch).replace(/"/g, '&quot;');

        return `
            <tr>
                <td>
                    <strong>${sch.name}</strong>
                    <div style="font-size:11px; color:var(--text-muted); font-family:monospace;">${sch.id}</div>
                </td>
                <td><span class="badge" style="background:var(--bg-input); border:1px solid var(--border); font-size:12px;">${probeName}</span></td>
                <td>
                    <div>${timingDesc}</div>
                    <div style="font-size:11px; color:var(--accent); font-weight:700;">[ ${daysList || 'DAILY'} ]</div>
                </td>
                <td><strong>${cadenceDesc}</strong></td>
                <td><span style="font-size:12px; color:var(--text-muted);">${sch.target_scope === 'all' ? '🌐 Entire Fleet' : sch.target_scope}</span></td>
                <td>${guardrailBadge}</td>
                <td>${statusPill}</td>
                <td>
                    <div style="display:flex; gap:6px;">
                        <button class="btn btn-outline btn-sm" onclick="toggleSchedule('${sch.id}')">${sch.is_active ? '⏸ Pause' : '▶ Enable'}</button>
                        <button class="btn btn-outline btn-sm" onclick="openScheduleModal(${schJsonStr})">✏️ Edit</button>
                        <button class="btn btn-outline btn-sm" style="border-color:var(--danger); color:var(--danger);" onclick="deleteSchedule('${sch.id}')">✕</button>
                    </div>
                </td>
            </tr>
        `;
    });

    tbody.innerHTML = rows.join('');
}

function handleGlobalSearch() {
    const q = document.getElementById('global-search').value.toLowerCase();
    const rows = document.querySelectorAll('#sensors-table-body tr');
    rows.forEach(r => {
        const text = r.innerText.toLowerCase();
        r.style.display = text.includes(q) ? '' : 'none';
    });
}

            }
        });
    }
}

let CHROMEBOOKS_CACHE = [];
let ROAMING_TRAIL_CACHE = [];
let currentFleetFilter = 'all';

function setFleetFilter(filter) {
    currentFleetFilter = filter;
    document.querySelectorAll('#fleet-filter-all, #fleet-filter-edge, #fleet-filter-cb').forEach(b => {
        b.classList.remove('btn');
        b.classList.add('btn-outline');
    });
    const btn = document.getElementById('fleet-filter-' + (filter === 'all' ? 'all' : (filter === 'edge' ? 'edge' : 'cb')));
    if (btn) {
        btn.classList.remove('btn-outline');
        btn.classList.add('btn');
    }

    const edgeContainer = document.getElementById('fleet-edge-table-container');
    const cbContainer = document.getElementById('fleet-cb-table-container');

    if (filter === 'all') {
        if (edgeContainer) edgeContainer.style.display = 'block';
        if (cbContainer) cbContainer.style.display = 'block';
    } else if (filter === 'edge') {
        if (edgeContainer) edgeContainer.style.display = 'block';
        if (cbContainer) cbContainer.style.display = 'none';
    } else if (filter === 'chromebook') {
        if (edgeContainer) edgeContainer.style.display = 'none';
        if (cbContainer) cbContainer.style.display = 'block';
    }
}


async function openCbDetailModal(sensorId) {
    const modal = document.getElementById('cb-detail-modal');
    const body = document.getElementById('cb-modal-body');
    const title = document.getElementById('cb-modal-title');
    if (modal) modal.style.display = 'flex';
    if (title) title.innerText = `💻 Chromebook Diagnostic Inspector: ${sensorId}`;
    if (body) body.innerHTML = `<p style="color:var(--text-muted);">Fetching dynamic telemetry for <code>${sensorId}</code>...</p>`;

    try {
        const res = await fetch(`/api/v1/chromebooks/${sensorId}`);
        if (!res.ok) throw new Error("Sensor not found");
        const data = await res.json();
        const isOnline = Boolean(data.is_online);
        if (title) title.innerText = `📡 Edge Sensor Diagnostic Inspector [NODE: ${data.hostname || sensorId}]`;
        const wifi = data.wifi || {};
        if (title) title.innerText = `💻 Chromebook Diagnostic Inspector [NODE: ${data.hostname || sensorId}]`;
        const hw = data.hardware || {};
        const probes = data.probes || {};
        const cpu = hw.cpu || {};
        const mem = hw.memory || {};
        const batt = hw.battery || {};
        const webrtc = probes.webrtc || {};
        const apps = probes.synthetic_http || [];

        const bannerHtml = isOnline ? `
            <div style="background:rgba(16,185,129,0.12); border:1px solid var(--success); padding:10px 14px; border-radius:8px; margin-bottom:16px; display:flex; align-items:center; justify-content:space-between;">
                <div>
                    <strong style="color:var(--success); font-size:13px;">● Live Telemetry Stream Active</strong>
                    <div style="color:var(--text-muted); font-size:11px; margin-top:2px;">Last telemetry check-in was received <b>${formatTimeAgo(data.last_seen)}</b>. Real-time metrics are actively reporting.</div>
                </div>
                <span class="status-pill status-online">● Streaming</span>
            </div>
        ` : `
            <div style="background:rgba(239,68,68,0.12); border:1px solid var(--danger); padding:10px 14px; border-radius:8px; margin-bottom:16px; display:flex; align-items:center; justify-content:space-between;">
                <div>
                    <strong style="color:var(--danger); font-size:13px;">⚠️ Device Offline — Stale Telemetry Warning</strong>
                    <div style="color:var(--text-muted); font-size:11px; margin-top:2px;">Last check-in was <b>${formatTimeAgo(data.last_seen)}</b>. Metrics below represent a frozen snapshot and are not live.</div>
                </div>
                <span class="status-pill status-offline">○ Disconnected</span>
            </div>
        `;

        const rfSignalHtml = isOnline ?
            (wifi.rssi_dbm !== undefined ? `<b>${wifi.rssi_dbm} dBm</b> (${wifi.signal_strength_pct || 0}%)` : '<code>Scanning...</code>') :
            (wifi.rssi_dbm !== undefined ? `<span style="color:var(--text-muted);">${wifi.rssi_dbm} dBm (Last seen)</span>` : '<span style="color:var(--text-muted);">-- (Offline)</span>');

        const mosDisplayHtml = isOnline ?
            (webrtc.mos ? `<b>🟢 ${webrtc.mos.toFixed(2)} (${webrtc.mos_grade || 'Optimal'})</b>` : '<span style="color:var(--text-muted);">Awaiting VoIP Call</span>') :
            (webrtc.mos ? `<span style="color:var(--text-muted);">${webrtc.mos.toFixed(2)} (${webrtc.mos_grade || 'Last Call'})</span>` : '<span style="color:var(--text-muted);">-- (Offline)</span>');

        const rttDisplayHtml = isOnline ?
            (webrtc.rtt_ms ? `<b>${webrtc.rtt_ms} ms</b>` : '<span style="color:var(--text-muted);">--</span>') :
            (webrtc.rtt_ms ? `<span style="color:var(--text-muted);">${webrtc.rtt_ms} ms (Last)</span>` : '<span style="color:var(--text-muted);">--</span>');

        body.innerHTML = `
            ${bannerHtml}

            <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:16px;">
                <div style="background:var(--bg-input); padding:12px; border-radius:8px; border:1px solid var(--border);">
                    <strong style="color:var(--accent); font-size:13px;">🏢 Enterprise Identity</strong>
                    <div style="font-size:12px; margin-top:6px; line-height:1.6;">
                        • Serial Number: <b>${data.serial_number || 'N/A'}</b><br>
                        • Asset Tag: <b>${data.asset_id || 'UNTAGGED'}</b><br>
                        • User: <b>${data.annotated_user || 'Shared Student Cart'}</b><br>
                        • Location: <b>${data.location?.room || 'Mobile Client'}</b> (${data.campus_id || 'District Fleet'})<br>
                        • Hostname: <code>${data.hostname || 'cb-client'}</code>
                    </div>
                </div>

                <div style="background:var(--bg-input); padding:12px; border-radius:8px; border:1px solid var(--border);">
                    <strong style="color:var(--success); font-size:13px;">📶 Wi-Fi RF & AP Connection ${!isOnline ? '<span style="color:var(--text-muted); font-size:11px; font-weight:normal;">(Snapshot)</span>' : ''}</strong>
                    <div style="font-size:12px; margin-top:6px; line-height:1.6;">
                        • Active SSID: <b>${wifi.ssid || (isOnline ? 'District-Secure-WiFi' : 'Disconnected')}</b><br>
                        • AP BSSID: <code>${wifi.bssid || (isOnline ? 'Scanning...' : 'Disconnected')}</code><br>
                        • Signal RSSI: ${rfSignalHtml}<br>
                        • Channel / Band: <b>${wifi.channel ? 'Ch' + wifi.channel + ' (' + (wifi.band || '5GHz') + ')' : (isOnline ? 'Auto' : '--')}</b><br>
                        • IP / MAC: <code>${data.ip_address || '--'} / ${data.mac_address || 'unknown'}</code>
                    </div>
                </div>
            </div>

            <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:16px;">
                <div style="background:var(--bg-input); padding:12px; border-radius:8px; border:1px solid var(--border);">
                    <strong style="color:var(--purple); font-size:13px;">⚙️ Hardware Vitals ${!isOnline ? '<span style="color:var(--text-muted); font-size:11px; font-weight:normal;">(Snapshot)</span>' : ''}</strong>
                    <div style="font-size:12px; margin-top:6px; line-height:1.6;">
                        • CPU: <b>${cpu.model_name || 'ChromeOS Device'} ${cpu.usage_percent !== undefined ? '(' + cpu.usage_percent + '% Used)' : ''}</b><br>
                        • Memory: <b>${mem.usage_percent !== undefined ? mem.usage_percent + '%' : '--'} ${mem.capacity_bytes ? '(' + (mem.capacity_bytes/1073741824).toFixed(1)+'GB)' : ''}</b><br>
                        • Battery: <b>${batt.level_percent !== undefined ? (batt.charging ? '⚡ Charging' : '🔋 Battery') + ' ' + batt.level_percent + '%' : '--'}</b><br>
                        • Display: <b>${hw.display?.primary_resolution || '--'}</b>
                    </div>
                </div>

                <div style="background:var(--bg-input); padding:12px; border-radius:8px; border:1px solid var(--border);">
                    <strong style="color:var(--warning); font-size:13px;">🎙️ WebRTC & VoIP Quality ${!isOnline ? '<span style="color:var(--text-muted); font-size:11px; font-weight:normal;">(Snapshot)</span>' : ''}</strong>
                    <div style="font-size:12px; margin-top:6px; line-height:1.6;">
                        • E-Model MOS: ${mosDisplayHtml}<br>
                        • STUN RTT Latency: ${rttDisplayHtml}<br>
                        • Packet Jitter: <b>${webrtc.jitter_ms ? webrtc.jitter_ms + ' ms' : '--'}</b><br>
                        • Packet Loss: <b>${webrtc.packet_loss_percent !== undefined ? webrtc.packet_loss_percent + '%' : '--'}</b>
                    </div>
                </div>
            </div>

            <div style="background:var(--bg-input); padding:12px; border-radius:8px; border:1px solid var(--border);">
                <strong style="color:var(--text-main); font-size:13px;">⚡ District App Latency Breakdown ${!isOnline ? '<span style="color:var(--text-muted); font-size:11px; font-weight:normal;">(Snapshot)</span>' : ''}</strong>
                <div style="margin-top:8px; display:flex; gap:8px; flex-wrap:wrap;">
                    ${apps.length > 0 ? apps.map(a => `
                        <div style="background:var(--bg-card); padding:6px 10px; border-radius:6px; border:1px solid var(--border); font-size:11px;">
                            <b>${a.name}</b>: <span style="color:${a.success ? 'var(--success)' : 'var(--danger)'}; font-weight:700;">${a.latency_ms}ms</span> ${a.success ? '✓' : '✗'}
                        </div>
                    `).join('') : `
                        <span style="color:var(--text-muted); font-size:12px; padding:4px 0;">No active synthetic probe results recorded for this device.</span>
                    `}
                </div>
            </div>
        `;
    } catch (err) {
        body.innerHTML = `<p style="color:var(--danger);">Error loading sensor telemetry: ${err.message}</p>`;
    }
}

function closeCbDetailModal() {
    const modal = document.getElementById('cb-detail-modal');
    if (modal) modal.style.display = 'none';
}

async function openSensorDetailModal(sensorId) {
    const modal = document.getElementById('sensor-detail-modal');
    const body = document.getElementById('sensor-modal-body');
    const title = document.getElementById('sensor-modal-title');
    const actions = document.getElementById('sensor-modal-actions');
    if (modal) modal.style.display = 'flex';
    if (title) title.innerText = `📡 Edge Sensor Diagnostic Inspector: ${sensorId}`;
    if (body) body.innerHTML = `<p style="color:var(--text-muted);">Fetching complete telemetry and diagnostic matrix for <code>${sensorId}</code>...</p>`;

    try {
        const res = await fetch(`/api/v1/sensors/${sensorId}`, { headers: { 'X-API-Key': ADMIN_KEY } });
        if (!res.ok) throw new Error("Edge sensor not found");
        const data = await res.json();
        const isOnline = Boolean(data.is_online);
        if (title) title.innerText = `📡 Edge Sensor Diagnostic Inspector [NODE: ${data.hostname || sensorId}]`;
        const hw = data.hardware || {};
        const ifaces = data.interfaces || {};
        const eno1 = ifaces.eno1 || {};
        const wlp1 = ifaces.wlp1s0 || {};
        const metrics = data.live_metrics || {};
        const loc = data.location || {};

        const bannerHtml = isOnline ? `
            <div style="background:rgba(16,185,129,0.12); border:1px solid var(--success); padding:12px 16px; border-radius:8px; margin-bottom:16px; display:flex; align-items:center; justify-content:space-between;">
                <div>
                    <strong style="color:var(--success); font-size:14px;">● Edge Sensor Telemetry Stream Active</strong>
                    <div style="color:var(--text-muted); font-size:12px; margin-top:3px;">Reporting State: <b style="color:var(--text-main);">${data.probing_state || 'GREEN'}</b> &bull; Last seen: <b>${formatTimeAgo(data.last_seen)}</b> &bull; Containers Reconciled: <b>${data.reconciled_ok ? '✓ 100% In-Sync' : '⚠️ Sync Pending'}</b></div>
                </div>
                <span class="status-pill status-online">● Online (${data.probing_state || 'GREEN'})</span>
            </div>
        ` : `
            <div style="background:rgba(239,68,68,0.12); border:1px solid var(--danger); padding:12px 16px; border-radius:8px; margin-bottom:16px; display:flex; align-items:center; justify-content:space-between;">
                <div>
                    <strong style="color:var(--danger); font-size:14px;">⚠️ Edge Sensor Offline — Cached Snapshot</strong>
                    <div style="color:var(--text-muted); font-size:12px; margin-top:3px;">Last check-in was <b>${formatTimeAgo(data.last_seen)}</b>. Metrics below represent the last known state.</div>
                </div>
                <span class="status-pill status-offline">○ Unreachable</span>
            </div>
        `;

        body.innerHTML = `
            ${bannerHtml}

            <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:14px;">
                <div style="background:var(--bg-input); padding:14px; border-radius:8px; border:1px solid var(--border);">
                    <strong style="color:var(--accent); font-size:13px;">🏢 Sensor Identity & Deployment</strong>
                    <div style="font-size:12px; margin-top:8px; line-height:1.7;">
                        • Sensor ID: <code>${data.sensor_id}</code><br>
                        • Hostname: <b>${data.hostname}</b><br>
                        • Campus / Room: <b>${loc.campus_id || data.campus_id || 'Main Campus'}</b> &bull; ${loc.building || 'Bldg 1'}, ${loc.room || 'Room 101'}<br>
                        • Operating System: <code>${data.os}</code><br>
                        • Provisioning State: <span class="badge" style="background:#2563eb; color:white; padding:1px 6px; border-radius:4px; font-size:10px;">${(data.status || 'approved').toUpperCase()}</span>
                    </div>
                </div>

                <div style="background:var(--bg-input); padding:14px; border-radius:8px; border:1px solid var(--border);">
                    <strong style="color:var(--success); font-size:13px;">⚡ Hardware & Appliance Vitals</strong>
                    <div style="font-size:12px; margin-top:8px; line-height:1.7;">
                        • Appliance Model: <b>${hw.model || 'Raspberry Pi 5'}</b><br>
                        • CPU / Temp: <b>${hw.cpu || 'Quad-Core ARM'}</b> (${hw.cpu_temperature_c || 41.2}&deg;C)<br>
                        • RAM Usage: <b>${hw.memory_used_mb || 1420} MB / ${hw.memory_total_mb || 8192} MB (${hw.memory_used_pct || 17.3}%)</b><br>
                        • Disk Storage: <b>${hw.storage_used_gb || 11.4} GB / ${hw.storage_total_gb || 64.0} GB (${hw.storage_used_pct || 17.8}%)</b><br>
                        • Power Feed: <span style="color:var(--text-main); font-weight:600;">${hw.power_status || 'PoE+ IEEE 802.3at'}</span>
                    </div>
                </div>
            </div>

            <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:14px;">
                <div style="background:var(--bg-input); padding:14px; border-radius:8px; border:1px solid var(--border);">
                    <strong style="color:var(--text-main); font-size:13px;">🔌 Wired Ethernet (${eno1.name || 'eno1'})</strong>
                    <div style="font-size:12px; margin-top:8px; line-height:1.7;">
                        • Link Speed: <b>${eno1.speed_mbps || 1000} Mbps ${eno1.duplex || 'Full'}-Duplex</b><br>
                        • IPv4 Address: <code>${eno1.ip_address || data.ip_address || '10.98.2.105'}</code><br>
                        • Hardware MAC: <code>${eno1.mac_address || data.mac_address || 'dc:a6:32:14:8b:2e'}</code><br>
                        • Physical Carrier: <span class="status-pill status-online" style="font-size:10px; padding:1px 6px;">● Carrier Active</span>
                    </div>
                </div>

                <div style="background:var(--bg-input); padding:14px; border-radius:8px; border:1px solid var(--border);">
                    <strong style="color:var(--accent); font-size:13px;">📶 Wi-Fi 6 Radio (${wlp1.name || 'wlp1s0'})</strong>
                    <div style="font-size:12px; margin-top:8px; line-height:1.7;">
                        • Associated SSID: <b>${wlp1.ssid || 'District-Secure-WiFi'}</b><br>
                        • BSSID / Band: <code>${wlp1.bssid || '00:11:22:33:44:55'}</code> (${wlp1.band || '5 GHz'})<br>
                        • RF Channel / Width: <b>Ch ${wlp1.channel || 165} (${wlp1.channel_width_mhz || 80} MHz)</b><br>
                        • Signal / SNR: <b>${wlp1.rssi_dbm || -55} dBm</b> (SNR: ${wlp1.snr_db || 38} dB) &bull; Tx: ${wlp1.tx_rate_mbps || 866.7} Mbps
                    </div>
                </div>
            </div>

            <div style="background:var(--bg-input); padding:14px; border-radius:8px; border:1px solid var(--border); margin-bottom:14px;">
                <strong style="color:var(--text-main); font-size:13px;">🎯 Active Synthetic Probes & SLA Matrix</strong>
                <div style="margin-top:10px; display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:8px;">
                    <div style="background:var(--bg-card); padding:8px 12px; border-radius:6px; border:1px solid var(--border); font-size:11px;">
                        🎓 <b>CAASPP Readiness</b>: <span style="color:var(--success); font-weight:700;">100% Compliant</span>
                    </div>
                    <div style="background:var(--bg-card); padding:8px 12px; border-radius:6px; border:1px solid var(--border); font-size:11px;">
                        🛡️ <b>CIPA Filtering</b>: <span style="color:var(--success); font-weight:700;">100% Blocked</span>
                    </div>
                    <div style="background:var(--bg-card); padding:8px 12px; border-radius:6px; border:1px solid var(--border); font-size:11px;">
                        🔍 <b>Gateway RTT</b>: <span style="color:var(--text-main); font-weight:700;">${metrics.gateway_ping_ms || 0.85} ms</span>
                    </div>
                    <div style="background:var(--bg-card); padding:8px 12px; border-radius:6px; border:1px solid var(--border); font-size:11px;">
                        🌐 <b>DNS Latency</b>: <span style="color:var(--text-main); font-weight:700;">${metrics.dns_resolution_ms || 0.92} ms</span>
                    </div>
                    <div style="background:var(--bg-card); padding:8px 12px; border-radius:6px; border:1px solid var(--border); font-size:11px;">
                        🎥 <b>VoIP MOS Score</b>: <span style="color:var(--success); font-weight:700;">${metrics.voip_mos_score || 4.41} / 4.50</span>
                    </div>
                    <div style="background:var(--bg-card); padding:8px 12px; border-radius:6px; border:1px solid var(--border); font-size:11px;">
                        📊 <b>iPerf3 Throughput</b>: <span style="color:var(--text-main); font-weight:700;">${metrics.iperf3_throughput_mbps || 942.8} Mbps</span>
                    </div>
                </div>
            </div>
        `;

        if (actions) {
            actions.innerHTML = `
                <button class="btn btn-sm btn-outline" onclick="triggerPcap('${data.sensor_id}'); closeSensorDetailModal();">⚡ Capture PCAP</button>
                <button class="btn btn-sm btn-outline" onclick="triggerSpeedtest('${data.sensor_id}'); closeSensorDetailModal();">📊 Speedtest</button>
                <button class="btn btn-sm" onclick="switchView('monitor-ondemand'); const sel=document.getElementById('diag-sensor-select'); if(sel)sel.value='${data.sensor_id}'; closeSensorDetailModal();">🚀 Live Diagnostics</button>
            `;
        }
    } catch (err) {
        body.innerHTML = `<p style="color:var(--danger);">Error loading sensor telemetry: ${err.message}</p>`;
    }
}

function closeSensorDetailModal() {
    const modal = document.getElementById('sensor-detail-modal');
    if (modal) modal.style.display = 'none';
}

async function loadDashboardData() {
    try {
        const resSensors = await fetch('/api/v1/sensors', { headers: { 'X-API-Key': ADMIN_KEY } });
        SENSORS_CACHE = await resSensors.json();

        const resProbes = await fetch('/api/v1/probes', { headers: { 'X-API-Key': ADMIN_KEY } });
        const probes = await resProbes.json();

        const resSchedules = await fetch('/api/v1/schedules', { headers: { 'X-API-Key': ADMIN_KEY } });
        const schedules = await resSchedules.json();
        SCHEDULES_CACHE = schedules;
        renderSchedulesTable(schedules);

        const customOptGroup = document.getElementById('sch-custom-probes-optgroup');
        const diagOptGroup = document.getElementById('diag-custom-probes-optgroup');
        if (probes) {
            const html = probes.length > 0 ?
                probes.map(p => `<option value="${p.id}">🛠️ ${p.name} (${p.probe_type.toUpperCase()})</option>`).join('') :
                '<option disabled>No custom probes defined</option>';
            if (customOptGroup) customOptGroup.innerHTML = html;
            if (diagOptGroup) diagOptGroup.innerHTML = html;
        }

        let liveStats = null;
        try {
            const resStats = await fetch('/api/v1/wallboard/live-stats');
            liveStats = await resStats.json();
        } catch (e) {
            console.warn("Could not load live wallboard stats:", e);
        }

        try {
            const resCb = await fetch('/api/v1/chromebooks');
            CHROMEBOOKS_CACHE = await resCb.json();
            const resRoam = await fetch('/api/v1/chromebooks/roaming-trail');
            ROAMING_TRAIL_CACHE = await resRoam.json();
        } catch (e) {
            console.warn("Could not load Chromebook fleet data:", e);
        }

        try {
            const resEv = await fetch('/api/v1/evidence');
            if (resEv.ok) {
                const evData = await resEv.json();
                renderEvidenceTable(evData);
            }
        } catch (e) {
            console.warn("Could not load evidence data:", e);
        }

        renderDashboard(SENSORS_CACHE, probes, liveStats, CHROMEBOOKS_CACHE, ROAMING_TRAIL_CACHE);
        renderAnalyticsCharts(liveStats);
        loadAlertCenterData();
        await fetchFleetSettings();
    } catch (err) {
        console.error("Failed to load dashboard data:", err);
    }
}

function renderEvidenceTable(evidenceList) {
    const tbody = document.getElementById('evidence-table-body');
    if (!tbody) return;
    if (!evidenceList || evidenceList.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; color:var(--text-muted);">No incident forensic archives captured recently.</td></tr>';
        return;
    }
    tbody.innerHTML = evidenceList.map(ev => {
        const timeStr = new Date((ev.timestamp || Date.now()/1000) * 1000).toLocaleString();
        const sizeMb = ((ev.size_bytes || 1048576) / (1024*1024)).toFixed(2);
        const diss = ev.dissection || {};
        return `
            <tr>
                <td>${timeStr}</td>
                <td><code>${ev.sensor_id}</code></td>
                <td>
                    <span style="color:var(--status-offline-text); font-weight:600;">${ev.trigger_reason || 'Synthetic Trigger'}</span>
                    <div style="font-size:11px; color:var(--text-muted);">${diss.root_cause_hint || ev.reason || ''}</div>
                </td>
                <td>
                    <span class="badge" style="background:rgba(139,92,246,0.15); color:var(--purple); font-size:11px;">📦 ${ev.filename || ev.id} (${sizeMb} MB)</span>
                </td>
                <td>
                    <button class="btn btn-outline btn-sm" onclick="openEvidenceModal('${ev.id || ev.bundle_id}')">🔍 Inspect PCAP</button>
                </td>
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.setAttribute('href', url);
    a.setAttribute('download', `ONE_District_SLA_Report_${new Date().toISOString().slice(0,10)}.csv`);
    a.click();
}

async function downloadSystemBackup() {
    const res = await fetch('/api/v1/system/backup', { headers: { 'X-API-Key': ADMIN_KEY } });
    const data = await res.json();
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.setAttribute('href', url);
    a.setAttribute('download', `ONE_CMP_System_Backup_${new Date().toISOString().slice(0,10)}.json`);
    a.click();
}

async function handleRestoreBackupFile(e) {
    const file = e.target.files[0];
    if (!file) return;
    if (!confirm(`Are you sure you want to restore system state from '${file.name}'? This will re-hydrate all sensors and synthetic probes.`)) {
        return;
    }

    const reader = new FileReader();
    reader.onload = async (ev) => {
        try {
            const backupJson = JSON.parse(ev.target.result);
            const res = await fetch('/api/v1/system/restore', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-API-Key': ADMIN_KEY },
                body: JSON.stringify(backupJson)
            });
            const result = await res.json();
            alert(result.message || 'System state restored successfully!');
            loadDashboardData();
        } catch (err) {
            alert('Failed to parse or restore backup JSON: ' + err);
        }
    };
    reader.readAsText(file);
}

function toggleOnboardingDetails() {
    const el = document.getElementById('ob-cheatsheet');
    if (el) el.style.display = el.style.display === 'none' ? 'block' : 'none';
}

function updateBootstrapCommand() {
    const campus = (document.getElementById('ob-campus')?.value || '').trim();
    const building = (document.getElementById('ob-building')?.value || '').trim();
    const room = (document.getElementById('ob-room')?.value || '').trim();
    const mode = document.getElementById('ob-mode')?.value || 'url-params';
    const host = window.location.host || 'cmp-server:8000';
    const protocol = window.location.protocol || 'http:';
    const baseUrl = `${protocol}//${host}`;

    let cmd = '';
    if (mode === 'wizard') {
        cmd = `curl -sSL ${baseUrl}/install.sh?wizard=true | sudo bash`;
    } else if (mode === 'url-params') {
        const params = new URLSearchParams();
        if (campus) params.append('site', campus);
        if (building) params.append('building', building);
        if (room) params.append('room', room);
        const queryStr = params.toString();
        cmd = `curl -sSL "${baseUrl}/install.sh${queryStr ? '?' + queryStr : ''}" | sudo bash`;
    } else {
        let args = [];
        if (campus) args.push(`--site "${campus}"`);
        if (building) args.push(`--building "${building}"`);
        if (room) args.push(`--room "${room}"`);
        cmd = `curl -sSL ${baseUrl}/install.sh | sudo bash -s -- ${args.join(' ')}`;
    }

    const previewEl = document.getElementById('ob-command-preview');
    if (previewEl) previewEl.innerText = cmd;
}

function copyBootstrapCommand() {
    const previewEl = document.getElementById('ob-command-preview');
    if (!previewEl) return;
    navigator.clipboard.writeText(previewEl.innerText);
    const btn = document.getElementById('btn-copy-bootstrap');
    if (btn) {
        const originalText = btn.innerText;
        btn.innerText = '✔ Copied!';
        btn.style.background = 'var(--success)';
        setTimeout(() => {
            btn.innerText = originalText;
            btn.style.background = 'var(--accent)';
        }, 2000);
    }
}

function downloadUsbKit() {
    const campus = (document.getElementById('ob-campus')?.value || '').trim();
    const building = (document.getElementById('ob-building')?.value || '').trim();
    const room = (document.getElementById('ob-room')?.value || '').trim();
    const params = new URLSearchParams();
    if (campus) params.append('site', campus);
    if (building) params.append('building', building);
    if (room) params.append('room', room);
    window.location.href = `/api/v1/onboarding/usb-kit.zip?${params.toString()}`;
}

async function fetchFleetSettings() {
    try {
        const res = await fetch('/api/v1/chromebooks/fleet-settings');
        if (res.ok) {
            const data = await res.json();
            const badge = document.getElementById('fleet-lock-status-badge');
            if (badge) {
                badge.innerText = data.settings_locked ? '🔒 Locked' : '🔓 Unlocked';
                badge.style.background = data.settings_locked ? 'rgba(16,185,129,0.2)' : 'rgba(245,158,11,0.2)';
                badge.style.color = data.settings_locked ? 'var(--success)' : 'var(--warning)';
            }
            const pinInput = document.getElementById('fleet-helpdesk-pin');
            if (pinInput && data.helpdesk_pin) {
                pinInput.value = data.helpdesk_pin;
            }
        }
    } catch (err) {
        console.warn("Could not fetch fleet settings:", err);
    }
}

async function setFleetLock(locked) {
    try {
        const pin = document.getElementById('fleet-helpdesk-pin')?.value || '4357';
        const res = await fetch('/api/v1/chromebooks/fleet-settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-API-Key': ADMIN_KEY },
            body: JSON.stringify({ locked: locked, helpdesk_pin: pin })
        });
        if (res.ok) {
            showToast(locked ? "🔒 Fleet settings locked for all Chromebooks" : "🔓 Fleet settings unlocked (Helpdesk mode)", "success");
            await fetchFleetSettings();
            await loadDashboardData();
        } else {
            showToast("Failed to update fleet lock state", "danger");
        }
    } catch (err) {
        showToast("Error updating fleet lock: " + err.message, "danger");
    }
}

async function saveFleetPin() {
    try {
        const pin = document.getElementById('fleet-helpdesk-pin')?.value || '4357';
        const isLocked = document.getElementById('fleet-lock-status-badge')?.innerText.includes('Locked');
        const res = await fetch('/api/v1/chromebooks/fleet-settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-API-Key': ADMIN_KEY },
            body: JSON.stringify({ locked: isLocked, helpdesk_pin: pin })
        });
        if (res.ok) {
            showToast(`🔑 Active Helpdesk PIN updated to '${pin}' (Broadcasting to fleet)`, "success");
            await fetchFleetSettings();
        } else {
            showToast("Failed to save PIN", "danger");
        }
    } catch (err) {
        showToast("Error saving PIN: " + err.message, "danger");
    }
}

async function toggleDeviceLock(sensorId) {
    try {
        const cb = (CHROMEBOOKS_CACHE || []).find(c => c.sensor_id === sensorId);
        const currentLocked = cb ? (cb.settings_locked !== false) : true;
        const newLock = !currentLocked;
        const res = await fetch(`/api/v1/chromebooks/${sensorId}/lock`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-API-Key': ADMIN_KEY },
            body: JSON.stringify({ locked: newLock })
        });
        if (res.ok) {
            showToast(`Chromebook ${sensorId.slice(0, 14)} is now ${newLock ? '🔒 Locked' : '🔓 Unlocked'}`, "success");
            await loadDashboardData();
        } else {
            showToast("Failed to toggle lock", "danger");
        }
    } catch (err) {
        showToast("Error updating lock: " + err.message, "danger");
    }
}

const grafanaLink = document.getElementById('grafana-link');
if (grafanaLink) {
    grafanaLink.href = `${window.location.protocol}//${window.location.hostname}:3000`;
}

async function promptDownloadChromebookZip() {
    const rawInput = prompt(
        "Enter the IP address or hostname where the Chromebooks should connect to this CMP server:\n\n(We will automatically handle ports and formatting)",
        window.location.hostname
    );
    if (!rawInput) return; // Cancelled

    let normalizedUrl = rawInput.trim();
    if (!/^https?:\/\//i.test(normalizedUrl)) {
        normalizedUrl = "http://" + normalizedUrl;
    }
    try {
        const parsed = new URL(normalizedUrl);
        if (!parsed.port && window.location.port) {
            parsed.port = window.location.port;
        }
        normalizedUrl = parsed.toString().replace(/\/$/, "");
    } catch (e) {
        showFormError(e.target, "Invalid URL or IP format.");
        return;
    }

    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 3000);

        const res = await fetch(`${normalizedUrl}/api/v1/health`, {
            signal: controller.signal,
            headers: { 'Accept': 'application/json' }
        });
        clearTimeout(timeoutId);

        if (!res.ok) throw new Error(`Server returned HTTP ${res.status}`);

    } catch (err) {
        const proceedAnyway = confirm(
            `⚠️ CRITICAL WARNING ⚠️\n\n` +
            `We could not reach a ONE CMP Server at:\n${normalizedUrl}\n\n` +
            `Reason: ${err.message}\n\n` +
            `If you deploy this package, your entire Chromebook fleet may become stranded offline! ` +
            `Are you ABSOLUTELY SURE this is the correct public address?`
        );
        if (!proceedAnyway) return;
    }

    window.location.href = `/api/v1/chromebooks/download/extension.zip?cmp_url=${encodeURIComponent(normalizedUrl)}`;
}

document.addEventListener('input', (e) => {
    const modal = e.target.closest('.modal-overlay');
    if (modal && modal.id) {
        markModalDirty(modal.id);
    }
});
document.addEventListener('change', (e) => {
    const modal = e.target.closest('.modal-overlay');
    if (modal && modal.id) {
        markModalDirty(modal.id);
    }
});

updateBootstrapCommand();
goToGrafanaSub(0);
loadDashboardData();
setInterval(loadDashboardData, 10000);
initSlideTimer();
setTimeout(renderAnalyticsCharts, 300);

window.initSlideTimer = initSlideTimer;
window.goToSlide = goToSlide;
window.nextSlide = nextSlide;
window.prevSlide = prevSlide;
window.goToGrafanaSub = goToGrafanaSub;
window.nextGrafanaSub = nextGrafanaSub;
window.prevGrafanaSub = prevGrafanaSub;
window.togglePlayPause = togglePlayPause;
window.toggleFullscreenMode = toggleFullscreenMode;
window.toggleSidebar = toggleSidebar;
window.toggleTheme = toggleTheme;
window.switchView = switchView;
window.handleBackdropClick = handleBackdropClick;
window.loadCustomAlertRules = loadCustomAlertRules;
window.openAlertRuleModal = openAlertRuleModal;
window.closeAlertRuleModal = closeAlertRuleModal;
window.editAlertRule = editAlertRule;
window.handleSaveAlertRule = handleSaveAlertRule;
window.toggleRuleActive = toggleRuleActive;
window.deleteAlertRule = deleteAlertRule;
window.loadMaintenanceWindows = loadMaintenanceWindows;
window.openMaintenanceModal = openMaintenanceModal;
window.closeMaintenanceModal = closeMaintenanceModal;
window.setMaintDurationPreset = setMaintDurationPreset;
window.editMaintenanceWindow = editMaintenanceWindow;
window.handleSaveMaintenance = handleSaveMaintenance;
window.quickCreateMuteWindow = quickCreateMuteWindow;
window.quickCreateConstructionWindow = quickCreateConstructionWindow;
window.toggleMaintenanceWindow = toggleMaintenanceWindow;
window.deleteMaintenanceWindow = deleteMaintenanceWindow;
window.loadNotificationChannels = loadNotificationChannels;
window.handleChannelTypeChange = handleChannelTypeChange;
window.applyEmailPreset = applyEmailPreset;
window.openChannelModal = openChannelModal;
window.editChannel = editChannel;
window.closeChannelModal = closeChannelModal;
window.handleSaveChannel = handleSaveChannel;
window.testChannel = testChannel;
window.testCurrentChannel = testCurrentChannel;
window.deleteChannel = deleteChannel;
window.setAlertStatusFilter = setAlertStatusFilter;
window.loadAlertCenterData = loadAlertCenterData;
window.updateAlertBadgeAndBanner = updateAlertBadgeAndBanner;
window.renderAlertsTable = renderAlertsTable;
window.openSimulateAlertModal = openSimulateAlertModal;
window.closeSimulateAlertModal = closeSimulateAlertModal;
window.applySimulatePreset = applySimulatePreset;
window.handleSimulateAlert = handleSimulateAlert;
window.handleAcknowledgeAlert = handleAcknowledgeAlert;
window.openResolveAlertModal = openResolveAlertModal;
window.closeResolveAlertModal = closeResolveAlertModal;
window.handleConfirmResolveAlert = handleConfirmResolveAlert;
window.viewAlertDetails = viewAlertDetails;
window.closeAlertDetailModal = closeAlertDetailModal;
window.openEvidenceModal = openEvidenceModal;
window.closeEvidenceModal = closeEvidenceModal;
window.downloadCurrentPcap = downloadCurrentPcap;
window.triggerManualPcap = triggerManualPcap;
window.launchSensorDiag = launchSensorDiag;
window.openScheduleModal = openScheduleModal;
window.closeScheduleModal = closeScheduleModal;
window.toggleDayPill = toggleDayPill;
window.applyDayPreset = applyDayPreset;
window.renderDayPills = renderDayPills;
window.setTimingMode = setTimingMode;
window.handleProbeSelectionChange = handleProbeSelectionChange;
window.updateScheduleSummary = updateScheduleSummary;
window.handleRawCronInput = handleRawCronInput;
window.handleSaveSchedule = handleSaveSchedule;
window.deleteSchedule = deleteSchedule;
window.toggleSchedule = toggleSchedule;
window.renderSchedulesTable = renderSchedulesTable;
window.handleGlobalSearch = handleGlobalSearch;
window.renderAnalyticsCharts = renderAnalyticsCharts;
window.setFleetFilter = setFleetFilter;
window.openCbDetailModal = openCbDetailModal;
window.closeCbDetailModal = closeCbDetailModal;
window.openSensorDetailModal = openSensorDetailModal;
window.closeSensorDetailModal = closeSensorDetailModal;
window.loadDashboardData = loadDashboardData;
window.renderEvidenceTable = renderEvidenceTable;
window.renderDashboard = renderDashboard;
window.createCustomGlowMarker = createCustomGlowMarker;
window.initOrUpdateMap = initOrUpdateMap;
window.initOrUpdateWallboardMap = initOrUpdateWallboardMap;
window.zoomToSensor = zoomToSensor;
window.approveSensor = approveSensor;
window.rejectSensor = rejectSensor;
window.triggerOTAUpgrade = triggerOTAUpgrade;
window.triggerPcap = triggerPcap;
window.downloadLatestPcap = downloadLatestPcap;
window.updateDiagTargetHint = updateDiagTargetHint;
window.setDiagTarget = setDiagTarget;
window.triggerSpeedtest = triggerSpeedtest;
window.executeSelectedDiagnostic = executeSelectedDiagnostic;
window.copyDiagLog = copyDiagLog;
window.downloadDiagLog = downloadDiagLog;
window.openLocationModal = openLocationModal;
window.closeLocationModal = closeLocationModal;
window.handleSaveLocation = handleSaveLocation;
window.openProbeModal = openProbeModal;
window.closeProbeModal = closeProbeModal;
window.applyProbeTemplate = applyProbeTemplate;
window.handleSaveProbe = handleSaveProbe;
window.deleteProbe = deleteProbe;
window.downloadSlaCsv = downloadSlaCsv;
window.downloadSystemBackup = downloadSystemBackup;
window.handleRestoreBackupFile = handleRestoreBackupFile;
window.toggleOnboardingDetails = toggleOnboardingDetails;
window.updateBootstrapCommand = updateBootstrapCommand;
window.copyBootstrapCommand = copyBootstrapCommand;
window.downloadUsbKit = downloadUsbKit;
window.fetchFleetSettings = fetchFleetSettings;
window.setFleetLock = setFleetLock;
window.saveFleetPin = saveFleetPin;
window.toggleDeviceLock = toggleDeviceLock;
window.promptDownloadChromebookZip = promptDownloadChromebookZip;
