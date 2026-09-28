# Multi-Agent Swarm Architecture

**Status**: Code complete, wired into the CLI, makes real (non-tool-calling) calls to Mercury-2 or the local model via `/swarm run`. **No successful live call has been made from this environment** — no `INCEPTION_API_KEY` and no reachable Ollama here — so both paths are verified only up through a clean, honest failure (see "Verification"). It is still not a tool-execution loop; see "Not done" at the bottom.
**Location**: `apps/web/agent-swarm/`
**CLI Integration**: `/swarm` command inside the `kudbee` REPL (same convention as `/memory`, `/model`, `/cat`)

---

## Overview

A **hierarchical multi-agent framework** where a single **orchestrator** manages a team of up to **12 specialized agent roles**. Agents can dynamically spawn **sub-agents** to delegate work, creating a tree-structured organization — bounded by hard depth/agent/budget ceilings so a bad goal string or a bug can't fork-bomb the process.

### Key Features

✅ **12 Agent Roles** — specialized roles for different tasks
✅ **Dynamic Spawning** — agents create sub-agents as needed, bounded by hard ceilings
✅ **Cost-Aware Model Routing** — cheap local model by default for mechanical roles, enterprise model for reasoning roles (extends the routing added in `apps/web/cli.ts` #271)
✅ **Budget Enforcement** — tokens/cost/time are actually debited and checked, not just recorded
✅ **Hierarchical Delegation** — up to 4 levels of agent depth (hard cap)
✅ **Task Management** — assign, track, complete tasks
✅ **Swarm Metrics** — monitor efficiency, cost, progress

---

## Agent Roles

| Role | Purpose | Max Children | Default Model Tier |
|------|---------|--------------|---------------------|
| **orchestrator** | Coordinates swarm, delegates work | 12 | complex (Mercury-2) |
| **planner** | Breaks down tasks, creates roadmaps | 4 | complex |
| **debugger** | Diagnoses failures, suggests fixes | 2 | complex |
| **optimizer** | Improves solutions, refactors | 2 | complex |
| **synthesizer** | Combines results, creates summaries | 1 | complex |
| **supervisor** | Oversees other agents | 6 | complex |
| **researcher** | Gathers info, analyzes data | 3 | local (Qwen2.5 1.5B) |
| **executor** | Performs actions, writes files | 2 | local |
| **validator** | Validates outputs, checks quality | 1 | local |
| **monitor** | Tracks progress, alerts on issues | 0 | local |
| **communicator** | Handles external APIs, messaging | 2 | local |
| **specialist** | Domain-specific work | 3 | local |

"Default model tier" is a starting point, not a hard assignment: a goal that matches the same complexity heuristic `apps/web/cli.ts` uses (`selectModelForGoal`/`isComplexGoal` — code keywords, JSON structure, length > 150 chars) can escalate a local-tier role to the complex model for that one task. See `model-router.ts`.

---

## Architecture

```
Orchestrator (root, depth 0)
├─ Planner (depth 1)
│  ├─ Researcher (depth 2)
│  └─ Executor (depth 2)
│     └─ Optimizer (depth 3)      ← depth 4 would be the last allowed level
├─ Researcher (depth 1)
├─ Executor (depth 1)
├─ Validator (depth 1)
├─ Optimizer (depth 1)
└─ Monitor (depth 1)
```

### Hierarchy constraints (all actually enforced, not just documented)

| Constraint | Value | Enforced in |
|---|---|---|
| Max depth | 4 levels (root = depth 0) | `spawnAgent()` — rejects with `reason` before creating the child |
| Max total agents (swarm-wide) | 64 | `spawnAgent()` — backstop independent of any single parent's `maxChildren` |
| Max children per parent | Per-role, see table above | `spawnAgent()` |
| Budget floor | Parent needs enough tokens left to fund a child | `spawnAgent()` |
| Goal text | Control characters stripped, capped at 4000 chars, empty rejected | `sanitizeGoal()` in `orchestrator.ts` |
| Message queue | Capped at 5000 entries (oldest dropped) | `sendMessage()` |

The per-role `maxChildren` table alone does **not** bound the tree — an orchestrator with 12 children, each themselves able to spawn, multiplies out fast. The depth cap and the swarm-wide agent ceiling are the actual backstop; they were added and verified with an adversarial spawn-flood test (chain-spawn past depth 4, then flood-spawn past the ceiling) before this was called done.

---

## Model Routing (cost-aware)

`model-router.ts` extends the CLI's existing simple/complex heuristic to per-role defaults:

- Mechanical/lookup roles (researcher, executor, validator, monitor, communicator, specialist) default to the cheap local model.
- Reasoning/coordination roles (orchestrator, planner, debugger, optimizer, synthesizer, supervisor) default to the enterprise agent model.
- A goal matching the complexity heuristic can escalate any role to the complex model for that task.
- **No fake savings**: if the local model isn't confirmed pulled (`localAvailable`), routing falls back to the complex model honestly and says so — same contract as `apps/web/cli.ts`'s `selectModelForGoal`.

`SwarmOrchestrator`'s constructor takes an optional `RouterModels` config; `apps/web/cli.ts` passes one built from `client.models` (the server's live model list) the first time `/swarm` is used, so `localAvailable` reflects whether Qwen2.5 1.5B is actually pulled into Ollama — not a hardcoded guess.

