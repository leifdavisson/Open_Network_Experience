#!/usr/bin/env bash
# Open Network Experience (ONE) - Chrome Extension Packager

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
EXT_DIR="${ROOT_DIR}/chromebook-sensor"
PEM_FILE="${ROOT_DIR}/server/deploy/certs/chromebook-sensor.pem"
CRX_FILE="${ROOT_DIR}/server/deploy/chromebook-sensor.crx"
ID_FILE="${ROOT_DIR}/server/deploy/chromebook-sensor.id"

mkdir -p "${ROOT_DIR}/server/deploy/certs"

CHROME_BIN="google-chrome"
if ! command -v google-chrome &> /dev/null; then
    if command -v chromium &> /dev/null; then
        CHROME_BIN="chromium"
    elif command -v chromium-browser &> /dev/null; then
        CHROME_BIN="chromium-browser"
    else
        echo "Error: Neither google-chrome nor chromium is installed."
        exit 1
    fi
fi

if [[ -f "${PEM_FILE}" ]]; then
    echo "Packaging extension using existing private key..."
    ${CHROME_BIN} --headless --no-sandbox --pack-extension="${EXT_DIR}" --pack-extension-key="${PEM_FILE}"
else
    echo "Packaging extension and generating new private key..."
    ${CHROME_BIN} --headless --no-sandbox --pack-extension="${EXT_DIR}"
    mv "${ROOT_DIR}/chromebook-sensor.pem" "${PEM_FILE}"
fi

mv "${ROOT_DIR}/chromebook-sensor.crx" "${CRX_FILE}"

# Generate Extension ID for update.xml
openssl rsa -in "${PEM_FILE}" -pubout -outform DER 2>/dev/null | sha256sum | head -c 32 | tr '0-9a-f' 'a-p' > "${ID_FILE}"
EXT_ID=$(cat "${ID_FILE}")

echo "Extension packaged successfully at ${CRX_FILE}"
echo "Extension ID: ${EXT_ID}"
