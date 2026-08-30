# UpCloud API Operations Guide

**CRITICAL:** This is the verified, tested reference for UpCloud API operations.
DO NOT guess the JSON format. Always reference this document.

## Authentication

```bash
export UPCLOUD_TOKEN="your-token"
AUTH_HEADER="Authorization: Bearer $UPCLOUD_TOKEN"
BASE_URL="https://api.upcloud.com/1.3"
```

---

## SERVER OPERATIONS

### List All Servers
```bash
curl -s -H "$AUTH_HEADER" "$BASE_URL/server" | python3 -m json.tool
```

### Get Server Details
```bash
curl -s -H "$AUTH_HEADER" "$BASE_URL/server/{uuid}" | python3 -m json.tool
```

### Create Server
```bash
curl -s -X POST \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  "$BASE_URL/server" \
  -d '{
    "server": {
      "zone": "fi-hel2",
      "title": "server-name",
      "hostname": "server-hostname",
      "plan": "1xCPU-1GB",
      "storage_devices": {
        "storage_device": [{
          "action": "create",
          "size": 10,
          "tier": "maxiops",
          "title": "root-disk"
        }]
      },
      "login_user": {
        "username": "root",
        "ssh_keys": {
          "ssh_key": ["ssh-ed25519 AAAA... user@host"]
        }
      }
    }
  }'
```

### Stop Server (HARD) — ✅ VERIFIED FORMAT
**CRITICAL:** The JSON wrapper MUST be `stop_server`, NOT `server`.
```bash
curl -s -X POST \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  "$BASE_URL/server/{uuid}/stop" \
  -d '{"stop_server": {"stop_type": "hard", "timeout": "60"}}'
```

**WRONG (will return UNKNOWN_ATTRIBUTE or SERVER_STATE_ILLEGAL):**
```bash
# DO NOT USE
-d '{"stop_type": "hard"}'
-d '{"server": {"stop_type": "hard"}}'
```

### Stop Server (SOFT)
```bash
curl -s -X POST \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  "$BASE_URL/server/{uuid}/stop" \
  -d '{"stop_server": {"stop_type": "soft", "timeout": "60"}}'
```

### Start Server
```bash
curl -s -X POST \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  "$BASE_URL/server/{uuid}/start"
```

### Restart Server
```bash
curl -s -X POST \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  "$BASE_URL/server/{uuid}/restart" \
  -d '{"restart_server": {"stop_type": "soft", "timeout": "60", "timeout_action": "destroy"}}'
```

### Delete Server (must be stopped first)
```bash
# With storage cascade delete
curl -s -X DELETE \
  -H "$AUTH_HEADER" \
  "$BASE_URL/server/{uuid}?storages=true"

# Without deleting storage
curl -s -X DELETE \
  -H "$AUTH_HEADER" \
  "$BASE_URL/server/{uuid}"
```

### Rename Server
```bash
curl -s -X PUT \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  "$BASE_URL/server/{uuid}" \
  -d '{"server": {"title": "new-name"}}'
```

---

## NETWORK OPERATIONS

### List All Networks
```bash
curl -s -H "$AUTH_HEADER" "$BASE_URL/network"
```

### Create Network
```bash
curl -s -X POST \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  "$BASE_URL/network" \
  -d '{
    "network": {
      "name": "my-network",
      "zone": "fi-hel2",
      "router": "router-uuid",
      "ip_networks": {
        "ip_network": [{
          "address": "10.0.0.0/24",
          "family": "IPv4",
          "dhcp": "yes"
        }]
      }
    }
  }'
```

---

## ROUTER OPERATIONS

### List All Routers
```bash
curl -s -H "$AUTH_HEADER" "$BASE_URL/router"
```

### Create Router
```bash
curl -s -X POST \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  "$BASE_URL/router" \
  -d '{"router": {"name": "my-router"}}'
```

### Attach Network to Router
```bash
curl -s -X POST \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  "$BASE_URL/router/{router-uuid}/networks" \
  -d '{"network": {"uuid": "network-uuid"}}'
```

---

## IP ADDRESS OPERATIONS

### List All IPs
```bash
curl -s -H "$AUTH_HEADER" "$BASE_URL/ip_address"
```

### Attach Floating IP
```bash
curl -s -X POST \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  "$BASE_URL/server/{uuid}/ip_address" \
  -d '{"ip_address": {"family": "IPv4", "floating": "yes"}}'
```

