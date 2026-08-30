# Think Box AI — UI Enhancement + Multi-Agent Architecture Plan

**Date:** 2026-08-30
**Status:** Ready for Implementation
**Scope:** Enhance `apps/web/` UI + document multi-agent patterns from KudbeeZero repos

---

## Part A: UI Enhancement (Immediate)

### Goal

Improve the existing Think Box AI web UI (`apps/web/public/`) with professional typography, kinetic motion-transition animations, and refined UI/UX.

### Affected Files

```
apps/web/public/
├── index.html          # Add kinetic welcome, refine structure
├── css/
│   └── main.css        # Add typography scale, animations, enhanced components
└── js/
    └── app.js          # Add KineticType engine, wire animations to existing panels
```

### Design Patterns from `KudbeeZero/kudbee-lemonade`

#### CSS Variable System (Alpha-Based Depth)

```css
--bg-alpha-01: rgba(255, 255, 255, 0.01);
--bg-alpha-02: rgba(255, 255, 255, 0.02);
--bg-alpha-03: rgba(255, 255, 255, 0.03);
--bg-alpha-04: rgba(255, 255, 255, 0.04);
--bg-alpha-05: rgba(255, 255, 255, 0.05);
--bg-alpha-06: rgba(255, 255, 255, 0.06);
--bg-alpha-07: rgba(255, 255, 255, 0.07);
--bg-alpha-08: rgba(255, 255, 255, 0.08);
--bg-alpha-1:  rgba(255, 255, 255, 0.1);
--bg-alpha-2:  rgba(255, 255, 255, 0.2);
```

#### Component Architecture

- **TitleBar** → Think Box AI header (logo, model selector, status)
- **ModelManager (left panel)** → Files + Plugins sidebar
- **LogsWindow (center)** → Terminal panel
- **ChatWindow (right)** → Tasks + Thoughts sidebar
- **StatusBar** → Bottom status indicator
- **ResizableDivider** → Draggable panel dividers

#### Status System

```css
--status-connecting: rgba(255, 165, 0, 0.1);
--on-status-connecting: #ffa500;
--status-connected: rgba(0, 255, 0, 0.1);
--on-status-connected: #00ff00;
--status-error: rgba(255, 68, 68, 0.1);
--on-status-error: #ff4444;
--status-disconnected: rgba(136, 136, 136, 0.1);
--on-status-disconnected: var(--text-secondary);
```

### Typography System

```css
--font-display: 'Inter', 'SF Pro Display', -apple-system, sans-serif;
--font-body: 'Inter', 'SF Pro Text', -apple-system, sans-serif;
--font-mono: 'JetBrains Mono', 'Fira Code', 'SF Mono', monospace;

--text-xs:  10px;
--text-sm:  12px;
--text-base: 14px;
--text-lg:  18px;
--text-xl:  24px;
--text-2xl: 30px;
```

### Animation System

