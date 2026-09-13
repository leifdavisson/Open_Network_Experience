# Architecture Decision Record (ADR)
**Decision ID:** ADR-014
**Title:** Chromebook Sensor MV3 Architecture: Sandbox Security Boundaries, Layer 1 vs Layer 3 Telemetry, and Local Network Access Compliance
**Status:** Accepted
**Date:** September 13, 2026
**License:** [GNU AGPLv3](https://www.gnu.org/licenses/agpl-3.0.en.html)

## Context & Problem Statement
The ONE Chromebook Sensor is deployed as a Manifest V3 (MV3) Chrome extension across K-12 school districts to provide 24/7 client-side Wi-Fi and application telemetry. During empirical field testing and browser runtime audits, several physical and security architectural boundaries were encountered:
1. **Layer 1 Physical Carrier Indeterminacy**: Chromium executes inside an unprivileged userspace sandbox without access to low-level kernel networking ioctls (`SIOCETHTOOL`) or `/sys/class/net/<iface>/carrier`. When an Ethernet cable is unplugged or switched to Wi-Fi, the OS routing table and DHCP client frequently keep the IP assigned to the NIC until lease teardown or socket cleanup. Consequently, `chrome.system.network` continues to report the Ethernet interface with an IP, preventing pure Layer 1 physical link sensing.
2. **Enterprise Policy Boundaries (RF & Device Identity)**: Privileged APIs (`chrome.networkingPrivate` for BSSID, RSSI dBm, Frequency, and Channel; `chrome.enterprise.deviceAttributes` for Serial Number and Asset ID) are strictly restricted by Google to enterprise-managed ChromeOS devices force-installed via Google Workspace Admin Console (`device_local_accounts` or `policy_installed`). Unmanaged Chromebooks, developer mode sideloads, and desktop Chrome browsers return `undefined` for these namespaces.
3. **Chrome Local Network Access (LNA) Compliance**: Modern Chromium versions enforce strict CORS preflight and address space restrictions when web pages or service workers attempt to communicate with private subnets (`10.0.0.0/8`, `192.168.0.0/16`, `172.16.0.0/12`, `localhost`). Probes to local gateways or internal CMP instances risk silent network blockages without explicit permission headers and target space annotations.
4. **Data Integrity & Truthfulness ("Zero Guessing")**: In the absence of RF telemetry, naive systems guess BSSIDs or default gateways, or misclassify disconnected wired adapters.

## Decision
1. **Explicit "Not Supported" State for Restricted Metrics**:
   - The sensor strictly rejects guessing, estimation heuristics, or dummy MAC generation.
   - When running on unmanaged devices or standard desktop browsers, restricted fields explicitly display:
     - BSSID: `"Not supported (Requires Managed ChromeOS)"`
     - RSSI & Channel: `"Not supported (Unmanaged)"`
     - Device Identity: `"Unmanaged Device (<uuid>...)"`
     - Status Card: `"Active Network State (Managed Policy Restricted)"`
2. **Layer 3/4 Functional Probing Over Layer 1 Link Guessing**:
   - Rather than attempting to guess physical cable presence, the sensor assesses network health via active Layer 3/4 reachability (Gateway RTT, HTTP synthetic latency, dual-stack DNS resolution, and WebRTC MOS scores).
   - Dynamic interface state changes are detected via `chrome.system.network.onNetworkListChanged` and `window.addEventListener('online'/'offline')`, triggering immediate diagnostic sweeps.
3. **Local Network Access (LNA) Compliance**:
   - All synthetic fetch probes directed at local IPs or RFC 1918 gateway targets annotate requests with `targetAddressSpace: 'local'` and `mode: 'no-cors'` or properly configured CORS headers to satisfy Chromium's Private Network Access security model.
4. **Popout Diagnostic Center**:
   - In addition to standard browser action popups (which truncate long tables and close upon losing focus), the extension supports an independent popout window mode (`chrome.windows.create({ type: 'popup', width: 900, height: 750 })`) providing unobstructed visibility into live telemetry.
5. **Two-Tier Resilient Telemetry Queue**:
   - Sensor telemetry is buffered locally in `IndexedDB` with an in-memory FIFO fallback queue and backpressure eviction (capped at 500 events) to survive network drops without consuming unbounded device memory.

## Alternatives Considered
- **Guessing Gateway & Default Interface via Routing Metric Tricks**: Rejected. Chromium's sandbox purposefully conceals kernel routing tables. Guessing default gateways resulted in misleading diagnostic reports in multi-homed or docking station environments.
- **Requiring NPAPI/Native Messaging Host for L1 Access**: Rejected. Native messaging requires installing and maintaining a separate host binary on every Chromebook, defeating the zero-touch web deployment model required by school districts.
- **Silently Omitting Missing RF Metrics**: Rejected in favor of explicit "Not supported" badges, which educate IT administrators on why enterprise policy installation is necessary for RF visibility.

## Consequences & Trade-offs
- **Pros**:
  - 100% architectural truthfulness: NOC operators and school IT staff are never misled by fabricated or guessed network data.
  - Zero-touch installation through Google Workspace Admin Console.
  - Compliance with upcoming Chromium Local Network Access security restrictions.
  - Reliable live interface transition detection without relying on unsupported kernel hooks.
- **Cons**:
  - Requires managed ChromeOS device enrollment to view physical Wi-Fi AP BSSID and RF channel information.
