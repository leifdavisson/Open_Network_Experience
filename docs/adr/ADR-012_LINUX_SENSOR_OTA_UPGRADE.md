# Architecture Decision Record (ADR)
**Decision ID:** ADR-012
**Title:** Linux Edge Sensor Over-The-Air (OTA) Upgrade Pipeline via Reconciler Graceful Respawn
**Status:** Accepted
**Date:** September 02, 2026
**License:** [GNU AGPLv3](https://www.gnu.org/licenses/agpl-3.0.en.html)

## Context & Problem Statement
Physical edge sensors deployed across campus networks require remote software upgrade capabilities without manual SSH intervention or destructive reinstallations. Running full `install.sh` scripts remotely wipes `/etc/sensor/reconciler.json`, destroys persistent sensor identity and API keys (forcing devices into an orphaned "Pending" state), and invoking `systemctl restart` from within a child process triggers systemd CGroup `SIGKILL` race conditions.

## Decision
1. **Control Plane Signal**: The CMP exposes a `/api/v1/sensors/{id}/upgrade` endpoint that flags `ota_upgrade: true` in the sensor's periodic reconciliation polling response.
2. **Compile-Before-Swap Verification**: The edge sensor's `reconciler.py` downloads the new executable from the CMP, compiles it using Python's `py_compile` module to verify syntax integrity, and only overwrites the live binary upon 0 exit code.
3. **Acknowledgment & Graceful Exit**: The reconciler calls `/api/v1/sensors/{id}/upgrade/clear` to reset the flag on the CMP, then terminates with `sys.exit(0)`.
4. **Systemd Supervision**: Because the systemd unit specifies `Restart=always`, systemd automatically respawns the newly installed binary cleanly without process hierarchy conflicts.

## Alternatives Considered
- **Direct SSH Invocation from CMP (`ssh root@sensor install.sh`)**: Rejected due to network boundary traversal constraints (sensors may be behind NAT/firewalls without inbound SSH access) and risk of wiping sensor identity files.
- **In-process execv / fork**: Rejected due to lingering memory allocations and file descriptor inheritance issues compared to a clean systemd restart.

## Consequences & Trade-offs
- **Pros**: Zero-touch, firewall-friendly pull-based updates; guarantees syntax verification before replacement; preserves hardware credentials and identity tokens.
- **Cons**: Requires sensors to have outbound HTTP/HTTPS access to the CMP port.
