/**
 * Swarm Orchestrator
 *
 * Manages agent lifecycle, task delegation, and multi-agent coordination.
 */

import { randomUUID } from "node:crypto";
import type {
  AgentConfig,
  AgentTask,
  SwarmState,
  AgentMessage,
  SpawnRequest,
  SpawnResponse,
  SwarmMetrics,
  AgentRole,
} from "./types.ts";
import { routeModelForAgent, budgetMultiplierForRole, type RouterModels } from "./model-router.ts";
import { callModel, ModelCallError } from "./model-client.ts";

const uuidv4 = randomUUID;

/**
 * Hard ceilings independent of per-role maxChildren. Per-role limits alone
 * don't bound the tree: an orchestrator (maxChildren=12) whose children are
 * all planners (maxChildren=4) could reach 12*4*... agents by depth 4 with
 * every individual spawn passing its local check. These are the actual
 * safety backstop — every spawnAgent() call is checked against both.
 */
const MAX_SWARM_DEPTH = 4;
const MAX_TOTAL_AGENTS = 64;
const MAX_GOAL_LENGTH = 4000;

/** Strip control/formatting characters a goal string has no legitimate use for. */
function sanitizeGoal(goal: string): string {
  // eslint-disable-next-line no-control-regex
  const stripped = goal.replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/g, "").trim();
  return stripped.slice(0, MAX_GOAL_LENGTH);
}

const ROLE_CONFIGS: Record<AgentRole, { maxChildren: number; tools: string[] }> = {
  orchestrator: { maxChildren: 12, tools: ["delegate", "monitor", "spawn_agent"] },
  researcher: { maxChildren: 3, tools: ["fetch_url", "read_file", "analyze"] },
  executor: { maxChildren: 2, tools: ["write_file", "execute_task", "commit"] },
  validator: { maxChildren: 1, tools: ["validate", "test", "report"] },
  optimizer: { maxChildren: 2, tools: ["refactor", "profile", "improve"] },
  monitor: { maxChildren: 0, tools: ["track_progress", "alert", "report"] },
  communicator: { maxChildren: 2, tools: ["send_message", "fetch_url", "log"] },
  planner: { maxChildren: 4, tools: ["break_down_task", "create_roadmap", "prioritize"] },
  debugger: { maxChildren: 2, tools: ["diagnose", "trace", "suggest_fix"] },
  synthesizer: { maxChildren: 1, tools: ["combine_results", "summarize", "export"] },
  specialist: { maxChildren: 3, tools: ["domain_specific_action"] },
  supervisor: { maxChildren: 6, tools: ["oversee", "escalate", "report"] },
};

export class SwarmOrchestrator {
  private state: SwarmState;
  private messageQueue: AgentMessage[] = [];
  private roleInstances: Map<AgentRole, number> = new Map();
  private routerModels: RouterModels;

  constructor(routerModels?: RouterModels) {
    // Defaults match apps/web/cli.ts (KUDBEE_LOCAL_MODEL / KUDBEE_COMPLEX_MODEL).
    // localAvailable defaults false so budget/model decisions never claim
    // savings the caller hasn't confirmed are real (AGENTS.md §4.4) — pass
    // { localAvailable: true } once you've checked Ollama has the model pulled.
    this.routerModels = routerModels || {
      localModel: process.env.KUDBEE_LOCAL_MODEL || "qwen2.5:1.5b",
      complexModel: process.env.KUDBEE_COMPLEX_MODEL || "mercury-2",
      localAvailable: false,
    };

    this.state = {
      agents: new Map(),
      tasks: new Map(),
      hierarchy: new Map(),
      activeAgents: new Set(),
      completedAgents: new Set(),
      failedAgents: new Set(),
      totalCost: 0,
      totalTokens: 0,
      startTime: new Date(),
    };

    // Initialize role counters
    Object.keys(ROLE_CONFIGS).forEach((role) => {
      this.roleInstances.set(role as AgentRole, 0);
    });
  }

