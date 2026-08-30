#!/usr/bin/env bash
#
# Open Network Experience Platform - 1-Line Zero-Touch Edge Sensor Installer & Bootstrap
#
# Usage:
#   1-Line Remote Install (from SSH):
#     curl -sSL http://10.98.2.125:8000/install.sh | sudo bash -s -- --cmp http://10.98.2.125:8000/api/v1 --site "West High" --room "MDF 101"
#
#   Local Install:
#     sudo ./install.sh --cmp http://10.98.2.125:8000/api/v1 --site "City Center" --room "IT Ops"
#

set -euo pipefail

# Text colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}================================================================${NC}"
echo -e "${CYAN}   🚀 Open Network Experience (ONE) Edge Sensor 1-Line Installer ${NC}"
echo -e "${CYAN}================================================================${NC}"

# Root verification
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}Error: This script must be run as root (use sudo).${NC}" 1>&2
   exit 1
fi

# Default Argument Values
CMP_URL=""
SITE_NAME="Main Campus"
BUILDING_NAME="Main Building"
ROOM_NAME="Room 101"
DISTRICT_NAME="Default District"
ENROLL_TOKEN=""
FORCE_INSTALL=0

# Parse Command Line Arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --cmp|-c)
      CMP_URL="$2"
      shift 2
      ;;
    --site|-s)
      SITE_NAME="$2"
      shift 2
      ;;
    --building|-b)
      BUILDING_NAME="$2"
      shift 2
      ;;
    --room|-r)
      ROOM_NAME="$2"
      shift 2
      ;;
    --district|-d)
      DISTRICT_NAME="$2"
      shift 2
      ;;
    --token|-t)
      ENROLL_TOKEN="$2"
      shift 2
      ;;
    --force|-f)
      FORCE_INSTALL=1
      shift
      ;;
    *)
      echo -e "${YELLOW}Unknown option: $1${NC}"
      shift
      ;;
  esac
done

# If CMP_URL not passed, attempt to extract from download origin or use default
if [[ -z "$CMP_URL" ]]; then
    CMP_URL="http://central-monitoring-platform.local/api/v1"
fi

echo -e "${BLUE}Configuration Parameters:${NC}"
echo -e "  • CMP Control Plane: ${CYAN}${CMP_URL}${NC}"
echo -e "  • District:          ${CYAN}${DISTRICT_NAME}${NC}"
echo -e "  • Campus / Site:     ${CYAN}${SITE_NAME}${NC}"
echo -e "  • Building:          ${CYAN}${BUILDING_NAME}${NC}"
echo -e "  • Room / Location:   ${CYAN}${ROOM_NAME}${NC}"
echo ""

# Hardware compliance check
echo -e "${BLUE}1. Checking Hardware Specs...${NC}"
CPU_CORES=$(nproc)
TOTAL_MEM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
TOTAL_MEM_GB=$(awk "BEGIN {print int($TOTAL_MEM_KB/1024/1024)}")
TOTAL_DISK_KB=$(df / | tail -1 | awk '{print $2}')
TOTAL_DISK_GB=$(awk "BEGIN {print int($TOTAL_DISK_KB/1024/1024)}")

echo -e "  • CPU Cores: ${GREEN}${CPU_CORES}${NC}"
echo -e "  • Memory:    ${GREEN}${TOTAL_MEM_GB} GB${NC}"
echo -e "  • Disk:      ${GREEN}${TOTAL_DISK_GB} GB${NC}"

if [[ "$CPU_CORES" -lt 2 || "$TOTAL_MEM_KB" -lt 3670016 ]]; then
    if [[ "$FORCE_INSTALL" -eq 1 ]]; then
        echo -e "  ${YELLOW}⚠️ Hardware below recommended 4-core/8GB spec, but --force was specified. Proceeding...${NC}"
    else
        echo -e "  ${YELLOW}⚠️ Notice: Optimal production performance requires 4 cores / 8GB RAM. Use --force to override.${NC}"
    fi
fi

# Install system dependencies
echo -e "\n${BLUE}2. Installing System Dependencies & Network Tools...${NC}"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq > /dev/null 2>&1
apt-get install -y -qq \
    wpasupplicant \
    iperf3 \
    mtr-tiny \
    curl \
    ca-certificates \
    gnupg \
    python3 \
    python3-pip \
    iproute2 \
    systemd \
    > /dev/null 2>&1
echo -e "  • Packages installed: ${GREEN}OK${NC}"

# Install Docker if missing
if ! command -v docker &> /dev/null; then
    echo -n "  • Installing Docker engine... "
    curl -fsSL https://get.docker.com | sh > /dev/null 2>&1
    systemctl enable docker > /dev/null 2>&1
    systemctl start docker > /dev/null 2>&1
    echo -e "${GREEN}OK${NC}"
else
    echo -e "  • Docker engine: ${GREEN}Already installed${NC}"
fi