```css
--ease-out-expo: cubic-bezier(0.16, 1, 0.3, 1);
--duration-fast: 200ms;
--duration-normal: 400ms;
--duration-slow: 600ms;
--stagger: 50ms;

@keyframes slideUpFade {
  from { opacity: 0; transform: translateY(12px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes scaleIn {
  from { opacity: 0; transform: scale(0.95); }
  to   { opacity: 1; transform: scale(1); }
}
@keyframes gradientSweep {
  0%   { background-position: -200% center; }
  100% { background-position: 200% center; }
}

.kinetic-hero    { animation: slideUpFade var(--duration-slow) var(--ease-out-expo) both; }
.kinetic-scale   { animation: scaleIn var(--duration-normal) var(--ease-out-expo) both; }
.cascade > *     { animation: slideUpFade var(--duration-normal) var(--ease-out-expo) both; }
.cascade > *:nth-child(1) { animation-delay: calc(var(--stagger) * 0); }
.cascade > *:nth-child(2) { animation-delay: calc(var(--stagger) * 1); }
.cascade > *:nth-child(3) { animation-delay: calc(var(--stagger) * 2); }
.cascade > *:nth-child(4) { animation-delay: calc(var(--stagger) * 3); }

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

### Kinetic Typography Content

**Welcome banner (hero):**
- "What shall we build today?"
- "Ready to optimize your workflow?"
- "Let's craft something exceptional."
- "Your ideas, amplified."

**Contextual status labels:**
- "Analyzing user patterns..."
- "Optimizing search visibility..."
- "Refining interface details..."
- "Ensuring accessibility..."

### UI Implementation Tasks

#### 1. Enhance index.html
- [ ] Add kinetic welcome banner with cycling hero text
- [ ] Add `data-kinetic` attributes to elements that animate
- [ ] Refine header with gradient accent on brand text
- [ ] Add empty-state messages with motion

#### 2. Enhance main.css
- [ ] Add font stack tokens (Inter, JetBrains Mono)
- [ ] Add type scale tokens
- [ ] Add alpha-based depth system (adapted from Lemonade)
- [ ] Add animation keyframes and utility classes
- [ ] Enhance `.btn-*` states (hover lift, active press, focus ring)
- [ ] Enhance `.status-dot` with smoother pulse and status colors
- [ ] Add panel entrance animations (slide-up fade)
- [ ] Add cascade stagger for list items (tasks, files, thoughts)
- [ ] Add gradient sweep for brand text
- [ ] Add `prefers-reduced-motion` support
- [ ] Refine spacing/whitespace for professional rhythm
- [ ] Add toast/notification styling (if applicable)

#### 3. Enhance app.js
- [ ] Add KineticType class with: hero(), cascade(), scaleIn(), wordCycle(), gradientSweep()
- [ ] Wire hero text to cycle through welcome phrases on load
- [ ] Wire cascade animation to panel content updates (tasks, thoughts, files)
- [ ] Wire scale-in to dynamic values (model name, status text, counts)
- [ ] Wire terminal message entrance (slide-up fade per message)
- [ ] Wire empty-state kinetic messages

---

## Part B: Multi-Agent Architecture — How It Actually Works

### Source: `KudbeeZero/kilocode` AgentManager (analyzed `AgentManagerProvider.ts` + `WorktreeManager.ts`)

### Q1: How are sub-agents deployed and run concurrently?

**Answer:** Git worktrees + session forking.

```
1. User creates new agent task
   ↓
2. AgentManagerProvider.onCreateWorktree() called
   ↓
3. WorktreeManager.createWorktree() → git worktree add -b {branch} .kilo/worktrees/{name}
   ↓
4. Creates new CLI session in worktree directory
   ↓
5. Session runs independently on its own branch
   ↓
6. Semaphore(3) limits concurrent git operations to 3
   ↓
7. onForkSession() → clones existing session state into new worktree
```

**Key code from `AgentManagerProvider.ts`:**
```typescript
// Creates a new worktree + session
private async onCreateWorktree(baseBranch?: string, branchName?: string): Promise<null> {
  const created = await this.createWorktreeOnDisk({ baseBranch, branchName })
  await this.runSetupScriptForWorktree(created.result.path, created.result.branch, created.worktree.id)
  const session = await this.createSessionInWorktree(created.result.path, created.result.branch, created.worktree.id)
  state.addSession(session.id, created.worktree.id)
  this.notifyWorktreeReady(session.id, created.result, created.worktree.id)
}

