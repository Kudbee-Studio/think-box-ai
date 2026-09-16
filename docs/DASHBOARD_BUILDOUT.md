# Dashboard → Middleware → Backend — Build-Out List

**Goal:** connect the visualisation surface to the swarm runtime with **no heavy
servers, no framework, no daemon fleet**. Everything below is stdlib or a single
optional binary, and every step is independently shippable.

**Current state (2026-09-15):** the dashboard and the swarm share one SQLite
directory and one JSONL event stream. That is already a working "middleware" —
it just hasn't been named or hardened.

```
 ┌────────────┐   writes    ┌───────────────────────────┐   reads   ┌──────────────┐
 │ big_swarm  │ ──────────► │ SQLite (black box)        │ ────────► │ dashboard    │
 │ (runtime)  │             │ + swarm_events.jsonl      │           │ (1 process)  │
 └────────────┘             │ data/thinkboxmd/db/*.db   │           └──────────────┘
                            └───────────────────────────┘                    │
                                                                   cloudflared tunnel
                                                                             │
                                                                      iPhone / browser
```

## Principle: files over servers

| Concern | Do NOT add | Do instead |
|---------|-----------|-----------|
| Transfer state | Redis/Kafka/NATS | SQLite + append-only JSONL |
| Push updates | WebSocket cluster | short-poll `/api/*` (2.5 s) |
| Build tooling | webpack/vite | one inline HTML string |
| Server runtime | FastAPI/gunicorn | `http.server.ThreadingHTTPServer` |
| Auth | OAuth server | Cloudflare Access (zero code) |

A single `ThreadingHTTPServer` process plus a file is enough for the demo, a
team, and a founder review. Introduce infrastructure only when a measured
bottleneck demands it (see §5).

---

## Phase 0 — Already done (today)

- [x] `experiments/swarm_dashboard.py` — one stdlib process, mobile-first, 6 tabs
- [x] Read-only SQLite access (`file:…?mode=ro`) so the dashboard can never corrupt runtime data
- [x] JSONL event stream as the live bus (`data/thinkboxmd/swarm_events.jsonl`)
- [x] `/api/live`, `/api/strength`, `/api/instruments`, `/api/proof`, `/api/sessions`, `/healthz`
- [x] CSP / `X-Frame-Options` / `nosniff` / `Referrer-Policy` headers
- [x] Cloudflare quick tunnel for a phone-viewable link

## Phase 1 — Harden the middleware (½ day)

- [ ] **Single source of truth for paths.** Extract `data/thinkboxmd/` + DB names
      into one module (`thinkbox/paths.py`) imported by swarm, dashboard, and tests.
      *Why:* today three files independently hardcode `data/thinkboxmd/db/…`.
- [ ] **Read-only enforcement.** Assert the dashboard opens every DB `mode=ro`
      (already true) and add a startup check that fails loudly if a DB is missing.
- [ ] **Event rotation.** Cap `swarm_events.jsonl` (e.g. 5 MB) with a
      `swarm_events.1.jsonl` rotation so long runs stay fast to read.
- [ ] **Schema version table.** Add `schema_version` to each DB; dashboard shows a
      banner if it is older than the code expects.
- [ ] **Structured error surface.** Any handler exception returns
      `{"error": "...", "trace": "..."}` instead of a stack trace.

## Phase 2 — Optional auth + always-on link (½ day)

- [ ] **Cloudflare Access in front of the tunnel.** Zero application code; kills
      the "anyone with the URL can read the swarm" problem.
- [ ] **Named tunnel** (`cloudflared tunnel create kudbee-dash`) instead of the
      quick tunnel, so the URL is stable and survives restarts.
- [ ] **Bind to `127.0.0.1` only** (already true) — never `0.0.0.0`.
- [ ] **Read-only token for the API** if the tunnel is ever made public:
      `Authorization: Bearer <token>`, compared with `hmac.compare_digest`.

## Phase 3 — Backend integration (1 day)

- [ ] **Mount the dashboard API in `backend/main.py`** as `/dash/*` reusing the
      same reader functions, so one service serves both the engine API and the view.
- [ ] **Expose the existing `/run` endpoint** as a dashboard action: a
      "Run swarm" button POSTs to `/api/run` which shells the same
      `big_swarm.BigSwarm` entrypoint the CLI uses.
- [ ] **Use `backend/audit_storage.py`** alongside `thinkbox/ledger.py` so the
      existing audit log and the hash-chain ledger are reconciled in one view.
- [ ] **Reuse `core/sessions.py`** for session titles/notes so dashboard sessions
      and engine sessions are the same entities rather than two ID spaces.

## Phase 4 — Caching (¼ day)

- [ ] **ETag on `/api/strength` and `/api/instruments`** keyed on
      `max(ended_at, file mtime)`; return `304` on match.
- [ ] **Bounded in-process cache** with a 2 s TTL for read-heavy endpoints.
- [ ] **Client cache:** already `no-store` for live, `max-age=60` for HTML.
- [ ] Do **not** add a cache server; SQLite reads at this size are microseconds.

## Phase 5 — Only when measured (scale triggers)

Do these **only** when a number forces it, and record the number in the PR:

- [ ] If dashboard reads exceed ~200 rps → add a read replica SQLite handle per
      thread, or move hot tables to Postgres.
- [ ] If runs exceed ~50k workers → replace JSONL events with a SQLite `events`
      table + `rowid` cursor (still no broker).
- [ ] If multiple machines produce runs → Upstash Redis as a queue and the same
      SQLite schema replicated per worker, not shared.
- [ ] If the tunnel needs to be permanent → named tunnel + Access, still no app code.

---

## Definition of shipped

A stranger on a phone can:
1. open the tunnelled URL and see live compartments colouring in,
2. read the Strength Index and its learning curve,
3. open a proof chain and see it verify,
4. see the genome hash for the run.

…and none of that required a second server process.

## Anti-goals (explicitly rejected)

- Kubernetes, Docker Compose, or a service mesh for a 1-process dashboard.
- A React/Vite build step for six tabs.
- WebSockets before polling is measurably insufficient.
- Any new database before SQLite is measurably insufficient.