---

## STORAGE OPERATIONS

### List All Storage
```bash
curl -s -H "$AUTH_HEADER" "$BASE_URL/storage?private=1"
```

### Create Storage
```bash
curl -s -X POST \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  "$BASE_URL/storage" \
  -d '{
    "storage": {
      "size": 10,
      "tier": "maxiops",
      "title": "my-disk",
      "zone": "fi-hel2"
    }
  }'
```

### Attach Storage to Server
```bash
curl -s -X POST \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  "$BASE_URL/server/{uuid}/storage/attach" \
  -d '{"storage_device": {"type": "disk", "address": "virtio:1", "storage": "storage-uuid"}}'
```

### Detach Storage from Server
```bash
curl -s -X POST \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  "$BASE_URL/server/{uuid}/storage/detach" \
  -d '{"storage_device": {"address": "virtio:1"}}'
```

### Delete Storage
```bash
curl -s -X DELETE \
  -H "$AUTH_HEADER" \
  "$BASE_URL/storage/{uuid}"
```

---

## PYTHON HELPER FUNCTIONS

```python
import json, subprocess, os

TOKEN = os.environ['THINKBOX_UPCLOUD_API_TOKEN']
BASE = "https://api.upcloud.com/1.3"
HDR = f"Authorization: Bearer {TOKEN}"

def api(method, path, data=None):
    cmd = ["curl", "-s", "-X", method, "-H", HDR, "-H", "Content-Type: application/json"]
    if data:
        cmd += ["-d", json.dumps(data)]
    cmd.append(f"{BASE}{path}")
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    try:
        return json.loads(r.stdout)
    except:
        return r.stdout

def list_servers():
    return api("GET", "/server")

def get_server(uuid):
    return api("GET", f"/server/{uuid}")

def create_server(title, hostname, zone, plan, ssh_key, size=10):
    return api("POST", "/server", {
        "server": {
            "zone": zone,
            "title": title,
            "hostname": hostname,
            "plan": plan,
            "storage_devices": {
                "storage_device": [{
                    "action": "create",
                    "size": size,
                    "tier": "maxiops",
                    "title": f"{hostname}-os"
                }]
            },
            "login_user": {
                "username": "root",
                "ssh_keys": {"ssh_key": [ssh_key]}
            }
        }
    })

def stop_server(uuid, hard=True):
    """Stop a server. Default is hard stop."""
    return api("POST", f"/server/{uuid}/stop", {
        "stop_server": {
            "stop_type": "hard" if hard else "soft",
            "timeout": "60"
        }
    })

def start_server(uuid):
    return api("POST", f"/server/{uuid}/start")

def delete_server(uuid, delete_storage=True):
    """Delete a server. Must be stopped first."""
    return api("DELETE", f"/server/{uuid}?storages={'true' if delete_storage else 'false'}")

def rename_server(uuid, new_title):
    return api("PUT", f"/server/{uuid}", {
        "server": {"title": new_title}
    })

def wait_for_state(uuid, target_state, timeout=120):
    """Wait for a server to reach a specific state."""
    import time
    for i in range(timeout // 5):
        s = get_server(uuid)
        state = s['server']['state']
        if state == target_state:
            return True
        time.sleep(5)
    return False

def delete_server_full(uuid, delete_storage=True):
    """Stop, wait, then delete a server."""
    stop_server(uuid)
    wait_for_state(uuid, 'stopped')
    return delete_server(uuid, delete_storage)
```

---

## COMMON MISTAKES

| Mistake | Error | Fix |
|---------|-------|-----|
| Wrong stop JSON key | `UNKNOWN_ATTRIBUTE` | Use `{"stop_server": {...}}` not `{"server": {...}}` |
| Delete while running | `SERVER_STATE_ILLEGAL` | Stop first, wait for `stopped`, then delete |
| Missing Content-Type | Various errors | Always include `-H "Content-Type: application/json"` |
| Wrong timeout format | `TIMEOUT_INVALID` | Timeout is a string `"60"`, not a number |

---

## REFERENCE

- Official docs: https://developers.upcloud.com/1.3/
- Server operations: https://developers.upcloud.com/1.3/8-servers/
- Stop endpoint: `POST /1.3/server/{uuid}/stop`
- Delete endpoint: `DELETE /1.3/server/{uuid}?storages=true`
