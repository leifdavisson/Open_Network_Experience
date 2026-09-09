#!/usr/bin/env bash
#
# Open Network Experience (ONE) - Edge Sensor Offboarding & De-provisioning Wrapper
#
# Copyright (C) 2026 Open Network Experience Authors.
# Licensed under the GNU Affero General Public License v3.0 (AGPLv3).
# See LICENSE in the project root for full license details.
#
# Usage:
#   ./scripts/offboard.sh <DEVICE_IP> <USERNAME> <SECRET_CREDENTIALS_FILE> [--archive|--wipe]
#
# Description:
#   Connects via secure SSH to the specified target edge appliance and executes an idempotent
#   de-provisioning pipeline, returning the device to its pre-onboard baseline state.

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

print_banner() {
    echo -e "${CYAN}================================================================${NC}"
    echo -e "${CYAN}  🧹 Open Network Experience (ONE) Sensor Offboarding Harness   ${NC}"
    echo -e "${CYAN}================================================================${NC}"
}

print_usage() {
    echo -e "${BOLD}Usage:${NC}"
    echo "  $0 <DEVICE_IP> <USERNAME> <SECRET_CREDENTIALS_FILE> [MODE]"
    echo ""
    echo -e "${BOLD}Arguments:${NC}"
    echo "  DEVICE_IP               IPv4 or IPv6 address of target edge appliance"
    echo "  USERNAME                SSH user with sudo privileges"
    echo "  SECRET_CREDENTIALS_FILE Path to file with SSH private key or password (chmod 0600/0400)"
    echo "  MODE                    (Optional) '--archive' to backup data before wipe (default: '--wipe')"
    echo ""
    echo -e "${BOLD}Examples:${NC}"
    echo "  $0 10.98.2.105 kern ~/.ssh/id_ed25519 --archive"
    echo "  $0 10.98.2.141 kern /etc/one/sensor.pass --wipe"
    exit 1
}

