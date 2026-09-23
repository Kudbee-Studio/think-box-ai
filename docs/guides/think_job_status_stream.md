# Think Job status stream (hermetic SSE)

PR #137 adds Server-Sent Events (SSE) for Think Job status **deltas** so clients can
subscribe instead of polling `GET /api/v1/run/job/{engine_id}/status`.

## Routes

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/run/job/{engine_id}/status/stream` | Single-job status deltas |
| GET | `/api/v1/run/job/by-receipt/{receipt_id}/status/stream` | Same stream keyed by receipt |
| GET | `/api/v1/run/jobs/status/stream` | Dashboard digest revision deltas |
| GET | `/api/v1/run/jobs/status/digest` | Counts-only digest poll (multiplex boot) |

PR #139 UI multiplexes digest poll + list with optional digest SSE alongside receipt-keyed job watch.

All routes require the same API key as other `/api/v1` surfaces. Query parameters:

- `max_events` (default 64, capped by `THINKBOX_STREAM_MAX_EVENTS`)
- `timeout_s` (idle close, default 120)
- `heartbeat_s` (heartbeat interval, default 15)

## Event kinds

- `hello` — initial snapshot (`think_job_stream_hello`)
- `status` — incremental delta (`think_job_status_delta`)
- `heartbeat` — no state change (`think_job_stream_heartbeat`)
- `close` — terminal or timeout (`think_job_stream_close`)

## Four-state

CODE COMPLETE / TEST VERIFIED on branch only. **Not LIVE VERIFIED.** Hermetic mock
provider only; no live Mercury.

## Fallback

Clients should keep poll (`GET .../status`) as fallback when SSE disconnects; poll
responses include `poll.stream` paths pointing at these routes.

## Control-plane UI (PR #138)

Static page: `public/control-plane/think_job_status.html` with
`think_job_status_client.js`.

- Initial `GET .../status` loads `poll.stream` hints (no parallel status plane).
- Subscribe via **fetch + ReadableStream** so `X-API-Key` auth works (EventSource
  cannot set headers fail-closed).
- On SSE error, close, or unsupported body: exponential backoff reconnect (max 3),
  then **degraded poll** at `poll.recommended_interval_ms`.
- Shared logic for tests: `thinkbox/think_job_status_ui.py`.

Four-state: CODE COMPLETE / TEST VERIFIED on branch only — not LIVE VERIFIED.
