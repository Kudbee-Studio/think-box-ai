/**
 * Multi-Agent Swarm System
 *
 * A hierarchical multi-agent framework where:
 * - 1 orchestrator manages the swarm
 * - Up to 12 specialized agent types
 * - Agents can spawn sub-agents (up to 4 levels deep)
 * - Task delegation and distributed execution
 * - Budget tracking (tokens, cost, time)
 */

export { SwarmOrchestrator } from "./orchestrator.ts";
export { SwarmCLI } from "./cli-integration.ts";
export { ALL_AGENT_ROLES, isAgentRole } from "./types.ts";
export type {
  AgentRole,
  AgentConfig,
  AgentTask,
  SwarmState,
  AgentMessage,
  SpawnRequest,
  SpawnResponse,
  SwarmMetrics,
} from "./types.ts";
export { routeModelForAgent, isComplexGoal, budgetMultiplierForRole } from "./model-router.ts";
export type { RouterModels, ModelRouteDecision, RouteReason } from "./model-router.ts";
