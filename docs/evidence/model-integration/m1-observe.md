# M1: read-only repository investigation by a local worker (OBSERVE mode)

Branch `feat/think-token-observe-loop`. First slice of the autonomous-coding roadmap from the architecture audit. Nothing is written to the repository.

## What was built

- **`repo_search` and `repo_read`** ([repo-tools.ts](../../../apps/web/repo-tools.ts)): literal search and numbered-line reads, confined to the repo with symlink-safe reads. Secrets, `.env`, keys, databases, `.git`, `node_modules` and the app's data folders are not readable. Size, match and time caps. They live in the one tool registry but are **opt-in**: not offered, and refused, unless a run's allowlist names them, so Mercury's default tools did not change.
- **A finding contract and validator** (`grounding.ts`, the same module as the live-data validator): a worker reports one finding `{file, line, quote, claim, absence_search?}`. The file must have been read, the line returned by a tool, the quote present at that line in the tool output, backticked identifiers present in the evidence, and any claim of absence ("no tests", "unused", "without any tests", ...) backed by a recorded repo search that found nothing and was not cut off. After that the runner **re-reads the quote from disk** itself.
- **A generalized local tool loop** (`local-tools.ts` `LoopSpec`): the same loop serves live lookups and repo investigations, for native tools (Qwen) and constrained JSON (Gemma). The report option is withheld until a tool call has returned something. A rejected report gets one round of feedback naming the unsupported claims.
- **Mayor/Convoy**: a `repo` worker kind, a `think_mode` (OBSERVE and LEARN plan; SIMULATE and AUTONOMOUS are refused until they exist), a policy rule stating what the mode allows, local-model-only in this version.
- **Thought persistence** (requested by the founder): dashboard thoughts were in memory only and vanished on reload. They are now saved per profile in SQLite (secrets redacted, size-capped, bounded), replayed on connect, and removed by the dashboard's Clear. The dashboard's `init` handler had also been discarding the server's thoughts.

## Live results (real Qwen 2.5 3B through Ollama, the real repository, real server; `tests/e2e/observe-live.ts`)

| Goal | Outcome | What happened |
|---|---|---|
| "Find one function in apps/web that has no test" (attempt 1, before the report option was withheld) | FAILED `no_tool_call` | the model invented `apps/web/someFunction.ts:123 itCanBeUsed()` without looking; the loop refused it |
| same goal (attempt 2) | COMPLETED, GROUNDED (wrongly) | the finding was real, but "without any tests" was not recognized as a claim of absence, so no proof was required. **A validator gap, found by this run and fixed** |
| same goal (attempt 3) | FAILED `grounding_failed` | the same finding, now correctly rejected: no search proves absence |
| same goal (attempt 4, with the feedback round) | COMPLETED, `found: false` | after the rejection the model gave up. Honest, not a verified finding |
| "Find one exported function in apps/web/repo-tools.ts" | COMPLETED, GROUNDED, disk re-check passed | `apps/web/agent.ts:20` `export function costUsd(...)`; my script's independent read confirmed the quote at that line |

So: the loop, the validator and the disk check work against the real repo, and the small model's weakness showed up as rejections, not as bad findings accepted. **The 3B model did not complete the two-step "prove it has no test" task in four tries.** The easy goal passed, but the finding cited `agent.ts`, not the `repo-tools.ts` I named: grounded means true, not necessarily on-topic, so a human must still judge relevance.

## UNPROVEN

- Gemma on this loop (too slow here to include) and Mercury (repo investigation is local-only in this version).
- Any model completing the absence-proof task live.
- Goal-relevance of a finding (not checked by code).
- Human approval of the *outcome* (only the convoy is approved before it runs).
- M2 (convoy outcome feeding Think Token candidates, a job-state projection, a dashboard tab) is not built yet.
