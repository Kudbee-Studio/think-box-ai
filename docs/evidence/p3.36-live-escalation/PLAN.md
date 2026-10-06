# P3.36 live check of the escalation lane through the real server: pre-registration (written BEFORE the run)

Question: does the escalation lane (#371) work through the real path an operator uses, a convoy planned, approved and run by the server, with a real Ollama model, real Mercury and the real dashboard? #371's 35-goal run called the shared `attemptRepo` directly; the server path (Mayor plan naming the escalation, human approval, the convoy runner's second worker, run records, cost, dashboard) had unit tests only. This is an integration check, not a statistical experiment, so the criteria are stated as pass/fail facts.

## Setup (frozen)
- A real server (`server.ts`) on a random 127.0.0.1 port with a throwaway data dir; `KUDBEE_REPO_ROOT` = the deterministic fixture repository of the P3.34 held-out world (`startHeld2World`, hash `9fb7ce053a04baaf70b2bfb11b2c07ecbbbdd209424e21bf4319de014b1818fd`); the real Mercury key from `.env` (never printed or written); real Ollama (`qwen2.5:3b` installed locally); `KUDBEE_DAILY_BUDGET_USD=0.05`. The founder's own server on :3000 is not touched (the script refuses to run if its random port is taken, and never uses :3000).
- Real Chromium driven by Playwright. Every click (plan, submit, approve the convoy) is made through the dashboard UI. The clicker is Playwright, not a person: the honest limit of this proof. The model field is left BLANK so the plan's model comes from the measured routing table.
- Six goals, fixed now: the first three `HELD2_GOALS` (untested function in a named file); "Which file defines CAP_3 and what is its value?" (expected `src/playlist.ts`, 35); "Which file defines CAP_8 and what is its value?" (expected `src/cron.ts`, 70); "Find a function named dissolveQuasar." (does not exist). One run each, in this order; none is edited or repeated.

## Pass criteria (all must hold; each is checked by the script from the server's own records)
1. Every plan names an escalation to `mercury-2` (`plan.escalation.model`) and a local first worker.
2. Every convoy reaches COMPLETED with grounding GROUNDED. The five positive goals' final findings pass the fixture's machine check (right file, right function or value); the missing-function goal reports `found=false`.
3. For every convoy WITH an `escalation-1` worker: its model is `mercury-2`, its cost is above 0, the convoy has two child runs, the first worker did not itself produce an accepted finding for a goal that expects one (it failed, was not grounded, was not on disk, or reported "no finding" on an untested-function or constant goal), and the second run's events include the `spend:` line.
4. For every convoy WITHOUT an escalation worker: the first worker completed GROUNDED, its cost is 0, and it either found something or the goal is the missing-function goal.
5. At least 2 of the 6 convoys escalate. Otherwise the run is **INCONCLUSIVE** for the escalation path (the local model solved too much to exercise it) and is reported as such, not as a pass.
6. Total convoy cost <= $0.05; the Mercury key value appears nowhere in any API response or page text the script fetched; no browser console errors; the server on :3000 was never contacted.
7. A screenshot of the first escalated convoy's detail (both workers visible) is saved.

## Known limits (stated now)
- Six goals, one local model, one run each: this shows the path works, not how often.
- The fixture is the same synthetic family as the experiments; GitHub lookups and specialist convoys are not exercised.
- Playwright clicks, not a person; the approval gate is exercised but its human judgement is not.
