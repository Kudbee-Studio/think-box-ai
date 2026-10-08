# P3.80 first-run setup, install script, run summary (product ideas 1, 2, 3)

| # | Item | State | Basis |
|---|---|---|---|
| 1 | `GET /api/setup` + Tools > Get started checklist (connect a model, first goal, spend limit, health check). Opens by itself once on a fresh install until dismissed. | PROVEN for the rules, the route and the rendering (tests/setup-status, setup-route, setup-panel). Key values never appear in the response; a blank or example-placeholder key does not count; a reachable Ollama counts. UNPROVEN in a real browser, including the auto-open and the dismiss memory. |
| 1 | `kudbee init` creates an owner-only `.env` from `.env.example`, never overwrites | PROVEN (tests/install-init.test.ts) |
| 2 | `install.sh` (`--check` reports node >= 22.6, git, npm and changes nothing; otherwise npm install, links `kudbee` into ~/.local/bin, runs init and doctor) | `--check` and the "node too old" refusal PROVEN. The install path itself (npm install, symlink) was NOT run in this change; it is UNPROVEN. |
| 3 | `GET /api/runs/:id/summary` and a plain card after each run (what changed, cost, steps, approvals, contradiction warning, next steps) | PROVEN for the summary rules and wiring (tests/run-summary, setup-panel). UNPROVEN on a live run in the browser. |

## Not claimed
- `npx kudbee` does not exist: nothing is published to npm. The installer works from a clone.
- No Windows (non-WSL) or macOS testing; the installer is bash and the sandbox is Linux-only.
- The wizard does not take a key in the browser: keys are put into `.env` by the user (no secrets through the dashboard).
- The summary lists files the run wrote; it does not show the diff, which stays in the Changes panel.
