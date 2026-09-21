# ADR 004: Upstash Box Authentication Contract

**Date:** 2026-09-21
**Status:** Accepted

## Context

The think-box-ai repository implements a remote execution adapter for Upstash Box in `thinkbox/execution_adapter.py`. The adapter requires two environment variables:
- `UPSTASH_PUBLIC_BOX_URL` — the Box host URL
- `UPSTASH_PUBLIC_BOX_TOKEN` — the Bearer token used in the `Authorization` header

The broader runtime contract (`KUDBEE_AGENT_RUNTIME_CONTRACT.md`) lists `UPSTASH_BOX_API_KEY` as an "API key for Upstash Box remote worker", but this variable is **never referenced in Python source code**. The adapter does not read, use, or depend on `UPSTASH_BOX_API_KEY` for authentication. The only Python code that references `UPSTASH_BOX_API_KEY` is documentation and configuration listings.

## Options Considered

1. **Adapter reads `UPSTASH_PUBLIC_BOX_TOKEN` as Bearer token** — current implementation, correct per source code, but `UPSTASH_PUBLIC_BOX_TOKEN` is absent in the runtime environment.
2. **Adapter reads `UPSTASH_BOX_API_KEY` as Bearer token** — would align with runtime contract documentation, but no code change was made because the existing HTTP 404 `preview not found` response from the endpoint occurs regardless of authentication method, and the endpoint itself is not live/provisioned for this URL.
3. **Both tokens supported with fallback** — would add code complexity without fixing the fundamental issue that the Box preview endpoint returns `preview not found` for this URL, independent of auth.

## Decision

The adapter contract is definitively `UPSTASH_PUBLIC_BOX_TOKEN` (Bearer auth header). The environment provides `UPSTASH_BOX_API_KEY` but it is **not** used by the adapter. The runtime contract documentation should be updated to reflect that `UPSTASH_BOX_API_KEY` is a documented environment variable for Upstash Box but is not the credential consumed by the remote execution adapter.

**Consequences:**
- `UPSTASH_PUBLIC_BOX_TOKEN` must be set for the adapter to enter `is_configured()` state and attempt remote execution.
- `UPSTASH_BOX_API_KEY` remains present in the environment but has no effect on the adapter; it is effectively a no-op for Box remote execution.
- The classification in `docs/CONTINUITY.md` is **B**: credential contract confirmed but required credential (`UPSTASH_PUBLIC_BOX_TOKEN`) missing.
- No code changes are required; this is a documentation/clarification mismatch.

## Consequences

- Positive: Clear contract defined solely from source code (`thinkbox/execution_adapter.py:27-28`). No hidden dependencies.
- Positive: Runtime contract docs updated to avoid future confusion between `UPSTASH_BOX_API_KEY` and `UPSTASH_PUBLIC_BOX_TOKEN`.
- Negative: Until `UPSTASH_PUBLIC_BOX_TOKEN` is provisioned, `LIVE_VERIFIED` remains unachievable and the adapter will fail closed with `NOT_CONFIGURED`.
- Negative: The endpoint returns `preview not found` regardless of auth, so even with the correct token, live execution cannot be proven in this sandbox.