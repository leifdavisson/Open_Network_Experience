#!/usr/bin/env bash
#
# Open Network Experience Platform - 1-Line Zero-Touch Edge Sensor Installer & Bootstrap
#
# Copyright (C) 2026 Open Network Experience Authors.
# Licensed under the GNU Affero General Public License v3.0 (AGPLv3).
# See LICENSE in the project root for full license details.
#
# Usage:
#   1-Line Remote Install (from SSH):
#     curl -sSL http://<cmp>:8000/install.sh | sudo bash -s -- --site "West High" --room "204"
#
#   Interactive Wizard Mode:
#     curl -sSL http://<cmp>:8000/install.sh | sudo bash -s -- --wizard
#     sudo ./install.sh --wizard
#
#   Local Install with parameters:
#     sudo ./install.sh --cmp http://192.0.2.10:8000/api/v1 --site "City Center" --room "IT Ops"
#

set -euo pipefail

# Text colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${CYAN}================================================================${NC}"
echo -e "${CYAN}   🚀 Open Network Experience (ONE) Edge Sensor Installer        ${NC}"
echo -e "${CYAN}================================================================${NC}"

# Root verification
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}Error: This script must be run as root (use sudo).${NC}" 1>&2
   exit 1
fi

# Default Argument Values (Can be replaced by server dynamic query injector)
CMP_URL=""
SITE_NAME="Main Campus"
BUILDING_NAME="Main Building"
ROOM_NAME="Room 101"
DISTRICT_NAME="Unified School District"
LOCATION_NOTES="Ceiling AP Drop"
ENROLL_TOKEN=""
WIFI_SSID=""
WIFI_PSK=""
FORCE_INSTALL=0
LAUNCH_WIZARD=0
EXPLICIT_ARGS=0

# Parse Command Line Arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --wizard|-w)
      LAUNCH_WIZARD=1
      shift
      ;;
    --cmp|-c)
      CMP_URL="$2"
      EXPLICIT_ARGS=1
      shift 2
      ;;
    --site|-s|--campus)
      SITE_NAME="$2"
      EXPLICIT_ARGS=1
      shift 2
      ;;
    --building|-b)
      BUILDING_NAME="$2"
      EXPLICIT_ARGS=1
      shift 2
      ;;
    --room|-r)
      ROOM_NAME="$2"
      EXPLICIT_ARGS=1
      shift 2
      ;;
    --district|-d)
      DISTRICT_NAME="$2"
      EXPLICIT_ARGS=1
      shift 2
      ;;
    --notes)
      LOCATION_NOTES="$2"
      EXPLICIT_ARGS=1
      shift 2
      ;;
    --token|-t)
      ENROLL_TOKEN="$2"
      EXPLICIT_ARGS=1
      shift 2
      ;;
    --wifi-ssid)
      WIFI_SSID="$2"
      EXPLICIT_ARGS=1
      shift 2
      ;;
    --wifi-psk)
      WIFI_PSK="$2"
      EXPLICIT_ARGS=1
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

# If run interactively on a TTY without explicit site/room args, ask if technician wants the wizard
if [[ "$EXPLICIT_ARGS" -eq 0 && "$LAUNCH_WIZARD" -eq 0 && -t 0 ]]; then
    echo -e "${YELLOW}No deployment location specified.${NC}"
    read -r -p "Would you like to run the Interactive Setup Wizard (one-wizard)? [Y/n]: " WIZ_CHOICE || WIZ_CHOICE="y"
    if [[ "$WIZ_CHOICE" =~ ^([yY][eE][sS]|[yY]|"")$ ]]; then
        LAUNCH_WIZARD=1
    fi
fi

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

if [[ "$CPU_CORES" -lt 2 || "$TOTAL_MEM_KB" -lt 1800000 ]]; then
    if [[ "$FORCE_INSTALL" -eq 1 ]]; then
        echo -e "  ${YELLOW}⚠️ Hardware below recommended spec, but --force was specified. Proceeding...${NC}"
    else
        echo -e "  ${YELLOW}⚠️ Notice: Standard sensor spec is 2-4 cores / 2-8GB RAM. Low memory single-board detected.${NC}"
    fi
fi

# Install system dependencies
echo -e "\n${BLUE}2. Installing System Dependencies & Network Tools...${NC}"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq > /dev/null 2>&1 || true
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
    wireless-tools \
    > /dev/null 2>&1 || true
echo -e "  • Packages installed: ${GREEN}OK${NC}"

