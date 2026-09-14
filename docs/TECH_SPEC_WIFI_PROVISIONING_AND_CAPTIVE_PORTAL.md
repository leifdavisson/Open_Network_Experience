# Technical Specification: Remote Wi-Fi SSID Probing, Provisioning & Captive Portal Traversal (Headless Screencast)

**Document Version**: 1.0.0  
**Status**: Proposal / Ready for Review  
**Target Component**: CMP Server, Sensor Agent, CMP Web Dashboard  
**License**: GNU AGPLv3  

---

## 1. Executive Summary & Problem Statement

School districts, hospitals, and enterprise facilities manage distributed edge sensors across multiple sites. Network operations teams often need to onboard or reconfigure sensors onto local Wi-Fi networks without physical on-site access or serial console access.

Currently:
1. **No Remote SSID Visibility**: The CMP cannot inspect what 2.4 GHz / 5 GHz / 6 GHz SSIDs an edge sensor can hear in its local RF environment.
2. **Manual Wi-Fi Association**: Operators cannot provision Wi-Fi credentials (WPA2/WPA3 PSK, 802.1X EAP, or Open) down to sensors remotely.
3. **Captive Portal Blockers**: When connecting to guest networks (e.g. Cisco ISE, Aruba ClearPass, Meraki Splash, FortiGuest), sensors have no physical display or input peripherals to complete terms-of-service click-throughs, CAPTCHAs, or guest logins. Standard iframes inside the CMP fail due to private subnet routing (`10.0.0.1`), DNS interception, and `X-Frame-Options` restrictions.

This specification defines the end-to-end architecture for:
- **Remote Wi-Fi Survey & Probing**: Triggering on-demand wireless scans from the CMP and returning signal levels (RSSI), frequency, and encryption types.
- **Secure Remote Provisioning**: Pushing encrypted Wi-Fi profiles with automated connection watchdog and fallback rollback.
- **Interactive Captive Portal Traversal (Option B)**: Streaming an ephemeral, headless Chromium viewport from the sensor to the CMP dashboard via Chrome DevTools Protocol (CDP) and WebSocket, enabling operators to interactively complete any captive portal without security header or routing breakage.

---

## 2. End-to-End System Architecture

```mermaid
sequenceDiagram
    autonumber
    participant CMP_UI as CMP Dashboard (Web)
    participant CMP_API as CMP Server (FastAPI)
    participant Sensor as Sensor Agent (one-sensor)
    participant AP as Local Wi-Fi AP & Gateway

    Note over CMP_UI,Sensor: Phase 1: On-Demand Wi-Fi Survey
    CMP_UI->>CMP_API: POST /api/v1/sensors/{id}/wifi/scan
    CMP_API->>Sensor: Scan Command via MQTT / WSS Control Channel
    Sensor->>AP: 802.11 Probe Request (wpa_cli / nmcli)
    AP-->>Sensor: 802.11 Beacons / Probe Responses
    Sensor->>CMP_API: Report Survey Results (SSID, BSSID, RSSI, Security, Portal Detected)
    CMP_API-->>CMP_UI: Display Wi-Fi Survey Table

    Note over CMP_UI,Sensor: Phase 2: Remote Credential Provisioning
    CMP_UI->>CMP_API: POST /api/v1/sensors/{id}/wifi/connect (SSID, Credentials)
    CMP_API->>Sensor: Push Encrypted Wi-Fi Profile with 60s Watchdog
    Sensor->>AP: Associate (WPA2-PSK / WPA3-SAE / 802.1X / Open)
    AP-->>Sensor: Associated + DHCP IP Assigned

    Note over Sensor,AP: Phase 3: Egress & Captive Portal Detection
    Sensor->>AP: Probe http://connectivitycheck.gstatic.com/generate_204
    alt Direct WAN Egress (HTTP 204)
        Sensor->>CMP_API: Report Online (State: CONNECTED)
    else Captive Portal Intercepted (HTTP 302 / HTML)
        Sensor->>CMP_API: Report State: CAPTIVE_PORTAL_INTERCEPTED (Redirect URL)
        CMP_API-->>CMP_UI: Alert Operator: "Captive Portal Interaction Required"
    end

    Note over CMP_UI,Sensor: Phase 4: Headless Screencast Interaction (Option B)
    CMP_UI->>CMP_API: Operator clicks "Open Remote Portal"
    CMP_API->>Sensor: InitBrowserSession(sessionId)
    Sensor->>Sensor: Launch Ephemeral Chromium (--headless=new, --window-size=1024,768)
    Sensor->>Sensor: Start CDP Screencast (Page.startScreencast)
    loop Viewport Stream & Event Relay
        Sensor-->>CMP_API: Screencast Frames (JPEG / Base64) via WebSocket
        CMP_API-->>CMP_UI: Render to HTML5 <canvas>
        CMP_UI->>CMP_API: Pointer / Keystroke Events
        CMP_API->>Sensor: Input.dispatchMouseEvent / Input.dispatchKeyEvent
    end
    AP-->>Sensor: Portal Authenticated (Gateway Unblocks Sensor MAC)
    Sensor->>AP: Probe generate_204 -> Returns 204 OK!
    Sensor->>Sensor: Terminate Chromium (SIGTERM, Purge Temp Profile)
    Sensor->>CMP_API: Report State: CAPTIVE_RESOLVED_ONLINE
    CMP_API-->>CMP_UI: Display "Wi-Fi Connected & Internet Egress Verified"
```

