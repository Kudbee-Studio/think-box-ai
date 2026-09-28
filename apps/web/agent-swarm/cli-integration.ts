/**
 * Kudbee CLI Integration for Agent Swarm
 *
 * Commands:
 * - kudbee swarm start "<goal>"           # Start swarm with goal
 * - kudbee swarm agents                   # List all agents
 * - kudbee swarm tree                     # Show agent hierarchy
 * - kudbee swarm status                   # Show swarm metrics
 * - kudbee swarm spawn <parent-id> <role> # Manually spawn agent
 * - kudbee swarm task <agent-id> "<goal>" # Assign task to agent
 * - kudbee swarm stop                     # Shutdown swarm
 */

import { SwarmOrchestrator } from "./orchestrator";
import { AgentRole, SpawnRequest } from "./types";

export class SwarmCLI {
  private orchestrator: SwarmOrchestrator | null = null;

  async handleCommand(args: string[]): Promise<void> {
    const [command, ...params] = args;

    switch (command) {
      case "start":
        await this.startSwarm(params[0]);
        break;
      case "agents":
        this.listAgents();
        break;
      case "tree":
        this.showTree();
        break;
      case "status":
        this.showStatus();
        break;
      case "spawn":
        await this.spawnAgent(params[0], params[1] as AgentRole);
        break;
      case "task":
        await this.assignTask(params[0], params[1]);
        break;
      case "stop":
        await this.stopSwarm();
        break;
      default:
        console.log("❌ Unknown swarm command");
    }
  }

  private async startSwarm(goal: string): Promise<void> {
    if (this.orchestrator) {
      console.log("⚠️  Swarm already running");
      return;
    }

    this.orchestrator = new SwarmOrchestrator();
    const rootAgent = await this.orchestrator.initialize(goal);

    console.log(`\n🚀 Swarm started: ${goal}`);
    console.log(`📍 Orchestrator: ${rootAgent.id}`);
    console.log(`💰 Budget: ${rootAgent.budget.tokens} tokens, $${rootAgent.budget.cost}\n`);

    // Initial team spawn
    await this.buildInitialTeam(rootAgent.id);
  }

  private async buildInitialTeam(orchestratorId: string): Promise<void> {
    if (!this.orchestrator) return;

    const initialRoles: AgentRole[] = [
      "planner",      // Break down tasks
      "researcher",   // Research & analysis
      "executor",     // Execute tasks
      "validator",    // Validate results
      "optimizer",    // Optimize solutions
      "monitor",      // Monitor progress
    ];

    console.log("👥 Building initial team...\n");

    for (const role of initialRoles) {
      const response = await this.orchestrator.spawnAgent({
        parentId: orchestratorId,
        role,
        goal: `Specialized ${role} agent for swarm`,
        budget: { tokens: 50000, cost: 25, time: 600 },
        priority: "high",
      });

      if (response.success) {
        console.log(`   ✓ ${role.padEnd(15)} → ${response.agentId}`);
      }
    }
    console.log();
  }

  private listAgents(): void {
    if (!this.orchestrator) {
      console.log("❌ No swarm running");
      return;
    }

    const metrics = this.orchestrator.getMetrics();
    console.log(`\n📊 Agent Summary`);
    console.log(`   Total agents: ${metrics.totalAgents}`);
    console.log(`   Active: ${metrics.activeAgents}`);
    console.log(`   Completed: ${metrics.completedTasks}`);
    console.log(`   Failed: ${metrics.failedTasks}\n`);
  }

  private showTree(): void {
    if (!this.orchestrator) {
      console.log("❌ No swarm running");
      return;
    }

    const tree = this.orchestrator.getAgentTree();
    console.log("\n🌳 Agent Hierarchy\n");
    this.printTree(tree.agents, 0);
  }

  private printTree(agents: any[], indent: number): void {
    for (const agent of agents) {
      const prefix = "  ".repeat(indent) + "├─ ";
      const status = {
        active: "🔵",
        completed: "✅",
        pending: "⏳",
      }[agent.status] || "❓";

      console.log(`${prefix}${status} ${agent.name} (${agent.role})`);
      if (agent.children?.length > 0) {
        this.printTree(agent.children, indent + 1);
      }
    }
    console.log();
  }

  private showStatus(): void {
    if (!this.orchestrator) {
      console.log("❌ No swarm running");
      return;
    }

    const metrics = this.orchestrator.getMetrics();
    console.log(`\n📈 Swarm Metrics`);
    console.log(`   Agents: ${metrics.totalAgents} total, ${metrics.activeAgents} active`);
    console.log(`   Tasks: ${metrics.completedTasks} complete, ${metrics.failedTasks} failed`);
    console.log(`   Efficiency: ${(metrics.efficiency * 100).toFixed(1)}%`);
    console.log(`   Cost: $${metrics.totalCost.toFixed(2)}`);
    console.log(`   Tokens: ${metrics.totalTokens.toLocaleString()}`);
    console.log(`   Depth: ${metrics.depth} levels\n`);
  }

  private async spawnAgent(parentId: string, role: AgentRole): Promise<void> {
    if (!this.orchestrator) {
      console.log("❌ No swarm running");
      return;
    }

    const response = await this.orchestrator.spawnAgent({
      parentId,
      role,
      goal: `Spawned ${role} agent`,
      budget: { tokens: 25000, cost: 12, time: 300 },
      priority: "medium",
    });

    if (response.success) {
      console.log(`✅ Spawned: ${response.agentId}`);
    } else {
      console.log(`❌ Failed: ${response.error || response.reason}`);
    }
  }

  private async assignTask(agentId: string, goal: string): Promise<void> {
    if (!this.orchestrator) {
      console.log("❌ No swarm running");
      return;
    }

    const task = await this.orchestrator.assignTask(agentId, goal, true, "high");
    console.log(`✅ Task assigned: ${task.id}`);
  }

  private async stopSwarm(): Promise<void> {
    if (!this.orchestrator) {
      console.log("❌ No swarm running");
      return;
    }

    await this.orchestrator.shutdown();
    this.orchestrator = null;
  }
}
