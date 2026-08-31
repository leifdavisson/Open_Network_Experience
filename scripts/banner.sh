#!/usr/bin/env bash
# Open Network Experience (ONE) — Terminal ASCII Art & CLI Banner
# License: GNU AGPLv3

CLR_CYAN='\033[38;2;0;210;255m'
CLR_BLUE='\033[38;2;0;102;255m'
CLR_GREEN='\033[38;2;16;185;129m'
CLR_MUTED='\033[38;2;148;163;184m'
CLR_WHITE='\033[38;2;248;250;252m'
CLR_BOLD='\033[1m'
CLR_RESET='\033[0m'

echo -e "${CLR_CYAN}"
cat << "BANNER_EOF"
  ____  _   _ _____   _   _ _____ _______        _____  ____  _  __
 / __ \| \ | | ____| | \ | | ____|_   _\ \      / / _ \|  _ \| |/ /
| |  | |  \| |  _|   |  \| |  _|   | |  \ \ /\ / / | | | |_) | ' /
| |__| | |\  | |___  | |\  | |___  | |   \ V  V /| |_| |  _ <| . \
 \____/|_| \_|_____| |_| \_|_____| |_|    \_/\_/  \___/|_| \_\_|\_\
BANNER_EOF

echo -e "${CLR_BLUE}               EXPERIENCE PLATFORM // ${CLR_GREEN}v0.4.0${CLR_RESET}"
echo ""
echo -e "${CLR_CYAN}       /\\        ${CLR_WHITE}${CLR_BOLD}OPEN NETWORK EXPERIENCE${CLR_RESET}"
echo -e "${CLR_CYAN}  /\\  /  \\  /\\   ${CLR_MUTED}\"Every Packet Accountable. Every Experience Verified.\"${CLR_RESET}"
echo -e "${CLR_CYAN} /  \\/    \\/  \\  ${CLR_MUTED}-------------------------------------------------------${CLR_RESET}"
echo -e "${CLR_CYAN}|   /\\_/\\_/\\   | ${CLR_GREEN}[•]${CLR_WHITE} Edge Prober Telemetry   : ${CLR_GREEN}ACTIVE${CLR_RESET}"
echo -e "${CLR_BLUE} \\ /  \\  /  \\ /  ${CLR_GREEN}[•]${CLR_WHITE} Chrome Extension Bridge : ${CLR_CYAN}SYNCED${CLR_RESET}"
echo -e "${CLR_BLUE}  \\    \\/    /   ${CLR_GREEN}[•]${CLR_WHITE} Control Plane Ingestion : ${CLR_GREEN}CONNECTED (AGPLv3)${CLR_RESET}"
echo -e "${CLR_GREEN}   \\  /  \\  /${CLR_RESET}"
echo -e "${CLR_GREEN}    \\/____\\/${CLR_RESET}"
echo ""