Budgets are also tier-scaled: local-tier roles get roughly 30% of the token/cost footprint a complex-tier role gets by default (`budgetMultiplierForRole`), reflecting that their default model is far cheaper per call.

**Known quirk, not a bug**: the shared complexity heuristic flags goals containing words like "research", "analyze", "debug" as complex. A `researcher` role's typical goal text ("research the topic", "analyze the data") matches that same pattern, which escalates it to the complex-tier model almost every time in practice — the per-task escalation is working as designed, it just means "researcher defaults to local" is a weaker guarantee in practice than the role table suggests. Worth revisiting the heuristic (or giving swarm roles their own goal-independent tier) if that escalation rate turns out to defeat the cost-saving purpose of tiering at all.

---

## CLI Usage

Commands live inside the `kudbee` interactive REPL as `/swarm <subcommand>` — same dispatch convention as every other slash command in `apps/web/cli.ts` (`line.split(/\s+/)`, no shell quoting). Everything after the subcommand and any required IDs is space-joined as the goal text, so you don't quote it.

```
kudbee› /swarm start Analyze user data and generate insights

✅ Swarm initialized with orchestrator: orchestrator-91348bef

🚀 Swarm started: Analyze user data and generate insights
📍 Orchestrator: orchestrator-91348bef
💰 Budget: 100000 tokens, $100

👥 Building initial team...

🤖 Spawned agent: planner-1 (planner-2641e219) → model=mercury-2
   ✓ planner         → planner-2641e219
🤖 Spawned agent: researcher-1 (researcher-95f98f2e) → model=qwen2.5:1.5b
   ✓ researcher      → researcher-95f98f2e
🤖 Spawned agent: executor-1 (executor-6f2a4234) → model=qwen2.5:1.5b
   ✓ executor        → executor-6f2a4234
🤖 Spawned agent: validator-1 (validator-87819fed) → model=qwen2.5:1.5b
   ✓ validator       → validator-87819fed
🤖 Spawned agent: optimizer-1 (optimizer-b5ef437a) → model=mercury-2
   ✓ optimizer       → optimizer-b5ef437a
🤖 Spawned agent: monitor-1 (monitor-678018df) → model=qwen2.5:1.5b
   ✓ monitor         → monitor-678018df

kudbee› /swarm tree

🌳 Agent Hierarchy

├─ 🔵 orchestrator-1 (orchestrator)
  ├─ 🔵 planner-1 (planner)
  ├─ 🔵 researcher-1 (researcher)
  ├─ 🔵 executor-1 (executor)
  ├─ 🔵 validator-1 (validator)
  ├─ 🔵 optimizer-1 (optimizer)
  └─ 🔵 monitor-1 (monitor)

kudbee› /swarm status

📈 Swarm Metrics
   Agents: 7 total, 7 active
   Tasks: 0 complete, 0 failed
   Efficiency: 0.0%
   Cost: $0.00
   Tokens: 0
   Depth: 1 levels

kudbee› /swarm spawn planner-1 researcher
🤖 Spawned agent: researcher-2 (researcher-...) → model=qwen2.5:1.5b
✅ Spawned: researcher-...

kudbee› /swarm task planner-1 Analyze the requirements doc
✅ Task assigned: task-...

kudbee› /swarm run planner-1
⏳ Running planner-6c1fabf3…
❌ planner-6c1fabf3 failed: INCEPTION_API_KEY is not set — cannot call mercury-2

kudbee› /swarm stop

🛑 Swarm shutdown
{ "totalAgents": 8, "activeAgents": 6, "failedTasks": 1, "totalCost": 0, "totalTokens": 0, ... }
```

