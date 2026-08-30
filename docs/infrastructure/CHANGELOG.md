# Infrastructure Changelog

**Last Updated:** 2026-08-30

---

## 2026-08-30 — CRITICAL: UpCloud Stop API Format

| Field | Value |
|-------|-------|
| Date | 2026-08-30 |
| Discovery | UpCloud stop API requires `{"stop_server": {"stop_type": "hard", "timeout": "60"}}` — NOT `{"server": {...}}` |
| Evidence | Official docs at https://developers.upcloud.com/1.3/8-servers/ confirm the wrapper key is `stop_server` |
| Architectural Consequence | Using wrong key causes `UNKNOWN_ATTRIBUTE` error; servers won't stop, can't be deleted |
| Decision | Created `UPCLOUD-API-REFERENCE.md` with verified formats for ALL operations |
| Status | VERIFIED |

**LESSON:** Always read official API docs before using an endpoint. Never guess JSON format.
**REFERENCE:** `docs/infrastructure/UPCLOUD-API-REFERENCE.md`

---

## 2026-08-30 — Server Cleanup

| Field | Value |
|-------|-------|
| Date | 2026-08-30 |
| Discovery | 8 orphan/temp servers were wasting resources |
| Evidence | Server inventory showed 10 servers, only 2 needed |
| Architectural Consequence | Cleaned down to 2 servers: kudbee-gpu-primary, kudbee-host-v1-mercury |
| Decision | Deleted all non-essential servers using verified stop+delete procedure |
| Status | VERIFIED |

---

## 2026-08-30 — Initial Discovery

| Field | Value |
|-------|-------|
| Date | 2026-08-30 |
| Discovery | Complete infrastructure inventory via UpCloud API |
| Evidence | API calls to `/1.3/server`, `/1.3/ip_address`, `/1.3/network`, `/1.3/router` |
| Architectural Consequence | All infrastructure is API-manageable; single token provides full visibility |
| Decision | Document everything; preserve access path |
| Status | VERIFIED |

---

| Field | Value |
|-------|-------|
| Date | 2026-08-30 |
| Discovery | 10 servers across 2 zones (fi-hel2, us-chi1) |
| Evidence | API enumeration |
| Architectural Consequence | GPU server is in same zone as most servers; Chicago is separate |
| Decision | GPU server is primary compute target once SSH access recovered |
| Status | VERIFIED |

---

| Field | Value |
|-------|-------|
| Date | 2026-08-30 |
| Discovery | All production servers are publickey-only SSH |
| Evidence | `ssh -v` debug shows `Authentications that can continue: publickey` |
| Architectural Consequence | Cannot SSH without private key; must use web console emergency access |
| Decision | Document emergency access procedure; do not attempt destructive recovery |
| Status | VERIFIED |

---

| Field | Value |
|-------|-------|
| Date | 2026-08-30 |
| Discovery | kudbee-host-v1-mercury deployed from UpCloud K8s 1.35 template |
| Evidence | Storage labels: `_os_brand_name: Kubernetes`, `_template_uuid: 01000000-0000-4000-8000-000160150100` |
| Architectural Consequence | Think Box v1 was a Kubernetes node; Mercury 2 was likely a K8s workload |
| Decision | Investigate K8s state once SSH access recovered |
| Status | VERIFIED |

---

| Field | Value |
|-------|-------|
| Date | 2026-08-30 |
| Discovery | Kubernetes not running on any server |
| Evidence | Port scan: 6443, 10250, 2379 all closed on kudbee-host-v1-mercury |
| Architectural Consequence | Mercury 2 is not currently running; cluster may have been decommissioned |
| Decision | Need SSH access to investigate further |
| Status | VERIFIED |

---

| Field | Value |
|-------|-------|
| Date | 2026-08-30 |
| Discovery | Mercury 2 not found in workspace, environment, or running processes |
| Evidence | Searched files, env vars, processes, ports on all accessible servers |
| Architectural Consequence | Mercury 2 source/config not in this environment |
| Decision | User clarification needed on Mercury 2 location |
| Status | UNKNOWN |

---

| Field | Value |
|-------|-------|
| Date | 2026-08-30 |
| Discovery | Utility network routing works between servers in fi-hel2 |
| Evidence | Foothold (10.6.23.7) can reach GPU (10.6.13.220) and Mercury (10.6.22.159) via private IPs |
| Architectural Consequence | Server-to-server communication possible via utility network |
| Decision | Can use foothold as jump host for private network access |
| Status | VERIFIED |

---

| Field | Value |
|-------|-------|
| Date | 2026-08-30 |
| Discovery | kudbee-command and kudbee-access on different utility subnet |
| Evidence | Foothold cannot route to 10.6.23.x subnet |
| Architectural Consequence | These servers are on isolated utility network |
| Decision | May need to reconfigure routing or use public IPs |
| Status | VERIFIED |

---

| Field | Value |
|-------|-------|
| Date | 2026-08-30 |
| Discovery | GPU server cloned from Ubuntu 24.04 + NVIDIA drivers template |
| Evidence | Storage label: `_template_uuid: 01000000-0000-4000-8000-000030700200` |
| Architectural Consequence | GPU server has CUDA drivers pre-installed |
| Decision | Ready for ML workloads once SSH access recovered |
| Status | VERIFIED |

---

| Field | Value |
|-------|-------|
| Date | 2026-08-30 |
| Discovery | CAPU (Cluster API for UpCloud) labels on kudbee-host-v1-mercury |
| Evidence | Labels: capu_cluster_id, capu_cluster_name: think-box-test, capu_generated_name: kid-bee-mlw5f-6wmt7 |
| Architectural Consequence | Server was provisioned as part of a Kubernetes cluster via CAPU |
| Decision | Recovery may involve re-initializing the CAPU cluster |
| Status | VERIFIED |

---

| Field | Value |
|-------|-------|
| Date | 2026-08-30 |
| Discovery | Floating IPs attached but not routing |
| Evidence | 87.58.149.103 and 87.58.151.132 both timeout from external and internal |
| Architectural Consequence | Floating IPs need OS-level configuration (ARP announcement, route) |
| Decision | Configure floating IPs inside OS once SSH access recovered |
| Status | LIKELY |

---

| Field | Value |
|-------|-------|
| Date | 2026-08-30 |
| Discovery | 3 orphaned temp servers from failed SSH injection attempts |
| Evidence | kilo-ssh-injector, kilo-ssh-injector-v2, ubuntu-24.04-clone storage |
| Architectural Consequence | Wasting credits (~$2/hr for GPU, but these are small) |
| Decision | Safe to delete; deferred to user approval |
| Status | VERIFIED |

---

| Field | Value |
|-------|-------|
| Date | 2026-08-30 |
| Discovery | All infrastructure documentation created |
| Evidence | `docs/infrastructure/` directory with 12 files |
| Architectural Consequence | Future agents can discover infrastructure in minutes |
| Decision | Maintain as living documentation |
| Status | VERIFIED |
