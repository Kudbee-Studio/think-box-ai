/**
 * Swarm Orchestrator
 *
 * Manages agent lifecycle, task delegation, and multi-agent coordination.
 */

import { randomUUID } from "node:crypto";
import {
  AgentConfig,
  AgentTask,
  SwarmState,
  AgentMessage,
  SpawnRequest,
  SpawnResponse,
  SwarmMetrics,
  AgentRole,
} from "./types";
import { routeModelForAgent, budgetMultiplierForRole, RouterModels } from "./model-router";

const uuidv4 = randomUUID;

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
    const rootAgent = this.createAgent(
      "orchestrator",
      `orchestrator-${uuidv4().slice(0, 8)}`,
      goal,
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

    if (parent.maxChildren <= (this.state.hierarchy.get(parent.id) || []).length) {
      return { success: false, reason: "Parent has reached max children limit" };
    }

    // Inherit and reduce budget, scaled by the child role's cost tier
    const childBudget = this.scaledBudget(request.role, parent.budget, request.budget);

    const childId = `${request.role}-${uuidv4().slice(0, 8)}`;
    const childAgent = this.createAgent(
      request.role,
      childId,
      request.goal,
      request.parentId,
      childBudget
    );

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
      goal: request.goal,
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

    const task: AgentTask = {
      id: `task-${uuidv4()}`,
      agentId,
      goal,
      priority,
      delegated,
      subTasks: [],
      status: "pending",
      progress: 0,
      createdAt: new Date(),
    };

    this.state.tasks.set(task.id, task);

    if (delegated && agent.role !== "orchestrator") {
      // Spawn researcher to handle task
      await this.spawnAgent({
        parentId: agentId,
        role: "researcher",
        goal,
        budget: { tokens: agent.budget.tokens * 0.5 },
        priority,
      });
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
   * Route message between agents
   */
  sendMessage(message: AgentMessage): void {
    this.messageQueue.push(message);
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
