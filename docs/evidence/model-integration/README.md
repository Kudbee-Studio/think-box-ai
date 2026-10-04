# Model integration tranche: live-data tool, local tool calling, grounding, convoys, Mayor, queued approvals

Branch `feat/live-data-recipes`. Everything below was run on this machine on 2026-10-04 and 2026-10-05 (UTC).
Real services used where stated: real Ollama (`gemma3:4b`, `qwen2.5:3b`), the real GitHub API for `Kudbee-Studio/think-box-ai`, real Inception `mercury-2`.
Cost of all live Mercury calls together: about $0.04 (cap was $0.20). No secret is printed or stored in any file here.

Machine-readable results sit next to this file:

| File | What it is |
|---|---|
| [live-lookup.json](live-lookup.json) | the five lookup recipes against real GitHub, no model involved |
| [local-tools-live.json](local-tools-live.json) | Qwen and Gemma calling `live_lookup` themselves, real Ollama + real GitHub |
| [live-acceptance.json](live-acceptance.json) | "What is the last PR?" as a convoy on Mercury, Gemma and Qwen, and the governed multi-worker run (dry run, queued approval, live) |
| [convoy-e2e.json](convoy-e2e.json) + `convoy-*.png` | the Convoys window in real Chromium at 1440 and 390 px (13 of 13 steps) |

## Four-state table

| Item | CODE COMPLETE | TEST VERIFIED | LIVE VERIFIED | PRODUCTION READY |
|---|---|---|---|---|
| `live_lookup` tool, normalized evidence (latest PR any state, open PRs, CI, issues, branches) | yes | yes (unit + governed path + fake GitHub) | yes, real GitHub, all 5 recipes, no model | no |
| Local-model tool calling (Qwen native tools, Gemma constrained JSON) | yes | yes (28 cases: success, malformed, denied, tool failure, multi-step, step limit) | yes, real Ollama + real GitHub, one lookup each | no |
| Shared grounding validator | yes | yes (17 + server paths) | yes, it graded the real answers of all three models GROUNDED | no |
| Convoy record (aggregation, drill-down, one row) | yes | yes | yes, API + real browser (fake model) + real models | no |
| Mayor planner, worker budget, policy (dry run only) | yes | yes (18; structural no-I/O check; server-level "nothing ran") | yes, dry run against the live server, nothing ran | no |
| Queued approvals (PENDING to APPROVED to RUNNING to COMPLETED, expiry, reject, human-only) | yes | yes (15 + server) | yes, live: blocked while PENDING, then approved | no |
| Live run with real workers | yes | yes | yes: 3 lookup workers (Mercury, Gemma, Qwen) and 3 specialist workers (Mercury) | no |
| Dashboard Convoys window + CLI `/convoy` | yes | yes | yes in Chromium (fake model); CLI not run against a real model | no |

LIVE VERIFIED here means real service evidence exists for that item. Nothing is PRODUCTION READY: CI did not run (account billing lock) and the list below is not proven.

## "What is the last PR?" on three models (live-acceptance.json)

Same question, same governed tool, same evidence path, same grounding validator. Real GitHub reported #360 as the newest PR (merged); #359 is "closed without merging".

| | Mercury `mercury-2` | Qwen `qwen2.5:3b` | Gemma `gemma3:4b` |
|---|---|---|---|
| Convoy / worker | `431bd834` / `lookup-1` | `5613ca15` / `lookup-1` | `8db56eb7` / `lookup-1` |
| How it asked for the tool | native function calling, offered only `live_lookup` | Ollama native `tool_calls` | JSON schema (`format`); Ollama refuses `tools` for this model |
| Tool call | `live_lookup {recipe: latest_pr}`, ok, 161 ms | same, ok, 350 ms | same, ok, 353 ms |
| Tool calls | 1 | 1 | 1 |
| Approval | first network access to api.github.com, approved (by the script) | same | same |
| Evidence returned | 5 PRs, newest #360 merged | same | same |
| Grounding | GROUNDED (8 numbers, 1 link, 1 id, 1 branch, 1 state checked) | GROUNDED (7 numbers, 1 id, 1 state) | GROUNDED (7 numbers, 1 id, 1 state) |
| Final answer | #360, merged, with its link | #360, merged | #360, merged, by KudbeeZero |
| Tokens | 2,118 | 1,226 | 970 |
| Cost | $0.000669 | $0 | $0 |
| Latency (whole convoy) | 1.6 s | 26.1 s | 208.5 s |
| Approval record | APPROVED by `human`, policy `requires_approval`, risk low, chain verified | same | same |

