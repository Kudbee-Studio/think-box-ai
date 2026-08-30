# Mercury 2

**Last Updated:** 2026-08-30

---

## Current State

| Item | Status |
|------|--------|
| Mercury 2 found in workspace | ❌ NOT FOUND |
| Mercury 2 process on any server | ❌ NOT FOUND |
| Mercury 2 config files | ❌ NOT FOUND |
| Mercury 2 environment variables | ❌ NOT FOUND |
| Mercury 2 documentation | ❌ NOT FOUND |
| Mercury 2 in code repository | ❌ NOT FOUND |

---

## What We Know

Mercury 2 is referenced by the user as:
- The platform/API for the Think Token
- Something that was running on "Think Box v1" (kudbee-host-v1-mercury)
- Something KUDBEE should integrate with

## What We Don't Know

- Mercury 2's source code location
- Mercury 2's runtime (Docker? K8s pod? Bare binary?)
- Mercury 2's API endpoints
- Mercury 2's authentication mechanism
- Mercury 2's database
- Mercury 2's current deployment status

---

## Investigation Results

### Searched Locations

| Location | Result |
|----------|--------|
| Workspace files | No mercury references |
| Environment variables | No mercury variables |
| Running processes (foothold) | No mercury processes |
| Docker containers (foothold) | No containers |
| Kubernetes (all servers) | No K8s running |
| Port scans (all servers) | No Mercury-like services |
| Storage templates | No Mercury template |

### Hypotheses

1. **Mercury 2 was a Kubernetes workload** that was decommissioned when the cluster was torn down
2. **Mercury 2 runs in a different environment** (different cloud, different account)
3. **Mercury 2 needs to be redeployed** from source
4. **Mercury 2 is the Upstash Box** (unlikely — different service model)

---

## Mercury ↔ KUDBEE Integration Plan

**Deferred** pending Mercury 2 discovery.

**Integration points to investigate:**
1. Does Mercury 2 provide model inference? → KUDBEE Provider interface
2. Does Mercury 2 manage tokens? → KUDBEE Token hierarchy
3. Does Mercury 2 provide agent capabilities? → KUDBEE Capability registry
4. Does Mercury 2 have its own memory? → KUDBEE Memory layer

---

## Recovery Steps

To find Mercury 2:

1. **Gain SSH access to kudbee-host-v1-mercury** via web console
2. Search for Mercury artifacts:
   ```bash
   find / -name "*mercury*" 2>/dev/null
   find / -name "*thing*" -o -name "*think*token*" 2>/dev/null
   docker images 2>/dev/null | grep -i mercury
   crictl images 2>/dev/null | grep -i mercury
   ls /opt/ /srv/ /var/lib/ 2>/dev/null
   ```
3. Check for deployment manifests:
   ```bash
   find / -name "*.yaml" -o -name "*.yml" 2>/dev/null | head -20
   ```
4. Check systemd services:
   ```bash
   systemctl list-units --all | grep -i mercury
   ```
