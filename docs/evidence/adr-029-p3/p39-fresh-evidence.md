# ADR 029 P3.9: fresh evidence beats memory (2026-10-02)

Mercury spend: about **$0.01** (one live run of about $0.004, one extraction and one challenge call).

## The incident

On the founder's server, the goal "WHAT PR ARE WE WORKING ON?" got the answer "PR #304 (draft)". The run's own first tool call (`fetch_url` on the GitHub pulls API) had returned `[]`, no open pull requests. The answer matched a recalled memory, "Open PR state 2026-09-30", which is a snapshot: the worker repeated an old note over a fresh tool result, and a memory written with "this note decays" was shown to the planner with no date or age.

## What changed

1. **Rule in the system prompt** (`evidence.ts` `EVIDENCE_RULE`, used by `agent.ts`): "Tool results from THIS run outrank recalled memories and lessons. If they conflict, trust the tool result, say the memory is stale, and never answer from memory alone when a tool already answered." It also tells the planner that anything about live state marked STALE must be verified with a tool.
2. **Dates and staleness.** Recalled memories show `updated <date>`; Think Tokens show `saved <date>`. Text about live state (open PRs, CI/checks, servers, ports, balances, deploys, drafts) older than 24 h is labeled `STALE, verify with a tool`. The label is by wording, so a note that never uses those words cannot be flagged.
3. **Final-answer check** (`agent.ts`): a deterministic gate (`conflictCandidate`) fires only when a tool result in this run was empty or failed (empty list, zero count, HTTP error, `ok:false`) **and** the answer asserts a concrete state (a `#NNN`, "is open/running/passing", a count) without saying it found nothing. A model call then confirms the conflict. If confirmed, the model is retried once, without tools, with the conflict spelled out; if the retry still conflicts, the answer is replaced by `FLAGGED: ... What the tools said: ...`. An unusable judge reply leaves the answer alone. `THINKBOX_EVIDENCE_CHECK=off` disables it. The gate is heuristic: an answer that contradicts a tool in other ways (for example a wrong number from a non-empty result) is not checked.
4. **Failures become learnable.** The run record stores `evidence_conflicts`; it flows into the run view the extractor sees, with a line in the extraction prompt that a lesson about avoiding that mistake is worth keeping.

## Evidence

| Item | CODE | TEST | LIVE | PROD |
|---|---|---|---|---|
| Rule in the system prompt; dated/STALE labels in the planner context | yes | yes (`tests/evidence.test.ts`) | yes (the live run's context carried the recalled note) | no |
| Final-answer check, retry, flag | yes | yes: incident replay + CI-status case + server-down case + retry-still-conflicts + no-extra-call + unusable judge, with a scripted model; mutation checks fail the tests when the gate or the retry is removed | **not triggered live** (see below) | no |
| Failure recorded as a lesson via the normal path | yes | yes (extraction stores `when_to_use`; `evidence_conflicts` reaches the run view) | yes: **TT-000007** (below) | no |
| Stale memory retired | n/a | n/a | yes (local file) | n/a |

### Regression tests (`tests/evidence.test.ts`)
- Incident replay: the stale "#304 draft" memory is in the planner context (labeled `2026-09-30, STALE, verify with a tool`), the tool returns `[]`, the scripted model first repeats #304, the judge says conflict, the retry (no tools, conflict in the prompt) says there are no open pull requests, and the result says so. Pass condition: "no open pull requests".
- Two more conflict cases: CI memory says passing but the API reports zero workflow runs; server memory says running but the health check returns 503.
- The scripted model proves the plumbing, not real-model judgment.

### Live run (real Mercury 2, real server path, copy of the real data directory with the stale memory present)
`scripts/live-evidence-check.mjs`, raw in `p39-live-open-prs.json`. The recalled memories included "Open PR state 2026-09-30"; the model fetched `api.github.com/.../pulls?state=open` (`[]`), the HTML pulls page, and the closed list, and answered: no open pull requests; the most recent merged PR is #320. No evidence conflict was recorded, so the final-answer check did not have to fire: with the rule and the STALE label the model answered correctly the first time. One run only; it shows the incident goal now passes, not that the check catches a bad answer from a real model (the incident cannot be re-provoked on demand).
Not exercised: the request was served from a copy of the data directory made while the real server held a write-ahead log, so it saw only the main database file (no accepted lessons); the live run was on a sibling server, not on :3000, which keeps running the old code until you restart it.

### The lesson (normal extract/challenge path, real DB)
The founder's run was rebuilt from the pasted terminal transcript (same goal, the same two `fetch_url` calls and answer) with the `evidence_conflicts` entry the new check records, and passed through `processFinishedRun` with real Mercury against `apps/web/data/think-tokens.db` (backed up first as `think-tokens.db.bak-pre-incident-20261002`). Result: **TT-000007**, accepted, challenge `pass` by `mercury-2`: "Trust fresh tool output over stale memory. If a tool like fetch_url returns an empty list of PRs, do not fall back to an old cached answer. Instead, report that no open PRs were found or use a secondary source (e.g., HTML) to verify. This prevents repeating outdated information." It was not hand-inserted, but the run record is a replay with an added conflict note, not a live capture.

### Stale memory
`apps/web/data/memory/org/open-pr-state-2026-09-30-main-is-the-merged-baseline.md` (local, gitignored): title now starts `[SUPERSEDED 2026-10-02]`, tag `superseded`, and a notice says not to use it as the current PR list. The original text is kept below the notice and as a copy in `apps/web/data/memory-backups/`. The running server loads memory at start, so it needs a restart to see the change.

## UNPROVEN
- That a real model's judge call catches a real conflict reliably (only a scripted model was used for the check path).
- Anything about answers that contradict a non-empty tool result.
- The staleness labels depend on keywords.