All output above is from an actual `node --experimental-strip-types` run against this code, not hand-written — see "Verification" below. `/swarm run planner-1` failing with a clear `INCEPTION_API_KEY is not set` message (rather than a fabricated answer or a silent success with `cost: $0.00`) is the correct, honest result in an environment with no key configured — it's the same failure `apps/web/agent.ts`'s own `inceptionConfigured()` gate would produce for the single-agent path.

Every command after `spawn`/`task`/`run`'s first argument accepts either the agent's short display **name** (`planner-1`, as printed above) or its full ID (`planner-6c1fabf3...`) — `resolveAgentRef()` tries an exact ID match first, then a name match, and the CLI reports a clear "no agent matches" error rather than a stack trace if neither resolves.

### Command reference

| Command | Effect |
|---|---|
| `/swarm start <goal>` | Create orchestrator + spawn the 6-role starter team (planner, researcher, executor, validator, optimizer, monitor) |
| `/swarm agents` | Agent/task counts |
| `/swarm tree` | Hierarchy view with status per agent |
| `/swarm status` | Cost, tokens, efficiency, depth |
| `/swarm spawn <parent> <role>` | Manually spawn a sub-agent (role validated against the 12 known roles; `<parent>` accepts name or ID) |
| `/swarm task <agent> <goal>` | Assign a task; delegates to a spawned researcher unless the agent is already at max depth |
| `/swarm run <agent>` | **Actually calls** the agent's routed model (Mercury-2 via Inception, or the local model via Ollama) with its pending task's goal, records real token/cost usage, and marks the task complete or failed based on a real response — see "Model Execution" below |
| `/swarm stop` | Shut down and print final metrics |

An unrecognized role, a missing/unresolvable agent reference, or a swarm-wide limit hit all print a clear `❌ ...` message rather than failing silently or throwing an unhandled rejection into the REPL.

---

## Model Execution (`/swarm run`)

`model-client.ts` makes a real, single-shot chat completion call — **not** the tool-calling loop in `apps/web/agent.ts`. It dispatches on the agent's routed model name (`isInceptionModel()`, same check `apps/web/agent.ts` uses):

- **Mercury-2** → `POST {INCEPTION_BASE_URL}/chat/completions` with the `INCEPTION_API_KEY` bearer token, same base URL and pricing table (`costUsd()`) as the existing single-agent path — imported directly from `apps/web/agent.ts` rather than duplicated, so the two paths can't drift out of sync on pricing.
- **Local model** → `POST {OLLAMA_BASE_URL}/api/chat` with `stream: false`. Local calls cost `$0`.

`SwarmOrchestrator.runAgent(agentId)` finds the agent's most recent non-terminal task, makes the call, and:
- **On success**: `completeTask()` with the real response text, `recordSpend()` with the real `prompt_tokens`/`completion_tokens`/cost the API reported.
- **On failure** (no key, unreachable host, non-2xx, empty completion): `failTask()` with the real error message. Nothing is fabricated and no spend is recorded for a call that didn't happen — verified by running both failure paths in an environment with neither Mercury-2 nor Ollama configured (no fake `$0.00 success`, real `❌ ... failed:` output with the actual cause).

No tool use (`write_file`, `fetch_url`, etc.) happens through this path — it's a plain question-in, answer-out call. Giving swarm agents real tools means bridging to `apps/web/agent.ts`'s `runToolAgent`/`AgentHooks`, which needs a real per-agent workspace and a concurrency-safe approval flow; that's out of scope here (see "Not done").

---

## Budget System

Each agent has:

```typescript
budget: { tokens: number, cost: number, time: number }
```

### What's real vs. what's bookkeeping

- **Inheritance/scaling** (`scaledBudget`): when a parent spawns a child, the child's requested budget is scaled by the role's cost tier and capped by what the parent has left. This happens whether or not you pass explicit `tokens`/`cost` in the spawn request — omit them (as the starter-team builder does) to let tier scaling apply; pass them explicitly only when you need to override the default for one spawn.
- **Debit on spawn**: the parent's budget is reduced by the committed child budget *immediately*, not just recorded — so a parent can't over-commit the same tokens to many children before any of them report spend back.
- **`recordSpend(agentId, { tokens, cost, timeMs })`**: decrements an agent's remaining budget and rolls the spend into swarm-wide `totalCost`/`totalTokens`. **`SwarmOrchestrator.runAgent()` calls this automatically** after every real model call made through `/swarm run` — it is no longer purely a manual hook. `getMetrics().totalCost`/`totalTokens` will still read `0` if every call so far has failed closed (no key, unreachable Ollama) — that's the honest state, not a bug (see "Verification").
- **Budget floor on spawn**: a parent with too little budget left is refused a new child (`"Parent budget too low to fund a child agent"`), rather than spawning a child that inherits a budget of effectively zero.

