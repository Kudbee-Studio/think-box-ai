# Multi-Agent Swarm Architecture

**Status**: Ready for Local Integration  
**Location**: `apps/web/agent-swarm/`  
**CLI Integration**: `kudbee swarm` commands  

---

## Overview

A **hierarchical multi-agent framework** where a single **orchestrator** manages a team of up to **12 specialized agent types**. Agents can dynamically spawn **sub-agents** to delegate work, creating a tree-structured organization of autonomous workers.

### Key Features

✅ **12 Agent Types** - Specialized roles for different tasks  
✅ **Dynamic Spawning** - Agents create sub-agents as needed  
✅ **Budget Tracking** - Token, cost, and time budgets per agent  
✅ **Hierarchical Delegation** - Up to 4 levels of agent depth  
✅ **Task Management** - Assign, track, complete tasks  
✅ **Swarm Metrics** - Monitor efficiency, cost, progress  

---

## Agent Roles

| Role | Purpose | Max Children | Can Spawn |
|------|---------|--------------|-----------|
| **orchestrator** | Coordinates swarm, delegates work | 12 | ✅ Yes |
| **researcher** | Gathers info, analyzes data | 3 | ✅ Yes |
| **executor** | Performs actions, writes files | 2 | ✅ Yes |
| **validator** | Validates outputs, checks quality | 1 | ❌ No |
| **optimizer** | Improves solutions, refactors | 2 | ✅ Yes |
| **monitor** | Tracks progress, alerts on issues | 0 | ❌ No |
| **communicator** | Handles APIs, messaging | 2 | ✅ Yes |
| **planner** | Breaks down tasks, creates roadmaps | 4 | ✅ Yes |
| **debugger** | Diagnoses failures, suggests fixes | 2 | ✅ Yes |
| **synthesizer** | Combines results, summarizes | 1 | ✅ Yes |
| **specialist** | Domain-specific work | 3 | ✅ Yes |
| **supervisor** | Oversees other agents | 6 | ✅ Yes |

---

## Architecture

```
Orchestrator (root)
├─ Planner
├─ Researcher
│  ├─ Researcher (sub)
│  └─ Communicator
├─ Executor
│  ├─ Executor (sub)
│  └─ Optimizer
├─ Validator
├─ Monitor
├─ Debugger
├─ Synthesizer
└─ Specialist
```

### Hierarchy Constraints

- **Max Depth**: 4 levels (root → L1 → L2 → L3)
- **Max Children**: Per-role limits (orchestrator=12, planner=4, etc.)
- **Budget Inheritance**: Child budgets are 70-80% of parent
- **Spawning**: Any agent can spawn sub-agents (except validator, monitor)

---

## CLI Commands

### Start Swarm

```bash
kudbee swarm start "Analyze user data and generate insights"
```

Creates:
- 1 orchestrator agent
- 6 initial team members (planner, researcher, executor, validator, optimizer, monitor)

### List Agents

```bash
kudbee swarm agents
```

Shows:
- Total agents
- Active agents
- Completed tasks
- Failed tasks

### Show Agent Tree

```bash
kudbee swarm tree
```

Displays:
- Hierarchical agent tree
- Agent names and roles
- Status (active/completed/pending)

### Show Metrics

```bash
kudbee swarm status
```

Reports:
- Agent counts
- Task completion rates
- Efficiency %
- Total cost
- Token usage
- Swarm depth

### Spawn Sub-Agent

```bash
kudbee swarm spawn <parent-id> <role>
```

Example:
```bash
kudbee swarm spawn researcher-1 executor
```

### Assign Task

```bash
kudbee swarm task <agent-id> "Your task here"
```

Example:
```bash
kudbee swarm task orchestrator-abc "Analyze the codebase"
```

### Stop Swarm

```bash
kudbee swarm stop
```

Shuts down all agents and reports final metrics.

---

## Data Flow

### 1. Task Assignment

```
User/CLI
  ↓
Orchestrator.assignTask()
  ↓
Task created (pending)
  ↓
Agent picks up task
  ↓
Task status: running
```

### 2. Agent Spawning

```
Parent Agent
  ↓
Check capacity (maxChildren, budget)
  ↓
Request sub-agent spawn
  ↓
Orchestrator.spawnAgent()
  ↓
Child created with inherited budget
  ↓
Child added to hierarchy
  ↓
Task delegated to child
```

### 3. Task Completion

```
Agent completes task
  ↓
Orchestrator.completeTask(taskId, result)
  ↓
Task status: complete
  ↓
Agent marked completed
  ↓
Result stored
  ↓
Budget credited back
```

---

## Budget System

Each agent gets:

```typescript
budget: {
  tokens: number,        // LLM tokens available
  cost: number,          // USD budget
  time: number           // Seconds available
}
```

### Budget Inheritance

When spawning:
- Child tokens = parent.tokens * 0.8
- Child cost = min(request.cost, parent.cost * 0.5)
- Child time = parent.time * 0.7

### Budget Tracking

- Tokens spent per API call
- Cost calculated per model call
- Time tracked per task
- Swarm fails if budget exhausted

---

## Implementation Files

| File | Purpose |
|------|---------|
| `types.ts` | Type definitions (AgentConfig, AgentTask, etc.) |
| `orchestrator.ts` | Core SwarmOrchestrator class |
| `cli-integration.ts` | kudbee swarm CLI commands |
| `index.ts` | Exports |

---

## Integration with Kudbee CLI

