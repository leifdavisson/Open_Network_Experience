#!/usr/bin/env bash

# ONE - Start Public Cloudflare Tunnel for Google Workspace Deployment
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [ ! -f "${ROOT_DIR}/scratch/cloudflared" ]; then
    echo "Downloading cloudflared..."
    mkdir -p "${ROOT_DIR}/scratch"
    wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -O "${ROOT_DIR}/scratch/cloudflared"
    chmod +x "${ROOT_DIR}/scratch/cloudflared"
fi

echo "Starting secure Cloudflare tunnel to local ONE dashboard (port 443)..."
nohup "${ROOT_DIR}/scratch/cloudflared" tunnel --url https://localhost:443 --no-tls-verify > "${ROOT_DIR}/scratch/tunnel.log" 2>&1 &
TUNNEL_PID=$!

echo "Waiting for tunnel to establish (5 seconds)..."
sleep 5

TUNNEL_URL=$(grep -o 'https://[^"]*\.trycloudflare\.com' "${ROOT_DIR}/scratch/tunnel.log" | head -n 1)

if [ -z "$TUNNEL_URL" ]; then
    echo "Error establishing tunnel. Check scratch/tunnel.log"
    exit 1
fi

echo ""
echo "=========================================================================="
echo "✅ TUNNEL ESTABLISHED SUCCESSFULLY!"
echo "Your ONE Dashboard is now publicly accessible for the next 7 days at:"
echo "   $TUNNEL_URL"
echo ""
echo "Google Workspace 'Custom URL' Deployment Configuration:"
echo "   Update URL: $TUNNEL_URL/api/v1/extension/update.xml"
echo ""
echo "Note: The tunnel process ($TUNNEL_PID) is running in the background."
echo "=========================================================================="