---

## Security & Limits (what's actually enforced today)

This was built, then adversarially tested against itself before being called done — not just designed on paper:

1. **Depth cap (4 levels)** — verified: chain-spawning past depth 4 is rejected with a clear reason at the exact boundary.
2. **Swarm-wide agent ceiling (64)** — verified: exists independently of per-role `maxChildren` so a wide-then-deep spawn pattern can't bypass it.
3. **Per-role `maxChildren`** — verified: root (orchestrator, `maxChildren=12`) refuses a 13th child.
4. **Budget floor + immediate debit** — verified: draining a parent's budget via `recordSpend` makes the next spawn attempt fail closed rather than proceeding with a near-zero budget.
5. **Goal sanitization** — control characters stripped, length capped at 4000 chars, empty-after-cleaning goals rejected (`initialize`, `spawnAgent`, `assignTask` all go through this).
6. **Tool authorization gate** — `isToolAllowed(agentId, tool)` checks a tool call against the agent's role-scoped tool list. **This is a gate a caller must invoke** — it isn't automatically enforced on any execution path yet, because there is no execution path wired in yet. Anyone wiring the swarm to `apps/web/agent.ts`'s tool loop must call this before dispatching a tool, the same way that loop's own approval gates work today.
7. **Unbounded message queue** — capped at 5000 entries, drops oldest rather than growing forever.
8. **Role validation on the CLI boundary** — `/swarm spawn <parent> <role>` rejects an unrecognized role string before it reaches orchestration logic, listing the 12 valid roles.
9. **Real model calls fail closed** — `/swarm run` never fabricates a response or records spend for a call that didn't happen. Verified against both backends with neither configured: a clear `INCEPTION_API_KEY is not set` for Mercury-2, a clear "unreachable at http://127.0.0.1:11434 ... ollama pull ..." for the local model, `getMetrics().totalCost`/`totalTokens` staying at `0`, and the task correctly marked failed (not silently dropped).
10. **Name-or-ID resolution at the CLI boundary** — `resolveAgentRef()` tries an exact ID, then a name match, and the CLI prints a clear "no agent matches" rather than orchestration logic seeing a raw, unresolved user string. Found because an early hand-test used the printed name (`planner-1`) where the code expected the full ID and got a confusing "Agent not found" — fixed rather than left as a gotcha.

### What this does NOT do (explicit non-goals for this pass)

- **No cross-process or cross-machine coordination.** Everything above lives in one Node process's memory. No persistence across restarts, no distributed locking, no network-addressable agents.
- **No telephony or external communication tool.** The `communicator` role has a declarative tool list (`send_message`, `fetch_url`, `log`) but nothing wires it to an actual phone/SMS/voice API. If you want that, it's a new gated tool added to `apps/web/agent.ts`'s toolset, behind the same approval-gate pattern as the existing `fetch_url` tool — not something to bolt on inside the orchestrator.
- **Single-shot calls only, no tools.** `/swarm run` makes one real question-in/answer-out call to Mercury-2 or the local model (`model-client.ts`) and records the real result — but it does not give the agent `write_file`/`fetch_url`/etc. Wiring an agent's `context.model` decision to the actual tool-calling loop (`apps/web/agent.ts`'s `runToolAgent`) — with a real per-agent workspace and a concurrency-safe approval flow for potentially several agents running at once — is the next real integration step, not done here.
- **No authentication.** Same posture as the rest of `apps/web` today — keep this on localhost.

---

## Implementation Files

| File | Purpose |
|------|---------|
| `types.ts` | `AgentRole` union + `ALL_AGENT_ROLES`/`isAgentRole` runtime validators, `AgentConfig`, `AgentTask`, `SwarmState`, `AgentMessage`, spawn request/response, `SwarmMetrics` |
| `model-router.ts` | Per-role model tier defaults, complexity-based escalation, budget tier multiplier — extends `apps/web/cli.ts`'s routing heuristic |
| `model-client.ts` | Real single-shot model calls — Mercury-2 via Inception's `/chat/completions`, local model via Ollama's `/api/chat`; fails closed with `ModelCallError`, reuses `costUsd`/`inceptionConfigured`/`isInceptionModel` from `apps/web/agent.ts` |
| `orchestrator.ts` | `SwarmOrchestrator` — spawn/assign/complete/fail lifecycle, depth/ceiling/budget enforcement, goal sanitization, tool authorization gate, name-or-ID resolution, message queue, `runAgent()` (real execution), tree + metrics reporting |
| `cli-integration.ts` | `SwarmCLI` — the `/swarm` subcommand handler wired into `apps/web/cli.ts` |
| `index.ts` | Public exports |

