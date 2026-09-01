## What's Changed

<!-- Fill in the tag comparison URL after tagging -->
**Full Changelog**: https://github.com/leifdavisson/Open_Network_Experience/compare/v0.4.0...v0.5.0

---

## 🏗️ Probe Truthfulness Architecture

The most significant change in v0.5.0 is a **fundamental correctness fix** for all on-demand diagnostic probes.

**Before:** Every probe in the CMP's "Run Diagnostics" UI executed from *inside the CMP Docker container*. This was architecturally incorrect — the CMP sits on a management VLAN with direct routing to the sensor subnet, so VLAN isolation checks always passed, DNS results reflected the CMP's resolvers, and VoIP jitter measured the CMP's internet path — not the student device's.

**After:** Probes now SSH to the physical edge sensor appliance and execute the probe scripts there. Results reflect actual network conditions from the sensor's VLAN and network perspective. A `[Physical Sensor (x.x.x.x)]` / `[CMP Container]` source tag on every result row makes data provenance transparent.

```
CMP Dashboard  →  POST /diagnostics/run
      ↓
  is_edge?  ──YES──▶  SSH → sensor  →  ./probe.py --json  →  parse JSON  →  display
      │                                                                  ↑ [Physical Sensor]
      NO
      ↓
  CMP socket probe  →  display
                   ↑ [CMP Container (sensor SSH unavailable)]
```

---

## ✨ New Features

### RingCentral UCaaS Health Probe
New synthetic probe validating RingCentral TURN relay, SIP trunk API, and session control endpoints — critical for districts using RingCentral for phone/video.

### Wi-Fi Client Isolation Validator
Verifies that guest/student SSIDs correctly block peer-to-peer lateral traffic. Tests adjacent IPs via TCP SYN and validates ARP isolation and mDNS suppression from the sensor's wired vantage.

### `--json` Mode on All Sensor Probe Scripts
All four probe scripts (`voip_jitter_probe.py`, `segmentation_prober.py`, `dns_multi_resolver_probe.py`, `caaspp_readiness.py`) now support `--json` flag for structured stdout delegation. Normal interactive use is unchanged.

### Alert Rules & Webhook Routing
Prometheus alert rules with configurable multi-day construction-period muting. Alertmanager webhook configuration for NOC notification pipelines.

---

## 🔒 Security Hardening

| Item | Before | After |
|---|---|---|
| `SSH_PASS` default | `"Kern1234"` (bench password) | `""` (empty — delegation disabled if unset) |
| `SSH_USER` default | `"kern"` (bench username) | `"sensor"` (generic) |
| Bench sensor auto-approval | `f10325921*` prefix → auto-approved, auto-IP | All sensors start `pending` regardless of ID |
| CMP IP references | Hardcoded `10.98.2.125` | `CMP_HOST` env-var (default: `localhost`) |
| Sensor IP fallback | Hardcoded `10.98.2.105` | `null` — populated by reconciler check-in |
| `.env.example` | Bench-specific values | Generic production template with docs |

---

## 🐛 Bug Fixes

- **`state.py` `NameError: name 'time' is not defined`** — missing `import time` caused crash in `get_or_create_sensor()` for new sensors
- **SSH delegation timeouts** — probes were silently timing out (12s default) for slow scripts. Now per-probe: voip→20s, segmentation→15s, DNS→25s, CAASPP→35s
- **DNS fallback hardcoded `3.8ms`** — CMP fallback now performs real `socket.getaddrinfo()` timing
- **RingCentral 503 false-negative** — HTTP 503 from RingCentral health endpoints is now correctly treated as `ok`
- **`write_metrics()` crash in `client_isolation_probe.py`** — filesystem write failure no longer crashes the probe

---

## 📊 Test Coverage

```
359 passed  (server/ + sensor/)
 98 passed  (deploy_bench.sh integration)
  0 failed
  0 errors
```

Automated validation matrix: `pytest`, `mypy`, Bandit SAST, MC/DC truth-table coverage, RTM traceability.

---

## ⚙️ Upgrade Notes

### Environment Variables (New)
Add to your `.env` and `docker-compose.yml`:

```bash
CMP_HOST=cmp.yourdistrict.edu   # or IP of your CMP server
CMP_PORT=8000
ADMIN_API_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
SSH_USER=sensor                  # SSH user on edge sensor appliances
SSH_PASS=                        # Leave empty; configure SSH key-based auth instead
```

### SSH Key-Based Auth (Recommended)
Instead of `SSH_PASS`, configure key-based auth between CMP and sensors:

```bash
# On CMP host:
ssh-keygen -t ed25519 -f /etc/one/sensor_rsa -N ""
# On each sensor:
cat /etc/one/sensor_rsa.pub >> ~/.ssh/authorized_keys
```

Then mount the key in docker-compose and update `_run_remote_sensor_probe()` to use `-i /etc/one/sensor_rsa`.

### Existing Bench Deployments
The bench sensor (`f10325921...`) is no longer auto-approved on first contact. Run the seed script to re-register:

```bash
python3 scripts/clean_and_seed_db.py
```
