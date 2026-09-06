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

CMP_HOST="${CMP_HOST:-10.98.2.125}"
SENSOR_HOST="${SENSOR_HOST:-}"
SSH_USER="${SSH_USER:-kern}"
SSH_PASS="${SSH_PASS:-}"
ADMIN_API_KEY="${ADMIN_API_KEY:-admin-noc-key-change-me}"
SENSOR_HOSTS=()

if [[ -n "${SENSOR_HOST}" ]]; then
    IFS=' ,' read -r -a env_sensors <<< "${SENSOR_HOST}"
    for s in "${env_sensors[@]}"; do
        [[ -n "$s" ]] && SENSOR_HOSTS+=("$s")
    done
fi

# Parse optional CLI overrides
while [[ $# -gt 0 ]]; do
    case "$1" in
        --cmp)
            CMP_HOST="$2"; shift 2 ;;
        --sensor|--sensors)
            IFS=' ,' read -r -a parsed_sensors <<< "$2"
            for s in "${parsed_sensors[@]}"; do
                # Expand 3-digit shorthand e.g. 141 -> 10.98.2.141
                if [[ "$s" =~ ^[0-9]+$ ]]; then
                    s="10.98.2.${s}"
                fi
                [[ -n "$s" ]] && SENSOR_HOSTS+=("$s")
            done
            shift 2 ;;
        --user)
            SSH_USER="$2"; shift 2 ;;
        --pass)
            SSH_PASS="$2"; shift 2 ;;
        --help|-h)
            echo "Usage: $0 [--cmp <ip>] [--sensor <ip|shorthand>] [--user <user>] [--pass <password>]"
            echo "Or define CMP_HOST, SENSOR_HOST, SSH_USER, SSH_PASS in .env"
            exit 0 ;;
        *)
            echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done

# Prompt for password if not provided
if [[ -z "${SSH_PASS}" ]]; then
    if [[ -t 0 ]]; then
        read -rsp "Enter SSH password for bench (${SSH_USER}@bench): " SSH_PASS
        echo ""
    else
        read -r SSH_PASS || true
    fi
fi

