# Product acceptance: can a new user get a verified fix on their own repository?

Written 2026-10-07 after running the flow against real servers started from the merged code and this branch, with real models, in a real browser where a browser is named. It is an acceptance **walk-through**, not a statistical test: each step was run once.

## The flow, and what happened

| # | Step (what a customer does) | Result | Evidence |
|---|---|---|---|
| 1 | Open the dashboard | A plain three-step first-run guide; the header is one row with every control visible from 1024 to 2560 px; the model picker shows measured cost and speed (`⚡ mercury-2 — Inception · ~$0.0021/task · 2.6 s`) | PRs #399, #405 (P3.65), Chromium screenshots |
| 2 | Paste a GitHub repository link in Files, Clone | An approval modal appears (it leaves the machine); the clone appears in the Files panel | P3.60, Chromium |
| 3 | Reload the page | The clone and any files the agent made are still there (one workspace per profile) | P3.60 tests and Chromium |
| 4 | Press "use for agent" | The row shows an AGENT REPO badge; the choice is saved per profile and survives a restart | P3.61 tests and Chromium |
| 5 | Ask a question about the repository | The repository convoy completed in one pass: "README:1 — The file `README` contains the text `Hello World!`", $0.0003 (it failed before two defects were fixed in P3.64) | convoy `104fb39c` (FAILED) vs the re-run (COMPLETED) |
| 6 | Ask for a fix (SIMULATE) on a repository selected with "use for agent" | Mercury proposed the one-line fix for $0.0026; the plan offered only the checks the repository defines (`lint, test`); a human approval was requested for the sandbox run; the sandbox ran `lint` (passed) and `test` (3 passed, 0 failed); verdict `verified: yes`; the change was NOT applied to any working tree | convoy `47eec9f4`; before the generic-checks fix (P3.66) the same request ended PARTIAL: "NOT VERIFIED: the checks were not run (dependencies are not installed in apps/web)" |
| 7 | See the cost and which model ran | Every step prints tokens and dollars; xAI models use the provider's billed cost; a provider failure before the run does anything retries on the next-best model and says so | P3.54, P3.56 |

## What stayed true throughout
Every step that writes, runs code or leaves the machine asks first; the verdict is built by code; a failed or unverifiable result is labelled as such, not smoothed over (step 6's first attempt and step 5's first attempt are the proof).

## Limits (stated, not hidden)
- **Node (npm) projects only** for the sandboxed checks: a repository needs a `package.json` (at its root or in `apps/web`) with at least one of the scripts `lint`, `typecheck`, `typecheck:tsc` or `test`. Other languages: the agent can read and propose changes, but nothing verifies them.
- **A project that declares dependencies must have them installed** already: the sandbox has no network, so it refuses (with the reason) rather than pretend. The step 6 repository declared none.
- Step 6 used a small repository placed in the profile's workspace with `git init` (a seeded one-line pagination bug and three tests), not a fresh GitHub clone: the clone and "use for agent" legs were proven separately on `octocat/Hello-World`. The same environment setting carries both, but they were not chained in one run.
- One run of each step; one browser (headless Chromium); one operator. The models' success rates come from the frozen-task experiments (66 tasks per model), not from this walk-through.
- The founder's own story and walkthrough video on the website are still empty by design.
