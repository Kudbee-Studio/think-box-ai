# PR #101 — BYOC Mercury-2 + Upstash THINK Stash × Proof Bind (×10)

**Status:** Draft scaffold — plan only (no feature code in commit 0)  
**Branch:** `feat/byoc-think-stash-mercury-upstash-x10`  
**Base:** `main` (includes merged PR #100 Demo-in-10 / control-plane proof)  
**Implementer:** KILO (follow-on commits on this branch)  
**Merge:** Founder on GitHub only — do not auto-merge  

---

## Goal

Wire **Bring Your Own Credentials (BYOC)** for **Inception Mercury-2**, persist **THINK / reasoning** payloads to **Upstash Vector** as a durable stash, and **bind** each stash entry to the **control-plane proof chain** (#97–#99) so retrieval is verifiable offline.

Reuses:

- `thinkbox/reasoning.py` + `thinkbox/burst.py` (reasoning capture)
- `thinkbox/session.py` (`UpstashVectorSync`, fail-closed `EmbeddingError`)
- `thinkbox/embedder.py` (`OpenAICompatEmbedder` / BYOC embed route)
- `thinkbox/agent/control_plane/` (receipts, export, `verify_chain`)

Hermetic CI: mocked providers and `DeterministicEmbedder` in unit tests; no public `:8000`/`:8001` bind.

---

## Ten planned commits (implementation order)

| # | Commit (conventional) | Deliverable |
|---|-------------------------|-------------|
| 1 | `feat(byoc): env contract + resolver for Mercury-2 BYOC` | Document and implement `resolve_mercury_byoc()` — `INCEPTION_API_KEY`, optional `INCEPTION_BASE_URL` / model id; fail-closed when live path requested without credentials; no secrets in logs. Module: `thinkbox/byoc/mercury_config.py`. |
| 2 | `feat(byoc): register BYOC Mercury-2 with openai_compat provider` | Factory that builds `OpenAICompatProvider` from resolver output only (config change, not runtime hardcode). Module: `thinkbox/byoc/mercury_provider.py`. |
| 3 | `feat(think): THINK stash record model + SQLite index` | `ThinkStashRecord` (session_id, burst_id, reasoning_sha256, vector_id, proof_receipt_id, timestamps). Module: `thinkbox/think_stash/record.py` + local store. |
| 4 | `feat(think): capture hook from burst/runtime into stash draft` | After `ReasoningNormalizer` / burst pair completion, append normalized reasoning + metadata to stash draft (no vector yet). Module: `thinkbox/think_stash/capture.py`. |
| 5 | `feat(think): Upstash Vector upsert for THINK chunks` | Extend stash path to embed reasoning text via BYOC or test embedder; upsert with dense vector + metadata; raise `EmbeddingError` on failure (never silent `False`). Module: `thinkbox/think_stash/upstash_sync.py`. |
| 6 | `feat(think): proof bind — link stash id to ActionReceipt chain` | On proof export, write `think_stash_id` + `reasoning_sha256` into receipt metadata; verify bind in `verify_chain()`. Module: `thinkbox/think_stash/proof_bind.py`. |
| 7 | `feat(api): GET /think/stash and /think/stash/{id}/proof` | Read-only API over stash store + bound proof bundle pointer. Module: `backend/api/v1/think_stash.py`. |
| 8 | `feat(dashboard): THINK stash panel + BYOC status + last upsert` | Control-plane UI: BYOC configured/missing, last stash id, link to proof verify. Module: `public/control-plane/think_stash.html` + dashboard state emit. |
| 9 | `test(think): hermetic e2e — mock Mercury → stash → proof bind → verify` | Single test file exercising mocked provider, deterministic embedder, SQLite + fake vector client. Module: `tests/unit/think_stash/test_e2e.py`. |
| 10 | `docs(status): PR #101 map + THINK_STASH_BOUND tag` | Update `STATUS.md` / `AGENTS.md` with PR #101 feature table and tag `THINK_STASH_BOUND` (parity with PR #100 `CONTROL_PLANE_BOUND`). |

---

## Evidence labels

All dashboard and API responses from this wedge use evidence labels: `simulated`, `inferred`, `verified`, or `physically_measured`. Live Mercury-2 or live Upstash calls are **verified** only after documented smoke with real credentials — not claimed in scaffold PR.

---

## Out of scope (this PR)

- Multi-agent coalition / economy modules  
- New non-stdlib dependencies without ADR  
- Exposing inference ports publicly  
- Implementing commits 1–10 in the scaffold PR (this document only)

---

## References

- PR #97 — Agent control plane ×10  
- PR #98 — Dashboard control-plane bind  
- PR #99 — Durable proof plane  
- PR #100 — Demo-in-10 × control-plane × durable proof (merged on `main`)  
- `docs/think-burst-protocol.md` — reasoning field capture  
- `data/findings/thinkboxmd_upstash_vector_defect.md` — dense index + embedder requirements  
