# Mercury 2 + Inception Integration

**Last Updated:** 2026-08-30
**Status:** Integration in progress

---

## Overview

Mercury 2 is the AI model inference platform that powers KUDBEE's Think Token.
Inception is the model provider API used by Mercury 2 / Think Box.

---

## Inception API

| Field | Value |
|-------|-------|
| Provider | Inception |
| API Key Name | INCEPTION_API_KEY |
| API Key Location | `~/.env` on target servers |
| Key Format | `sk_63c907f6e5c65a4fd03d1bafcd81e895` |
| Token Balance | ~99,000,000+ tokens remaining |
| Purpose | Model inference via Think Box / Mercury 2 |

### Where the key must live:

| Server | Path | Status |
|--------|------|--------|
| kudbee-host-v1-mercury | `~/.env` | Target (needs SSH) |
| kudbee-gpu-primary | `~/.env` | Target (needs SSH) |
| kilo-gateway | `~/.env` | Target (just created) |

### .env file format:
```
INCEPTION_API_KEY=sk_63c907f6e5c65a4fd03d1bafcd81e895
```

### Permissions:
```bash
chmod 600 ~/.env
```

---

## Mercury 2

| Field | Value |
|-------|-------|
| Purpose | AI model inference platform |
| Relationship to KUDBEE | Provides model inference for Think Token |
| Original host | kudbee-host-v1-mercury (Think Box v1) |
| Deployment method | Kubernetes workload (CAPU) |
| Current status | Not running (K8s cluster down) |

---

## Architecture (Target)

```
INCEPTION API (sk_63c9...)
    │
    ▼
MERCURY 2 (model inference platform)
    │
    ▼
KUDBEE (agent orchestration + token economics)
    │
    ▼
THINK BOX (isolated agent execution)
    │
    ├─ Intent → Opportunity → Capability → Outcome → Proof
    ├─ THINK HATS (professional capabilities)
    ├─ THINK COMMONS (collective intelligence)
    └─ THINK SWARM (agent coordination)
    │
    ▼
THINK TOKEN (THNK) — rewards based on Proof/Jury score
```

---

## Integration Points

### Mercury 2 → KUDBEE
- Model inference provider (register in `core/providers/`)
- Capability discovery for agents
- Token consumption tracking

### KUDBEE → Mercury 2
- Agent orchestration
- Memory persistence
- Governance and audit
- Token economics (THNK rewards)

---

## Immediate Action Required

1. **Gain SSH to kilo-gateway** (87.58.149.190) — server is up but SSH not responding
2. **Write `~/.env` with INCEPTION_API_KEY** on accessible server
3. **Verify Inception API connectivity** — test that the key works
4. **Deploy Mercury 2** to kilo-gateway or kudbee-host-v1-mercury
5. **Register Mercury as KUDBEE provider** in `core/providers/`

---

## Lessons Learned

1. **Never send secrets through chat** — write directly to server `.env` files
2. **SSH keys must be account-level in UpCloud** to work across servers
3. **New servers take 2-5 minutes** for cloud-init to finish and SSH to work
4. **Floating IPs need OS-level config** to route properly
5. **Utility network routing** works between servers in same zone