if [[ $# -lt 3 ]]; then
    print_banner
    echo -e "${RED}Error: Missing required arguments.${NC}" >&2
    print_usage
fi

DEVICE_IP="$1"
USERNAME="$2"
SECRET_CREDENTIALS_FILE="$3"
MODE="${4:---wipe}"

IP_REGEX="^([0-9]{1,3}\.){3}[0-9]{1,3}$"
HOSTNAME_REGEX="^([a-zA-Z0-9](([a-zA-Z0-9-]){0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$"
if [[ ! "$DEVICE_IP" =~ $IP_REGEX && ! "$DEVICE_IP" =~ $HOSTNAME_REGEX && "$DEVICE_IP" != "localhost" ]]; then
    echo -e "${RED}Error: Invalid DEVICE_IP format: '${DEVICE_IP}'. Must be a valid IPv4 address or FQDN.${NC}" >&2
    exit 1
fi

USER_REGEX="^[a-zA-Z0-9_-]{1,32}$"
if [[ ! "$USERNAME" =~ $USER_REGEX ]]; then
    echo -e "${RED}Error: Invalid USERNAME format: '${USERNAME}'. Only alphanumeric, underscores, and dashes allowed.${NC}" >&2
    exit 1
fi

if [[ ! -f "$SECRET_CREDENTIALS_FILE" ]]; then
    echo -e "${RED}Error: SECRET_CREDENTIALS_FILE does not exist: '${SECRET_CREDENTIALS_FILE}'.${NC}" >&2
    exit 1
fi

FILE_PERMS=$(stat -c "%a" "$SECRET_CREDENTIALS_FILE" 2>/dev/null || stat -f "%Lp" "$SECRET_CREDENTIALS_FILE" 2>/dev/null || echo "unknown")
if [[ "$FILE_PERMS" != "600" && "$FILE_PERMS" != "400" && "$FILE_PERMS" != "unknown" ]]; then
    echo -e "${RED}Security Error: Insecure permissions (${FILE_PERMS}) on credentials file.${NC}" >&2
    echo -e "${YELLOW}Mitigation: Run 'chmod 0600 ${SECRET_CREDENTIALS_FILE}' before executing.${NC}" >&2
    exit 1
fi

if [[ "$MODE" != "--archive" && "$MODE" != "--wipe" ]]; then
    echo -e "${RED}Error: Unknown mode '${MODE}'. Allowed options are '--archive' or '--wipe'.${NC}" >&2
    print_usage
fi

print_banner
echo -e "${BLUE}Target Device:${NC}      ${GREEN}${DEVICE_IP}${NC}"
echo -e "${BLUE}SSH Username:${NC}       ${GREEN}${USERNAME}${NC}"
echo -e "${BLUE}Credentials File:${NC}   ${GREEN}${SECRET_CREDENTIALS_FILE} (${FILE_PERMS})${NC}"
echo -e "${BLUE}Execution Mode:${NC}     ${YELLOW}${MODE}${NC}"
echo ""

IS_SSH_KEY=0
if grep -qE "(BEGIN .* PRIVATE K.Y|BEGIN OPENSSH PRIVATE K.Y)" "$SECRET_CREDENTIALS_FILE" 2>/dev/null; then
    IS_SSH_KEY=1
fi

SSH_SOCKET_DIR="/tmp/ssh-one-${USER:-root}"
mkdir -p "$SSH_SOCKET_DIR"
chmod 0700 "$SSH_SOCKET_DIR"
CONTROL_PATH="${SSH_SOCKET_DIR}/%C"

SSH_COMMON_OPTS=(
    -o "StrictHostKeyChecking=no"
    -o "UserKnownHostsFile=/dev/null"
    -o "ConnectTimeout=10"
    -o "BatchMode=yes"
    -o "ControlMaster=auto"
    -o "ControlPath=${CONTROL_PATH}"
    -o "ControlPersist=60s"
    -o "LogLevel=ERROR"
)

cleanup_session() {
    ssh -O exit -o "ControlPath=${CONTROL_PATH}" "${USERNAME}@${DEVICE_IP}" 2>/dev/null || true
    rm -rf "$SSH_SOCKET_DIR" 2>/dev/null || true
}
trap cleanup_session EXIT

run_ssh() {
    local cmd="$1"
    if [[ "$IS_SSH_KEY" -eq 1 ]]; then
        ssh "${SSH_COMMON_OPTS[@]}" -i "$SECRET_CREDENTIALS_FILE" "${USERNAME}@${DEVICE_IP}" "$cmd"
    else
        local pass
        pass=$(head -n 1 "$SECRET_CREDENTIALS_FILE" | sed 's/^SSH_PASS=//')
        sshpass -p "$pass" ssh "${SSH_COMMON_OPTS[@]}" -o "BatchMode=no" "${USERNAME}@${DEVICE_IP}" "$cmd"
    fi
}

run_ssh_stdin() {
    if [[ "$IS_SSH_KEY" -eq 1 ]]; then
        ssh "${SSH_COMMON_OPTS[@]}" -i "$SECRET_CREDENTIALS_FILE" "${USERNAME}@${DEVICE_IP}" "bash -s"
    else
        local pass
        pass=$(head -n 1 "$SECRET_CREDENTIALS_FILE" | sed 's/^SSH_PASS=//')
        sshpass -p "$pass" ssh "${SSH_COMMON_OPTS[@]}" -o "BatchMode=no" "${USERNAME}@${DEVICE_IP}" "bash -s"
    fi
}

run_scp_download() {
    local remote_src="$1"
    local local_dst="$2"
    if [[ "$IS_SSH_KEY" -eq 1 ]]; then
        scp -o "StrictHostKeyChecking=no" -o "UserKnownHostsFile=/dev/null" -i "$SECRET_CREDENTIALS_FILE" "${USERNAME}@${DEVICE_IP}:${remote_src}" "$local_dst"
    else
        local pass
        pass=$(head -n 1 "$SECRET_CREDENTIALS_FILE" | sed 's/^SSH_PASS=//')
        sshpass -p "$pass" scp -o "StrictHostKeyChecking=no" -o "UserKnownHostsFile=/dev/null" "${USERNAME}@${DEVICE_IP}:${remote_src}" "$local_dst"
    fi
}

echo -e "${BLUE}[1/5] Testing SSH Connectivity & Remote Elevation...${NC}"
if ! run_ssh "echo 'SSH_OK'" &>/dev/null; then
    echo -e "${RED}Error: Unable to connect to ${USERNAME}@${DEVICE_IP} using provided credentials.${NC}" >&2
    exit 2
fi
echo -e "  ✓ SSH Connectivity: ${GREEN}ESTABLISHED${NC}"

DEVICE_HOSTNAME=$(run_ssh "hostname" 2>/dev/null || echo "sensor-node")
SENSOR_UUID=$(run_ssh "cat /etc/sensor/reconciler.json 2>/dev/null | grep -o '\"sensor_id\": *\"[^\"]*\"' | cut -d'\"' -f4 || cat /etc/machine-id 2>/dev/null || echo 'unknown'")
echo -e "  ✓ Device Hostname:  ${CYAN}${DEVICE_HOSTNAME}${NC}"
echo -e "  ✓ Sensor Identity:  ${CYAN}${SENSOR_UUID}${NC}"

if [[ "$MODE" == "--archive" ]]; then
    echo -e "\n${BLUE}[2/5] Creating Compressed Pre-Wipe State Archive...${NC}"
    ARCHIVE_TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    REMOTE_ARCHIVE="/tmp/one_offboard_${DEVICE_HOSTNAME}_${ARCHIVE_TIMESTAMP}.tar.gz"
    LOCAL_BACKUP_DIR="$(pwd)/backups/sensor_archives"
    mkdir -p "$LOCAL_BACKUP_DIR"

    run_ssh_stdin << REMOTE_ARCHIVE_SCRIPT
set -eu
sudo tar -czf "${REMOTE_ARCHIVE}" \
    /etc/sensor \
    /var/lib/sensor \
    /var/lib/node_exporter/textfile_collector \
    2>/dev/null || sudo tar -czf "${REMOTE_ARCHIVE}" -C /etc sensor 2>/dev/null || true
sudo chmod 0644 "${REMOTE_ARCHIVE}" 2>/dev/null || true
REMOTE_ARCHIVE_SCRIPT

    LOCAL_ARCHIVE_PATH="${LOCAL_BACKUP_DIR}/offboard_${DEVICE_HOSTNAME}_${ARCHIVE_TIMESTAMP}.tar.gz"
    if run_scp_download "${REMOTE_ARCHIVE}" "${LOCAL_ARCHIVE_PATH}"; then
        echo -e "  ✓ Remote archive transferred to: ${GREEN}${LOCAL_ARCHIVE_PATH}${NC}"
        SHA=$(sha256sum "${LOCAL_ARCHIVE_PATH}" | awk '{print $1}')
        echo -e "  ✓ Archive SHA256: ${CYAN}${SHA}${NC}"
    else
        echo -e "  ${YELLOW}⚠️ Notice: No existing sensor state found to archive.${NC}"
    fi
    run_ssh "sudo rm -f ${REMOTE_ARCHIVE} 2>/dev/null || true"
else
    echo -e "\n${BLUE}[2/5] Skipping Archive Phase (--wipe requested)...${NC}"
fi

echo -e "\n${BLUE}[3/5] Terminating Sensor Processes & De-registering Services...${NC}"
run_ssh_stdin << 'REMOTE_TEARDOWN_SERVICES'
set -eu
if systemctl list-unit-files | grep -q "sensor-reconciler.service"; then
    sudo systemctl stop sensor-reconciler.service 2>/dev/null || true
    sudo systemctl disable sensor-reconciler.service 2>/dev/null || true
    sudo rm -f /etc/systemd/system/sensor-reconciler.service
    sudo systemctl daemon-reload 2>/dev/null || true
    sudo systemctl reset-failed 2>/dev/null || true
    echo "  ✓ sensor-reconciler.service: STOPPED and REMOVED"
else
    echo "  • sensor-reconciler.service: Not registered (OK)"
fi

sudo pkill -9 -f "reconciler.py" 2>/dev/null || true
sudo pkill -9 -f "_probe.py" 2>/dev/null || true
sudo pkill -9 -f "evidence_collector.py" 2>/dev/null || true
sudo pkill -9 -f "pcap_trigger.py" 2>/dev/null || true
sudo pkill -9 -f "wifi_dhcp_exporter.py" 2>/dev/null || true
sudo pkill -9 -f "one-wizard" 2>/dev/null || true
echo "  ✓ Lingering prober processes: TERMINATED"
REMOTE_TEARDOWN_SERVICES

echo -e "\n${BLUE}[4/5] Tearing Down Docker Containers & Pruning Test Images...${NC}"
run_ssh_stdin << 'REMOTE_TEARDOWN_DOCKER'
set -eu
if command -v docker &>/dev/null; then
    RUNNER_CONTAINERS=$(sudo docker ps -aq --filter "name=browser-transaction-tester" 2>/dev/null || true)
    if [[ -n "$RUNNER_CONTAINERS" ]]; then
        sudo docker rm -f $RUNNER_CONTAINERS >/dev/null 2>&1 || true
        echo "  ✓ Removed active playwright-runner containers"
    fi
    if sudo docker images | grep -q "open-ux/playwright-runner"; then
        sudo docker rmi -f open-ux/playwright-runner:latest >/dev/null 2>&1 || true
        echo "  ✓ Removed open-ux/playwright-runner:latest Docker image"
    fi
    sudo docker volume prune -f >/dev/null 2>&1 || true
    echo "  ✓ Pruned Docker volumes"
else
    echo "  • Docker engine: Not present or already clean"
fi
REMOTE_TEARDOWN_DOCKER

echo -e "\n${BLUE}[5/5] Purging Filesystem Artifacts & Sensitive Configurations...${NC}"
run_ssh_stdin << 'REMOTE_TEARDOWN_FILESYSTEM'
set -eu
PROBE_BINARIES=(
    "reconciler.py"
    "wizard.py"
    "one-wizard"
    "cipa_compliance.py"
    "caaspp_readiness.py"
    "iperf3_runner.py"
    "wifi_dhcp_exporter.py"
    "rrm_darrp_monitor.py"
    "pcap_trigger.py"
    "evidence_collector.py"
    "segmentation_prober.py"
    "dns_multi_resolver_probe.py"
    "voip_jitter_probe.py"
    "custom_probe_runner.py"
    "gps_location_collector.py"
)
for bin in "${PROBE_BINARIES[@]}"; do
    sudo rm -f "/usr/local/bin/${bin}"
done
echo "  ✓ Purged 15 prober binaries from /usr/local/bin"

if [[ -f /etc/sensor/reconciler.json ]]; then
    if command -v shred &>/dev/null; then
        sudo shred -u -z -n 3 /etc/sensor/reconciler.json 2>/dev/null || sudo rm -f /etc/sensor/reconciler.json
    else
        sudo rm -f /etc/sensor/reconciler.json
    fi
    echo "  ✓ Securely shredded /etc/sensor/reconciler.json"
fi

sudo rm -rf /etc/sensor
sudo rm -rf /var/lib/sensor
sudo rm -f /var/lib/node_exporter/textfile_collector/*.prom 2>/dev/null || true
sudo rm -rf /tmp/sensor /tmp/*.prom /tmp/pcap_* 2>/dev/null || true
echo "  ✓ Removed state directories (/etc/sensor, /var/lib/sensor, /tmp/sensor)"

if [[ -f /etc/wpa_supplicant/wpa_supplicant.conf ]]; then
    if [[ -f /etc/wpa_supplicant/wpa_supplicant.conf.orig ]]; then
        sudo mv /etc/wpa_supplicant/wpa_supplicant.conf.orig /etc/wpa_supplicant/wpa_supplicant.conf
        echo "  ✓ Restored original wpa_supplicant.conf"
    fi
fi
REMOTE_TEARDOWN_FILESYSTEM

echo -e "\n${BLUE}Verifying Pre-Onboard Device Baseline...${NC}"
AUDIT_ERRORS=0

if run_ssh "systemctl is-active sensor-reconciler 2>/dev/null" | grep -q "active"; then
    echo -e "  ${RED}✗ Audit Failure: sensor-reconciler service is still active!${NC}" >&2
    AUDIT_ERRORS=$((AUDIT_ERRORS + 1))
else
    echo -e "  ✓ Service Status:      ${GREEN}INACTIVE / REMOVED${NC}"
fi

REMAINING_FILES=$(run_ssh "ls -d /usr/local/bin/reconciler.py /etc/sensor /var/lib/sensor 2>/dev/null || true")
if [[ -n "$REMAINING_FILES" ]]; then
    echo -e "  ${RED}✗ Audit Failure: Residual files detected: ${REMAINING_FILES}${NC}" >&2
    AUDIT_ERRORS=$((AUDIT_ERRORS + 1))
else
    echo -e "  ✓ Filesystem Residue:  ${GREEN}CLEAN (0 files found)${NC}"
fi

if run_ssh "command -v docker &>/dev/null && docker ps -q --filter 'name=browser-transaction-tester'" | grep -q "[0-9a-f]"; then
    echo -e "  ${RED}✗ Audit Failure: Docker test container still running!${NC}" >&2
    AUDIT_ERRORS=$((AUDIT_ERRORS + 1))
else
    echo -e "  ✓ Docker Containers:   ${GREEN}CLEAN (0 containers found)${NC}"
fi

echo ""
if [[ "$AUDIT_ERRORS" -eq 0 ]]; then
    echo -e "${CYAN}================================================================${NC}"
    echo -e "${GREEN}🎉 Offboarding Complete: Device '${DEVICE_HOSTNAME}' is in Pre-Onboard State!${NC}"
    echo -e "${CYAN}================================================================${NC}"
    exit 0
else
    echo -e "${RED}Offboarding Completed with ${AUDIT_ERRORS} warnings/errors. Manual audit recommended.${NC}" >&2
    exit 3
fi
