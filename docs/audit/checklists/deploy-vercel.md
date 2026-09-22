# Vercel / preview deploy checklist

**Scope inspected (PR #125):** static control-plane HTML under `public/control-plane/`, Node app `apps/web/`, Python FastAPI `backend/`.

| Surface | Expected host | Repo artifact | Vercel fit |
|---------|---------------|---------------|------------|
| Control-plane HTML | CDN / static | `public/control-plane/*.html` | Static export or `public/` root — needs project config |
| Web shell | Node ≥22 | `apps/web/server.ts` (Express + WS) | Serverless limits on WebSocket; not Next.js |
| API | Python 3.10+ | `backend/main.py` (FastAPI) | Requires Python runtime or separate host |

## Blockers (2026-09-22)

1. **No `vercel.json`** in repository — routing/build not defined.
2. **No `VERCEL_*` credentials** in this cloud agent environment — preview deploy not attempted.
3. **Split stack** — FastAPI backend + Express `apps/web` + static control-plane; single Vercel project may be wrong topology.

## If founder enables preview

1. Add `vercel.json` (static `public/control-plane` **or** `apps/web` with explicit `builds`).
2. Set env vars per `docs/guides/setup.md` / backend `backend/security.py` (API keys via env only).
3. Capture preview URL + HTTP 200 on `/control-plane/index.html` in `data/thinkboxmd/artifacts/` and reference in pass JSON — then only claim **LIVE_VERIFIED (preview)**.

**Status:** DOCUMENTED BLOCKED — not LIVE_VERIFIED, not PRODUCTION.
