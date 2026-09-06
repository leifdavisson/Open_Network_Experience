#!/usr/bin/env bash
# Open Network Experience (ONE) - Developer Lab Bench Reset & Cleanup Tool
# Cleans up test bench computers: wipes test containers, databases, and edge sensor probe scripts.
#
# Copyright (C) 2026 Open Network Experience Authors.
# Licensed under GNU AGPLv3.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# 1. Load configuration from environment file if present
ENV_FILE="${ROOT_DIR}/.env"
if [[ -f "$ENV_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$ENV_FILE"
fi

CMP_HOST="${CMP_HOST:-}"
SENSOR_HOST="${SENSOR_HOST:-}"
SSH_USER="${SSH_USER:-}"
SSH_PASS="${SSH_PASS:-}"
LOCAL_ONLY=0
RESTART_CMP=1

# Parse optional CLI overrides
while [[ $# -gt 0 ]]; do
    case "$1" in
        --cmp)
            CMP_HOST="$2"; shift 2 ;;
        --sensor)
            SENSOR_HOST="$2"; shift 2 ;;
        --user)
            SSH_USER="$2"; shift 2 ;;
        --pass)
            SSH_PASS="$2"; shift 2 ;;
        --local-only)
            LOCAL_ONLY=1; shift ;;
        --no-restart-cmp)
            RESTART_CMP=0; shift ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --cmp <ip>         Target CMP Server IP / Hostname"
            echo "  --sensor <ip>      Target Test Sensor IP / Hostname"
            echo "  --user <user>      SSH Username for bench machines"
            echo "  --pass <password>  SSH Password for bench machines"
            echo "  --local-only       Only reset local CMP Docker environment"
            echo "  --no-restart-cmp   Do not start CMP containers back up after reset"
            echo "  --help, -h         Show this help message"
            echo ""
            echo "Configuration can also be set via .env (see .env.example)."
            exit 0 ;;
        *)
            echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done

echo "========================================================"
echo "  ONE Lab Bench Reset & Cleanup Harness"
echo "========================================================"

# Check if running local-only reset
if [[ "$LOCAL_ONLY" -eq 1 || ( -z "${CMP_HOST}" && -z "${SENSOR_HOST}" ) ]]; then
    echo "Operating in local CMP reset mode..."
    "${ROOT_DIR}/server/deploy/bench_reset.sh"
    exit 0
fi

if [[ -z "${SSH_USER}" || -z "${SSH_PASS}" ]]; then
    echo "ERROR: SSH credentials missing. Provide --user and --pass CLI flags or set SSH_USER/SSH_PASS in .env" >&2
    exit 1
fi

SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o PreferredAuthentications=password -o PubkeyAuthentication=no -o ConnectTimeout=15"
SSH_CMD="sshpass -p ${SSH_PASS} ssh ${SSH_OPTS}"

# ─────────────────────────────────────────────────────────
# 1. Reset Remote CMP Server
# ─────────────────────────────────────────────────────────
if [[ -n "${CMP_HOST}" ]]; then
    echo ""
    echo "=== 1. Cleaning CMP Server (${CMP_HOST}) ==="
    echo " - Checking SSH connectivity..."
    if ${SSH_CMD} "${SSH_USER}@${CMP_HOST}" "echo connected" &>/dev/null; then
        echo "   ✓ Connected to ${CMP_HOST}"

        echo " - Tearing down Docker Compose containers & volumes..."
        ${SSH_CMD} "${SSH_USER}@${CMP_HOST}" \
            "cd /home/${SSH_USER}/Open_Network_Experience/server/deploy 2>/dev/null && \
             (docker compose down -v 2>/dev/null || docker-compose down -v 2>/dev/null || true)"

        echo " - Removing SQLite database files and persistent volume data..."
        ${SSH_CMD} "${SSH_USER}@${CMP_HOST}" \
            "rm -rf /home/${SSH_USER}/Open_Network_Experience/server/data/* 2>/dev/null || true"

        if [[ "$RESTART_CMP" -eq 1 ]]; then
            echo " - Spinning clean CMP containers back up..."
            ${SSH_CMD} "${SSH_USER}@${CMP_HOST}" \
                "cd /home/${SSH_USER}/Open_Network_Experience/server/deploy && \
                 (docker compose up -d 2>/dev/null || docker-compose up -d 2>/dev/null || true)"
        fi
        echo "   ✓ CMP Server reset complete."
    else
        echo "   ✗ Could not reach CMP Server at ${CMP_HOST}. Skipping."
    fi
