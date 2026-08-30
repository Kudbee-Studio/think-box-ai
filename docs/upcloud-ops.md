# UpCloud Operations Knowledge Base

## Server Inventory

| Hostname | UUID | Plan | Zone | Public IPs | Purpose |
|----------|------|------|------|------------|---------|
| kudbee-host-v1 | 000d8567-72c8-46b8-99b6-89d260944d0b | PREMIUM-4xCPU-8GB | fi-hel2 | 212.147.250.183, 87.58.151.132 | Main runtime |
| ubuntu-8cpu-128gb-us-chi1 | 004c080f-5966-44ae-9260-16b6d55e11e3 | PREMIUM-8xCPU-128GB | us-chi1 | 152.44.35.44 | Firecracker host |
| gpu-ubuntu-12cpu-128gb-fi-hel2 | 002b8e55-1d81-4b3a-aff5-c15b2df0e66f | GPU-SPOT-12xCPU-128GB-2xL40S | fi-hel2 | 87.58.149.32 | GPU inference |

## API Authentication

```bash
# Bearer token authentication
curl -H "Authorization: Bearer $THINKBOX_UPCLOUD_API_TOKEN" \
  "https://api.upcloud.com/1.3/server"
```

## Server Creation (Working)

```python
# CORRECT: Use "action": "create" for new empty disk
body = {
    "server": {
        "hostname": "new-server",
        "plan": "PREMIUM-2xCPU-4GB",
        "zone": "fi-hel2",
        "title": "New Server",
        "storage_devices": {
            "storage_device": [{
                "action": "create",  # NOT "clone"
                "size": 50,
                "tier": "maxiops",
                "title": "root-disk",
            }]
        },
        "login_user": {
            "username": "root",
            "ssh_keys": {"ssh_key": ["ssh-ed25519 AAAA..."]},
            "create_password": "no",
        },
    }
}
```

## Storage Templates (Working)

| Template | UUID | Type |
|----------|------|------|
| Ubuntu 26.04 LTS | 01000000-0000-4000-8000-000030260200 | cloud-init |
| Ubuntu 24.04 LTS | 01000000-0000-4000-8000-000030240200 | cloud-init |
| Debian 11 (native) | 01000000-0000-4000-8000-000020060100 | native |

## Common API Errors

| Error | Cause | Fix |
|-------|-------|-----|
| METADATA_DISABLED_ON_CLOUD-INIT | Using cloud-init template without metadata | Use `"action": "create"` or enable metadata |
| METADATA_INVALID | Wrong metadata value format | Use boolean `true` or string `"1"` |
| UNKNOWN_ATTRIBUTE | Unsupported field in request | Remove `tags`, `metadata` from body |
| STORAGE_NOT_FOUND | Wrong template UUID | Use correct UUID from `/storage/template` |

## SSH Access

```bash
# Generate key
ssh-keygen -t ed25519 -f .ssh/kudbee_deploy -N ""

# Connect
ssh -i .ssh/kudbee_deploy root@<ip>
```

## What's Pre-installed on ubuntu-8cpu-128gb

- Ubuntu 26.04 LTS (Resolute Raccoon)
- CUDA drivers (if using GPU template)
- NVIDIA Container Toolkit (if GPU)
- Docker (verify with `docker --version`)
- Python 3.12+

## Deployment Checklist

1. [ ] SSH access working
2. [ ] Check existing packages (`docker`, `python3`, `nvidia-smi`)
3. [ ] Deploy Docker Compose stack
4. [ ] Configure Caddy reverse proxy
5. [ ] Start API + PostgreSQL + Redis
6. [ ] Verify health endpoints
