# Open Network Experience (ONE) — Brand Identity & Design System
**Version**: `1.0.0` (Release `v0.4.0`)
**License**: [GNU AGPLv3](file:///data/Open_Network_Experience/LICENSE) (file:///data/Open_Network_Experience/LICENSE)
**Repository**: [github.com/leifdavisson/Open_Network_Experience](https://github.com/leifdavisson/Open_Network_Experience)

---

## 1. Brand Vision & Positioning

### Mission Statement
> *"To democratize User Experience Insight (UXI) monitoring and synthetic network assurance for every school district, campus, and open-source enterprise—eliminating predatory hardware lock-in and multi-thousand-dollar annual SaaS tax."*

### Brand Personality
* **Authoritative & Engineering-First**: Rooted in rigorous RFC standards, DO-178C/ISO 26262 verification discipline, and deterministic measurements.
* **Accessible & Educational**: Friendly to junior sysadmins, high-school helpdesk apprentices, and seasoned CWNE/CCIE network architects alike.
* **Modern & Cyber-Clean**: Sleek dark-mode Network Operations Center (NOC) aesthetics paired with crystal-clear academic typography.

---

## 2. Logo & Brand Assets

All primary vector assets and scripts are maintained in [`assets/`](file:///data/Open_Network_Experience/assets) (file:///data/Open_Network_Experience/assets) and [`scripts/`](file:///data/Open_Network_Experience/scripts) (file:///data/Open_Network_Experience/scripts):

| Asset Name | Format | Use Case | Link |
| :--- | :--- | :--- | :--- |
| **Synthetic Hex Pulse** | SVG / Vector | Primary Logo Emblem, README, Web App Header | [Open `logo.svg`](file:///data/Open_Network_Experience/assets/logo.svg) (file:///data/Open_Network_Experience/assets/logo.svg) |
| **Animated Hex Pulse** | SVG (CSS Keyframes) | Live Web Console, Marketing Demos, Dynamic UIs | [Open `logo-animated.svg`](file:///data/Open_Network_Experience/assets/branding/logo-animated.svg) (file:///data/Open_Network_Experience/assets/branding/logo-animated.svg) |
| **Simplified Favicon** | SVG (32x32) | Browser Tabs, Bookmarks, Mobile Icons | [Open `favicon.svg`](file:///data/Open_Network_Experience/assets/favicon.svg) (file:///data/Open_Network_Experience/assets/favicon.svg) |
| **Terminal ASCII & ANSI Banner** | Shell Script (`.sh`) | CLI probers, Installer MOTD, Terminal Diagnostics | [Open `banner.sh`](file:///data/Open_Network_Experience/scripts/banner.sh) (file:///data/Open_Network_Experience/scripts/banner.sh) |
| **ONE Brand Mark** | SVG / Vector | Avatars, App Icons, Hardware Labels | [Open `one-logo-mark.svg`](file:///data/Open_Network_Experience/assets/branding/one-logo-mark.svg) (file:///data/Open_Network_Experience/assets/branding/one-logo-mark.svg) |
| **ONE Horizontal Dark** | SVG / Vector | Dark UI headers, Wide Banners, NOC Wallboard | [Open `one-logo-horizontal-dark.svg`](file:///data/Open_Network_Experience/assets/branding/one-logo-horizontal-dark.svg) (file:///data/Open_Network_Experience/assets/branding/one-logo-horizontal-dark.svg) |
| **ONE Horizontal Light** | SVG / Vector | Whitepapers, Board Presentations, Light Web | [Open `one-logo-horizontal-light.svg`](file:///data/Open_Network_Experience/assets/branding/one-logo-horizontal-light.svg) (file:///data/Open_Network_Experience/assets/branding/one-logo-horizontal-light.svg) |
| **Hero Artwork** | SVG / Vector (Hi-Res) | GitHub Hero, Documentation, Launch Banners | [Open `one_hero_banner.svg`](file:///data/Open_Network_Experience/assets/images/one_hero_banner.svg) (file:///data/Open_Network_Experience/assets/images/one_hero_banner.svg) |
| **Social Card (OG)** | SVG / 1200x630 | OpenGraph, Twitter Cards, Discord embeds | [Open `one_social_preview.svg`](file:///data/Open_Network_Experience/assets/images/one_social_preview.svg) (file:///data/Open_Network_Experience/assets/images/one_social_preview.svg) |

### Official Product Slogans & Taglines
- **Primary Platform Slogan**: *"Every Packet Accountable. Every Experience Verified."*
- **K-12 Education Tagline**: *"Know What Students & Teachers Experience Before The Morning Bell Rings."*
- **Enterprise / NOC Tagline**: *"Continuous Synthetic Probing from Edge Hardware to Chromebook Fleets."*

### Logo Construction & Symbolism ("The Synthetic Hex Pulse")
1. **Segment A (Top-Right / Electric Cyan -> Signal Blue)**: Represents **Hardware Edge Probers** monitoring local Wi-Fi RF and wired interfaces.
2. **Segment B (Right-Bottom / Signal Blue -> Emerald Green)**: Represents the central **FastAPI Control Plane & Time-Series DB**.
3. **Segment C (Left-Bottom / Emerald Green -> Teal/Cyan)**: Represents the distributed **Chromebook / Client Fleets**.
4. **Inner Core Waveform & Focal Dot**: Represents the real-time EKG heartbeat and ITU-T VoIP MOS rating of user experience.

---

## 3. Color Palette

### Primary NOC Palette (Dark Theme)
```
#0B0F19  ██  NOC Midnight Canvas      Background surface, base canvas
#1E293B  ██  Slate Slate 800          Card containers, borders, navigation bars
#00F0FF  ██  Cyber Cyan               Primary accent, Wi-Fi RF telemetry, active links
#3B82F6  ██  Electric Blue            Secondary accent, wired ethernet metrics
#8B5CF6  ██  Indigo Pulse             Tertiary accent, Chromebook fleet telemetry
```

### Telemetry Status Colors
```
#10B981  ██  Emerald Operational      Pass, Healthy, 100% SLA, CAASPP Ready (MOS >= 4.0)
#F59E0B  ██  Amber Warning            Elevated latency (>150ms), High Channel Flapping (>3/hr)
#F43F5E  ██  Rose Critical            Packet loss (>5%), SSL Pinning Bypass Failure, CIPA Block Fail
#64748B  ██  Muted Offline            Pending TOFU approval, Sensor unreachable
```

---

## 4. Typography & Styling

### Primary Web & UI Font Stack
* **Headings & Badges**: Inter, SF Pro Display, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif.
  * Weight: 800 (ExtraBold) or 900 (Black).
  * Letter Spacing: `-0.02em` for large display headings; `+0.05em` for uppercase badges.
* **Body Text**: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif.
  * Weight: 400 (Regular), 500 (Medium).
  * Line Height: `1.6` for optimal readability.
* **Code & Telemetry Metrics**: JetBrains Mono, Fira Code, SF Mono, Menlo, monospace.
  * Weight: 500 / 600.

---

## 5. Voice, Tone & Messaging Pillars

| Persona / Channel | Tone | Key Value Message |
| :--- | :--- | :--- |
| **K-12 School Districts** | Empathetic, Pragmatic, Budget-Conscious | *"Ensure flawless CAASPP state testing and Google Classroom streaming without spending $30,000/yr on proprietary sensors."* |
| **Network Engineers / NOC** | Technical, Exacting, Data-Driven | *"Dual-NIC scientific control eliminates finger-pointing between Wi-Fi APs and ISP WAN drops. Native PCAP ring buffers capture the exact packet drop."* |
| **Open Source / Homelab** | Hacker-Friendly, Modular, Unchained | *"100% AGPLv3. Deploy on Raspberry Pi 4/5, Intel N100 mini-PCs, or ChromeOS extensions in minutes with Docker Compose and FastAPI."* |

---

## 6. Official Backlinks & Companion Stack
When referencing external components and ecosystem partners, always link to official homepages:
* [FastAPI](https://fastapi.tiangolo.com/) — Modern high-performance web framework for Python.
* [VictoriaMetrics](https://victoriametrics.com/) — Fast, cost-effective TSDB time-series database.
* [Grafana](https://grafana.com/) — Open observability and visualization platform.
* [Grafana Loki](https://grafana.com/oss/loki/) — Scalable log aggregation engine.
* [Playwright](https://playwright.dev/) — Reliable end-to-end synthetic browser testing.
* [Raspberry Pi](https://www.raspberrypi.com/) — Affordable single-board computing hardware.