fi

# ─────────────────────────────────────────────────────────
# 2. Reset Remote Test Sensor
# ─────────────────────────────────────────────────────────
if [[ -n "${SENSOR_HOST}" ]]; then
    echo ""
    echo "=== 2. Cleaning Test Sensor Appliance (${SENSOR_HOST}) ==="
    echo " - Checking SSH connectivity..."
    if ${SSH_CMD} "${SSH_USER}@${SENSOR_HOST}" "echo connected" &>/dev/null; then
        echo "   ✓ Connected to ${SENSOR_HOST}"

        echo " - Stopping and disabling sensor-reconciler systemd service..."
        ${SSH_CMD} "${SSH_USER}@${SENSOR_HOST}" \
            "echo '${SSH_PASS}' | sudo -S systemctl stop sensor-reconciler 2>/dev/null || true && \
             echo '${SSH_PASS}' | sudo -S systemctl disable sensor-reconciler 2>/dev/null || true"

        echo " - Terminating any remaining python probers..."
        ${SSH_CMD} "${SSH_USER}@${SENSOR_HOST}" \
            "echo '${SSH_PASS}' | sudo -S pkill -f 'reconciler.py' 2>/dev/null || true; \
             echo '${SSH_PASS}' | sudo -S pkill -f '_probe.py' 2>/dev/null || true"

        echo " - Removing deployed synthetic probe scripts from /usr/local/bin..."
        ${SSH_CMD} "${SSH_USER}@${SENSOR_HOST}" \
            "echo '${SSH_PASS}' | sudo -S rm -f \
                /usr/local/bin/reconciler.py \
                /usr/local/bin/wizard.py \
                /usr/local/bin/one-wizard \
                /usr/local/bin/cipa_compliance.py \
                /usr/local/bin/caaspp_readiness.py \
                /usr/local/bin/iperf3_runner.py \
                /usr/local/bin/wifi_dhcp_exporter.py \
                /usr/local/bin/rrm_darrp_monitor.py \
                /usr/local/bin/pcap_trigger.py \
                /usr/local/bin/evidence_collector.py \
                /usr/local/bin/segmentation_prober.py \
                /usr/local/bin/dns_multi_resolver_probe.py \
                /usr/local/bin/voip_jitter_probe.py \
                /usr/local/bin/custom_probe_runner.py \
                /usr/local/bin/gps_location_collector.py"

        echo " - Cleaning temporary staging files and sensor caches..."
        ${SSH_CMD} "${SSH_USER}@${SENSOR_HOST}" \
            "echo '${SSH_PASS}' | sudo -S rm -rf /tmp/sensor /tmp/*.prom /var/lib/sensor/* 2>/dev/null || true && \
             echo '${SSH_PASS}' | sudo -S rm -f /var/lib/node_exporter/textfile_collector/*.prom 2>/dev/null || true"

        echo " - Resetting sensor registration config (/etc/sensor/reconciler.json)..."
        ${SSH_CMD} "${SSH_USER}@${SENSOR_HOST}" \
            "echo '${SSH_PASS}' | sudo -S rm -f /etc/sensor/reconciler.json 2>/dev/null || true"

        echo " - Pruning Docker test containers and volumes on sensor..."
        ${SSH_CMD} "${SSH_USER}@${SENSOR_HOST}" \
            "if command -v docker &>/dev/null; then \
                echo '${SSH_PASS}' | sudo -S docker system prune -af --volumes 2>/dev/null || true; \
             fi"

        echo "   ✓ Test Sensor cleanup complete."
    else
        echo "   ✗ Could not reach Sensor at ${SENSOR_HOST}. Skipping."
    fi
fi

echo ""
echo "========================================================"
echo "  Lab Bench Computers Cleanup Finished"
echo "========================================================"
