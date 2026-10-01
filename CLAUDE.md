# CLAUDE.md — kudbEE Agent OS Project Guidelines

**Purpose:** This file tells AI (Claude, other agents) how to contribute to this project effectively.

---

## Core Philosophy

**kudbEE is an enterprise-grade agent OS designed for:**
- ✅ Local-first, privacy-preserving execution
- ✅ Model-agnostic (Mercury-2, SmolLM2, Ollama, OpenAI-compatible)
- ✅ Low-latency reasoning with full tool access
- ✅ Transparent, auditable decision-making
- ✅ Persistent memory across sessions

**Non-goals:**
- ❌ Real-time (low-latency APIs are not critical)
- ❌ UI polish over substance
- ❌ Vendor lock-in to any single provider
- ❌ External service dependencies (PHP/SQLite only)

---

## Before You Start

### Read These First (Priority Order)
1. **AGENTS.md** — Architecture principles, coding rules, testing requirements
2. **docs/architecture-v1.md** — Layer discipline, data flow
3. **docs/project-foundation.md** — Dependencies, environment
4. **This file (CLAUDE.md)** — How AI agents should work here

### Key Files You'll Touch
```
apps/web/
├── server.ts           → Backend (Express + WebSocket)
├── agent.ts            → Worker agent loop (Inception client)
├── cli.ts              → Enterprise CLI (model routing, menus)
├── memory.ts           → Hybrid vector search (Upstash + BM25)
├── algorand.ts         → Read-only blockchain queries
├── runs.ts             → Run history persistence
└── public/
    ├── index.html      → Dashboard
    ├── js/app.js       → Frontend logic
    └── css/main-pro.css → Premium styling
```

### Local model setup (token-aware routing)

Simple goals auto-route to a cheap local Ollama model instead of Mercury-2. That
route does nothing until the model is actually pulled:

```bash
ollama list   # see which local models you already have; do not pull new ones for this
```

Set `THINKBOX_LOCAL_MODEL` (older name `KUDBEE_LOCAL_MODEL`; read by `cli.ts`, `server.ts` and the Think Token pipeline through `local-model.ts`) to a model from `ollama list`. If you do want the default `qwen2.5:1.5b`, you pull it yourself; nothing here does. Override the tag with the variable (read by both `cli.ts` and
`server.ts`). Without a matching tag in `ollama list`, routing falls back to
Mercury-2 and reports `route_reason: auto_fallback_no_local` with
`tokens_saved_est: 0` — it never claims savings that didn't happen. `/models` in
the CLI shows whether the configured local model is actually installed.

---

## Quality Standards

### 1. Architecture Layers (AGENTS.md §1.1)

**The system has 5 layers. Never violate this.**

```
┌─ LAYER 5: Runtime    (agent.ts, cli.ts, server.ts)
├─ LAYER 4: Tools      (tools registry, plugins)
├─ LAYER 3: Governance (approval gates, audit logs)
├─ LAYER 2: Providers  (Mercury-2, Ollama, OpenAI-compatible)
└─ LAYER 1: Foundation (config, logging, errors, memory)
```

**Rule:** A layer may ONLY import from layers beneath it.

### 2. Provider Independence (AGENTS.md §1.2)

**NO provider SDKs in runtime code.** Ever.

✅ Good:
```typescript
// apps/web/agent.ts
const response = await modelClient.chat(messages, tools);
// modelClient is generic ModelProvider protocol
```

❌ Bad:
```typescript
// Don't do this!
import Anthropic from "@anthropic-ai/sdk";
const client = new Anthropic();
```

### 3. Testing (AGENTS.md §3)

**Every PR must include tests.**

```bash
npm test  # Must pass before merge
```

**Coverage targets:**
- 80% for core logic
- 100% for critical paths (tool execution, memory writes)
- No new failures allowed

**Test strategy:**
- Unit: Pure logic, no I/O, no network
- Integration: Real SQLite/Upstash (with mocks if needed)
- E2E: Full agent loop with mock provider

---

## Common Tasks

