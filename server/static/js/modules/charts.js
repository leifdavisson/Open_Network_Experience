export let chartFault = null;
export let chartTrend = null;
export let chartAlarm = null;

export function initCharts() {
    console.log("Charts initialized");
}
export function renderAnalyticsCharts(liveStats) {
    // 1. Fault Situation Semi-Donut
    const ctxFault = document.getElementById('chart-fault-situation');
    if (ctxFault) {
        if (chartFault) chartFault.destroy();
        const faultPct = (liveStats && liveStats.kpis) ? Math.min(100, liveStats.kpis.faults * 10) : 0;
        const compPct = 100 - faultPct;
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

    // 2. 30-Day Trend Sparkline (eno1 vs wlp1s0)
    const ctxTrend = document.getElementById('chart-trend-analysis');
    if (ctxTrend) {
        if (chartTrend) chartTrend.destroy();
        const labels = Array.from({length: 15}, (_, i) => `Day ${i+1}`);
        const wiredData = (liveStats && liveStats.trends && liveStats.trends.wired) ? liveStats.trends.wired : [1.2, 1.15, 1.22, 1.18, 1.14, 1.25, 1.18, 1.19, 1.16, 1.20, 1.18, 1.17, 1.18, 1.18, 1.18];
        const wifiData = (liveStats && liveStats.trends && liveStats.trends.wifi) ? liveStats.trends.wifi : [4.5, 4.2, 4.8, 4.3, 4.1, 5.0, 4.4, 4.3, 4.2, 4.6, 4.3, 4.3, 4.35, 4.30, 4.32];


        const nodeLabelWired = (liveStats && liveStats.sensor_id) ? `[NODE: ${liveStats.hostname || liveStats.sensor_id}] eno1 Gateway Latency (ms)` : (liveStats && liveStats.campus_name ? `[AGGREGATE: ${liveStats.campus_name}] eno1 Gateway Latency (ms)` : `[AGGREGATE: All Campuses] eno1 Gateway Latency (ms)`);
        const nodeLabelWifi = (liveStats && liveStats.sensor_id) ? `[NODE: ${liveStats.hostname || liveStats.sensor_id}] wlp1s0 Wi-Fi Latency (ms)` : (liveStats && liveStats.campus_name ? `[AGGREGATE: ${liveStats.campus_name}] wlp1s0 Wi-Fi Latency (ms)` : `[AGGREGATE: All Campuses] wlp1s0 Wi-Fi Latency (ms)`);

        chartTrend = new Chart(ctxTrend, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: nodeLabelWired,
                        data: wiredData,

                        borderColor: '#38bdf8',
                        backgroundColor: 'rgba(56, 189, 248, 0.1)',
                        fill: true,
                        tension: 0.3,
                        borderWidth: 2,
                        pointRadius: 2
                    },
                    {
                        label: nodeLabelWifi,
                        data: wifiData,
                        borderColor: '#8b5cf6',
                        backgroundColor: 'rgba(139, 92, 246, 0.05)',
                        fill: true,
                        tension: 0.3,
                        borderWidth: 2,
                        pointRadius: 2
                    }
                ]
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