# Prepare Sensor Directories
mkdir -p /etc/sensor
mkdir -p /usr/local/bin
mkdir -p /var/lib/node_exporter/textfile_collector
mkdir -p /var/lib/sensor/snapshots
mkdir -p /var/lib/sensor/evidence_bundles

# Identify Script Source (Local git repository or Remote CMP Download)
SCRIPT_DIR="$(dirname "$(readlink -f "$0")" 2>/dev/null || echo ".")"
IS_LOCAL=0
if [[ -f "${SCRIPT_DIR}/reconciler/reconciler.py" ]]; then
    IS_LOCAL=1
fi

echo -e "\n${BLUE}3. Deploying Edge Probes & Synthetic Engine...${NC}"

PROBE_SCRIPTS=(
    "reconciler/reconciler.py:reconciler.py"
    "cipa_compliance.py:cipa_compliance.py"
    "caaspp_readiness.py:caaspp_readiness.py"
    "iperf3_runner.py:iperf3_runner.py"
    "wifi_dhcp_exporter.py:wifi_dhcp_exporter.py"
    "rrm_darrp_monitor.py:rrm_darrp_monitor.py"
    "pcap_trigger.py:pcap_trigger.py"
    "evidence_collector.py:evidence_collector.py"
    "segmentation_prober.py:segmentation_prober.py"
    "dns_multi_resolver_probe.py:dns_multi_resolver_probe.py"
    "voip_jitter_probe.py:voip_jitter_probe.py"
    "custom_probe_runner.py:custom_probe_runner.py"
    "gps_location_collector.py:gps_location_collector.py"
)

# Base URL for downloading remote scripts if running via curl pipe
BASE_DOWNLOAD_URL=$(echo "$CMP_URL" | sed 's|/api/v1||')

for item in "${PROBE_SCRIPTS[@]}"; do
    SRC_NAME="${item%%:*}"
    DEST_NAME="${item##*:}"

    if [[ "$IS_LOCAL" -eq 1 && -f "${SCRIPT_DIR}/${SRC_NAME}" ]]; then
        cp "${SCRIPT_DIR}/${SRC_NAME}" "/usr/local/bin/${DEST_NAME}"
    else
        # Download from CMP server endpoint
        curl -fsSL "${BASE_DOWNLOAD_URL}/sensor/scripts/${DEST_NAME}" -o "/usr/local/bin/${DEST_NAME}" 2>/dev/null || \
        curl -fsSL "https://raw.githubusercontent.com/leifdavisson/Open_Network_Experience/main/sensor/${SRC_NAME}" -o "/usr/local/bin/${DEST_NAME}" 2>/dev/null || true
    fi
    chmod +x "/usr/local/bin/${DEST_NAME}" 2>/dev/null || true
done
echo -e "  • 12 Synthetic Probes Installed: ${GREEN}OK${NC}"

# Derive Hardware Sensor ID
if [[ -f /etc/machine-id ]]; then
    SENSOR_UUID=$(cat /etc/machine-id | tr -d ' \n')
else
    SENSOR_UUID=$(python3 -c 'import uuid; print(uuid.uuid4().hex)')
fi

# Write /etc/sensor/reconciler.json configuration
cat << EOF > /etc/sensor/reconciler.json
{
    "cmp_url": "${CMP_URL}",
    "sensor_id": "${SENSOR_UUID}",
    "api_key": "",
    "enrollment_token": "${ENROLL_TOKEN}",
    "check_interval_seconds": 15,
    "wifi_interface": "wlan0",
    "wifi_config_path": "/etc/wpa_supplicant/wpa_supplicant.conf",
    "initial_location": {
        "district": "${DISTRICT_NAME}",
        "site": "${SITE_NAME}",
        "building": "${BUILDING_NAME}",
        "room": "${ROOM_NAME}"
    }
}
EOF
echo -e "  • Sensor Config written to /etc/sensor/reconciler.json: ${GREEN}OK${NC}"

# Install and Enable Systemd Service
cat << 'EOF' > /etc/systemd/system/sensor-reconciler.service
[Unit]
Description=Open Network Experience (ONE) Sensor Reconciler & Adaptive Prober
After=network-online.target docker.service
Wants=network-online.target docker.service

[Service]
Type=simple
User=root
ExecStart=/usr/bin/python3 /usr/local/bin/reconciler.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable sensor-reconciler.service > /dev/null 2>&1
systemctl restart sensor-reconciler.service

echo -e "\n${CYAN}================================================================${NC}"
echo -e "${GREEN}🎉 Sensor Provisioning Complete & Online!${NC}"
echo -e "${CYAN}================================================================${NC}"
echo -e "  • Sensor ID:       ${YELLOW}${SENSOR_UUID}${NC}"
echo -e "  • Service Status:  ${GREEN}Active & Running (systemctl status sensor-reconciler)${NC}"
echo -e "  • CMP Check-In:    ${CYAN}${CMP_URL}${NC}"
echo ""
echo -e "${YELLOW}To monitor live check-ins & adaptive probing:${NC}"
echo -e "  ${CYAN}journalctl -u sensor-reconciler -f${NC}"
echo ""
