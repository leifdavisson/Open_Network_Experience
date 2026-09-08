---
COMPONENT: Navigation Bar (Collapsible Sidebar)
SUB-COMPONENT: Toggle Navigation Button (#btn-toggle-sidebar)
EXPECTED: The sidebar should toggle between expanded and collapsed states when the button is clicked.
ACTION TAKEN: Clicked the toggle navigation button.
OBSERVED: The sidebar collapsed into icon-only mode smoothly. Clicked again, the sidebar expanded back.
STATUS: ✅ PASS
UX NOTE: Smooth CSS transition, clear icon styling.
---

---
COMPONENT: Navigation Bar (Collapsible Sidebar)
SUB-COMPONENT: NOC Overview Link (#nav-monitor-noc)
EXPECTED: The NOC Wallboard view should activate, and the link should be highlighted as active.
ACTION TAKEN: Clicked the NOC Overview link.
OBSERVED: The view switched to NOC Wallboard, the active class was applied, and charts and cards were visible.
STATUS: ✅ PASS
---

---
COMPONENT: Navigation Bar (Collapsible Sidebar)
SUB-COMPONENT: GIS Campus Map Link (#nav-monitor-map)
EXPECTED: The GIS campus map view should display with Leaflet tiles and sensor markers.
ACTION TAKEN: Clicked the GIS Campus Map link.
OBSERVED: The view switched to map view, the active nav was highlighted, and the Leaflet GIS canvas was loaded.
STATUS: ✅ PASS
---

---
COMPONENT: Navigation Bar (Collapsible Sidebar)
SUB-COMPONENT: Live Diagnostics Link (#nav-monitor-ondemand)
EXPECTED: The on-demand diagnostic test runner and action center should be displayed.
ACTION TAKEN: Clicked the Live Diagnostics link.
OBSERVED: The view switched to On-Demand Diagnostic Action Center with sensor selectors and ping/traceroute/speedtest tools.
STATUS: ✅ PASS
---

---
COMPONENT: Navigation Bar (Collapsible Sidebar)
SUB-COMPONENT: Reports & Forensics Link (#nav-monitor-reports)
EXPECTED: The forensics and SLA reporting view should be displayed.
ACTION TAKEN: Clicked the Reports & Forensics link.
OBSERVED: The view switched to Reports & Forensics center with log export and incident summaries.
STATUS: ✅ PASS
---
