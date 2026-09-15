export let chartFault = null;
export let chartTrend = null;
export let chartAlarm = null;

export function initCharts() {
    console.log("Charts initialized");
}
export function renderAnalyticsCharts(liveStats) {
    // 1. Fault Situation Semi-Donut (Issue #35: Real 7-Day Trailing SLA Compliance)
    const ctxFault = document.getElementById('chart-fault-situation');
    if (ctxFault) {
        if (chartFault) chartFault.destroy();
        const compPct = (liveStats && liveStats.compliance_7d) ? liveStats.compliance_7d.compliant_pct : 100;
        const faultPct = (liveStats && liveStats.compliance_7d) ? liveStats.compliance_7d.fault_pct : 0;

        // Dynamically update legend and evaluation window text
        const compEl = document.getElementById('fault-chart-comp-pct');
        const faultEl = document.getElementById('fault-chart-fault-pct');
        const windowEl = document.getElementById('fault-chart-window');
        if (compEl) compEl.textContent = `● Compliant (${compPct}%)`;
        if (faultEl) faultEl.textContent = `● Fault (${faultPct}%)`;
        if (windowEl && liveStats && liveStats.compliance_7d) {
            windowEl.textContent = liveStats.compliance_7d.eval_window || "Last 7 Days";
        }

        chartFault = new Chart(ctxFault, {
            type: 'doughnut',
            data: {
                labels: ['Compliant', 'Fault'],
                datasets: [{
                    data: [compPct, faultPct],
                    backgroundColor: ['#10b981', '#ef4444'],
                    borderWidth: 0
                }]
            },
            options: {
                circumference: 180,
                rotation: -90,
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } }
            }
        });
    }

    // 2. Trend Analysis (WAN Latency & SLA Stability - Issue #34)
    const ctxTrend = document.getElementById('chart-trend-analysis');
    const emptyBanner = document.getElementById('trend-empty-state-banner');
    if (ctxTrend) {
        if (chartTrend) chartTrend.destroy();
        const trends = (liveStats && liveStats.trends) ? liveStats.trends : null;
        const hasHistory = Boolean(trends && trends.has_history && trends.streams && trends.streams.some(s => s.data && s.data.length > 0));

        if (!hasHistory || (trends && trends.insufficient_data)) {
            if (emptyBanner) emptyBanner.style.display = 'flex';
            ctxTrend.style.opacity = '0.35';
        } else {
            if (emptyBanner) emptyBanner.style.display = 'none';
            ctxTrend.style.opacity = '1.0';
        }

        const labels = (trends && trends.labels && trends.labels.length > 0) ? trends.labels : ['Collecting...'];
        const datasets = [];

        if (trends && trends.streams && trends.streams.length > 0 && hasHistory) {
            const colors = ['#38bdf8', '#8b5cf6', '#10b981', '#f59e0b'];
            trends.streams.forEach((stream, idx) => {
                if (!stream.data || stream.data.length === 0) return;
                const col = colors[idx % colors.length];
                datasets.push({
                    label: `${stream.name} [${stream.target}]`,
                    data: stream.data,
                    borderColor: col,
                    backgroundColor: `${col}1a`,
                    fill: true,
                    tension: 0.3,
                    borderWidth: 2,
                    pointRadius: 2
                });
            });
        } else {
            datasets.push({
                label: 'Telemetry Accumulating',
                data: [0],
                borderColor: 'rgba(148, 163, 184, 0.4)',
                borderDash: [4, 4],
                fill: false,
                borderWidth: 1,
                pointRadius: 0
            });
        }

        const subTitleEl = document.getElementById('trend-analysis-subtitle');
        if (subTitleEl && trends && trends.streams && trends.streams.length > 0 && hasHistory) {
            subTitleEl.textContent = trends.streams.filter(s => s.data && s.data.length > 0).map(s => `● ${s.name}`).join('  ');
        }

        chartTrend = new Chart(ctxTrend, {
            type: 'line',
            data: {
                labels: labels,
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { grid: { color: 'rgba(51, 65, 85, 0.2)' }, ticks: { color: '#94a3b8', font: { size: 10 } } },
                    y: { grid: { color: 'rgba(51, 65, 85, 0.2)' }, ticks: { color: '#94a3b8', font: { size: 10 } }, min: 0 }
                },
                plugins: { legend: { display: false } }
            }
        });
    }

    // 3. Alarm Overview Donut (New vs Closed)
    const ctxAlarm = document.getElementById('chart-alarm-overview');
    if (ctxAlarm) {
        if (chartAlarm) chartAlarm.destroy();
        const activeAlarms = (liveStats && liveStats.kpis) ? liveStats.kpis.alarms : 0;
        chartAlarm = new Chart(ctxAlarm, {
            type: 'doughnut',
            data: {
                labels: ['Resolved', 'Active'],
                datasets: [{
                    data: [100, activeAlarms],
                    backgroundColor: ['#38bdf8', '#f59e0b'],
                    borderWidth: 0
                }]
            },
            options: {
                circumference: 180,
                rotation: -90,
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } }
            }
        });
    }
}
