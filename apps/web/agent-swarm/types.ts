/**
 * Multi-Agent Swarm Types
 *
 * Defines agent roles, spawning mechanics, and swarm coordination.
 */

export type AgentRole =
  | "orchestrator"      // Delegates work, manages swarm
  | "researcher"        // Gathers information, analyzes data
  | "executor"          // Performs actions, writes files
  | "validator"         // Validates outputs, checks quality
  | "optimizer"         // Improves solutions, refactors
  | "monitor"           // Tracks progress, alerts on issues
  | "communicator"      // Handles external APIs, messaging
  | "planner"           // Breaks down tasks, creates roadmaps
  | "debugger"          // Diagnoses failures, suggests fixes
  | "synthesizer"       // Combines results, creates summaries
  | "specialist"        // Domain-specific work
  | "supervisor";       // Oversees other agents

/**
 * Runtime-checkable list of every AgentRole, kept in sync with the union
 * above by hand (TS unions have no runtime representation to derive this
 * from automatically). Used to validate role strings coming from outside
 * the type system — e.g. CLI args — before they reach orchestrator logic.
 */
export const ALL_AGENT_ROLES: readonly AgentRole[] = [
  "orchestrator",
  "researcher",
  "executor",
  "validator",
  "optimizer",
  "monitor",
  "communicator",
  "planner",
  "debugger",
  "synthesizer",
  "specialist",
  "supervisor",
] as const;

export function isAgentRole(value: string): value is AgentRole {
  return (ALL_AGENT_ROLES as readonly string[]).includes(value);
}

export interface AgentConfig {
  id: string;
  role: AgentRole;
  name: string;
  parentId?: string;              // Parent agent if spawned
  depth: number;                  // Swarm hierarchy depth (0 = root)
  maxChildren: number;            // Max sub-agents this agent can spawn
  budget: {
    tokens: number;               // Token budget for this agent
    cost: number;                 // USD cost budget
    time: number;                 // Seconds time budget
  };
  tools: string[];                // Available tools
  capabilities: string[];         // Special capabilities
  context?: Record<string, any>;  // Agent-specific context
}

export interface AgentTask {
  id: string;
  agentId: string;
  goal: string;
  priority: "low" | "medium" | "high" | "critical";
  delegated: boolean;             // Can spawn sub-agents?
  subTasks: string[];             // IDs of spawned sub-tasks
  status: "pending" | "running" | "blocked" | "complete" | "failed";
  progress: number;               // 0-100
  result?: any;
  error?: string;
  createdAt: Date;
  startedAt?: Date;
  completedAt?: Date;
}

export interface SwarmState {
  agents: Map<string, AgentConfig>;
  tasks: Map<string, AgentTask>;
  hierarchy: Map<string, string[]>;  // parentId -> childIds
  activeAgents: Set<string>;
  completedAgents: Set<string>;
  failedAgents: Set<string>;
  totalCost: number;
  totalTokens: number;
  startTime: Date;
  endTime?: Date;
}

export interface AgentMessage {
  from: string;                   // Agent ID
  to: string;                     // Agent ID or "broadcast"
  type: "task" | "result" | "error" | "status" | "spawn_request";
  payload: any;
  timestamp: Date;
}

export interface SwarmMetrics {
  totalAgents: number;
  activeAgents: number;
  completedTasks: number;
  failedTasks: number;
  avgResponseTime: number;        // ms
  totalCost: number;
  totalTokens: number;
  efficiency: number;             // 0-1 based on success rate
  depth: number;                  // Max hierarchy depth
}

export interface SpawnRequest {
  parentId: string;
  role: AgentRole;
  goal: string;
  budget: Partial<AgentConfig["budget"]>;
  priority: AgentTask["priority"];
}

export interface SpawnResponse {
  success: boolean;
  agentId?: string;
  error?: string;
  reason?: string;
}
