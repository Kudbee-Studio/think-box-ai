# Think Job control-plane UI (PR #138, #139)

Hermetic dashboard page for watching Think Job status via SSE (#137) with poll fallback.
PR #139 adds **receipt-keyed watch** and a **jobs digest multiplex** panel on the same page.

## Open

`public/control-plane/think_job_status.html` (linked from control-plane index).

## Auth

Provide `X-API-Key` in the toolbar. The client uses **fetch** for SSE so headers are sent
fail-closed. Query `api_key` is not required for the default path.

## Flow

1. `JobsDigestMultiplexer` polls `GET /api/v1/run/jobs/status/digest` + job list (`detail=summary`).
2. Optional digest SSE: `GET /api/v1/run/jobs/status/stream` (hello + `think_jobs_digest_delta`).
3. Watch by **receipt id** (`GET /api/v1/run/job/by-receipt/{receipt_id}/status` + receipt stream) or engine id.
4. `poll.stream` hints from #134/#137 select job vs receipt stream URLs — no parallel status plane.
5. On errors: reconnect with backoff, then degraded poll at `recommended_interval_ms` (fail-closed).

## Four-state

CODE COMPLETE / TEST VERIFIED on branch only. Not LIVE VERIFIED. Not PRODUCTION READY.
