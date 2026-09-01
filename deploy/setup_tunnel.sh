#!/bin/bash
# Think Box AI — Cloudflare Tunnel setup script
# This creates a secure tunnel without exposing your server's IP

set -e

echo "Think Box AI — Cloudflare Tunnel Setup"
echo "======================================"

# Check if cloudflared is installed
if ! command -v cloudflared &> /dev/null; then
    echo "Installing cloudflared..."
    curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /usr/local/bin/cloudflared
    chmod +x /usr/local/bin/cloudflared
fi

# Login (opens browser)
echo "Login to Cloudflare..."
cloudflared tunnel login

# Create tunnel
echo "Creating tunnel..."
cloudflared tunnel create thinkbox-api

# Get tunnel ID
TUNNEL_ID=$(cloudflared tunnel list | grep thinkbox-api | awk '{print $1}')
echo "Tunnel ID: $TUNNEL_ID"

# Create config
mkdir -p /root/.cloudflared
cat > /root/.cloudflared/config.yml << EOF
tunnel: thinkbox-api
credentials-file: /root/.cloudflared/${TUNNEL_ID}.json
ingress:
  - hostname: api.thinkboxai.xyz
    service: http://localhost:8000
    originRequest:
      noTLSVerify: true
  - service: http_status:404
EOF

# DNS route
cloudflared tunnel route dns thinkbox-api api.thinkboxai.xyz

# Install as service
cloudflared service install

echo ""
echo "Tunnel configured!"
echo "Start with: systemctl start cloudflared"
echo "Enable auto-start: systemctl enable cloudflared"
echo "Check status: cloudflared tunnel info thinkbox-api"
