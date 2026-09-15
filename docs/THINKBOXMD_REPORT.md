# THINKBOXMD-RESEARCH — End-to-End Research Workflow Test

**Date:** 2026-09-15
**Runner:** KILO (cloud agent sandbox)
**Command:** `python3 experiments/thinkboxmd_research.py`
**Verdict:** 9 PASS / 2 PARTIAL / 0 FAIL (see below)
**Nature:** RESEARCH + INFRASTRUCTURE test. **Not clinical advice.** All scenarios synthetic (`SYNTHETIC=true`).

---

## 1. What was actually run

A real end-to-end research workflow driven by **live model calls** against the
Inception Mercury 2 API, wired through the repository's existing infrastructure:

| Layer | Component used | Real? |
|-------|----------------|-------|
| Think Box | `thinkbox.workspace.WorkspaceRegistry` + `WorkspaceStore` (SQLite) | ✅ real |
| Governance | `thinkbox.identity`, `thinkbox.governance_token`, `thinkbox.admission` | ✅ real |
| Audit / proof | `thinkbox.ledger.ActionLedger` (SHA-256 hash chain, SQLite) | ✅ real |
| Tracing | `thinkbox.thinktrace.ThinkTraceCapture` | ✅ real |
| Memory | `core.memory.store.MemoryStore` (SQLite) | ✅ real |
| Provider | `core.providers.openai_compat` → Mercury 2 (live) | ✅ real |
| Vector memory | `thinkbox.session.UpstashVectorSync` | ⚠️ broken (see §5) |

Worker agents are **not** simulated: each makes a live HTTP completion call to
`https://api.inceptionlabs.ai/v1` (model `mercury-2`, ~3–5 s/call).

---

## 2. The workflow

```
INTENT  →  THINK BOX  →  SWARM  →  RESEARCH  →  RECONCILE  →  FAILURE  →  MEMORY  →  PROOF
```

- **Think Box:** `THINKBOXMD-RESEARCH` created, persisted to SQLite, recorded in the ledger.
- **Swarm:** five specialized worker boxes — `PHARMA`, `TOX`, `VALIDATOR`, `SAFETY`, `SYNTH`.
- **Research:** each worker receives a synthetic scenario + strict tier contract
  (`EVIDENCE` / `INFERENCE` / `HYPOTHESIS` / `UNVERIFIED`) and returns strict JSON.
- **Reconcile:** tier distribution, primary-worker tier disagreements, SAFETY flags.
- **Failure test:** a provider failure is deliberately injected, then recovered.
- **Memory:** findings written to the persistent Commons (`MemoryStore`).
- **Proof:** machine-readable JSON + human-readable Markdown + hash.

---

## 3. Evidence (this run)

| Metric | Value |
|--------|-------|
| Run id | `thinkboxmd_20260915_231732` |
| Proof hash | `0723be5ea848a96fa85ad61c7ecf225139dff8efc6d527797fcb1f998c0bd6f5` |
| Ledger entries | 12 (chain valid: **True**) |
| Think traces | 10 total — 9 grounded, 1 ungrounded |
| Tier distribution | EVIDENCE 8 · INFERENCE 0 · HYPOTHESIS 0 · UNVERIFIED 1 |
| Memory entries | 9 written / 9 total |
| Vector sync | **False** — `HTTP 422 This index requires dense vectors` |
| Provider failure | detected ✅ · ledger-preserved ✅ · recovered ✅ |

Artifacts:
- `data/thinkboxmd/thinkboxmd_20260915_231732.json`
- `data/thinkboxmd/thinkboxmd_20260915_231732.md`

---

## 4. Final verdict by layer

