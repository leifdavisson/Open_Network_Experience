#!/usr/bin/env bash
#
# Open Network Experience Platform - Edge Sensor Installer
#
# 1. Enforces minimum hardware compliance (Linux, 4+ cores, 8GB+ RAM, 32GB+ storage).
# 2. Installs system network tools (wpasupplicant, iperf3, mtr-tiny, python3, docker).
# 3. Provisions Sensor Reconciler agent & systemd service (/usr/local/bin/reconciler.py).
# 4. Provisions CIPA Compliance probe (/usr/local/bin/cipa_compliance.py).
# 5. Configures directories for Node Exporter textfile collector metrics.
#

set -euo pipefail

# Text colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}===============================================${NC}"
echo -e "${BLUE}    Open UX Platform Sensor Installer          ${NC}"
echo -e "${BLUE}===============================================${NC}"

# Root verification
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}Error: This script must be run as root.${NC}" 1>&2
   exit 1
fi

# Flag to track initialization block status
BLOCKED=0

# 1. OS Check
echo -n "Checking OS Compatibility... "
OS_TYPE=$(uname -s)
if [[ "$OS_TYPE" != "Linux" ]]; then
    echo -e "${RED}FAILED${NC}"
    echo -e "  -> OS type is $OS_TYPE. Only Linux is supported."
    BLOCKED=1
else
    echo -e "${GREEN}OK (Linux)${NC}"
fi

# 2. CPU Core Check
echo -n "Checking CPU Cores... "
CPU_CORES=$(nproc)
if [[ "$CPU_CORES" -lt 4 ]]; then
    echo -e "${RED}FAILED${NC}"
    echo -e "  -> Detected $CPU_CORES CPU cores. Minimum requirement is 4 cores."
    BLOCKED=1
else
    echo -e "${GREEN}OK ($CPU_CORES cores)${NC}"
fi

# 3. RAM Check
echo -n "Checking Memory (RAM)... "
# Get total memory in KB
TOTAL_MEM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
# Convert to GB (roughly)
TOTAL_MEM_GB=$(echo "scale=1; $TOTAL_MEM_KB / 1024 / 1024" | bc 2>/dev/null || awk "BEGIN {print $TOTAL_MEM_KB/1024/1024}")

# 8GB minimum target is ~8388608 KB. We allow a buffer down to 7.0 GB for GPU memory reservations (e.g. Pi 5)
if [[ "$TOTAL_MEM_KB" -lt 7340032 ]]; then
    echo -e "${RED}FAILED${NC}"
    echo -e "  -> Detected ${TOTAL_MEM_GB} GB RAM. Minimum requirement is 8 GB."
    BLOCKED=1
else
    echo -e "${GREEN}OK (${TOTAL_MEM_GB} GB)${NC}"
fi

# 4. Storage Space Check
echo -n "Checking Root Storage Size... "
# Total size of the root filesystem in KB
TOTAL_DISK_KB=$(df / | tail -1 | awk '{print $2}')
TOTAL_DISK_GB=$(echo "scale=1; $TOTAL_DISK_KB / 1024 / 1024" | bc 2>/dev/null || awk "BEGIN {print $TOTAL_DISK_KB/1024/1024}")

# Minimum 32GB target (~33554432 KB). Allow buffer down to 25 GB to account for filesystem overhead.
if [[ "$TOTAL_DISK_KB" -lt 26214400 ]]; then
    echo -e "${RED}FAILED${NC}"
    echo -e "  -> Root filesystem total space is ${TOTAL_DISK_GB} GB. Minimum requirement is 32 GB."
    BLOCKED=1
else
    echo -e "${GREEN}OK (${TOTAL_DISK_GB} GB)${NC}"
fi

# Evaluate compliance
if [[ "$BLOCKED" -eq 1 ]]; then
    echo -e "\n${RED}======================================================${NC}"
    echo -e "${RED}INSTALLATION BLOCKED: Hardware compliance check failed.${NC}"
    echo -e "${RED}Please provision hardware matching the minimum specs.${NC}"
    echo -e "${RED}======================================================${NC}"
    exit 2
fi

echo -e "\n${GREEN}Hardware compliance checks passed successfully!${NC}"
echo -e "${BLUE}Starting installation of sensor dependencies...${NC}"

# Install core system packages
echo -n "Installing system packages... "
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
    > /dev/null 2>&1
echo -e "${GREEN}OK${NC}"

# Install Docker if not already present
if ! command -v docker &> /dev/null; then
    echo -n "Installing Docker... "
    curl -fsSL https://get.docker.com | sh > /dev/null 2>&1
    systemctl enable docker > /dev/null 2>&1
    systemctl start docker > /dev/null 2>&1
    echo -e "${GREEN}OK${NC}"
else
    echo -e "Docker already installed: ${GREEN}OK${NC}"
fi

# Copy reconciler agent to system path
echo -n "Installing Sensor Reconciler agent... "
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
cp "${SCRIPT_DIR}/reconciler/reconciler.py" /usr/local/bin/reconciler.py
chmod +x /usr/local/bin/reconciler.py

# Install systemd service
cp "${SCRIPT_DIR}/reconciler/sensor-reconciler.service" /etc/systemd/system/sensor-reconciler.service
systemctl daemon-reload
systemctl enable sensor-reconciler.service > /dev/null 2>&1
echo -e "${GREEN}OK${NC}"

# Create Node Exporter textfile collector directory
mkdir -p /var/lib/node_exporter/textfile_collector

# Copy CIPA compliance checker
cp "${SCRIPT_DIR}/cipa_compliance.py" /usr/local/bin/cipa_compliance.py
chmod +x /usr/local/bin/cipa_compliance.py

# Copy CAASPP & ELPAC State Testing Readiness Checker
cp "${SCRIPT_DIR}/caaspp_readiness.py" /usr/local/bin/caaspp_readiness.py
chmod +x /usr/local/bin/caaspp_readiness.py

# Copy Scheduled iperf3 Bandwidth Tester
cp "${SCRIPT_DIR}/iperf3_runner.py" /usr/local/bin/iperf3_runner.py
chmod +x /usr/local/bin/iperf3_runner.py

# Copy Wi-Fi and DHCP onboarding timing exporter
cp "${SCRIPT_DIR}/wifi_dhcp_exporter.py" /usr/local/bin/wifi_dhcp_exporter.py
chmod +x /usr/local/bin/wifi_dhcp_exporter.py

# Copy Wi-Fi RRM / DARRP / GSK Optimization Monitor
cp "${SCRIPT_DIR}/rrm_darrp_monitor.py" /usr/local/bin/rrm_darrp_monitor.py
chmod +x /usr/local/bin/rrm_darrp_monitor.py

# Create default sensor config directory
mkdir -p /etc/sensor

echo -e "\n${GREEN}=============================================${NC}"
echo -e "${GREEN}Sensor installation completed successfully.${NC}"
echo -e "${GREEN}=============================================${NC}"
echo -e "${YELLOW}Next steps:${NC}"
echo -e "  1. Edit /etc/sensor/reconciler.json with your CMP URL (leave api_key empty for pending registration approval)"
echo -e "  2. Start the reconciler: systemctl start sensor-reconciler"
echo -e "  3. Verify check-in: journalctl -u sensor-reconciler -f"