### Add to CLI Handler

In `apps/web/cli.ts`:

```typescript
import { SwarmCLI } from "./agent-swarm/cli-integration";

async function handleSwarmCommand(args: string[]) {
  const swarmCLI = new SwarmCLI();
  await swarmCLI.handleCommand(args);
}

// In main command router:
if (command === "swarm") {
  await handleSwarmCommand(rest);
}
```

### Usage Flow

```
$ kudbee swarm start "Build a feature"
🚀 Swarm started: Build a feature
📍 Orchestrator: orchestrator-abc123
💰 Budget: 100000 tokens, $100

👥 Building initial team...
   ✓ planner        → planner-1
   ✓ researcher     → researcher-1
   ✓ executor       → executor-1
   ✓ validator      → validator-1
   ✓ optimizer      → optimizer-1
   ✓ monitor        → monitor-1

$ kudbee swarm status
📈 Swarm Metrics
   Agents: 7 total, 7 active
   Tasks: 0 complete, 0 failed
   Efficiency: 0.0%
   Cost: $0.00
   Tokens: 0
   Depth: 1 levels

$ kudbee swarm task orchestrator-abc123 "Analyze requirements"
✅ Task assigned: task-xyz789

$ kudbee swarm tree
🌳 Agent Hierarchy

├─ 🔵 orchestrator-1 (orchestrator)
   ├─ 🔵 planner-1 (planner)
   ├─ 🔵 researcher-1 (researcher)
   ├─ 🔵 executor-1 (executor)
   ├─ 🔵 validator-1 (validator)
   ├─ 🔵 optimizer-1 (optimizer)
   └─ 🔵 monitor-1 (monitor)

$ kudbee swarm stop
🛑 Swarm shutdown
📈 Swarm Metrics
   ...
```

---

## Example: Multi-Level Delegation

```bash
# Start swarm
$ kudbee swarm start "Analyze and optimize code"

# Assign to orchestrator
$ kudbee swarm task orchestrator-1 "Optimize src/utils.ts"

# Orchestrator spawns planner
$ kudbee swarm spawn orchestrator-1 planner
✅ Spawned: planner-2

# Planner spawns researcher and executor
$ kudbee swarm spawn planner-2 researcher
✅ Spawned: researcher-2

$ kudbee swarm spawn planner-2 executor
✅ Spawned: executor-2

# Executor spawns optimizer
$ kudbee swarm spawn executor-2 optimizer
✅ Spawned: optimizer-1

# View final tree
$ kudbee swarm tree

├─ 🔵 orchestrator-1 (orchestrator)
   └─ 🔵 planner-2 (planner)
      ├─ 🔵 researcher-2 (researcher)
      └─ 🔵 executor-2 (executor)
         └─ 🔵 optimizer-1 (optimizer)
```

---

## Key Classes & Methods

### SwarmOrchestrator

```typescript
class SwarmOrchestrator {
  initialize(goal: string): Promise<AgentConfig>
  spawnAgent(request: SpawnRequest): Promise<SpawnResponse>
  assignTask(agentId, goal, delegated, priority): Promise<AgentTask>
  completeTask(taskId, result): void
  failTask(taskId, error): void
  sendMessage(message): void
  getMessages(agentId): AgentMessage[]
  getMetrics(): SwarmMetrics
  getAgentTree(): Record<string, any>
  shutdown(): Promise<void>
}
```

### SwarmCLI

```typescript
class SwarmCLI {
  handleCommand(args: string[]): Promise<void>
  // Private methods for each command
}
```

---

## Metrics & Monitoring

### SwarmMetrics

```typescript
interface SwarmMetrics {
  totalAgents: number
  activeAgents: number
  completedTasks: number
  failedTasks: number
  avgResponseTime: number      // ms
  totalCost: number
  totalTokens: number
  efficiency: number            // 0-1
  depth: number                 // Max hierarchy depth
}
```

### Real-time Monitoring

The monitor agent (`monitor` role) tracks:
- Agent health and status
- Task progress
- Cost/budget depletion
- Performance anomalies
- Failure patterns

---

## Next Steps (When You Get Home)

1. **Pull the files**
   ```bash
   git pull origin main
   ```

2. **Review the architecture**
   - Read `docs/MULTI_AGENT_SWARM_ARCHITECTURE.md`
   - Check `apps/web/agent-swarm/` files

3. **Integrate with CLI**
   - Add SwarmCLI to `apps/web/cli.ts`
   - Wire up swarm command handler

4. **Test locally**
   ```bash
   kudbee swarm start "Test swarm execution"
   kudbee swarm tree
   kudbee swarm status
   ```

5. **Extend agent types**
   - Add domain-specific agents
   - Customize tools per role
   - Tune budget multipliers

---

## Architecture Decisions

| Decision | Reason |
|----------|--------|
| Hierarchical spawning | Natural task decomposition |
| Budget inheritance | Prevents runaway spending |
| Role-based agents | Specialization improves performance |
| Max 12 agents | Keeps coordination tractable |
| Message queue | Async communication |
| Per-agent tools | Prevents unauthorized actions |

---

## Production Considerations

⚠️ **Before deploying:**
- Add authentication/authorization
- Implement persistent state storage
- Add audit logging
- Set up cost monitoring/alerts
- Test swarm scaling to 100+ agents
- Add graceful shutdown handling
- Implement agent health checks
- Add request timeout enforcement

---

Ready to integrate! 🚀