| Layer | Verdict | Basis |
|-------|---------|-------|
| BOOT | **PASS** | provider key present, all stores wired |
| THINK BOX | **PASS** | box created + persisted + ledgered |
| SWARM | **PASS** | 5/5 worker boxes registered |
| RESEARCH | **PASS** | 8 live model findings returned |
| SAFETY | **PASS** | synthetic-only enforced; Tier contract applied |
| EXECUTION | **PASS** | live provider calls succeeded |
| MEMORY | **PARTIAL** | local SQLite ✅; Upstash Vector ❌ (HTTP 422) |
| PROVENANCE | **PASS** | 10 traces captured, evidence_refs recorded |
| PROOF | **PASS** | ledger hash chain verifies |
| THINK INTEGRATION | **PARTIAL** | token economy is integer-simulation, not settlement |
| FAILURE RECOVERY | **PASS** | injected failure detected, preserved, recovered |

### Largest missing capability

> **No durable distributed execution substrate.**
> Think Boxes persist only as registry rows + SQLite snapshots, and workers run
> as in-process model calls. There is no scheduler or worker process isolation,
> no MCP tool bridge, and no credentialed Upstash Box / Redis work queue — so the
> system cannot fan work out across resilient, independently-restartable workers.

---

## 5. Defects discovered (real, reproducible)

1. **Upstash Vector client is incompatible with a dense index.**
   `thinkbox/session.py::UpstashVectorSync.upsert()` sends `{"id", "metadata"}`
   with no vector. The configured index is `DENSE`, `dimension=1536`, and rejects
   the write with `HTTP 422 {"error":"This index requires dense vectors"}`.
   Root cause: no embedding provider exists (`OpenAICompatProvider.embed()` and
   `OllamaProvider.embed()` both raise `NotImplementedError`).
   See `data/findings/thinkboxmd_upstash_vector_defect.md`.

2. **Mercury 2 output-contract variance.** Reasoning tokens consume the
   completion budget, so with a low `max_tokens` the JSON is truncated and
   unparseable. Mitigated in the experiment with `max_tokens=3500` plus one
   bounded retry; the unparseable case correctly degrades to `UNVERIFIED`
   rather than inventing a tier.

---

## 6. Access inventory (this sandbox)

| Service | Env present | Reachable | Usable | Notes |
|---------|-------------|-----------|--------|-------|
| Inception Mercury 2 (LLM) | `INCEPTION_API_KEY` | ✅ | ✅ **live** | `api.inceptionlabs.ai/v1`, `mercury-2` |
| Upstash Vector | `UPSTASH_VECTOR_REST_URL/TOKEN` | ✅ | ⚠️ partial | dense index needs a vector |
| Upstash Box | `UPSTASH_BOX_API_KEY`, `UPSTASH_PUBLIC_BOX_URL` | ✅ host | ❌ | preview returns `preview not found` |
| UpCloud `kudbee-host-v1` | `THINKBOX_UPCLOUD_API_TOKEN` | ✅ (80/443) | ❌ | token **401 invalid**; no SSH key; IP fronted by Cloudflare (1003) |
| Redis | — | — | ❌ | no client, no env |
| MCP servers | — | — | ❌ | none configured |
| GitHub | — | ✅ | ✅ (read) | billing-restricted per operator |

**UpCloud detail:** `UPCLOUD_SERVER_HOSTNAME=kudbee-host-v1`,
`UPCLOUD_SERVER_IP=212.147.250.183`, `UPCLOUD_SSH_USER=root`,
`UPCLOUD_SSH_KEY_PATH=~/.ssh/kilo-upcloud` (**file absent**).
API token is structurally accepted as an API token but rejected as invalid/expired.
Direct-IP HTTP returns Cloudflare error 1003 (host is proxied).
SSH port is filtered from this sandbox.

**To unblock UpCloud:** create a fresh API token (the operator notes the API
allows new token creation) and/or provision the SSH key at the configured path.
No other change is required.

---

## 7. Reproduce

```bash
python3 experiments/thinkboxmd_research.py
```

Requires only `INCEPTION_API_KEY` (already present). No third-party packages —
stdlib only.
