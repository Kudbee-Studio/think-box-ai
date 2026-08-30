# KUDBEE Infrastructure Documentation

**Last Updated:** 2026-08-30
**Status:** Active development environment
**Account:** kudbee (UpCloud)

---

## Quick Reference

| Resource | Count | Notes |
|----------|-------|-------|
| Servers | 10 | 7 production, 3 temporary |
| Zones | 2 | fi-hel2 (Finland), us-chi1 (Chicago) |
| GPUs | 2x NVIDIA L40S | 48 GB VRAM each |
| Floating IPs | 2 | |
| Public IPs | 12 | |
| Total CPU | 32 cores | |
| Total RAM | 332 GB | |
| Credits | 47,190 | |

## Documentation Index

| File | Purpose |
|------|---------|
| [ACCESS.md](ACCESS.md) | How to access the infrastructure |
| [UPCLOUD.md](UPCLOUD.md) | UpCloud API reference |
| [SSH.md](SSH.md) | SSH access patterns |
| [CREDENTIALS.md](CREDENTIALS.md) | Credential inventory (no secrets) |
| [NETWORK.md](NETWORK.md) | Network topology |
| [SERVERS.md](SERVERS.md) | Server inventory |
| [KUBERNETES.md](KUBERNETES.md) | Kubernetes cluster info |
| [MERCURY.md](MERCURY.md) | Mercury 2 service |
| [THINK-BOX.md](THINK-BOX.md) | Think Box architecture |
| [RECOVERY.md](RECOVERY.md) | Disaster recovery |
| [BOOTSTRAP.md](BOOTSTRAP.md) | Bootstrap specification |
| [CHANGELOG.md](CHANGELOG.md) | Change history |

## Architecture Overview

```
KUDBEE CLOUD (UpCloud Account: kudbee)
═══════════════════════════════════════════════════════════

fi-hel2 (Finland)                    us-chi1 (Chicago)
┌──────────────────────────┐        ┌────────────────────┐
│ kudbee-gpu-primary       │        │ kudbee-chicago     │
│ 12 CPU / 128 GB / 2xL40S │        │ 8 CPU / 128 GB     │
│ 87.58.149.32             │        │ 152.44.35.44       │
│ (LOCKED - no SSH key)    │        │ (LOCKED)           │
├──────────────────────────┤        └────────────────────┘
│ kudbee-host-v1-mercury   │
│ 4 CPU / 8 GB             │
│ 212.147.250.183          │
│ K8s 1.35 node            │
│ (LOCKED)                 │
├──────────────────────────┤
│ kudbee-command           │
│ 2 CPU / 4 GB             │
│ 87.58.149.70             │
│ (LOCKED)                 │
├──────────────────────────┤
│ kudbee-access            │
│ 2 CPU / 4 GB             │
│ 87.58.149.45             │
│ (LOCKED)                 │
├──────────────────────────┤
│ kudbee-debian            │
│ 2 CPU / 4 GB             │
│ 87.58.149.93             │
│ (LOCKED)                 │
├──────────────────────────┤
│ kilo-foothold            │
│ 1 CPU / 1 GB             │
│ 87.58.149.82             │
│ (ACCESSIBLE)             │
└──────────────────────────┘
```

## Critical Warnings

- All production servers are **publickey-only** SSH
- The private key is NOT available in this environment
- GPU server SSH is blocked — use UpCloud web console emergency console
- 3 orphaned temp servers should be cleaned up (cost savings)
- Floating IPs require OS-level configuration to route