  /**
   * Create root orchestrator agent
   */
  async initialize(goal: string): Promise<AgentConfig> {
    const cleanGoal = sanitizeGoal(goal);
    if (!cleanGoal) {
      throw new Error("Swarm goal must not be empty");
    }

    const rootAgent = this.createAgent(
      "orchestrator",
      `orchestrator-${uuidv4().slice(0, 8)}`,
      cleanGoal,
      undefined,
      { tokens: 100000, cost: 100, time: 3600 }
    );

    this.state.agents.set(rootAgent.id, rootAgent);
    this.state.activeAgents.add(rootAgent.id);

    console.log(`✅ Swarm initialized with orchestrator: ${rootAgent.id}`);
    return rootAgent;
  }

  /**
   * Create an agent instance
   */
  private createAgent(
    role: AgentRole,
    id: string,
    goal: string,
    parentId?: string,
    budget?: AgentConfig["budget"]
  ): AgentConfig {
    const config = ROLE_CONFIGS[role];
    const depth = parentId ? (this.state.agents.get(parentId)?.depth || 0) + 1 : 0;
    const count = (this.roleInstances.get(role) || 0) + 1;
    this.roleInstances.set(role, count);

    const route = routeModelForAgent(role, goal, this.routerModels);

    return {
      id,
      role,
      name: `${role}-${count}`,
      parentId,
      depth,
      maxChildren: config.maxChildren,
      tools: config.tools,
      capabilities: this.getCapabilitiesForRole(role),
      budget: budget || { tokens: 10000, cost: 10, time: 300 },
      context: { goal, model: route.model, modelRouteReason: route.reason },
    };
  }

  /**
   * Scale a budget request by the role's cost tier (local-model roles get a
   * lighter default footprint since their default model is far cheaper).
   * Callers that already computed an explicit budget for a role can skip
   * this — it only fills in when the caller left a field unset.
   */
  private scaledBudget(
    role: AgentRole,
    parentBudget: AgentConfig["budget"],
    requested: Partial<AgentConfig["budget"]>
  ): AgentConfig["budget"] {
    const tierMultiplier = budgetMultiplierForRole(role);
    return {
      tokens: Math.floor((requested.tokens ?? parentBudget.tokens * tierMultiplier) * 0.8),
      cost: Math.min(
        requested.cost ?? parentBudget.cost * tierMultiplier * 0.5,
        parentBudget.cost
      ),
      time: Math.floor((requested.time ?? parentBudget.time) * 0.7),
    };
  }

  /**
   * Spawn a child agent from a parent
   */
  async spawnAgent(request: SpawnRequest): Promise<SpawnResponse> {
    const parent = this.state.agents.get(request.parentId);

    if (!parent) {
      return { success: false, error: "Parent agent not found" };
    }

    // Hard backstops first — these bound the whole tree, not just one level.
    // Per-role maxChildren alone can't prevent exponential blow-up across
    // depth (e.g. 12 orchestrator children x 4 planner children x ... ), so
    // every spawn is checked against the swarm-wide ceilings regardless of
    // whether the parent's own local limit would have allowed it.
    if (this.state.agents.size >= MAX_TOTAL_AGENTS) {
      return { success: false, reason: `Swarm has reached the max agent ceiling (${MAX_TOTAL_AGENTS})` };
    }

    if (parent.depth + 1 > MAX_SWARM_DEPTH) {
      return { success: false, reason: `Spawn would exceed max swarm depth (${MAX_SWARM_DEPTH})` };
    }

    if (parent.maxChildren <= (this.state.hierarchy.get(parent.id) || []).length) {
      return { success: false, reason: "Parent has reached max children limit" };
    }

    // A parent that's nearly out of budget can't fund a child — without this,
    // budget "inheritance" (scaledBudget) is purely cosmetic bookkeeping that
    // never actually stops spending.
    const MIN_SPAWN_BUDGET_FRACTION = 0.1;
    if (
      parent.budget.tokens < parent.budget.tokens * MIN_SPAWN_BUDGET_FRACTION + 1 &&
      parent.budget.tokens < 500
    ) {
      return { success: false, reason: "Parent budget too low to fund a child agent" };
    }

    const cleanGoal = sanitizeGoal(request.goal);
    if (!cleanGoal) {
      return { success: false, error: "Spawn goal must not be empty" };
    }

    // Inherit and reduce budget, scaled by the child role's cost tier
    const childBudget = this.scaledBudget(request.role, parent.budget, request.budget);

    const childId = `${request.role}-${uuidv4().slice(0, 8)}`;
    const childAgent = this.createAgent(
      request.role,
      childId,
      cleanGoal,
      request.parentId,
      childBudget
    );

    // Debit the parent immediately for the budget it just committed to the
    // child — otherwise a parent could over-commit the same tokens/cost to
    // many children before any of them ever reports spend back.
    parent.budget.tokens = Math.max(0, parent.budget.tokens - childBudget.tokens);
    parent.budget.cost = Math.max(0, parent.budget.cost - childBudget.cost);

    // Register child
    this.state.agents.set(childId, childAgent);
    this.state.activeAgents.add(childId);

    // Add to hierarchy
    if (!this.state.hierarchy.has(request.parentId)) {
      this.state.hierarchy.set(request.parentId, []);
    }
    this.state.hierarchy.get(request.parentId)!.push(childId);

    // Create task for child
    const task: AgentTask = {
      id: `task-${childId}`,
      agentId: childId,
      goal: cleanGoal,
      priority: request.priority,
      delegated: request.role !== "validator" && request.role !== "monitor",
      subTasks: [],
      status: "pending",
      progress: 0,
      createdAt: new Date(),
    };

    this.state.tasks.set(task.id, task);

    console.log(
      `🤖 Spawned agent: ${childAgent.name} (${childId}) → model=${childAgent.context?.model}`
    );
    return { success: true, agentId: childId };
  }