---

## 3. Component Details & Protocols

### 3.1 Sensor Wi-Fi Survey & Association Subsystem
1. **Wi-Fi Scanner**:
   - Uses `nmcli -t -f SSID,BSSID,CHAN,SIGNAL,SECURITY dev wifi list --rescan yes` or `wpa_cli scan / scan_results`.
   - Normalizes signal strength to dBm and percentages.
   - Detects open networks likely running captive portals.
2. **Safe Association Watchdog**:
   - When switching SSIDs remotely, a bad password or authentication timeout could orphan the sensor from CMP management.
   - **Watchdog Logic**: If the sensor fails to verify uplink to CMP within `T_rollback` (default: 60s), the network stack automatically restores the previous active connection (e.g. Ethernet, cellular, or previous Wi-Fi profile).

### 3.2 Captive Portal Detection Engine
The sensor runs a multi-canary probe:
- Primary: `http://connectivitycheck.gstatic.com/generate_204`
- Secondary: `http://captive.apple.com/hotspot-detect.html`

If the HTTP status code is `302 Found` or returns an HTML body, the target redirect URL is extracted from the `Location` header or meta-refresh tags.

### 3.3 Option B: Headless Chromium Screencast Engine
To bypass CORS, private subnet isolation (`10.0.0.1`), and complex client-side JavaScript / anti-bot mechanisms, the sensor spawns an ephemeral Chromium instance:

#### Command Line Flags for Low-Memory Embedded Devices
```bash
chromium-browser \
  --headless=new \
  --no-sandbox \
  --disable-gpu \
  --disable-dev-shm-usage \
  --disable-software-rasterizer \
  --disable-extensions \
  --disable-background-networking \
  --disable-sync \
  --mute-audio \
  --window-size=1024,768 \
  --remote-debugging-port=9222 \
  --user-data-dir=/tmp/chromium-captive-session \
  "about:blank"
```

#### Chrome DevTools Protocol (CDP) Flow
- **`Page.startScreencast`**:
  ```json
  {
    "method": "Page.startScreencast",
    "params": {
      "format": "jpeg",
      "quality": 75,
      "maxWidth": 1024,
      "maxHeight": 768,
      "everyNthFrame": 1
    }
  }
  ```
- **Pacing with `Page.screencastFrameAck`**: The sensor acknowledges frames to Chromium to maintain smooth streaming without queuing memory spikes.
- **Interactive Input Dispatch**:
  - `Input.dispatchMouseEvent` (`mousePressed`, `mouseReleased`, `mouseMoved`, `mouseWheel`)
  - `Input.dispatchKeyEvent` (`rawKeyDown`, `keyUp`) and `Input.insertText`

#### Edge Resource Envelope
- **RAM Footprint**: ~150–250MB strictly during interactive login.
- **Idle RAM Footprint**: 0MB (Chromium is terminated immediately once HTTP 204 egress is confirmed).
- **Hard Timeout**: 300 seconds maximum runtime watchdog to prevent memory leaks from abandoned sessions.

---

## 4. Token & Session Expiration Management

1. **MAC-Based State (Predominant Model)**:
   In most enterprise WLCs (Aruba, Cisco, UniFi), network authorization is tied to the physical Layer 2 MAC address at the gateway firewall. The sensor itself holds no token.
2. **Session Expiry Detection**:
   The sensor runs a lightweight background daemon checking `http://connectivitycheck.gstatic.com/generate_204` every 60 seconds.
3. **Renewal Workflow**:
   - If the portal returns 302, the sensor marks the session expired.
   - If static terms / guest credentials were saved with policy `auto_reauthenticate: true`, the sensor runs an automated re-submission script.
   - If interactive intervention is required (e.g. 2FA SMS or CAPTCHA), the sensor alerts CMP: `WIFI_CAPTIVE_PORTAL_EXPIRED`.

---

## 5. Security & Isolation Controls

- **Control-Plane Encryption**: All survey data, credentials, and screencast frames flow across existing mutual TLS (mTLS) or authenticated WebSocket channels.
- **Ephemeral Chromium Sandboxing**: User data directory `/tmp/chromium-captive-session` is mounted on tmpfs and securely wiped (`shred`/`rm -rf`) on process exit.
- **Coordinate Boundary Enforcement**: CMP frontend scales click coordinates strictly within the `1024x768` bounding box to avoid input out-of-bounds errors.

---

## 6. Project References & Official Documentation

- **Chrome DevTools Protocol (CDP)**: [CDP Page Domain](https://chromedevtools.github.io/devtools-protocol/tot/Page/) | [CDP Input Domain](https://chromedevtools.github.io/devtools-protocol/tot/Input/)
- **Chromium Project**: [Chromium Headless Mode](https://developer.chrome.com/docs/chromium/new-headless)
- **Browser Screencast Implementations**: [Browserless Screencast Guide](https://www.browserless.io/blog/screencast) | [Playwright Documentation](https://playwright.dev/)
- **IETF Captive Portal Standards**: [RFC 8908 (Captive-Portal Architecture)](https://datatracker.ietf.org/doc/html/rfc8908) | [RFC 8910 (Captive-Portal Identification)](https://datatracker.ietf.org/doc/html/rfc8910)
- **Linux Wireless Utilities**: [NetworkManager DBus API](https://networkmanager.dev/docs/api/latest/) | [wpa_supplicant Documentation](https://w1.fi/wpa_supplicant/)
