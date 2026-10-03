# PR #341: Phase 3 item 6 — Git panel browser test (/api/git)

**Status:** CODE COMPLETE / TEST VERIFIED. This is a local HTTP/browser-module run, not LIVE VERIFIED
and not PRODUCTION READY.

## What this changes

Phase 3 item 6 asks for a browser-level test of the dashboard Git panel (`/api/git`, mounted and
hardened in #289). `tests/git-routes.test.ts` already drives `/api/git` over HTTP, but only with node
`fetch` — it never exercises the dashboard module the browser actually runs. This PR closes that gap.

| File | Purpose |
|------|---------|
| `apps/web/tests/git-panel-browser.test.ts` | Loads the real `public/js/git-integration.js` into `node:vm` with a `fetch` bound to a real spawned `server.ts` |
| `docs/roadmaps/ROADMAP.md` | Item 6 marked in progress with the test named |

No route, UI, or security change. No new dependency or framework.

## Browser-test mechanism reused

The repository has no browser-automation dependency (no Playwright/Puppeteer; `package.json` devDeps
are types only). The established convention for driving real dashboard scripts is a `node:vm` sandbox
with a small fake DOM (`tests/think-token-dashboard.test.ts`, `tests/git-panel-escaping.test.ts`).
This test follows that convention and additionally binds the sandbox's `fetch` to a real `server.ts`
process — the same spawn pattern `git-routes.test.ts` uses for the API.

## What the test proves (the dashboard-facing path)

1. `loadRepositories()` → `GET /api/git/repos` populates `panel.repositories` from the real route.
2. `openFile()` → `GET /api/git/file` returns the saved content and the correct detected `language`.
3. Traversal reads (absolute canary, `../`, nested `../../`) are refused at the API boundary with
   400/403, never reach the editor, and the canary value never leaks.
4. `saveFile()` → `POST /api/git/save` writes inside the confined git workspace and reads back.

## Tests / results

```
node --experimental-strip-types --no-warnings --test --test-timeout=30000 tests/git-panel-browser.test.ts
# tests 4  # pass 4  # fail 0
```

Existing Git route tests (`tests/git-routes.test.ts`): **7/7 OK**.
Related regression (`git-panel-escaping`, `git-file-tree`, `git-log-format`, `dashboard-lockdown`,
`local-only`): green. A 7-suite combined run showed one flaky failure
(`local-only` → "Janus image service is opt-in"); it passes in isolation and in repeated pair runs,
and is a pre-existing concurrent-server-spawn flake unrelated to this change.

## Mutation proof

- Removing `language` from the `/api/git/file` JSON fails the open-file test (and the save/read-back test): **2 failures**.
- Disabling workspace confinement in `git-repo-manager.ts` (`resolveInside`) fails the traversal test: **1 failure**.
- Both mutations restored; the suite is green again.

## Four-state

| State | This PR |
|-------|---------|
| CODE COMPLETE | yes (browser-boundary test) |
| TEST VERIFIED | yes (4/4 new; git-routes 7/7; mutation-proven) |
| LIVE VERIFIED | **no** — local loopback only, no external service |
| PRODUCTION READY | **no** |

## Notes

- Environment setup: this worktree had no `apps/web/node_modules`; `better-sqlite3` (v13.0.3) ships no
  prebuilt binary for Node 22.23 (ABI 127), so the sandbox build toolchain was installed and the module
  compiled from source. That is environment setup, not a repository change.
- No live UpCloud, GitHub, or other external service was contacted. Clone tests use public-repo URL
  validation only; no network clone occurs.