  /**
   * Assign task to agent (or spawn sub-agent if delegated)
   */
  async assignTask(
    agentId: string,
    goal: string,
    delegated: boolean = false,
    priority: "low" | "medium" | "high" | "critical" = "medium"
  ): Promise<AgentTask> {
    const agent = this.state.agents.get(agentId);
    if (!agent) {
      throw new Error(`Agent ${agentId} not found`);
    }

    const cleanGoal = sanitizeGoal(goal);
    if (!cleanGoal) {
      throw new Error("Task goal must not be empty");
    }

    const task: AgentTask = {
      id: `task-${uuidv4()}`,
      agentId,
      goal: cleanGoal,
      priority,
      delegated,
      subTasks: [],
      status: "pending",
      progress: 0,
      createdAt: new Date(),
    };

    this.state.tasks.set(task.id, task);

    // Delegation spawns a sub-agent — goes through the same spawnAgent()
    // depth/ceiling/budget checks as a manual spawn, so a delegated task
    // can fail to delegate (falls back to the agent doing it directly)
    // rather than silently bypassing the swarm-wide limits.
    if (delegated && agent.role !== "orchestrator" && agent.depth < MAX_SWARM_DEPTH) {
      const response = await this.spawnAgent({
        parentId: agentId,
        role: "researcher",
        goal: cleanGoal,
        budget: { tokens: agent.budget.tokens * 0.5 },
        priority,
      });
      if (!response.success) {
        console.log(`  ⚠ delegation skipped (${response.reason || response.error}) — ${agent.name} will handle it directly`);
      }
    }

    return task;
  }

  /**
   * Mark task complete
   */
  completeTask(taskId: string, result: any): void {
    const task = this.state.tasks.get(taskId);
    if (!task) return;

    task.status = "complete";
    task.progress = 100;
    task.result = result;
    task.completedAt = new Date();

    const agent = this.state.agents.get(task.agentId);
    if (agent) {
      this.state.activeAgents.delete(agent.id);
      this.state.completedAgents.add(agent.id);
    }
  }

  /**
   * Mark task failed
   */
  failTask(taskId: string, error: string): void {
    const task = this.state.tasks.get(taskId);
    if (!task) return;

    task.status = "failed";
    task.error = error;
    task.completedAt = new Date();

    const agent = this.state.agents.get(task.agentId);
    if (agent) {
      this.state.activeAgents.delete(agent.id);
      this.state.failedAgents.add(agent.id);
    }
  }

