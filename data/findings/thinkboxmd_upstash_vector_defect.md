# Finding: Upstash Vector sync is incompatible with the configured dense index

**Date:** 2026-09-15
**Discovered by:** `experiments/thinkboxmd_research.py` (THINKBOXMD-RESEARCH run)
**Severity:** Medium — distributed/vector memory silently fails
**Status:** Open

## Summary

`thinkbox/session.py::UpstashVectorSync.upsert()` reports success/failure as a
boolean and swallows the HTTP error. Against the project's actual Upstash Vector
index it fails every time, and the boolean gives no reason.

## Evidence

```
GET  {UPSTASH_VECTOR_REST_URL}/info ->
  {"result":{"vectorCount":0,"dimension":1536,
   "similarityFunction":"DOT_PRODUCT","indexType":"DENSE", ...}}

POST {UPSTASH_VECTOR_REST_URL}/upsert  (client payload: {"id", "metadata"}) ->
  HTTP 422 {"error":"This index requires dense vectors","status":422}
```

## Root cause

1. The index is **DENSE** with `dimension=1536` and therefore requires a
   `vector` field on every upsert.
2. `UpstashVectorSync.upsert()` sends only `id` + `metadata` — no vector.
3. There is **no working embedding provider** in the repo:
   - `core/providers/openai_compat.py:70` — `embed()` raises `NotImplementedError`
   - `core/providers/ollama.py:105` — `embed()` raises `NotImplementedError`

So even a corrected client has nothing to embed with today.

## Impact

- `thinkbox/session.py` (Phase 8 "Session tracking with Upstash Vector sync"),
  `thinkbox/substrate.py::ThinkBoxVectorSync`, and any "Commons survives a new
  session" claim that depends on Vector are **not actually working**.
- Local `MemoryStore` (SQLite) is unaffected and does persist.

## Recommended fix (not yet implemented)

1. Add an `embed()` implementation to at least one provider (Mercury 2 exposes
   an OpenAI-compatible surface; add an embedding-capable provider or a local
   hashing embedder explicitly labelled non-semantic).
2. Change `UpstashVectorSync.upsert()` to include the `vector`.
3. Stop swallowing the error: return/propagate the HTTP status + body so callers
   can distinguish "not configured" from "configured but rejected".
4. Add a test that asserts a non-2xx upsert is surfaced, not silently `False`.

Deliberately **not** implemented as part of the THINKBOXMD test — recorded here
as the next integration boundary rather than fixed ad hoc.
