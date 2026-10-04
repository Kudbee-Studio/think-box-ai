# P3.21 dashboard live verification (#360)

Real Chromium (Playwright, headless) against the real `server.ts` at 1440, 1024 and 390 px wide.
The model behind the server is a scripted stand-in (`tests/helpers/mock-inception.ts`), so no provider was contacted and nothing cost money.
Reproduce: `cd apps/web && npx playwright install chromium && npm run test:e2e` (opt-in; not part of `npm test`).

- Machine-readable results: [results.json](results.json) (24 of 24 steps passed, generated 2026-10-04).
- One screenshot per step and viewport sits next to it (`1440-*.png`, `1024-*.png`, `390-*.png`), including `*-governance-approval-pending.png` and `1440-startup-guard-error.png`.

## Four-state table

| Item | CODE COMPLETE | TEST VERIFIED | LIVE VERIFIED | PRODUCTION READY |
|---|---|---|---|---|
| #356 window manager + taskbar | yes | yes (fake DOM) | yes, after 6 fixes below (drag, resize, minimize, maximize, close, reload restore, header toggle at 3 widths) | no |
| #357 workflow save/load + Actions | yes | yes | yes, after 3 fixes (builder layout, Load list, templates draggable/click/keyboard) | no |
| #358 agent tracking + governance window | yes | yes | yes, after 2 fixes (ghost "2 running", window size): "1 running" badge, steps and tokens shown, Approve and Reject from the governance window | no |
| #359 switchable profiles | yes | yes | yes for create/switch/isolation/restore through the header switcher; export/import at API level only (the dashboard has no export/import control) | no |
| CodeQL fix (profile import, memory write) | yes | yes | n/a | no |
| Freeze fix (taskbar render loop) | yes | yes | yes: before/after below | no |
| Startup guard (error panel + Retry) | yes | yes | yes (WebSocket blocked, panel shown, Retry recovers) | no |
| Flake fix (ports, orphaned server) | yes | yes (3 full runs green, no leaked processes) | n/a | no |

LIVE VERIFIED here means real browser plus real server, with a scripted model. It does not mean a real Mercury or Ollama model.

## Freeze regression (introduced by #356, found by this run)

Before: `WindowManager._syncTaskbar` emptied and rebuilt the taskbar inside `document.body`; the same manager observes `body` with a `MutationObserver`, and every observer callback ended in `_syncTaskbar`. Each rebuild queued another callback, an endless microtask loop. The page never painted or answered input: an endless spinner, models never loaded. The fake-DOM tests cannot see this.
After: the rebuild is skipped when nothing it shows changed, mutations inside the taskbar are ignored, and minimize syncs explicitly.
Proof both ways is part of the script (`w pre-fix freeze is caught by the watchdog`): the #356 `window-manager.js` from `origin/main` is served to the page and the page stops answering within 3 s; every other step runs against the fixed file with 0 taskbar rebuilds per second at rest.

## Bugs found by the browser run and fixed

1. Taskbar render loop froze the page (above).
2. A new window opened over the header and covered the buttons that open the next window.
3. A window could be dragged or resized partly off the right edge (a 300 px window hung off a 390 px screen).
4. After a reload every restored panel stayed an unmanaged full-screen backdrop covering the whole dashboard (observer started after `restore()`).
5. After a reload each restored window took the last-clicked opener, so a header button closed the wrong window.
6. A static panel closed by hiding it (workflow builder, approval modal...) was never registered again when reopened: no taskbar entry, dead title-bar buttons.
7. Workflow builder: three columns squeezed to a sliver in a floating window; the Load list collapsed to 0 px.
8. Workflow templates had no `draggable="true"`, so a mouse user could not add a step at all; click and Enter/Space now add one too.
9. Agent registry revived the last finished agent as a ghost when `status: running` arrived before the run existed ("2 running" for one goal).
10. Governance window opened too small: the Approve/Reject row was below the fold.
11. CSP listed `ws://[::1]:PORT`, which Chromium rejects as an invalid source (a console error on every load).
12. `launch.mjs` fallback used `spawnSync`, so stopping the launcher orphaned the server and its port.
13. Five generated `routes/*.js` mirrors were tracked in git (the launcher rewrites them on every start).

## CodeQL (local, CodeQL CLI 2.27.1, security-extended, diffed against `origin/main`)

| Language | main | #360 | New alerts |
|---|---|---|---|
| JavaScript/TypeScript | 36 | 35 | 0 (the `memory.ts` http-to-file-access alert is gone; #359's two `profiles.ts` alerts never reach main) |
| Python | 21 | 21 | 0 |

## Other gates (clean worktree)

- `npm run typecheck` and `npm run lint` clean.
- Full `npm test`: 869 of 869, three runs in a row; no server or browser process left behind.
- `npm run test:coverage`: 90.67% lines, 83.27% branches, 95.07% functions (threshold 90% lines).
- `npm audit`: 0 vulnerabilities.

## Flake root causes

- 21 test files picked `20000 + random()` for their server port while `node --test` runs files in parallel: two servers could pick the same port (the health probe was answered by the other server) and the range overlaps the OS's own outbound ports. All now use `tests/helpers/free-port.ts`.
- `launch.test.ts` leaked one server per full run: the `KUDBEE_NO_BUILD` fallback blocked in `spawnSync`, so SIGTERM never reached the server. Fixed in `launch.mjs`; a new test proves the server stops with its launcher.

## UNPROVEN

- A real Mercury or Ollama model driving the dashboard (the model was scripted).
- Real touch input at 390 px (desktop Chromium with a 390 px viewport; no touch emulation; HTML5 drag is not exercised at 390 px, click and Enter are).
- Browsers other than Chromium.
- GitHub Actions: CI could not run (account billing lock), so none of the repository's CI jobs ran for this branch; the local equivalents above did. The local CodeQL version may differ from the one GitHub runs.
- Profile export/import from the dashboard UI (no control exists; proven through the API).
- The 120 s approval auto-deny path in a browser.
