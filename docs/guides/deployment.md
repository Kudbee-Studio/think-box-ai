# Production Deployment Guide

## Quick Start with Docker

```bash
# 1. Clone and configure
git clone https://github.com/Kudbee-Studio/think-box-ai.git
cd think-box-ai
cp .env.example .env
# Edit .env and set your API keys

# 2. Run with Docker Compose
docker-compose up -d

# 3. Check health
curl http://localhost:8000/health
```

## Production Deployment Options

### Option 1: Reverse Proxy with nginx

```nginx
server {
    listen 80;
    server_name api.thinkboxai.xyz;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.thinkboxai.xyz;

    ssl_certificate /etc/letsencrypt/live/api.thinkboxai.xyz/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.thinkboxai.xyz/privkey.pem;

    # Security headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

    location / {
        limit_req zone=api burst=20 nodelay;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
}
```

### Option 2: SSH Tunnel (for remote access)

```bash
# Create SSH tunnel from local machine to remote server
ssh -L 8000:localhost:8000 user@your-server -N

# Now access via http://localhost:8000
```

### Option 3: Cloudflare Tunnel (recommended for production)

```bash
# Install cloudflared
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared
chmod +x cloudflared

# Authenticate
./cloudflared tunnel login

# Create tunnel
./cloudflared tunnel create thinkbox-api

# Configure
cat > ~/.cloudflared/config.yml << EOF
tunnel: thinkbox-api
credentials-file: ~/.cloudflared/<tunnel-id>.json
ingress:
  - hostname: api.thinkboxai.xyz
    service: http://localhost:8000
  - service: http_status:404
EOF

# Run
./cloudflared tunnel run thinkbox-api
```

### Option 4: WireGuard VPN (for private network)

```ini
# /etc/wireguard/wg0.conf
[Interface]
PrivateKey = <server-private-key>
Address = 10.0.0.1/24
ListenPort = 51820

[Peer]
PublicKey = <client-public-key>
AllowedIPs = 10.0.0.2/32
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `THINKBOX_API_KEY` | Primary API key | (required) |
| `THINKBOX_API_KEYS` | Comma-separated keys | (optional) |
| `THINKBOX_RATE_LIMIT` | Requests per minute | 100 |
| `THINKBOX_ALLOWED_ORIGINS` | CORS origins | localhost |
| `THINKBOX_DEFAULT_PROVIDER` | LLM provider | openai_compat |
| `THINKBOX_DEFAULT_MODEL` | LLM model | gpt-4o-mini |
| `THINKBOX_LOG_LEVEL` | Logging level | INFO |

## Security Checklist

- [ ] Use strong API keys (32+ bytes random)
- [ ] Enable HTTPS via reverse proxy
- [ ] Configure CORS for your domain only
- [ ] Set appropriate rate limits
- [ ] Run as non-root user
- [ ] Enable firewall (ufw/iptables)
- [ ] Use Docker with resource limits
- [ ] Set up log monitoring
- [ ] Enable automated backups
- [ ] Keep dependencies updated