  /**
   * Execute an agent's pending task against its routed model (Mercury-2 or
   * the local model — see agent.context.model, set by model-router.ts at
   * spawn time) and record the real result.
   *
   * This is a single-shot completion, not the tool-calling loop in
   * apps/web/agent.ts — see model-client.ts's header comment for why. It
   * finds the agent's most recent non-terminal task, calls the model once,
   * and on success calls completeTask() with the real response text and
   * recordSpend() with the real token/cost usage the API reported. On
   * failure it calls failTask() with the real error — never a fabricated
   * result, and never spend recorded for a call that didn't happen.
   */
  async runAgent(agentId: string): Promise<{ success: boolean; result?: string; error?: string }> {
    const agent = this.state.agents.get(agentId);
    if (!agent) {
      return { success: false, error: "Agent not found" };
    }

    const task = Array.from(this.state.tasks.values())
      .reverse()
      .find((t) => t.agentId === agentId && t.status !== "complete" && t.status !== "failed");
    if (!task) {
      return { success: false, error: "No pending task for this agent — assign or spawn one first" };
    }

    const model = (agent.context?.model as string | undefined) || this.routerModels.complexModel;
    const systemPrompt =
      `You are the "${agent.name}" agent (role: ${agent.role}) in a multi-agent swarm. ` +
      `Your capabilities: ${agent.capabilities.join(", ")}. Respond concisely and actionably; ` +
      `you have no tools in this call — text response only.`;

    task.status = "running";
    task.startedAt = new Date();

    let call;
    try {
      call = await callModel(model, task.goal, systemPrompt);
    } catch (err) {
      const message =
        err instanceof ModelCallError
          ? err.message
          : `Unexpected error calling ${model}: ${err instanceof Error ? err.message : String(err)}`;
      this.failTask(task.id, message);
      return { success: false, error: message };
    }

    const withinBudget = this.recordSpend(agentId, {
      tokens: call.promptTokens + call.completionTokens,
      cost: call.costUsd,
      timeMs: call.latencyMs,
    });
    this.completeTask(task.id, call.content);
    if (!withinBudget) {
      console.log(`  ⚠ ${agent.name} has exhausted its budget completing this task`);
    }

    return { success: true, result: call.content };
  }

  /**
   * Record actual spend against an agent's remaining budget and roll it up
   * into swarm-wide totals. Call this after every real model call — before
   * this method existed, state.totalCost/totalTokens and the per-agent
   * budget were write-only fields nothing ever decremented, so a caller
   * reading getMetrics() mid-run would see cost=0 no matter how much had
   * actually been spent.
   *
   * Returns false if the agent has no budget left, so the caller can stop
   * issuing further model calls for it (fail closed on exhaustion rather
   * than silently going over budget).
   */
  recordSpend(agentId: string, spend: { tokens: number; cost: number; timeMs?: number }): boolean {
    const agent = this.state.agents.get(agentId);
    if (!agent) return false;

    agent.budget.tokens = Math.max(0, agent.budget.tokens - spend.tokens);
    agent.budget.cost = Math.max(0, agent.budget.cost - spend.cost);
    if (spend.timeMs) {
      agent.budget.time = Math.max(0, agent.budget.time - Math.ceil(spend.timeMs / 1000));
    }

    this.state.totalTokens += spend.tokens;
    this.state.totalCost += spend.cost;

    return agent.budget.tokens > 0 && agent.budget.cost > 0;
  }

  /**
   * Authorization gate: is this agent allowed to invoke this tool? Every
   * role's tool list in ROLE_CONFIGS is declarative metadata unless
   * something actually checks it before a tool call executes — this is
   * that check. Callers wiring the swarm to a real tool-execution loop
   * (apps/web/agent.ts) must call this before dispatching, not just before
   * spawning.
   */
  isToolAllowed(agentId: string, tool: string): boolean {
    const agent = this.state.agents.get(agentId);
    if (!agent) return false;
    return agent.tools.includes(tool);
  }

