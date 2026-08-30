# UpCloud Infrastructure

**Last Updated:** 2026-08-30

---

## Account

| Field | Value |
|-------|-------|
| Username | kudbee |
| Credits | 47,190 |
| API Version | 1.3 |
| API Endpoint | https://api.upcloud.com/1.3/ |

## Resource Limits

| Resource | Limit |
|----------|-------|
| Cores | 100 |
| Memory | 307,200 MB (300 GB) |
| Public IPv4 | 20 |
| Public IPv6 | 100 |
| Networks | 100 |
| Routers | 100 |
| Server Groups | 200 |
| Firewall Rules | Unlimited |
| GPUs | 0 (GPU servers don't count) |

---

## Server Inventory

### Production Servers

| # | Title | UUID | Hostname | Plan | CPU | RAM | Zone | State |
|---|-------|------|----------|------|-----|-----|------|-------|
| 1 | kudbee-gpu-primary | 002b8e55 | gpu-ubuntu-12cpu-128gb-fi-hel2 | GPU-SPOT-12xCPU-128GB-2xL40S | 12 | 128 GB | fi-hel2 | started |
| 2 | kudbee-host-v1-mercury | 000d8567 | kudbee-host-v1 | PREMIUM-4xCPU-8GB | 4 | 8 GB | fi-hel2 | started |
| 3 | kudbee-command | 00ddc075 | kudbee-cmd | PREMIUM-2xCPU-4GB | 2 | 4 GB | fi-hel2 | started |
| 4 | kudbee-access | 007691c9 | kudbee-access | PREMIUM-2xCPU-4GB | 2 | 4 GB | fi-hel2 | started |
| 5 | kudbee-debian | 00331bb2 | kudbee-debian | PREMIUM-2xCPU-4GB | 2 | 4 GB | fi-hel2 | started |
| 6 | kudbee-chicago-8cpu | 004c080f | ubuntu-8cpu-128gb-us-chi1 | PREMIUM-8xCPU-128GB | 8 | 128 GB | us-chi1 | started |

### Temporary/Orphan Servers

| # | Title | UUID | Plan | CPU | RAM | Zone | State |
|---|-------|------|------|-----|-----|------|-------|
| 7 | kilo-foothold | 000e73d0 | 1xCPU-1GB | 1 | 1 GB | fi-hel2 | started |
| 8 | kilo-orphan-v2 | 0035a60c | 1xCPU-1GB | 1 | 1 GB | fi-hel2 | started |
| 9 | kilo-orphan-v1 | 00d270d5 | 1xCPU-1GB | 1 | 1 GB | fi-hel2 | started |
| 10 | kudbee-test | 00b49236 | PREMIUM-2xCPU-4GB | 2 | 4 GB | fi-hel2 | started |

---

## IP Addresses

### Production IPs

| Server | Public IP | Private IP | Floating IP |
|--------|-----------|------------|-------------|
| kudbee-gpu-primary | 87.58.149.32 | 10.6.13.220 | 87.58.149.103 |
| kudbee-host-v1-mercury | 212.147.250.183 | 10.6.22.159 | 87.58.151.132 |
| kudbee-command | 87.58.149.70 | 10.6.23.9 | — |
| kudbee-access | 87.58.149.45 | 10.6.23.4 | — |
| kudbee-debian | 87.58.149.93 | 10.6.23.10 | — |
| kudbee-chicago-8cpu | 152.44.35.44 | 10.3.7.136 | — |

### Temporary IPs

| Server | Public IP | Private IP |
|--------|-----------|------------|
| kilo-foothold | 87.58.149.82 | 10.6.23.7 |
| kilo-orphan-v2 | 87.58.149.56 | — |
| kilo-orphan-v1 | 87.58.149.87 | — |
| kudbee-test | 87.58.149.73 | 10.6.23.8 |

---

## GPU Details

| Field | GPU 0 | GPU 1 |
|-------|-------|-------|
| Model | NVIDIA L40S | NVIDIA L40S |
| CUDA Cores | 18,176 | 18,176 |
| VRAM | 48 GB | 48 GB |
| Serial | 1791025012991 | 1791025001009 |

---

## Storage Devices

| Server | Title | UUID | Size | Tier |
|--------|-------|------|------|------|
| kudbee-gpu-primary | Device 1 | 0158d252 | 300 GB | maxiops |
| kudbee-host-v1-mercury | primary disk | 01caf4dd | 100 GB | maxiops |
| kudbee-chicago-8cpu | Device 1 | 01e1b777 | 400 GB | maxiops |

---

## API Quick Reference

```bash
# List all servers
GET /1.3/server

# Get server details
GET /1.3/server/{uuid}

# Rename server
PUT /1.3/server/{uuid}  body: {"server": {"title": "new-name"}}

# Start/Stop/Restart
POST /1.3/server/{uuid}/start
POST /1.3/server/{uuid}/stop
POST /1.3/server/{uuid}/restart

# List all IPs
GET /1.3/ip_address

# List all networks
GET /1.3/network

# List all routers
GET /1.3/router

# Create server
POST /1.3/server
body: {
  "server": {
    "hostname": "name",
    "zone": "fi-hel2",
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
        "ssh_key": ["ssh-ed25519 ..."]
      }
    }
  }
}
```