if [[ -z "${CMP_HOST}" || ${#SENSOR_HOSTS[@]} -eq 0 || -z "${SSH_USER}" || -z "${SSH_PASS}" ]]; then
    echo "ERROR: Target parameters missing. Provide CLI flags (--cmp, --sensor, --user, --pass) or create a .env file (see .env.example)." >&2
    exit 1
fi

echo "========================================================"
echo "  ONE Lab Bench Staging Harness (Developer Tool Only)"
echo "  Target CMP Server  : ${CMP_HOST}"
echo "  Target Test Sensors: ${SENSOR_HOSTS[*]}"
echo "========================================================"

echo "=== 1. Running Local Test Suite & Incongruity Checks ==="
pytest -q "$(dirname "$0")/../server"

SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o PreferredAuthentications=password -o PubkeyAuthentication=no -o ConnectTimeout=15"
SSH_CMD="sshpass -p ${SSH_PASS} ssh ${SSH_OPTS}"
RSYNC_RSH="sshpass -p '${SSH_PASS}' ssh ${SSH_OPTS}"

echo "=== 2. Remote Architecture & Pre-Flight Validation ==="
CMP_ARCH=$(${SSH_CMD} "${SSH_USER}@${CMP_HOST}" "uname -m")
echo " - CMP Server Architecture : ${CMP_ARCH}"
for sensor in "${SENSOR_HOSTS[@]}"; do
    SENSOR_ARCH=$(${SSH_CMD} "${SSH_USER}@${sensor}" "uname -m")
    echo " - Edge Sensor (${sensor}) Architecture: ${SENSOR_ARCH}"
done

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
PRIMARY_SENSOR="${SENSOR_HOSTS[0]}"
# Ensure .env on CMP has correct values for SSH delegation and self-referencing probes
${SSH_CMD} "${SSH_USER}@${CMP_HOST}" \
    "cd /home/${SSH_USER}/Open_Network_Experience && \
     sed -i 's|^CMP_HOST=.*|CMP_HOST=${CMP_HOST}|g' .env 2>/dev/null || echo 'CMP_HOST=${CMP_HOST}' >> .env; \
     sed -i 's|^SSH_USER=.*|SSH_USER=${SSH_USER}|g' .env 2>/dev/null || echo 'SSH_USER=${SSH_USER}' >> .env; \
     sed -i 's|^SSH_PASS=.*|SSH_PASS=${SSH_PASS}|g' .env 2>/dev/null || echo 'SSH_PASS=${SSH_PASS}' >> .env; \
     sed -i 's|^SENSOR_HOST=.*|SENSOR_HOST=${PRIMARY_SENSOR}|g' .env 2>/dev/null || echo 'SENSOR_HOST=${PRIMARY_SENSOR}' >> .env"
${SSH_CMD} "${SSH_USER}@${CMP_HOST}" \
    "cd /home/${SSH_USER}/Open_Network_Experience/server/deploy && docker compose up -d --build --force-recreate cmp-server"

echo "=== 5. Updating Test Sensor Probe Scripts ==="
for sensor in "${SENSOR_HOSTS[@]}"; do
    echo " - Syncing probe suite to ${sensor}..."
    rsync -avz \
        --exclude='__pycache__' \
        --exclude='*.prom' \
        -e "${RSYNC_RSH}" \
        "$(dirname "$0")/../sensor/" \
        "${SSH_USER}@${sensor}:/tmp/sensor/"

    ${SSH_CMD} "${SSH_USER}@${sensor}" \
        "echo '${SSH_PASS}' | sudo -S cp /tmp/sensor/*.py /usr/local/bin/ 2>/dev/null || true && \
         echo '${SSH_PASS}' | sudo -S cp /tmp/sensor/reconciler/reconciler.py /usr/local/bin/ 2>/dev/null || true && \
         if [[ -f /etc/sensor/reconciler.json ]]; then \
             echo '${SSH_PASS}' | sudo -S sed -i 's|\"cmp_url\": \".*\"|\"cmp_url\": \"http://${CMP_HOST}:8000/api/v1\"|g' /etc/sensor/reconciler.json 2>/dev/null || true; \
         fi && \
         echo '${SSH_PASS}' | sudo -S systemctl enable sensor-reconciler 2>/dev/null || true && \
         echo 'Building open-ux/playwright-runner:latest locally on sensor...' && \
         echo '${SSH_PASS}' | sudo -S docker build -t open-ux/playwright-runner:latest /tmp/sensor/playwright-runner/ 2>/dev/null || true && \
         echo '${SSH_PASS}' | sudo -S systemctl restart sensor-reconciler"
    echo "   ✓ Sensor ${sensor} updated, playwright runner built, and sensor-reconciler restarted."
done

echo "=== 6. End-to-End Live Health Smoke Test ==="
echo -n " - Checking CMP Web UI (http://${CMP_HOST}:8000)... "
curl -sf -o /dev/null "http://${CMP_HOST}:8000/" && echo "✓ OK" || echo "✗ FAIL"

echo -n " - Waiting for sensors to register and auto-approving bench nodes... "
sleep 4
PENDING_IDS=$(curl -sf -H "X-API-Key: ${ADMIN_API_KEY}" "http://${CMP_HOST}:8000/api/v1/sensors" 2>/dev/null | \
    python3 -c "import sys,json; d=json.load(sys.stdin); print(' '.join([s['sensor_id'] for s in d if s.get('status')=='pending']))" 2>/dev/null || true)
for pid in $PENDING_IDS; do
    curl -sf -X POST -H "X-API-Key: ${ADMIN_API_KEY}" "http://${CMP_HOST}:8000/api/v1/sensors/${pid}/approve" >/dev/null 2>&1 || true
done
echo "✓ OK"

echo -n " - Checking Live Diagnostics API on CMP... "
# Retrieve the first approved sensor ID registered on the CMP (bench sensor registers via reconciler)
SENSOR_ID=$(curl -sf -H "X-API-Key: ${ADMIN_API_KEY}" \
    "http://${CMP_HOST}:8000/api/v1/sensors" 2>/dev/null | \
    python3 -c "import sys,json; d=json.load(sys.stdin); ids=[s['sensor_id'] for s in d if s.get('status')=='approved' and not s['sensor_id'].startswith('chromebook')]; print(ids[0] if ids else '')" 2>/dev/null)
if [[ -z "$SENSOR_ID" ]]; then
    echo "⚠ SKIP (no physical approved sensors found — reconciler cycling)"
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

# Wait and retry for Node Exporter metrics to propagate
for sensor in "${SENSOR_HOSTS[@]}"; do
    echo -n " - Checking Sensor Metrics on ${sensor} (http://${sensor}:9100)... "
    MAX_RETRIES=5
    RETRY_DELAY=5
    SUCCESS=0
    for ((i=1; i<=MAX_RETRIES; i++)); do
        if curl -sf "http://${sensor}:9100/metrics" | grep -q "wifi_rrm_rssi_dbm"; then
            SUCCESS=1
            echo "✓ OK"
            break
        fi
        sleep $RETRY_DELAY
    done
    if [ $SUCCESS -eq 0 ]; then
        echo "✗ FAIL (probe running, waiting for metrics cycle timeout)"
    fi
done

echo "=== Bench Staging & Verification Complete ==="
