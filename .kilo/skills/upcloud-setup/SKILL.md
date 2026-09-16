# Skill: upcloud-setup

**Description:** Set up UpCloud infrastructure — API token, SSH key, Floating IP

# When to Use

Use when UpCloud access is blocked (401 token, missing SSH key, Cloudflare block) or when setting up a stable endpoint for the dashboard.

# Prerequisites

- Access to UpCloud panel (https://upcloud.com)
- Know the server hostname (e.g., `kudbee-host-v1`)
- Know the server IP (e.g., `212.147.250.183`)

# Workflow

## Step 1 — API Token

1. Log in to UpCloud panel
2. Go to API keys section
3. Create new API key
4. Set `THINKBOX_UPCLOUD_API_TOKEN` env var
5. Verify: `curl -s -H "Authorization: Bearer $THINKBOX_UPCLOUD_API_TOKEN" https://api.upcloud.com/v1/server`

## Step 2 — SSH Key

1. Generate or locate SSH key pair
2. Upload public key to UpCloud panel (Server → SSH keys → Add)
3. Place private key at `UPCLOUD_SSH_KEY_PATH` (default: `~/.ssh/kilo-upcloud`)
4. Set permissions: `chmod 600 ~/.ssh/kilo-upcloud`
5. Verify: `ssh -i ~/.ssh/kilo-upcloud root@$UPCLOUD_SERVER_IP`

## Step 3 — Cloudflare Bypass

If IP is behind Cloudflare (error 1003):
1. Request direct IP access from UpCloud support, OR
2. Use SSH tunnel instead of HTTP, OR
3. Use Floating IP (not behind Cloudflare)

## Step 4 — Floating IP (recommended)

1. Purchase Floating IP from UpCloud (~$3.50/month)
2. Assign to server in UpCloud panel
3. Note the Floating IP address
4. Dashboard URL: `http://FLOATING-IP:8787`
5. Bookmark on phone

## Step 5 — Verify Substrate Detection

```python
from thinkbox.substrate import detect_substrate
print(detect_substrate())  # Should print "upcloud-gpu"
```

Requires `THINKBOX_UPCLOUD_API_TOKEN` env var set.

# Environment Variables

| Variable | Purpose |
|----------|---------|
| `THINKBOX_UPCLOUD_API_TOKEN` | UpCloud API key |
| `UPCLOUD_SERVER_HOSTNAME` | Server hostname |
| `UPCLOUD_SERVER_IP` | Server IP |
| `UPCLOUD_SSH_KEY_PATH` | Path to SSH private key |
| `UPCLOUD_SSH_USER` | SSH username (default: root) |

# Rules

- Never commit API tokens or SSH keys
- Out of scope for KILO code: this is panel/infrastructure work
- Floating IP is the recommended stable endpoint approach