Against your existing Mercury trace (2 tool calls, about 14k tokens, $0.0039): the same question now takes 1 tool call, 2,118 tokens and $0.000669 on Mercury, because it asks one purpose-built tool instead of fetching raw GitHub JSON twice.
Gemma's 208 s is this machine (a 4B model split across a small GPU and CPU: about 85 s just to load, then slow generation), not a quality problem; all three answers are correct and grounded.

## Governed execution acceptance (live-acceptance.json, `governed`)

Goal: *Write a file notes.md containing exactly one sentence that says what a convoy is in this project.* The Director selects Builder, which pulls in Security and Validator.

1. **DRY RUN** (convoy state `PLANNED`, mode `plan_only`): the Mayor produced 3 workers in dependency order with their tools and permissions, the worker budget use, the policy (requires approval, risk medium) and the expected convoy (1 dashboard row, 3 children). Nothing ran: run records 0 to 0, 0 tool approvals asked, 0 convoy updates, workspace folders 2 to 2.
2. **QUEUED APPROVAL** (`PENDING`): the approval record carries the convoy id, goal, workers, worker budget, policy decision and risk, and an expiry. While pending: 0 runs, all 3 workers `pending`.
3. **APPROVE then LIVE** (over the authenticated socket, as `human`): `COMPLETED`, outcome `success`. Builder `write_file` ok, Security `read_file` ok, Validator `read_file` ok. Cost $0.001963, 3 tool calls, 6,444 tokens, aggregated from the child runs. One convoy row, 0 child runs as top-level rows, evidence chain verified.

### What the live runs found and fixed

The first live runs were not successes, and each failure was a real defect that mocks had hidden:

1. The specialist job re-selected specialists from the goal text and **ignored the approved plan** (the Validator was dropped). It now runs exactly the planned specialists.
2. The Mayor now adds the Validator the job proof requires (as the Director does for Builder), and the reason is part of the plan the human approves.
3. The Validator was never told which artifact to read (`artifact_path` was not among its inputs), so a real model guessed `README.md`. It is now an input.
4. A Security or Validator worker was handed the whole job text ("write notes.md") as its own task and tried to do the Builder's job. Each specialist now gets its own task, its allowed tools and the artifact path.
5. The tool-approval modal was **covered by any open window** (it kept `z-index: 20`; managed windows start at 1000). It only worked at 1440 px because nothing overlapped. Found with the Convoys window at 390 px; the modal is now above all windows, with a test.
6. Two honest outcomes remain by design: a goal with no artifact, or one that involves the read-only Researcher, ends `PARTIAL` because the existing proof needs an artifact the Validator can re-read. The Mayor now warns about both in the plan. The proof was not weakened.

Intermediate live results are kept in `live-acceptance.json` (`governed_first_run_without_validator`).

## Tests

- `npm test`: 996 of 996 pass (was 911 at the start of this tranche); typecheck and lint clean; coverage 91.2% lines, every new module at 98% or more.
- New suites: `live-lookup` (12), `grounding` (17), `local-tools` (28), `mayor` (18), `convoy` (15), `convoy-runner` (12), `convoy-server` (10, real server process), `route-decision` (4).
- Opt-in live scripts: `npm run test:live-lookup`, `test:live-local-tools`, `test:live-acceptance`, `test:e2e:convoy` (Chromium needs `LD_LIBRARY_PATH=$HOME/tools/chromelibs/usr/lib/x86_64-linux-gnu` on this box).

## UNPROVEN

- The tool approvals in every live run were granted **by the script**, standing in for the human reviewer (each grant is recorded). The click-through is proven in real Chromium only against a fake GitHub, fake Ollama and a scripted Mercury stand-in.
- No real model was driven through the dashboard UI in a browser; no real touch input at 390 px.
- The CLI `/convoy` commands are unit-wired and parity-tested but were not run against a live server by hand.
- Convoy cost budgets are enforced at plan time (worst case) and between workers; a specialist job runs as one call, so spend inside it is only checked after it finishes.
- Convoy approval expiry (15 minutes) is proven with an injected clock, not waited out.
- Reading and writing convoys is scoped to the active profile; profile switching during a running convoy was not exercised.
- The GitHub lookups are unauthenticated (60 requests per hour per IP); a rate-limited reply is reported as an explicit failure, not exercised live.
- GitHub Actions did not run (billing lock). CodeQL status: see the PR.
- Researcher-involving specialist jobs cannot pass the existing proof (see above); changing that rule is a separate decision.