// Forks existing session into new worktree
private onForkSession(sessionId: string, worktreeId?: string, messageId?: string) {
  return forkSession({...}, sessionId, worktreeId, messageId)
}
```

### Q2: How does the "mayor"/head agent work?

**Answer:** `AgentManagerProvider` is the "mayor" — a singleton orchestrator that:
- Owns all worktree state (`WorktreeStateManager`)
- Tracks all sessions (`panelSessions: Set<string>`)
- Routes messages between UI and CLI backend
- Enforces concurrency limits (`Semaphore(3)`)
- Recovers state after interruption

**No separate "mayor" process** — it's a class instance running inside the VS Code extension host. For Think Box AI, this would be a long-running process or service.

### Q3: How does the UI show agent names and navigation?

**Answer:** Messages sent from backend to frontend via `postToWebview()`:

```typescript
// Message types sent to UI
postToWebview({ type: "agentManager.worktreeStats", stats })
postToWebview({ type: "agentManager.worktreeSetup", status: "ready", sessionId, branch, worktreeId })
postToWebview({ type: "agentManager.sessionMeta", sessionId, mode: "worktree", branch, path })
postToWebview({ type: "agentManager.sessionForked", sessionId, forkedFromId, worktreeId })
postToWebview({ type: "agentManager.multiVersionProgress", status, total, completed, groupId })
```

**UI features:**
- Tree view showing worktrees as parent nodes, sessions as children
- Branch names visible for each agent
- Custom labels via `state.updateWorktreeLabel(worktreeId, label)`
- Collapsible sections per worktree
- Tab ordering persisted (`setTabOrder`, `setWorktreeOrder`)
- Visibility tracking (`AgentManagerVisiblePresence`)

### Q4: How do worktrees tie into the frontend?

**Answer:** WorktreeStateManager → postToWebview → WebView UI

```
WorktreeStateManager (state)
  ↓
pushState() → serializes full state
  ↓
postToWebview({ type: "agentManager.state", worktrees, sessions })
  ↓
WebView receives → renders tree view
  ↓
User clicks worktree → onMessage() routes to handler
  ↓
Backend creates/updates/deletes worktree
```

**Worktree metadata stored:**
```typescript
interface Worktree {
  id: string
  branch: string
  path: string
  parentBranch: string
  remote?: string
  label?: string  // Custom name shown in UI
  sessions: Session[]
}
```

### Q5: How does middleware connect endpoints?

**Answer:** `KiloConnectionService` is the middleware layer:

```
Frontend (WebView)
  ↓ postMessage
AgentManagerProvider (orchestrator)
  ↓
KiloConnectionService (connection middleware)
  ↓
KiloClient (SDK) → HTTP/SSE → kilo serve (backend)
  ↓
Core agent runtime → LLM provider
```

**Key middleware responsibilities:**
- Manages WebSocket/SSE connection to backend
- Routes messages to correct CLI backend instances
- Handles reconnection and state recovery
- Provides `getClient()` for API calls
- Provides `getServerConfig()` for configuration
- Registers visible sessions for presence tracking

### Q6: How does state recovery work when internet/connection fails?

**Answer:** Multi-layer recovery:

```typescript
// 1. State persisted to disk
.kilo/agent-manager.json — full worktree + session state

// 2. On restart, recoverWorktrees() reads disk
private async recoverWorktrees(manager: WorktreeManager, state: WorktreeStateManager): Promise<void> {
  const infos = await manager.discoverWorktrees()  // Scan .kilo/worktrees/
  const result = restoreWorktrees(state, infos)     // Rebuild state from disk
  await state.flush()                                // Persist recovered state
}

// 3. Recover missed permission prompts
this.panel?.sessions.recoverPendingPrompts()

// 4. SSE reconnection handled by KiloConnectionService
//    - Automatic reconnection with exponential backoff
//    - Re-registers visible sessions on reconnect
//    - Replays missed stats (cachedWorktreeStats, cachedLocalStats)

