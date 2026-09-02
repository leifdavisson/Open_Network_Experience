#!/usr/bin/env bash
# Open Network Experience (ONE) - Developer Lab Bench Staging Tool
# NOTE: This script is exclusively a local developer harness for bench testing.
# Production multi-site rollouts use the pull-based Reconciler over HTTPS.
# Copyright (C) 2026 Open Network Experience Authors.
# Licensed under GNU AGPLv3.

set -euo pipefail

# 1. Load configuration from environment file if present
ENV_FILE="$(dirname "$0")/../.env"
if [[ -f "$ENV_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$ENV_FILE"
fi

CMP_HOST="${CMP_HOST:-}"
SENSOR_HOST="${SENSOR_HOST:-}"
SSH_USER="${SSH_USER:-}"
SSH_PASS="${SSH_PASS:-}"
ADMIN_API_KEY="${ADMIN_API_KEY:-admin-noc-key-change-me}"

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
        --help|-h)
            echo "Usage: $0 [--cmp <ip>] [--sensor <ip>] [--user <user>] [--pass <password>]"
            echo "Or define CMP_HOST, SENSOR_HOST, SSH_USER, SSH_PASS in .env"
            exit 0 ;;
        *)
            echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done

if [[ -z "${CMP_HOST}" || -z "${SENSOR_HOST}" || -z "${SSH_USER}" || -z "${SSH_PASS}" ]]; then
    echo "ERROR: Target parameters missing. Provide CLI flags (--cmp, --sensor, --user, --pass) or create a .env file (see .env.example)." >&2
    exit 1
fi

echo "========================================================"
echo "  ONE Lab Bench Staging Harness (Developer Tool Only)"
echo "  Target CMP Server : ${CMP_HOST}"
echo "  Target Test Sensor: ${SENSOR_HOST}"
echo "========================================================"

echo "=== 1. Running Local Test Suite & Incongruity Checks ==="
pytest -q "$(dirname "$0")/../server"

SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o PreferredAuthentications=password -o PubkeyAuthentication=no -o ConnectTimeout=15"
SSH_CMD="sshpass -p ${SSH_PASS} ssh ${SSH_OPTS}"
RSYNC_RSH="sshpass -p '${SSH_PASS}' ssh ${SSH_OPTS}"

echo "=== 2. Remote Architecture & Pre-Flight Validation ==="
CMP_ARCH=$(${SSH_CMD} "${SSH_USER}@${CMP_HOST}" "uname -m")
SENSOR_ARCH=$(${SSH_CMD} "${SSH_USER}@${SENSOR_HOST}" "uname -m")
echo " - CMP Server Architecture : ${CMP_ARCH}"
echo " - Edge Sensor Architecture: ${SENSOR_ARCH}"

echo "=== 3. Synchronizing CMP Server Core (Scoped Target Paths) ==="
rsync -avz \
    --exclude='.git' \
    --exclude='node_modules' \
    --exclude='__pycache__' \
    --exclude='.pytest_cache' \
    -e "${RSYNC_RSH}" \
    "$(dirname "$0")/../server/" "${SSH_USER}@${CMP_HOST}:/home/${SSH_USER}/Open_Network_Experience/server/"

rsync -avz \
    --exclude='.git' \
    --exclude='node_modules' \
    -e "${RSYNC_RSH}" \
    "$(dirname "$0")/../chromebook-sensor/" "${SSH_USER}@${CMP_HOST}:/home/${SSH_USER}/Open_Network_Experience/chromebook-sensor/"