### Adding a New Tool/Plugin

1. **Define the interface** in `tools/base.ts`
   ```typescript
   export interface Tool {
     name: string;
     description: string;
     schema: Record<string, any>;  // JSON schema for arguments
     permission: 'read_only' | 'read_write' | 'exec' | 'restricted';
     run(args: Record<string, any>): Promise<any>;
   }
   ```

2. **Implement the tool** in `tools/{name}.ts`
   ```typescript
   export class MyTool implements Tool {
     name = 'my_tool';
     permission = 'read_only';
     async run(args) { /* ... */ }
   }
   ```

3. **Register in the registry** in `agent.ts`
   ```typescript
   const tools = {
     my_tool: new MyTool(),
     // ...
   };
   ```

4. **Test it** in `tests/integration/test_my_tool.ts`
   ```typescript
   test('my_tool works with valid input', async () => {
     const tool = new MyTool();
     const result = await tool.run({ /* valid args */ });
     expect(result).toBeDefined();
   });
   ```

5. **Update AGENTS.md** with:
   - Tool name, permission level, description
   - Example usage in the CLI

### Adding Memory Layers

Memory has 4 layers. Each layer is immutable after creation and has specific rules:

| Layer | Scope | Write Rule | Query | Lifetime |
|-------|-------|-----------|-------|----------|
| **session** | One live connection | Transient (in-memory) | WebSocket events | Connection ends |
| **task** | One finished run | Auto-save (goal → outcome) | Search by goal | Forever |
| **org** | Organization knowledge | Agent's `/remember` tool | Hybrid Upstash + BM25 | Forever |
| **verified** | Ground truth | Human promotion from org only | Hybrid search | Forever |

**Rules:**
- ✅ Session layer is temporary (no persistence)
- ✅ Task layer auto-populates from run metadata
- ✅ Org layer requires external evidence (fetch_url, file, etc) to save
- ❌ Never store unverified claims in org/verified layers

---

## Commit Message Format

```
type(scope): subject line under 50 chars

Longer description explaining the change. Why, not what.
Reference related PRs/issues: fixes #271, relates to PR 272

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>
```

**Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

**Scope:** `agent-os`, `memory`, `tools`, `cli`, `dashboard`, `server`, `infra`, `security`

**Example:**
```
feat(cli): add interactive model selector with token optimization

- Add /select command for interactive model picker
- Implement selectModelForGoal() for smart routing
- Simple goals → SmolLM2 (60% token savings)
- Complex goals → Mercury-2 (full toolkit)
- Enterprise feel: organize models by capability

See docs/PR272_DASHBOARD_REDESIGN.md for context.

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>
```

---

## Merge policy

You may merge your own PRs under the standing authority and gates in `AGENTS.md` section 0.1 (local green, CI green, evidence section, diff reviewed,
guardrails intact). The review checklist below is what you check before merging your own PR.

## Review Checklist

**Before I approve a PR, I check:**

- [ ] **Layers:** No cross-layer imports or violations
- [ ] **Provider:** No hardcoded provider SDKs (only protocols)
- [ ] **Tests:** New tests added, all passing, no regressions
- [ ] **Memory:** Correct layer usage, evidence gates respected
- [ ] **Docs:** AGENTS.md updated, CLAUDE.md respected
- [ ] **Commit:** Message format correct, attribution included
- [ ] **No bloat:** Only changes needed for the task
- [ ] **Performance:** No obvious O(n²) or N+1 queries
- [ ] **Security:** No secrets, no world-readable files, localhost-only by default

---

## Performance Targets

| Metric | Target | Current |
|--------|--------|---------|
| Agent startup | < 500ms | 100-200ms ✅ |
| Memory recall | < 100ms | ~65ms ✅ |
| Dashboard load | < 1s | ~300ms ✅ |
| Run persistence | < 500ms | ~50ms ✅ |
| API response | < 100ms | ~20-50ms ✅ |

**If a change breaks these, document why and propose mitigation.**

---

## What NOT to Do

### ❌ Don't over-engineer

