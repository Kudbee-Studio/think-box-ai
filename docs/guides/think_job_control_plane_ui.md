# Think Job control-plane UI (PR #138)

Hermetic dashboard page for watching Think Job status via SSE (#137) with poll fallback.

## Open

`public/control-plane/think_job_status.html` (linked from control-plane index).

## Auth

Provide `X-API-Key` in the toolbar. The client uses **fetch** for SSE so headers are sent
fail-closed. Query `api_key` is not required for the default path.

## Flow

1. `GET /api/v1/run/jobs/status` populates the job list.
2. `GET /api/v1/run/job/{engine_id}/status` seeds state and reads `poll.stream` URLs.
3. `GET .../status/stream` delivers hello/delta/close events.
4. On errors: reconnect with backoff, then degraded poll at `recommended_interval_ms`.

## Four-state

CODE COMPLETE / TEST VERIFIED on branch only. Not LIVE VERIFIED. Not PRODUCTION READY.
