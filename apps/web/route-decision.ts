// One routing decision per goal (Layer 1, foundation: pure, no I/O).
// The server records WHO answered a goal and WHY the same way for every path (recipe, local chat, escalated to the worker agent, refused),
// so the run history, the dashboard result line and the CLI result line all say the same thing. Nothing here calls a model or a tool.

export type RoutePath = 'recipe' | 'local_chat' | 'escalated' | 'agent' | 'refused';

export interface RouteDecision {
  path: RoutePath;
  /** The model that answered (null when the goal was refused before any model ran). */
  model: string | null;
  /** The model the caller asked for, when it differs from the one that answered. */
  requested_model?: string;
  reason: string;
  recipe?: string;
}

export const recipeRoute = (model: string, recipe: string, label: string): RouteDecision => ({ path: 'recipe', model, recipe, reason: `a known live question (${label}): the lookup runs in code, ${model} only words the answer` });
export const localChatRoute = (model: string): RouteDecision => ({ path: 'local_chat', model, reason: 'a plain question the local model can answer from its own knowledge' });
export const agentRoute = (model: string): RouteDecision => ({ path: 'agent', model, reason: 'the worker agent runs the goal with tools' });
export const escalatedRoute = (requested: string, model: string, why: string): RouteDecision => ({ path: 'escalated', model, requested_model: requested, reason: `${why}; a local chat has no tools and cannot check live state` });
export const refusedRoute = (requested: string, why: string): RouteDecision => ({ path: 'refused', model: null, requested_model: requested, reason: why });

const PATH_LABEL: Record<RoutePath, string> = { recipe: 'recipe', local_chat: 'local chat', escalated: 'escalated', agent: 'worker agent', refused: 'refused' };

/** One short line for a terminal or the dashboard, for example `route: recipe · smollm2:360m`. */
export function routeLabel(route: unknown): string {
  const r = route as Partial<RouteDecision> | null | undefined;
  if (!r || typeof r !== 'object' || !(r.path && Object.hasOwn(PATH_LABEL, r.path))) return '';
  const via = r.path === 'escalated' && r.requested_model ? `${r.requested_model} → ${r.model}` : (r.model ?? 'no model');
  return `route: ${PATH_LABEL[r.path]} · ${via}${r.recipe ? ` · ${r.recipe}` : ''}`;
}
