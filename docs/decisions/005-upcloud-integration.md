# ADR 005: UpCloud Infrastructure Integration

**Date:** 2026-08-30
**Status:** Accepted

## Context

KUDBEE requires KVM-capable cloud infrastructure for Firecracker microVM execution. UpCloud provides bare-metal-like performance with PREMIUM plans that support nested KVM. The system needs programmatic server provisioning, management, and SSH key configuration.

## Decision

Create `core/infrastructure/upcloud.py` as the canonical UpCloud integration module, using Bearer token authentication from the `THINKBOX_UPCLOUD_API_TOKEN` environment variable.

## Key Endpoints Used

- `GET /server` — list servers (requires individual GET for full IP details)
- `GET /server/{uuid}` — get server details with IP addresses
- `POST /server` — create new server
- `POST /server/{uuid}/start` — start server
- `POST /server/{uuid}/stop` — stop server
- `DELETE /server/{uuid}` — delete server

## Architecture

```
core/infrastructure/
├── __init__.py    # exports
└── upcloud.py     # UpCloudClient, ServerSpec, ServerInfo, create_kvm_server
```

## Configuration

| Source | Variable | Purpose |
|--------|----------|---------|
| Environment | `THINKBOX_UPCLOUD_API_TOKEN` | API authentication |
| Environment | `UPCLOUD_SSH_KEY_PATH` | SSH key path for server access |
| Environment | `UPCLOUD_SSH_USER` | SSH username (default: root) |

## Identified Servers

| Hostname | Plan | Zone | State | Public IPs |
|----------|------|------|-------|------------|
| kudbee-host-v1 | PREMIUM-4xCPU-8GB | fi-hel2 | started | 212.147.250.183 |
| ubuntu-8cpu-128gb-us-chi1 | PREMIUM-8xCPU-128GB | us-chi1 | started | 152.44.35.44 |
| gpu-ubuntu-12cpu-128gb-fi-hel2 | GPU-SPOT-12xCPU-128GB-2xL40S | fi-hel2 | maintenance | 87.58.149.32 |

## Consequences

- Server provisioning is fully programmatic
- KVM capability requires PREMIUM plan or higher
- GPU servers available for ML workloads (deferred to Phase 2+)
- All operations use stdlib only (urllib) — no external dependencies
