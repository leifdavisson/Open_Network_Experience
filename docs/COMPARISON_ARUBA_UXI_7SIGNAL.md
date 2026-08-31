# Open Network Experience (ONE) vs. Commercial UXI Platforms
### A Comprehensive Architectural, Feature & Total Cost of Ownership (TCO) Breakdown
**Platform Version**: `v0.4.0`
**License**: [GNU AGPLv3](file:///data/Open_Network_Experience/LICENSE) (file:///data/Open_Network_Experience/LICENSE)
**Authoritative Source**: [github.com/leifdavisson/Open_Network_Experience](https://github.com/leifdavisson/Open_Network_Experience)

---

## Executive Summary

For over a decade, network administrators in K-12 education, higher education, and enterprise campuses have relied on **User Experience Insight (UXI)** sensors to capture true end-user synthetic network metrics. However, commercial market leaders—including **Aruba UXI (formerly Cape Networks)**, **7SIGNAL (Sapphire Eye / Mobile Eye)**, and **Cisco ThousandEyes**—have transitioned to aggressive subscription models and vendor-locked hardware appliances that impose massive financial burdens on public school districts and open-source operations.

**Open Network Experience (ONE)** provides a 100% open-source, vendor-agnostic UXI alternative designed to run on commodity single-board computers (Raspberry Pi 4/5, Intel N100) and native ChromeOS fleets with **zero per-sensor subscription fees**.

---

## 1. Direct Feature & Capability Comparison

| Feature Dimension | Aruba UXI (G-Series) | 7SIGNAL (Sapphire/Mobile Eye) | Open Network Experience (ONE) |
| :--- | :--- | :--- | :--- |
| **Licensing Model** | Proprietary SaaS ($300–$800 / sensor / yr) | Proprietary SaaS ($250–$600 / sensor / yr) | **100% Free & Open Source ([GNU AGPLv3](https://www.gnu.org/licenses/agpl-3.0.html))** |
| **Hardware Required** | Proprietary Aruba hardware ($500–$1,200/ea) | Proprietary Sapphire hardware ($800–$1,500) | **Commodity Hardware (Raspberry Pi 4/5, Intel NUC, Linux VMs)** |
| **Student 1:1 Fleet Agent** | Limited Windows/macOS agent ($) | Mobile Eye (ChromeOS/macOS/Windows) ($) | **Native Manifest V3 ChromeOS Extension included free** |
| **K-12 State Testing Harness** | Generic HTTP probes | Generic ping / traceroute | **Built-in CAASPP, Cambium TDS, ETS TOMS & SSL Pinning checks** |
| **Dual-NIC Scientific Control** | Yes (Ethernet + Wi-Fi) | Limited to Wi-Fi on lower tier | **Native Dual-NIC (eth0 baseline vs wlan0 RF isolation)** |
| **Wi-Fi RRM Flapping Monitor** | Basic BSSID tracking | Deep spectrum analysis (proprietary) | **FortiGate DARRP / GSK & IEEE 802.11 dynamic channel tracking** |
| **Forensic Incident Evidence** | 5-minute downsampled cloud charts | Cloud-only downsampled summaries | **Local 50MB RAM PCAP Ring Buffer + `.tar.gz` diagnostic vault** |
| **Control Plane Hosting** | Aruba Central Cloud only | 7SIGNAL Cloud only | **Self-hosted Docker (FastAPI, [VictoriaMetrics](https://victoriametrics.com/), [Grafana](https://grafana.com/)) or Cloud** |
| **Synthetic Browser Testing** | Pre-configured web scripts | Web latency metrics | **Headless [Playwright](https://playwright.dev/) with DOMContentLoaded & blocked ad tracking** |
| **CIPA Content Filter Audit** | Not natively supported | Not natively supported | **Automated `testfiltering.com` DNS & SSL inspection policy prober** |
| **Onboarding & Provisioning** | Manual cloud claim codes | Cloud licensing portal | **1-Line curl bootstrapper, DHCP Option 43 & FAT32 USB assembly line** |

---

## 2. Total Cost of Ownership (TCO) Analysis: 5-Year K-12 District Model

Consider a medium-sized school district with **15 campus sites**, deploying **3 hardware sensors per campus (45 sensors total)** and monitoring **5,000 1:1 student Chromebooks**:

```
5-Year Total Cost of Ownership (45 Hardware Sensors + 5,000 Chromebooks)
─────────────────────────────────────────────────────────────────────────────
Commercial Vendor (Aruba UXI / 7SIGNAL):
  • Initial Hardware (45 units @ $750/ea)         :  $33,750
  • Annual Sensor Subscriptions (45 @ $450/yr * 5): $101,250
  • Chromebook Fleet Licenses ($3/device/yr * 5)  :  $75,000
  ─────────────────────────────────────────────────────────────
  TOTAL 5-YEAR COMMERCIAL COST                    : $210,000

Open Network Experience (ONE):
  • Commodity Hardware (45 Pi 5 + Enclosures @ $95) :   $4,275
  • Software Subscriptions & Licenses             :       $0 (AGPLv3)
  • Chromebook Fleet Extension Deployment         :       $0 (Open Source)
  • Self-Hosted Server VM / TSDB Storage          :     $600 (Infrastructure)
  ─────────────────────────────────────────────────────────────
  TOTAL 5-YEAR ONE COST                           :   $4,875

  ESTIMATED 5-YEAR DISTRICT TAXPAYER SAVINGS      : $205,125 (97.7% Savings)
```

---

## 3. Why Open Network Experience Outperforms Closed Systems

### A. Real-Time Packet Capture Without Cloud Downsampling
Commercial cloud vendors store telemetry in 5-minute rolled-up averages. When intermittent Wi-Fi micro-bursts or dynamic channel changes cause Zoom or CAASPP disconnects, the cloud graph often shows a smoothed, misleading green line. ONE's edge reconciler runs a **50MB in-memory circular PCAP buffer**. When packet loss exceeds threshold, it freezes the buffer to disk, providing sysadmins with exact Wi-Fi beacon handshakes and EAP authentication drops in raw `.pcap` format.

### B. Purpose-Built for K-12 & Public Infrastructure
Commercial tools are engineered for corporate enterprise offices. ONE was built specifically for educational environments:
1. **Automated CAASPP / ELPAC Validation**: Validates Cambium TDS and ETS TOMS endpoints, certifying that network-wide SSL Decryption / MITM inspection is properly bypassed so student secure test kiosks do not crash.
2. **CIPA Content Filtering Audit**: Validates that school firewalls (FortiGate, Palo Alto, Lightspeed, Securly) block inappropriate categories while allowing educational domains.
3. **Chromebook Extension Offline Buffer**: ChromeOS devices queue WebRTC STUN latency and Wi-Fi roaming telemetry in IndexedDB during campus dead-zones and replay metrics the moment Wi-Fi reconnects.

---

## 4. Migration & Coexistence Strategy

Organizations do not need to rip-and-replace existing infrastructure. ONE integrates directly alongside existing Aruba, Cisco Catalyst, RUCKUS, or Fortinet wireless gear. Sensor endpoints can be deployed incrementally in problem classrooms or high-density lecture halls alongside current systems.

To get started:
* View the Quick Start guide: [**`GETTING_STARTED.md`**](file:///data/Open_Network_Experience/GETTING_STARTED.md) (file:///data/Open_Network_Experience/GETTING_STARTED.md)
* Read the Brand Guide: [**`BRAND_GUIDE.md`**](file:///data/Open_Network_Experience/docs/BRAND_GUIDE.md) (file:///data/Open_Network_Experience/docs/BRAND_GUIDE.md)
