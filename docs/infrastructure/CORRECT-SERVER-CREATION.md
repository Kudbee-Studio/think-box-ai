# KUDBEE Infrastructure — Correct Server Creation Procedure

**Last Updated:** 2026-08-30
**VERIFIED:** This procedure works. Do NOT deviate.

## The Correct Way to Create an UpCloud Server

### Option A: Via UpCloud Control Panel (RECOMMENDED)

1. Go to **Deploy a server** in UpCloud Control Panel
2. **Hostname:** `your-server-name`
3. **Plan:** Select GPU plan (e.g., `GPU-SPOT-20xCPU-256GB-3xL40S`)
4. **OS Template:** `Ubuntu Server 24.04 LTS (with NVIDIA drivers & CUDA)`
5. **Location:** `fi-hel2` (Finland)
6. **Metadata:** Enable (for SSH key injection)
7. **SSH Keys:** Add this public key:
   ```
   ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILZ6oDsNJowkIO3rrU7EbqvSvSvifZZTEKKfW44hotnZBc kilo-agent@kudbee
   ```
8. **Deploy**

### Option B: Via API (Advanced)

```json
POST /1.3/server
{
  "server": {
    "zone": "fi-hel2",
    "title": "server-name",
    "hostname": "server-hostname",
    "plan": "GPU-SPOT-20xCPU-256GB-3xL40S",
    "metadata": "yes",
    "storage_devices": {
      "storage_device": [{
        "action": "clone",
        "storage": "01000000-0000-4000-8000-000030700200",
        "title": "ubuntu-24.04-nvidia",
        "size": 400,
        "tier": "maxiops"
      }]
    },
    "networking": {
      "interfaces": {
        "interface": [
          {"ip_addresses": {"ip_address": [{"family": "IPv4"}]}, "type": "public"},
          {"ip_addresses": {"ip_address": [{"family": "IPv4"}]}, "type": "utility"}
        ]
      }
    },
    "login_user": {
      "username": "root",
      "ssh_keys": {
        "ssh_key": ["ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILZ6oDsNJowkIO3rrU7EbqvSvifZZTEKKfW44hotnZBc kilo-agent@kudbee"]
      }
    }
  }
}
```

## After Server Creation

1. Wait for `started` state
2. Wait 60 seconds for SSH to stabilize
3. SSH: `ssh -i ~/.ssh/kilocloud -o StrictHostKeyChecking=accept-new root@<public-ip>`
4. Install Docker: `apt-get update && apt-get install -y docker.io`
5. Start Docker: `systemctl enable docker && systemctl start docker`
6. Set Inception API key: `echo 'INCEPTION_API_KEY=sk_63c907f6e5c65a4fd03d1bafcd81e895' > /root/.env`

## What We Learned (The Hard Way)

| Mistake | Why It Was Wrong | Correct Approach |
|---------|-----------------|------------------|
| `"action": "create"` | Creates empty disk with no OS | Use `"action": "clone"` with template UUID |
| Not waiting for SSH | SSH daemon needs time to start | Wait 60 seconds after `started` state |
| Guessing API format | Wasted hours on wrong JSON | Read official docs first |
| Deleting foothold | Lost only SSH access path | Keep foothold alive until new server verified |
| Wrong stop JSON | `{"server": {...}}` fails | Use `{"stop_server": {"stop_type": "hard", "timeout": "60"}}` |

## Current Infrastructure

| Server | IP | Specs | Purpose |
|--------|-----|-------|---------|
| gpu-ubuntu-think-box-host | 87.58.149.157 | 3x L40S, 256 GB RAM, 20 cores | AI/ML compute |
| kudbee-gpu | (stopped) | 2x L40S | Legacy (delete) |

## To Delete

```bash
# Stop
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  https://api.upcloud.com/1.3/server/{uuid}/stop \
  -d '{"stop_server": {"stop_type": "hard", "timeout": "60"}}'

# Wait 15 seconds, then delete
curl -X DELETE -H "Authorization: Bearer $TOKEN" \
  https://api.upcloud.com/1.3/server/{uuid}?storages=true
```
