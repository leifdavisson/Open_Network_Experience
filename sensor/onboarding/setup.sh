#!/usr/bin/env bash
#
# Open Network Experience (ONE) - USB Flash Drive Auto-Staging Runner
#
# Copyright (C) 2026 Open Network Experience Authors.
# Licensed under the GNU Affero General Public License v3.0 (AGPLv3).
# See LICENSE in the project root for full license details.
#
# Usage:
#   Plug USB stick into a booted Ubuntu SBC or Mini-PC and run:
#     sudo ./setup.sh
#   or from any directory:
#     sudo /media/*/*/setup.sh
#

set -euo pipefail

# Root check
if [[ $EUID -ne 0 ]]; then
   echo "Error: This script must be run as root (use sudo ./setup.sh)." 1>&2
   exit 1
fi

SCRIPT_DIR="$(dirname "$(readlink -f "$0" 2>/dev/null || echo ".")")"

# Ensure Python 3 is present
if ! command -v python3 &> /dev/null; then
    echo "Installing Python3..."
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq > /dev/null 2>&1 || true
    apt-get install -y -qq python3 wpasupplicant > /dev/null 2>&1 || true
fi

# Locate usb_provisioner.py
PROVISIONER_SCRIPT=""
if [[ -f "${SCRIPT_DIR}/usb_provisioner.py" ]]; then
    PROVISIONER_SCRIPT="${SCRIPT_DIR}/usb_provisioner.py"
elif [[ -f "${SCRIPT_DIR}/onboarding/usb_provisioner.py" ]]; then
    PROVISIONER_SCRIPT="${SCRIPT_DIR}/onboarding/usb_provisioner.py"
elif [[ -f "/usr/local/bin/usb_provisioner.py" ]]; then
    PROVISIONER_SCRIPT="/usr/local/bin/usb_provisioner.py"
fi

if [[ -n "$PROVISIONER_SCRIPT" ]]; then
    python3 "$PROVISIONER_SCRIPT" --source "$SCRIPT_DIR" "$@"
else
    echo "Error: usb_provisioner.py not found in ${SCRIPT_DIR}." 1>&2
    exit 1
fi