echo "=== 4. Recreating CMP Control Plane Container ==="
# Ensure .env on CMP has correct values for SSH delegation and self-referencing probes
${SSH_CMD} "${SSH_USER}@${CMP_HOST}" \
    "cd /home/${SSH_USER}/Open_Network_Experience && \
     sed -i 's|^CMP_HOST=.*|CMP_HOST=${CMP_HOST}|g' .env 2>/dev/null || echo 'CMP_HOST=${CMP_HOST}' >> .env; \
     sed -i 's|^SSH_USER=.*|SSH_USER=${SSH_USER}|g' .env 2>/dev/null || echo 'SSH_USER=${SSH_USER}' >> .env; \
     sed -i 's|^SSH_PASS=.*|SSH_PASS=${SSH_PASS}|g' .env 2>/dev/null || echo 'SSH_PASS=${SSH_PASS}' >> .env; \
     sed -i 's|^SENSOR_HOST=.*|SENSOR_HOST=${SENSOR_HOST}|g' .env 2>/dev/null || echo 'SENSOR_HOST=${SENSOR_HOST}' >> .env"
${SSH_CMD} "${SSH_USER}@${CMP_HOST}" \
    "cd /home/${SSH_USER}/Open_Network_Experience/server/deploy && docker compose up -d --build --force-recreate cmp-server"

echo "=== 5. Updating Test Sensor Probe Scripts (${SENSOR_HOST}) ==="
rsync -avz \
    --exclude='__pycache__' \
    --exclude='*.prom' \
    -e "${RSYNC_RSH}" \
    "$(dirname "$0")/../sensor/" \
    "${SSH_USER}@${SENSOR_HOST}:/tmp/sensor/"

${SSH_CMD} "${SSH_USER}@${SENSOR_HOST}" \
    "echo '${SSH_PASS}' | sudo -S cp /tmp/sensor/*.py /usr/local/bin/ 2>/dev/null || true && \
     echo '${SSH_PASS}' | sudo -S cp /tmp/sensor/reconciler/reconciler.py /usr/local/bin/ 2>/dev/null || true && \
     echo '${SSH_PASS}' | sudo -S systemctl restart sensor-reconciler"

echo "=== 6. End-to-End Live Health Smoke Test ==="
echo -n " - Checking CMP Web UI (http://${CMP_HOST}:8000)... "
curl -sf -o /dev/null "http://${CMP_HOST}:8000/" && echo "✓ OK" || echo "✗ FAIL"

echo -n " - Checking Live Diagnostics API on CMP... "
# Retrieve the first approved sensor ID registered on the CMP (bench sensor registers via reconciler)
SENSOR_ID=$(curl -sf -H "X-API-Key: ${ADMIN_API_KEY}" \
    "http://${CMP_HOST}:8000/api/v1/sensors" 2>/dev/null | \
    python3 -c "import sys,json; d=json.load(sys.stdin); ids=[s['sensor_id'] for s in d if s.get('status')=='approved']; print(ids[0] if ids else '')" 2>/dev/null)
if [[ -z "$SENSOR_ID" ]]; then
    echo "⚠ SKIP (no approved sensors found — run reconciler or seed DB)"
else
    RESP=$(curl -sf -X POST -H 'Content-Type: application/json' -H "X-API-Key: ${ADMIN_API_KEY}" \
        -d '{"test_type": "dns"}' "http://${CMP_HOST}:8000/api/v1/sensors/${SENSOR_ID}/diagnostics/run")
    if [[ "$RESP" == *"\"status\":\"PASS\""* ]]; then
        echo "✓ PASS (sensor: ${SENSOR_ID})"
    else
        echo "✗ FAIL: $RESP"
    fi
fi

echo -n " - Checking VictoriaMetrics TSDB (http://${CMP_HOST}:8428)... "
curl -sf "http://${CMP_HOST}:8428/api/v1/query?query=cipa_compliance_status" | grep -q "result" && echo "✓ OK" || echo "✗ FAIL"

echo -n " - Checking Sensor Metrics (http://${SENSOR_HOST}:9100)... "
curl -sf "http://${SENSOR_HOST}:9100/metrics" | grep -q "wifi_rrm_rssi_dbm" && echo "✓ OK" || echo "✗ FAIL"

echo "=== Bench Staging & Verification Complete ==="