```typescript
// Too much abstraction:
class BaseFactory<T extends Provider<K extends Model>> { ... }

// Better: Simple, direct code
class Client {
  async chat(model: string, messages: any[]) { ... }
}
```

### ❌ Don't add features "for later"

```typescript
// Premature:
async function cacheStrategyFactory(strategy: string) { ... }

// Just write:
async function cache(key: string, value: any) {
  this.store[key] = value;
}
```

### ❌ Don't add flags or toggles without shipping

```typescript
// Bad: Dead code
if (process.env.EXPERIMENTAL_XYZ) { ... }

// Better: Ship the feature or don't
const newBehavior = true;
```

### ❌ Don't skip testing for "simple changes"

**All changes need tests.** Especially simple ones (they're where bugs hide).

### ❌ Don't "just commit" without AGENTS.md

**Every product change updates Markdown.**  No exceptions. This includes:
- New tools/plugins → Update tool list in AGENTS.md
- New memory features → Document layer changes
- CLI commands → Update `/help` and AGENTS.md
- Performance changes → Note the impact

---

## When to Create a New PR

Each PR should be **focused and self-contained:**

✅ **One PR per feature**
- "Add Algorand read-only queries" (one PR)
- "Add Mercury-2 worker agent" (one PR)
- "Improve dashboard styling" (one PR)

❌ **Never mix concerns**
- Don't mix security fixes + refactoring
- Don't mix features + performance work
- Don't mix styling + business logic

**Exception:** Security fixes can break this rule if absolutely necessary.

---

## Testing Strategy

### Unit Tests (Fast)
```bash
npm test  # Runs in < 5 seconds
```

**What to test:**
- Pure functions (parsing, validation, logic)
- Error cases (invalid input, timeouts)
- Edge cases (empty arrays, null values)

**Don't test:**
- External services (mock them)
- UI rendering (screenshot tests are elsewhere)
- Network calls (use mocks)

### Integration Tests (Medium)
```bash
npm run test:integration
```

**What to test:**
- Database operations (real SQLite)
- Memory layer behavior (Upstash mocked, BM25 real)
- Tool execution (with mocks for external APIs)
- API endpoints (real server, mock models)

### E2E Tests (Slow, infrequent)
```bash
npm run test:e2e
```

**What to test:**
- Full agent loop with real tool use
- Memory persistence across runs
- CLI commands end-to-end
- Dashboard workflows

---

## Common Pitfalls

### 1. "This will only be temporary"

**It won't be.** Clean code from the start.

### 2. "Tests can come later"

**They can't.** Tests are part of the PR. No merge without them.

### 3. "This doesn't affect performance"

**Measure it first.** Use `npm run profile` if available.

### 4. "Everyone does it this way"

**We don't.** Justify deviations in commit messages.

### 5. "This is a small fix, skip the PR"

**PR = documentation + testing + review.** Direct commits to main are never OK.

---

## Recommended Workflow

```bash
# 1. Create feature branch
git checkout -b feat/my-feature

# 2. Make changes, test locally
npm test
npm run lint

# 3. Update docs (AGENTS.md, CLAUDE.md, README)
$EDITOR AGENTS.md

# 4. Commit with proper message
git add .
git commit -m "feat(scope): description

Longer explanation.

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"

# 5. Push and create PR
git push origin feat/my-feature
gh pr create --title "PR title" --body "Details"

# 6. Review checks pass
# - CI tests pass
# - Code review approved
# - No merge conflicts
```

---

## Questions?

**Before asking in chat:**
1. Check AGENTS.md (architecture, rules, testing)
2. Check docs/architecture-v1.md (layers, protocols)
3. Check docs/project-foundation.md (environment, setup)
4. Check existing code for similar patterns

**If still stuck:** Ask with context:
- "What's the pattern for adding a new tool?"
- "Does this violate layer discipline?"
- "Is this the right place for this code?"

---

## Attribution

Generated by Claude Haiku 4.5 for kudbEE Agent OS.

**Last updated:** 2026-09-27

---

**Good luck! 🚀**
