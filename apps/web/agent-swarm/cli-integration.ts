/**
 * Kudbee CLI Integration for Agent Swarm
 *
 * Wired into apps/web/cli.ts as a `/swarm` REPL command (same convention as
 * /memory, /cat, /model — see handleCommand's `line.split(/\s+/)` dispatch).
 * No shell quoting: everything after the subcommand is space-joined as the
 * goal text, so `/swarm start Analyze the repo` works without quotes and
 * quotes typed in would be taken literally.
 *
 * Commands:
 * - /swarm start <goal>            Start swarm with goal
 * - /swarm agents                  List all agents
 * - /swarm tree                    Show agent hierarchy
 * - /swarm status                  Show swarm metrics
 * - /swarm spawn <parent-id> <role> Manually spawn agent
 * - /swarm task <agent-id> <goal>  Assign task to agent
 * - /swarm stop                    Shutdown swarm
 */

import { SwarmOrchestrator } from "./orchestrator.ts";
import { ALL_AGENT_ROLES, isAgentRole, type AgentRole } from "./types.ts";
import type { RouterModels } from "./model-router.ts";

export class SwarmCLI {
  private orchestrator: SwarmOrchestrator | null = null;
  private routerModels?: RouterModels;

  /**
   * @param routerModels Pass the caller's live model-availability check
   * (e.g. from apps/web/cli.ts's `client.models`) so role→model routing
   * reflects reality instead of always assuming the local model isn't
   * pulled. Omit to use env-var defaults with localAvailable=false.
   *
   * Deliberately not a TS parameter-property (`constructor(private x: T)`)
   * — apps/web runs its .ts files through `node --experimental-strip-types`,
   * which only strips type syntax and does not support parameter-property
   * shorthand (it desugars to a runtime assignment, not just type info).
   * That form throws ERR_UNSUPPORTED_TYPESCRIPT_SYNTAX at import time here;
   * confirmed by running this file directly with strip-types after the fix.
   */
  constructor(routerModels?: RouterModels) {
    this.routerModels = routerModels;
  }

  async handleCommand(args: string[]): Promise<void> {
    const [command, ...params] = args;

    switch (command) {
      case "start":
        await this.startSwarm(params.join(" "));
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
      case "spawn": {
        const [parentRef, roleArg] = params;
        if (!parentRef || !roleArg) {
          console.log("❌ Usage: /swarm spawn <parent-id-or-name> <role>");
          break;
        }
        if (!isAgentRole(roleArg)) {
          console.log(`❌ Unknown role "${roleArg}". Valid roles: ${ALL_AGENT_ROLES.join(", ")}`);
          break;
        }
        const parentId = this.resolveOrReport(parentRef);
        if (!parentId) break;
        await this.spawnAgent(parentId, roleArg);
        break;
      }
      case "task": {
        const [agentRef, ...goalParts] = params;
        if (!agentRef || goalParts.length === 0) {
          console.log("❌ Usage: /swarm task <agent-id-or-name> <goal>");
          break;
        }
        const agentId = this.resolveOrReport(agentRef);
        if (!agentId) break;
        await this.assignTask(agentId, goalParts.join(" "));
        break;
      }
      case "run": {
        const [agentRef] = params;
        if (!agentRef) {
          console.log("❌ Usage: /swarm run <agent-id-or-name>");
          break;
        }
        const agentId = this.resolveOrReport(agentRef);
        if (!agentId) break;
        await this.runAgent(agentId);
        break;
      }
      case "stop":
        await this.stopSwarm();
        break;
      default:
        console.log(
          "❌ Unknown swarm command. Try: start, agents, tree, status, spawn, task, run, stop"
        );
    }
  }

  private async startSwarm(goal: string): Promise<void> {
    if (this.orchestrator) {
      console.log("⚠️  Swarm already running");
      return;
    }

    if (!goal.trim()) {
      console.log("❌ Usage: /swarm start <goal>");
      return;
    }

    const orchestrator = new SwarmOrchestrator(this.routerModels);
    let rootAgent;
    try {
      rootAgent = await orchestrator.initialize(goal);
    } catch (err) {
      console.log(`❌ Failed to start swarm: ${err instanceof Error ? err.message : err}`);
      return;
    }
    this.orchestrator = orchestrator;

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
      // Deliberately don't pin tokens/cost here: a flat request per role
      // (e.g. a hardcoded 50000 tokens x 6 roles) can exceed the root's
      // total budget before the last couple of roles even get a turn, and
      // silently produces a 3-of-6 team with nothing telling you why. Omit
      // them so scaledBudget() applies the role's actual cost tier
      // (model-router.ts) against whatever budget the root still has left.
      const response = await this.orchestrator.spawnAgent({
        parentId: orchestratorId,
        role,
        goal: `Specialized ${role} agent for swarm`,
        budget: { time: 600 },
        priority: "high",
      });

      if (response.success) {
        console.log(`   ✓ ${role.padEnd(15)} → ${response.agentId}`);
      } else {
        // Never swallow a failed spawn — a silently incomplete starter team
        // is exactly the kind of fake success AGENTS.md §4.4 rules out.
        console.log(`   ✗ ${role.padEnd(15)} → ${response.error || response.reason}`);
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

  /**
   * Resolve a user-typed agent-id-or-name to a canonical ID, printing a
   * clear error and returning null if it doesn't match anything. Centralizes
   * the "not found" message so spawn/task/run report it identically.
   */
  private resolveOrReport(ref: string): string | null {
    if (!this.orchestrator) {
      console.log("❌ No swarm running");
      return null;
    }
    const id = this.orchestrator.resolveAgentRef(ref);
    if (!id) {
      console.log(`❌ No agent matches "${ref}" (try /swarm tree to see current names/IDs)`);
      return null;
    }
    return id;
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

    try {
      const task = await this.orchestrator.assignTask(agentId, goal, true, "high");
      console.log(`✅ Task assigned: ${task.id}`);
    } catch (err) {
      console.log(`❌ ${err instanceof Error ? err.message : err}`);
    }
  }

  private async runAgent(agentId: string): Promise<void> {
    if (!this.orchestrator) {
      console.log("❌ No swarm running");
      return;
    }

    console.log(`⏳ Running ${agentId}…`);
    const result = await this.orchestrator.runAgent(agentId);

    if (result.success) {
      console.log(`\n✅ ${agentId} completed:\n${result.result}\n`);
    } else {
      console.log(`❌ ${agentId} failed: ${result.error}`);
    }
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
