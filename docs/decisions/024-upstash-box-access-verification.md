# ADR 024: Upstash Box access verification (PR #201)

**Date:** 2026-09-24
**Status:** Accepted

## Context

PR #200 shipped a typed environmental-variables pack, including substrate keys `UPSTASH_PUBLIC_BOX_URL` and `UPSTASH_PUBLIC_BOX_TOKEN`. PR #201 must establish whether a Cursor agent runtime can actually access the configured Upstash Box using the existing adapter — without inventing a second auth path, printing secrets, or claiming live execution from mocks.

Historical CONTINUITY records already show the adapter contract (`thinkbox/execution_adapter.py`) and that `UPSTASH_BOX_API_KEY` is documentation-only.

## Options Considered

1. Treat HTTP reachability or a mocked `/run` stub as LIVE VERIFIED.
2. Reuse `UPSTASH_BOX_API_KEY` as a Bearer token when `UPSTASH_PUBLIC_BOX_TOKEN` is absent.
3. Probe only through the existing adapter contract; classify A–E honestly; persist a redacted evidence artifact.

## Decision

We chose option 3. Authentication remains `Authorization: Bearer $UPSTASH_PUBLIC_BOX_TOKEN` on `POST {url}/run`. Missing official env vars are classification **A** (`ENV_NOT_CONFIGURED`). HTTP 200 without a verified adapter receipt is **C**, not **D**. A local stub is never LIVE VERIFIED.

## Consequences

- Gate `upstash-box-access-verification` caps honesty at TEST_VERIFIED until a real configured Box execution produces classification D with `live_http_used=true`.
- `UPSTASH_BOX_API_KEY` may be present and is never sent.
- Founder review remains required; this PR is not production-ready.
- Cursor Cloud Agents inject adapter credentials via **Environment secrets** (dashboard), not via `.cursor/environment.json`. Partial Upstash secret sets (e.g. Vector + `UPSTASH_BOX_API_KEY` without the adapter pair) still classify as **A**.
