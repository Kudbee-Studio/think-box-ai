# M2: job state, LEARN mode, and the READY / OPEN / REVIEW / FINISHED board

Branch `feat/think-token-m2-lanes` (stacked on #363). Nothing is merged or written to the repository by any of this.

## Think Token job state (projection, no new store)

`convoy-job-state.ts` replays a convoy's real facts into the existing 100-cell reducer (`think-cube-state.js`): identity and planned jobs from the plan; worker boxes, propagation steps, locked evidence, disrupted validation cells and the jury verdict from the run; token-state cells when the convoy learned a token. It is recomputed on every read, so it cannot disagree with the convoy. `repair`, `harvest` and `commons` have no convoy signal and stay off; the view says so.

## LEARN mode

Plans take a mode. OBSERVE reads only and learns nothing. LEARN also lets a **verified** success (COMPLETED, GROUNDED, outcome success) run the existing Think Token pipeline **with no model**, so only the deterministic template extractor can write, and everything it writes is a `candidate` (never auto-accepted, no model spend). A failed, partial or ungrounded convoy teaches nothing. A lesson already in the store is reported as "already known", not as new. The template extractor now counts `live_lookup`, `repo_search` and `repo_read` as evidence tools (it only knew the older ones). SIMULATE and AUTONOMOUS are shown in the window but cannot be chosen: the planner refuses them.

## Emergency stop

`convoy_stop` aborts exactly one running convoy: its workers stop at their next step and the convoy ends FAILED with "stopped by operator", keeping the evidence so far.

## The agent board

Words follow Gas City, from its own explainer ([how-gas-city-works.md](https://github.com/gastownhall/gascity/blob/main/docs/getting-started/how-gas-city-works.md), read 2026-10-05): work items move `open` → `in_progress` → `closed`, and a bead with an open blocker is invisible to agents until the blocker closes (that is "ready"). The same page says review is **not** a built-in state there; reviewers are configuration. So REVIEW is ours and means one thing:

| Lane | A worker is here when |
|---|---|
| READY | its convoy is approved and every worker it depends on has finished, but nobody has taken it |
| OPEN | it is running |
| REVIEW | it produced a result (success or partial) and a human has not yet accepted or rejected the outcome |
| FINISHED | the outcome was accepted or rejected, or there was nothing to accept (failed, ungrounded, skipped, cancelled, rejected plan, expired) |

A worker whose plan is still waiting for approval, or whose blocker has not finished, is not on the board (the board counts them). The board is a pure view over convoys (`convoy-board.ts`), never a second store.

**Outcome review** fills the gap flagged in the architecture audit (only the plan was human-approved, never the result): `ConvoyStore.review()` accepts only `human`, only once, only for a finished convoy with something to judge, and the decision (who, when, why) is an entry in the convoy's hash-chained evidence log. **Rejecting retires the Think Token candidates that convoy created** (never a lesson that already existed); accepting an outcome does not accept a lesson.

Surfaces: the Convoys window (four lane columns with counts, Accept and Reject on REVIEW cards and in the convoy detail, a Think Token section with the 100-cell cube) and CLI `/convoy board`, `/convoy review ID accept|reject [note]`, `/convoy plan --mode learn`.

## About the notes you pasted

Those notes say hosted Gas Town's Refinery merges by itself. I could not verify that from the Gas City docs I read, which say review is configuration. Either way, nothing here merges anything: REVIEW is a human decision and the merge gates stay yours.

## Evidence

- Unit and server tests: job state, runner LEARN/stop rules, board lanes (including dependency-blocked workers), review rules and chain, a real server test for the board, accept, reject and token retirement.
- Real Chromium (fake services, 17 of 17 steps at 1440 and 390 px): mode selector, job-state cube with a CANDIDATE token, board lanes, a REVIEW card accepted by click moving to FINISHED.
- **Real services** (`CONVOY_MODE=learn npm run test:e2e:convoy-real`, real GitHub, real Qwen and Mercury): both COMPLETED and GROUNDED in LEARN mode and the Think Token section showed a stable job with a candidate (`convoy-real-learn-e2e.json`).

## UNPROVEN

- The real-model run did not click the REVIEW lane (the fake-service run did).
- The CLI board and review commands are parity-tested but were not run by hand against a live server with real convoys.
- Candidates come from the deterministic template extractor only, so they are generic ("Ground X in evidence"); whether such tokens ever help a worker is unproven (the repo's own A/B tests found no benefit from retrieving lessons).
- SIMULATE and AUTONOMOUS do not exist yet.

## Beads and dashboard integration (added in the same PR)

**Beads.** `convoy-beads.ts` is a pure view that gives every convoy a *convoy bead* (`tb-1a2b3c4d`) and every worker a *task bead* under it (`tb-1a2b3c4d.lookup-1`), in Gas City's terms: status `open` → `in_progress` → `closed`, `blocked_by`, `ready` (open with no open blocker), and `waiting_for` (a human's approval of the plan, or other beads). A worker's result stays `in_progress` (lane REVIEW) until a human accepts or rejects it, then it closes. It is a view over the convoys, not a store, so it cannot drift from them. `GET /api/beads?status=&type=&ready=1` serves it; board cards carry their bead id and blockers. Not done: importing from or exporting to the real Beads (`bd`) ledger.

**Layered process windows** (`public/js/process-windows.js`). Every agent has its own popup, and each step deeper opens another popup over it: **Agent** (lane, bead, blockers, model, cost, grounding, result, Accept/Reject, Stop) → **Run steps** → **Tool call** (arguments, output) → **Evidence** (lookup items or repo lines, the finding, the disk re-check). They are ordinary managed windows, so each has a title bar, a taskbar entry, drag and resize, and opens over the one that opened it; reopening one brings it forward, and open windows re-read the convoy on every update.

**Where it plugs into the existing dashboard:**
- the agent registry now ingests `convoy_update`, so convoy workers are agents with a lane and a bead; the taskbar shows `N running · M to review` and lane tags, and picking a convoy agent opens its Agent window (the generic governance window still serves other agents)
- a header chip `READY n · OPEN n · REVIEW n` that pulses when a result waits for a human, and opens the Convoys window
- a **Plan as convoy** button next to Run that carries the goal and model typed in the goal bar to the planner
- board cards open the Agent window

**Evidence:** Chromium at 1440 and 390 px, 19 of 19 steps, including a step that opens card → Agent → Run steps → Tool call → Evidence as four layered windows (z-order checked, no duplicates, closing one keeps the rest) and checks the chip and the goal-bar button (`convoy-1440-i-four-layered-windows.png`). Registry unit tests for convoy workers as agents. **UNPROVEN:** the layered windows against real-model runs in a browser (the browser run used fake services).