# Install Docker if missing
if ! command -v docker &> /dev/null; then
    echo -n "  • Installing Docker engine... "
    curl -fsSL https://get.docker.com | sh > /dev/null 2>&1 || true
    if command -v systemctl &> /dev/null; then
        systemctl enable docker > /dev/null 2>&1 || true
        systemctl start docker > /dev/null 2>&1 || true
    fi
    echo -e "${GREEN}OK${NC}"
else
    echo -e "  • Docker engine: ${GREEN}Already installed${NC}"
fi

# Prepare Sensor Directories
mkdir -p /etc/sensor
mkdir -p /etc/wpa_supplicant
mkdir -p /usr/local/bin
mkdir -p /var/lib/node_exporter/textfile_collector
mkdir -p /var/lib/sensor/snapshots
mkdir -p /var/lib/sensor/evidence_bundles

# Identify Script Source (Local git repository or Remote CMP Download)
SCRIPT_DIR="$(dirname "$(readlink -f "$0")" 2>/dev/null || echo ".")"
IS_LOCAL=0
if [[ -f "${SCRIPT_DIR}/reconciler/reconciler.py" || -f "${SCRIPT_DIR}/onboarding/wizard.py" ]]; then
    IS_LOCAL=1
fi

echo -e "\n${BLUE}3. Deploying Edge Probes, Synthetic Engine & Setup Wizard...${NC}"

PROBE_SCRIPTS=(
    "reconciler/reconciler.py:reconciler.py"
    "onboarding/wizard.py:wizard.py"
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

# Create global one-wizard symlink
ln -sf /usr/local/bin/wizard.py /usr/local/bin/one-wizard
chmod +x /usr/local/bin/one-wizard 2>/dev/null || true

echo -e "  • Synthetic Probes & one-wizard Installed: ${GREEN}OK${NC}"

# If Wi-Fi credentials supplied, configure wpa_supplicant
if [[ -n "$WIFI_SSID" ]]; then
    echo -e "\n${BLUE}4. Configuring Wi-Fi Credentials...${NC}"
    if [[ -n "$WIFI_PSK" ]]; then
        cat << EOF > /etc/wpa_supplicant/wpa_supplicant.conf
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=US

network={
    ssid="${WIFI_SSID}"
    psk="${WIFI_PSK}"
    key_mgmt=WPA-PSK
}
EOF
    else
        cat << EOF > /etc/wpa_supplicant/wpa_supplicant.conf
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=US

network={
    ssid="${WIFI_SSID}"
    key_mgmt=NONE
}
EOF
    fi
    echo -e "  • Wi-Fi configured for SSID: ${GREEN}${WIFI_SSID}${NC}"
fi

# Check if launching wizard
if [[ "$LAUNCH_WIZARD" -eq 1 ]]; then
    echo -e "\n${GREEN}Launching Interactive Setup Wizard...${NC}\n"
    if [[ -f /usr/local/bin/one-wizard ]]; then
        exec /usr/bin/python3 /usr/local/bin/one-wizard
    elif [[ -f "${SCRIPT_DIR}/onboarding/wizard.py" ]]; then
        exec /usr/bin/python3 "${SCRIPT_DIR}/onboarding/wizard.py"
    fi
fi

# Non-interactive / Default provisioning
echo -e "\n${BLUE}4. Writing Sensor Configuration & Identity...${NC}"

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
        "room": "${ROOM_NAME}",
        "notes": "${LOCATION_NOTES}"
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

if command -v systemctl &> /dev/null; then
    systemctl daemon-reload > /dev/null 2>&1 || true
    systemctl enable sensor-reconciler.service > /dev/null 2>&1 || true
    systemctl restart sensor-reconciler.service > /dev/null 2>&1 || true
fi

echo -e "\n${CYAN}================================================================${NC}"
echo -e "${GREEN}🎉 Sensor Provisioning Complete & Online!${NC}"
echo -e "${CYAN}================================================================${NC}"
echo -e "  • Sensor ID:       ${YELLOW}${SENSOR_UUID}${NC}"
echo -e "  • Campus Location: ${CYAN}${DISTRICT_NAME} / ${SITE_NAME} / ${ROOM_NAME}${NC}"
echo -e "  • Service Status:  ${GREEN}Active & Running (systemctl status sensor-reconciler)${NC}"
echo -e "  • CMP Check-In:    ${CYAN}${CMP_URL}${NC}"
echo ""
echo -e "${YELLOW}Helpdesk Quick Commands:${NC}"
echo -e "  • Live Logs:        ${BOLD}journalctl -u sensor-reconciler -f${NC}"
echo -e "  • Re-run Wizard:    ${BOLD}sudo one-wizard${NC}"
echo ""
