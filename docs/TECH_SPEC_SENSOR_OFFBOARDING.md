# Open Network Experience (ONE) - Edge Hardware Sensor Offboarding & De-provisioning

**Document ID:** SPEC-OPS-001
**Target Audience:** Network Engineers, System Administrators, DevOps
**Status:** Implemented

---

## 1. Executive Summary

This document specifies the architectural design and requirements for the automated, idempotent edge hardware sensor offboarding and de-provisioning script for the Open Network Experience (ONE) platform.

The goal is to provide a robust mechanism (`scripts/offboard.sh`) to connect via secure SSH to a specified target edge appliance and execute a de-provisioning pipeline, returning the device to its pre-onboard baseline state.

---

## 2. Requirements

*   **Idempotence:** The script must be safe to run multiple times without causing errors or unexpected state changes. If a component is already removed, the script should gracefully proceed.
*   **Error Handling:** Robust error handling is required to manage connectivity issues, invalid inputs, and unexpected system states.
*   **Complete Cleanup:** The de-provisioning process must ensure the removal of:
    *   `systemd` service (`sensor-reconciler.service`).
    *   Prober binaries (e.g., `reconciler.py`, `wizard.py`, etc.).
    *   Docker test containers and images (e.g., `open-ux/playwright-runner`).
    *   State files and directories (e.g., `/etc/sensor`, `/var/lib/sensor`).
    *   Sensitive credentials (shredded or removed).
*   **Configuration Restoration:** The script should restore original network configurations, specifically `wpa_supplicant.conf` if a backup exists.
*   **Execution Modes:**
    *   `--wipe` (default): Performs the de-provisioning and cleanup without backing up data.
    *   `--archive`: Creates a compressed archive of the sensor state before wiping, facilitating recovery or auditing.
*   **Security:**
    *   Validates input IP/hostname and username formats.
    *   Enforces strict permissions (0600 or 0400) on the secret credentials file.
    *   Securely shreds sensitive configuration files when possible.

---

## 3. Architecture & Workflow

The `scripts/offboard.sh` script executes in a sequential, 5-phase pipeline:

### Phase 1: Pre-flight Checks & Connection
1.  Validates arguments (IP/Hostname, Username, Credentials File, Execution Mode).
2.  Checks permissions on the credentials file.
3.  Establishes a multiplexed SSH connection for performance and reliability.
4.  Retrieves device hostname and sensor identity.

### Phase 2: Archiving (Conditional)
*   If the `--archive` mode is specified, the script creates a `tar.gz` archive of key state directories (`/etc/sensor`, `/var/lib/sensor`, `/var/lib/node_exporter/textfile_collector`) on the remote device.
*   The archive is then downloaded to the local machine (`backups/sensor_archives/`) and verified with a SHA256 checksum before being removed from the remote device.

### Phase 3: Service Termination
1.  Stops, disables, and removes the `sensor-reconciler.service`.
2.  Reloads the `systemd` daemon and resets failed units.
3.  Forcefully kills any lingering prober processes (e.g., `reconciler.py`, `pcap_trigger.py`).

### Phase 4: Docker Teardown
1.  Identifies and removes active `playwright-runner` containers.
2.  Removes the `open-ux/playwright-runner:latest` Docker image.
3.  Prunes dangling Docker volumes to reclaim space.

### Phase 5: Filesystem Cleanup & Restoration
1.  Purges all known prober binaries from `/usr/local/bin/`.
2.  Securely shreds (`shred -u -z -n 3`) or removes `/etc/sensor/reconciler.json`.
3.  Deletes state directories and temporary files (`/etc/sensor`, `/var/lib/sensor`, `/tmp/sensor`, Prometheus metrics).
4.  Restores `/etc/wpa_supplicant/wpa_supplicant.conf.orig` to `/etc/wpa_supplicant/wpa_supplicant.conf` if present.

### Phase 6: Post-Wipe Audit
*   Verifies that the `sensor-reconciler` service is inactive.
*   Checks for the absence of key residual files.
*   Ensures no relevant Docker containers are running.
*   Exits with `0` on success or `3` if warnings/errors are detected during the audit.

---

## 4. Usage Examples

**Standard Wipe (Password Authentication):**
```bash
./scripts/offboard.sh 10.98.2.141 admin /etc/one/sensor.pass --wipe
```

**Archive & Wipe (SSH Key Authentication):**
```bash
./scripts/offboard.sh 10.98.2.105 root ~/.ssh/id_ed25519 --archive
```
