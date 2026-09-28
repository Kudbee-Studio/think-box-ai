# Multi-Agent Swarm Architecture

**Status**: Code complete, hermetically tested, wired into the CLI. **Not** run against the live Mercury-2/Inception path — this is orchestration scaffolding (spawn/budget/routing bookkeeping), not a tool-execution loop. See "Not done" at the bottom.
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

kudbee› /swarm task orchestrator-91348bef Analyze the requirements doc
✅ Task assigned: task-...

kudbee› /swarm stop

🛑 Swarm shutdown
{ "totalAgents": 8, "activeAgents": 8, ... }
```

All output above is from an actual `node --experimental-strip-types` run against this code, not hand-written — see "Verification" below.

### Command reference

| Command | Effect |
|---|---|
| `/swarm start <goal>` | Create orchestrator + spawn the 6-role starter team (planner, researcher, executor, validator, optimizer, monitor) |
| `/swarm agents` | Agent/task counts |
| `/swarm tree` | Hierarchy view with status per agent |
| `/swarm status` | Cost, tokens, efficiency, depth |
| `/swarm spawn <parent-id> <role>` | Manually spawn a sub-agent (role validated against the 12 known roles) |
| `/swarm task <agent-id> <goal>` | Assign a task; delegates to a spawned researcher unless the agent is already at max depth |
| `/swarm stop` | Shut down and print final metrics |

An unrecognized role, a missing parent, or a swarm-wide limit hit all print a clear `❌ ...` message rather than failing silently or throwing an unhandled rejection into the REPL.

---

## Budget System

Each agent has:

```typescript
budget: { tokens: number, cost: number, time: number }
```

### What's real vs. what's bookkeeping

- **Inheritance/scaling** (`scaledBudget`): when a parent spawns a child, the child's requested budget is scaled by the role's cost tier and capped by what the parent has left. This happens whether or not you pass explicit `tokens`/`cost` in the spawn request — omit them (as the starter-team builder does) to let tier scaling apply; pass them explicitly only when you need to override the default for one spawn.
- **Debit on spawn**: the parent's budget is reduced by the committed child budget *immediately*, not just recorded — so a parent can't over-commit the same tokens to many children before any of them report spend back.
- **`recordSpend(agentId, { tokens, cost, timeMs })`**: call this after an agent actually makes a model call, to decrement its remaining budget and roll the spend into swarm-wide `totalCost`/`totalTokens`. **This orchestration layer does not call it automatically** — there's no LLM call wired in yet (see "Not done"). A caller wiring this to `apps/web/agent.ts`'s tool loop must call `recordSpend` after each real call, or `getMetrics().totalCost`/`totalTokens` will stay honestly at zero, same as they do today.
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

### What this does NOT do (explicit non-goals for this pass)

- **No cross-process or cross-machine coordination.** Everything above lives in one Node process's memory. No persistence across restarts, no distributed locking, no network-addressable agents.
- **No telephony or external communication tool.** The `communicator` role has a declarative tool list (`send_message`, `fetch_url`, `log`) but nothing wires it to an actual phone/SMS/voice API. If you want that, it's a new gated tool added to `apps/web/agent.ts`'s toolset, behind the same approval-gate pattern as the existing `fetch_url` tool — not something to bolt on inside the orchestrator.
- **No LLM calls.** `SwarmOrchestrator` is bookkeeping — agent lifecycle, hierarchy, budget accounting, model *routing decisions*. It does not itself call Mercury-2, Ollama, or anything else. Wiring an agent's `context.model` decision to an actual tool-calling loop (`apps/web/agent.ts`) is the next real integration step.
- **No authentication.** Same posture as the rest of `apps/web` today — keep this on localhost.

---

## Implementation Files

| File | Purpose |
|------|---------|
| `types.ts` | `AgentRole` union + `ALL_AGENT_ROLES`/`isAgentRole` runtime validators, `AgentConfig`, `AgentTask`, `SwarmState`, `AgentMessage`, spawn request/response, `SwarmMetrics` |
| `model-router.ts` | Per-role model tier defaults, complexity-based escalation, budget tier multiplier — extends `apps/web/cli.ts`'s routing heuristic |
| `orchestrator.ts` | `SwarmOrchestrator` — spawn/assign/complete/fail lifecycle, depth/ceiling/budget enforcement, goal sanitization, tool authorization gate, message queue, tree + metrics reporting |
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
# budget exhaustion, goal sanitization, unknown role/command handling
node --experimental-strip-types <a scratch script importing SwarmOrchestrator/SwarmCLI>
```

All of the "Security & Limits" claims above were confirmed this way, not just asserted. **Before you rely on this**, run `npm install && npx tsc --noEmit -p apps/web/tsconfig.json` once `node_modules` exists locally — the strip-types syntax check catches parse errors but not type errors, and `verbatimModuleSyntax`/`NodeNext` have sharp edges (see the parameter-property note above) that a full project check would catch that a syntax check can't.

---

## Not done / follow-ups

- **No automated test file** (e.g. `tests/agent-swarm.test.ts`) — verification so far is the adversarial scratch-script runs described above, not a committed, repeatable test suite. Given this repo's own AGENTS.md testing rules (§3), add one before treating this as done rather than "verified once."
- **Not wired to a real tool-execution loop.** `apps/web/agent.ts` has its own Mercury-2 tool-calling loop with its own approval gates; this swarm doesn't call it yet. `context.model` per agent is a *decision*, not a dispatch.
- **`recordSpend` isn't called automatically anywhere** — it exists so a future integration can call it after real model calls; right now nothing does, so swarm-wide cost/token metrics stay at zero through a full run (which is the honest state, not a bug).
- **No persistence.** A swarm's state disappears when the process exits or `/swarm stop` runs.

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