All imports use explicit `.ts` extensions and `import type` for type-only imports, matching this project's `NodeNext` + `verbatimModuleSyntax` `tsconfig.json` and its `node --experimental-strip-types` execution model. Note: TS parameter-property shorthand (`constructor(private x: T)`) is **not** supported by `--experimental-strip-types` (it desugars to a runtime assignment, not just type erasure) — this bit us once during development and is called out in a comment on `SwarmCLI`'s constructor so it doesn't get reintroduced.

---

## Verification

Since `apps/web/node_modules` isn't installed in the environment this was built in, verification was done by direct execution rather than a full `tsc` project check:

```bash
# Syntax check every file
node --experimental-strip-types --check apps/web/agent-swarm/*.ts
node --experimental-strip-types --check apps/web/cli.ts

# Functional smoke test (adversarial): depth cap, agent ceiling, maxChildren,
# budget exhaustion, goal sanitization, unknown role/command handling,
# name-vs-id resolution, and /swarm run's two real-call failure paths
node --experimental-strip-types <a scratch script importing SwarmOrchestrator/SwarmCLI>
```

All of the "Security & Limits" claims above were confirmed this way, not just asserted, including the two `/swarm run` failure paths — this sandbox has neither `INCEPTION_API_KEY` nor a reachable Ollama daemon (confirmed with a plain `curl` before writing `model-client.ts`, not assumed), so both backends were exercised down to a real network attempt / real "key missing" check, and confirmed to fail with a clear message rather than fabricate a result. **No successful live call to Mercury-2 or a local model has been made against this code** — that verification is still owed once you're on a machine with a real key or Ollama running.

**Before you rely on this**, run `npm install && npx tsc --noEmit -p apps/web/tsconfig.json` once `node_modules` exists locally — the strip-types syntax check catches parse errors but not type errors, and `verbatimModuleSyntax`/`NodeNext` have sharp edges (see the parameter-property note above) that a full project check would catch that a syntax check can't.

---

## Not done / follow-ups

- **No automated test file** (e.g. `tests/agent-swarm.test.ts`) — verification so far is the adversarial scratch-script runs described above, not a committed, repeatable test suite. Given this repo's own AGENTS.md testing rules (§3), add one before treating this as done rather than "verified once."
- **No successful live model call verified.** `/swarm run` is wired to real Mercury-2/Ollama HTTP calls and both failure paths (no key, unreachable host) are confirmed honest, but nobody has run it with a real `INCEPTION_API_KEY` or a real Ollama daemon yet — do that before treating the happy path as trustworthy, not just the failure path.
- **Not wired to a real tool-execution loop.** `/swarm run` is a single-shot question/answer call, not `apps/web/agent.ts`'s tool-calling loop — no `write_file`, `fetch_url`, etc. `context.model` per agent now drives a real dispatch, but only to a plain chat completion.
- **No persistence.** A swarm's state disappears when the process exits or `/swarm stop` runs.
- **No concurrency control across agents.** `runAgent()` has no lock or in-flight guard — if two `/swarm run` calls for related agents ever overlapped (e.g. a pasted multi-line command, or a future automated caller), nothing in this code prevents them from racing on the same budget bookkeeping. Not verified either way whether `apps/web/cli.ts`'s current single-user REPL can actually produce that overlap; flagging as an open question rather than asserting it's safe.

---

## Next Steps (when you're back on the local machine)

```bash
git fetch origin claude-kudbee/gracious-bohr-7sx86a
git checkout claude-kudbee/gracious-bohr-7sx86a
cd apps/web && npm install && npx tsc --noEmit -p tsconfig.json
```

Then try it for real:

```bash
kudbee
kudbee› /swarm start Analyze the repo and suggest one improvement
kudbee› /swarm tree
kudbee› /swarm status
kudbee› /swarm stop
```

If `tsc` finds anything the strip-types syntax check couldn't (type errors, a missed extension), fix those first. Then decide whether the next real step is wiring `recordSpend`/`isToolAllowed` into `apps/web/agent.ts`'s loop, or writing the committed test suite — both are listed above as not done, and either is a more honest "next" than adding more agent roles.
