/**
 * Swarm Model Router
 *
 * Extends the CLI's simple/complex routing heuristic (apps/web/cli.ts,
 * selectModelForGoal) to per-role defaults across the swarm. Cheap,
 * mechanical roles default to the local model; reasoning-heavy roles
 * default to the enterprise agent model. Any agent can still be
 * escalated per-task via the same isComplexGoal() heuristic so a
 * "simple" role doesn't get stuck on a genuinely hard task, and vice
 * versa a "complex" role isn't forced onto Mercury-2 for trivial busywork.
 *
 * No fake savings: if the local model isn't pulled, routing here must
 * fall back honestly, same contract as the CLI (AGENTS.md §4.4).
 */

import { AgentRole } from "./types";

export type RouteReason = "role_default" | "goal_override" | "fallback_no_local";

export interface ModelRouteDecision {
  model: string;
  reason: RouteReason;
  complexity: "simple" | "complex";
}

/**
 * Default routing tier per role. "local" = cheap Qwen2.5 1.5B class model,
 * "complex" = Mercury-2 class enterprise agent model.
 *
 * Roles that mostly watch, check, or relay (monitor, validator,
 * communicator) default local. Roles that plan, synthesize, debug,
 * or orchestrate default complex.
 */
const ROLE_DEFAULT_TIER: Record<AgentRole, "local" | "complex"> = {
  orchestrator: "complex",
  planner: "complex",
  debugger: "complex",
  optimizer: "complex",
  synthesizer: "complex",
  supervisor: "complex",
  researcher: "local",
  executor: "local",
  validator: "local",
  monitor: "local",
  communicator: "local",
  specialist: "local",
};

// Same heuristic family as apps/web/cli.ts COMPLEX_PATTERNS — kept in sync
// intentionally rather than imported, since cli.ts is a script entrypoint
// (not a module export) and duplicating a 6-line const is cheaper than
// restructuring that file's exports for one shared const.
const COMPLEX_PATTERNS = [
  /\b(code|write|generate|create|build|implement|design|refactor)\b/i,
  /\b(research|analyze|investigate|compare|debug|trace|profile)\b/i,
  /\b(multiple|several|many)\b.*\b(files|tasks|steps|goals|functions)\b/i,
  /\{.*\}/,
  /```/,
  /\b(algorithm|architecture|design pattern|optimize|complex)\b/i,
];

export function isComplexGoal(goal: string): boolean {
  return COMPLEX_PATTERNS.some((p) => p.test(goal)) || goal.length > 150;
}

export interface RouterModels {
  localModel: string;      // e.g. "qwen2.5:1.5b"
  complexModel: string;    // e.g. "mercury-2"
  localAvailable: boolean; // whether the local model is actually pulled/reachable
}

/**
 * Decide which model an agent should use for a given task goal.
 *
 * Role default sets the baseline tier; an explicit complexity signal in
 * the goal text can escalate a "local" role to complex, or de-escalate a
 * "complex" role to local for genuinely trivial busywork (status pings,
 * single-field lookups). Escalation only ever happens one direction at a
 * time per call — this is a per-task decision, not a role reassignment.
 */
export function routeModelForAgent(
  role: AgentRole,
  goal: string,
  models: RouterModels
): ModelRouteDecision {
  const defaultTier = ROLE_DEFAULT_TIER[role];
  const goalIsComplex = isComplexGoal(goal);
  const complexity: "simple" | "complex" = goalIsComplex ? "complex" : "simple";

  const wantsComplex = defaultTier === "complex" || goalIsComplex;

  if (wantsComplex) {
    return { model: models.complexModel, reason: "role_default", complexity };
  }

  if (models.localAvailable) {
    return { model: models.localModel, reason: "role_default", complexity };
  }

  // Local tier wanted but not available — fall back honestly, never
  // pretend the cheap route was taken.
  return { model: models.complexModel, reason: "fallback_no_local", complexity };
}

/**
 * Estimate the cost tier multiplier for budget accounting when spawning
 * sub-agents. Local-tier roles get a lighter default token/cost budget
 * since their default model is far cheaper per call.
 */
export function budgetMultiplierForRole(role: AgentRole): number {
  return ROLE_DEFAULT_TIER[role] === "local" ? 0.3 : 1.0;
}