// 5. WorktreeStateManager.load() recovers from .kilo/agent-manager.json
//    - If corrupted, state.prepareRecovery() creates backup
```

**For Think Box AI:**
- Persist state to SQLite (already have `core/memory/store.py`)
- On restart, scan worktree directories to rebuild state
- Recover pending tasks from SQLite
- SSE reconnection with replay of missed updates

### Q7: Is PHP used anywhere?

**Answer:** No. The entire Kilo Code stack is:
- TypeScript (VS Code extension, web UI, CLI)
- Node.js (backend server, workers)
- React/Solid (frontends)
- No PHP in any KudbeeZero repos analyzed

**PHP role for Think Box AI:** Not applicable based on reference repos. The AGENTS.md explicitly restricts to Python 3.10+ for core.

### Q8: How are agents tracked across sessions?

**Answer:** `WorktreeStateManager` is the single source of truth:

```typescript
// State structure
{
  worktrees: [
    {
      id: "wt-uuid-1",
      branch: "feat/auth-split",
      path: "/project/.kilo/worktrees/feat-auth-split",
      parentBranch: "main",
      sessions: [
        { id: "sess-uuid-1", status: "idle", model: "claude-sonnet" },
        { id: "sess-uuid-2", status: "running", model: "gpt-4" }
      ]
    }
  ],
  sessions: [...]  // Flat list for quick lookup
}
```

**Tracking mechanisms:**
- `panelSessions: Set<string>` — sessions owned by this panel
- `activeSessionId` — currently selected session
- `visiblePresence` — tracks which sessions user can see
- `staleWorktreeIds` — worktrees pending cleanup
- `toolRequests: Set<string>` — dedup duplicate tool requests

---

## Part C: Think Box AI Multi-Agent Mapping

### Architecture Decision: Monorepo Layers

| Layer | Kilo Code | Think Box AI |
|-------|-----------|--------------|
| Web UI | Solid + WebView | `apps/web/` (HTML/CSS/JS) |
| API | Express + Hono | `backend/` (Python) |
| Worker | Node.js + Redis | Future: Python + Redis |
| Agent Runtime | OpenCode (fork) | `core/runtime/` |
| Storage | SQLite + file | SQLite (`core/memory/`) |
| Connection | SSE + WebSocket | SSE (already in `apps/web/`) |

### Concurrency Model

| Kilo Pattern | Think Box AI Equivalent |
|-------------|------------------------|
| Semaphore(3) | Budget-based (token/iteration limits) |
| Git worktree per agent | Docker container or directory fork |
| Session fork | Think Box spawn |
| Promotion handoff | Observer validates → parent merges |
| State recovery | SQLite state + disk scan on restart |

### Failure Recovery

| Scenario | Kilo Approach | Think Box AI Approach |
|----------|---------------|----------------------|
| Internet outage | SSE reconnect + replay | SSE reconnect + SQLite replay |
| VS Code crash | restoreWorktrees() from disk | N/A (web-based) |
| Session crash | recoverPendingPrompts() | Re-read task state from SQLite |
| State corruption | Backup + recovery mode | SQLite transactions + WAL |

---

## Validation

### UI Enhancement
| Check | Method |
|-------|--------|
| Page loads | Open existing web UI in browser |
| Animations fire | Hero text animates on load |
| Kinetic content | Real terms cycle (not lorem ipsum) |
| No regression | All existing functionality works |
| Accessibility | `prefers-reduced-motion` disables animations |
| Performance | Animations use only `transform` and `opacity` |

### Architecture Patterns
| Check | Method |
|-------|--------|
| Patterns documented | Multi-agent patterns extracted from 3 reference repos |
| Mapping complete | Patterns mapped to Think Box AI equivalents |
| Phase 3 informed | Architecture decisions guide Phase 3 planning |

---

## Out of Scope

- New dashboard or separate app
- Backend changes (Phase 1)
- PHP integration (not in reference repos)
- New features or panels
- Mobile responsive redesign
- Packaging or distribution
- Phase 3 implementation (documented for future)
- Rust/Tauri desktop shell

---

## Risks

| Risk | Mitigation |
|------|------------|
| Animation jank | Only animate `transform`/`opacity` |
| FOIT/FOUT | `font-display: swap` |
| Existing breakage | Modify files in place incrementally |
| Over-animation | Keep durations ≤600ms; respect reduced-motion |
| Phase 3 complexity | Start with 2-agent parallelism, scale up |
| State corruption | SQLite WAL mode + backup on write |