  /**
   * Resolve a user-typed reference to a canonical agent ID. Every spawn
   * confirmation and /swarm tree line prints the short display name
   * (e.g. "planner-1"), not the full "planner-<8 hex chars>" ID — a user
   * will naturally type the name back. Checks the exact ID first (the
   * common case for programmatic callers), then falls back to a name
   * match. Returns undefined, never throws, so callers can produce their
   * own "not found" message with the original ref included.
   */
  resolveAgentRef(ref: string): string | undefined {
    if (this.state.agents.has(ref)) return ref;
    for (const agent of this.state.agents.values()) {
      if (agent.name === ref) return agent.id;
    }
    return undefined;
  }

  /**
   * Route message between agents
   */
  sendMessage(message: AgentMessage): void {
    this.messageQueue.push(message);
    // Unbounded growth here would be a memory leak in any long-running
    // swarm (e.g. a monitor agent broadcasting on every tick). Drop the
    // oldest rather than reject sends — messages are best-effort status,
    // not a durable log.
    const MAX_QUEUE = 5000;
    if (this.messageQueue.length > MAX_QUEUE) {
      this.messageQueue.splice(0, this.messageQueue.length - MAX_QUEUE);
    }
  }

  /**
   * Get pending messages for agent
   */
  getMessages(agentId: string): AgentMessage[] {
    return this.messageQueue.filter((m) => m.to === agentId || m.to === "broadcast");
  }

  /**
   * Get swarm metrics
   */
  getMetrics(): SwarmMetrics {
    const tasks = Array.from(this.state.tasks.values());
    const completed = tasks.filter((t) => t.status === "complete").length;
    const failed = tasks.filter((t) => t.status === "failed").length;
    const total = tasks.length;

    return {
      totalAgents: this.state.agents.size,
      activeAgents: this.state.activeAgents.size,
      completedTasks: completed,
      failedTasks: failed,
      avgResponseTime: 0, // Would be calculated from task timings
      totalCost: this.state.totalCost,
      totalTokens: this.state.totalTokens,
      efficiency: total > 0 ? completed / total : 0,
      depth: Math.max(...Array.from(this.state.agents.values()).map((a) => a.depth), 0),
    };
  }

  /**
   * Get agent tree visualization
   */
  getAgentTree(): Record<string, any> {
    const roots = Array.from(this.state.agents.values()).filter((a) => !a.parentId);

    const buildTree = (agentId: string): any => {
      const agent = this.state.agents.get(agentId);
      if (!agent) return null;

      const children = (this.state.hierarchy.get(agentId) || [])
        .map((childId) => buildTree(childId))
        .filter(Boolean);

      return {
        id: agent.id,
        name: agent.name,
        role: agent.role,
        status: this.state.activeAgents.has(agentId)
          ? "active"
          : this.state.completedAgents.has(agentId)
            ? "completed"
            : "pending",
        children,
      };
    };

    return {
      agents: roots.map((r) => buildTree(r.id)),
      metrics: this.getMetrics(),
    };
  }

  /**
   * Get capabilities for role
   */
  private getCapabilitiesForRole(role: AgentRole): string[] {
    const capabilities: Record<AgentRole, string[]> = {
      orchestrator: ["delegate", "spawn", "coordinate", "prioritize"],
      researcher: ["search", "analyze", "summarize", "extract"],
      executor: ["write", "execute", "modify", "deploy"],
      validator: ["verify", "test", "audit", "report"],
      optimizer: ["refactor", "improve", "benchmark", "profile"],
      monitor: ["track", "alert", "report", "escalate"],
      communicator: ["send", "receive", "integrate", "format"],
      planner: ["analyze", "plan", "schedule", "decompose"],
      debugger: ["diagnose", "trace", "fix", "learn"],
      synthesizer: ["combine", "aggregate", "summarize", "export"],
      specialist: ["domain_specific"],
      supervisor: ["oversee", "approve", "reject", "escalate"],
    };

    return capabilities[role] || [];
  }

  /**
   * Shutdown swarm
   */
  async shutdown(): Promise<void> {
    this.state.endTime = new Date();
    console.log("\n🛑 Swarm shutdown");
    console.log(JSON.stringify(this.getMetrics(), null, 2));
  }
}
