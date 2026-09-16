# PREP — Handoff & Readiness Brief

**Date:** 2026-09-15
**Repo:** `Kudbee-Studio/think-box-ai`
**Main:** `2cec2ce` — working tree clean, **302 tests OK** (1 skipped: optional `fastapi`/`uvicorn` absent in the sandbox)

This is the "pick it up cold" document. Everything below is verified or
explicitly marked as not-verified.

---

## 1. What is shipped and verified

| Capability | Evidence | Status |
|---|---|---|
| Mock vLLM transport (loopback `:8001`) | `thinkbox/mock_vllm.py`, burst smoke run | ✅ verified |
| THINK burst runner (offline + live) | `thinkbox/burst.py`, `data/evals/burst-smoke/` | ✅ verified |
| Disruptor + verifier harness | 15/15 passes, **STRONG** | ✅ verified |
| Harvest replay | groundedness 0.900, bind-failure 1.000 | ✅ verified |
| Interrupt/resume with checkpoints | `experiments/test_interrupt_resume.py` | ✅ verified |
| THINKBOXMD-RESEARCH workflow | `docs/THINKBOXMD_REPORT.md` — 9 PASS / 2 PARTIAL | ✅ verified |
| Swarm instrumentation (10 instruments) | `experiments/verify_instrumentation.py` — **11/11** | ✅ verified |
| Strength index + learning curve | `0.6405 → 0.7318 (+0.0913)` | ✅ verified |
| Dashboard (mobile-first) | stdlib server, tunnels via `cloudflared` | ✅ verified |
| Mercury 2 live provider | `api.inceptionlabs.ai/v1`, ~24 rps ceiling | ✅ verified |

**Run everything:**

```bash
python3 -m unittest discover tests/                    # 302 OK
python3 experiments/verify_instrumentation.py --live   # 11/11
python3 experiments/big_swarm.py --primary 256 --validators 64 --concurrency 32 --arena
python3 experiments/swarm_dashboard.py --port 8787
cloudflared tunnel --url http://127.0.0.1:8787
```

---

## 2. Repo / CI state

- `origin/main` is up to date; branch and main in sync (0 ahead / 0 behind).
- **CI is not trusted right now.** GitHub billing is restricted per the operator;
  the workflow in `.github/workflows/test.yml` runs `python3 -m unittest discover tests/ -v`.
  Treat local `302 OK` as the gate.
- One pre-existing environmental skip: optional `fastapi`/`uvicorn` are absent
  from the sandbox interpreter (no `pip`/`apt` network). The test skips rather
  than fails, so the suite is honest rather than red.
- PR **#62 MERGED**, PR **#60 MERGED**, PR **#61 still OPEN**
  (`feat/disruptor-evaluation` — superseded by work already on `main`; safe to close).

---

## 3. Known defects (open, not hidden)

| # | Defect | Impact | File |
|---|--------|--------|------|
| 1 | Upstash Vector writes rejected (`HTTP 422`, dense index needs a vector); no embedding provider exists | distributed/vector memory silently fails; local SQLite unaffected | `thinkbox/session.py`, `data/findings/thinkboxmd_upstash_vector_defect.md` |
| 2 | THINK token economy is integer simulation, no settlement | "minting" is conceptual | `thinkbox/economy.py`, `think_box_ai/token.py` |
| 3 | `core/solana/*` shells out to `solana`/`anchor` CLIs that are **not installed** | wallet/token ops return `CLI not installed` | `core/solana/__init__.py` |
| 4 | No MCP client/server; no Redis client; Upstash Box is metadata-only | no external tool bridge, no distributed queue | repo-wide |
| 5 | `tests/e2e/` is empty; `benchmarks/` has no artifacts | `AGENTS.md` §1.5 evidence requirement unmet | — |

**Fixed this cycle:** `thinkbox/economy.py::transfer()` deadlocked on any new
recipient (called `create_account()` while holding the same non-reentrant lock).
Fixed + regression test.

---

## 4. Access inventory (from the cloud sandbox)

| Service | Env present | Usable | Blocker |
|---|---|---|---|
| Inception Mercury 2 | `INCEPTION_API_KEY` | ✅ **yes** | — |
| Upstash Vector | `UPSTASH_VECTOR_REST_URL/TOKEN` | ⚠️ partial | dense index + no embedder |
| Upstash Box | `UPSTASH_BOX_API_KEY`, `UPSTASH_PUBLIC_BOX_URL` | ❌ | preview returns `preview not found` |
| UpCloud `kudbee-host-v1` (212.147.250.183) | `THINKBOX_UPCLOUD_API_TOKEN` | ❌ | token **401 invalid**; `~/.ssh/kilo-upcloud` absent; IP behind Cloudflare (1003) |
| Redis | — | ❌ | no client configured |
| MCP | — | ❌ | none configured |

**To unblock UpCloud:** mint a fresh API token from the panel and/or place the
SSH private key at the configured `UPCLOUD_SSH_KEY_PATH`. No code change needed.

---

## 5. Next, in priority order

1. **Embedding provider** → then fix `UpstashVectorSync.upsert()` to send a
   vector and to surface HTTP errors instead of returning bare `False`.
   *Unblocks distributed Commons.*
2. **Wire `SelfImprovementLoop` into the run** so the retest is automatic
   (today it is callable and verified, but the swarm does not yet drive it).
3. **`--replay <session_id>`** — reload a genome and re-run identically.
   Genome save/verify already works; only the replay driver is missing.
4. **Reputation-weighted worker sampling** in wave 2.
5. **Deduplication of path constants** (`data/thinkboxmd/db/…` is hardcoded in
   four places) — extract `thinkbox/paths.py`.
6. **`DASHBOARD_BUILDOUT.md` Phase 1–4** — harden middleware, optional Cloudflare
   Access, mount dashboard API under `backend/main.py`, ETag caching.

---

## 6. Guardrails to preserve

- **No fake success.** Every claim in the docs points at an artifact, a test
  result, or a run. Keep it that way; if a number is unknown, write `—`.
- **Signals are not failures.** Challenge activity and validator tier inflation
  are *reported*, never penalised in the strength index.
- **Files over servers.** Do not add a broker/framework for the dashboard until a
  measured number demands it (see `docs/DASHBOARD_BUILDOUT.md` §5).
- **Synthetic only, not clinical.** All THINKBOXMD scenarios are
  `SYNTHETIC=true`; never real patient data.
- **Never print secrets.** Env values were only ever probed for presence.
