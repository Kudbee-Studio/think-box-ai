// The project home: everything about the repository the agent is working on, on one page. Pure: the route gathers the facts, this arranges them.
// Runs are attributed by the `repo` field a run records when it starts, so runs from before that field existed are not counted.
export interface HomeRun { id: string; repo?: string; goal: string; status: string; cost_usd?: number; files?: string[]; started_at: number }
export interface HomeChange { path: string; status: string }
export interface HomeEvent { ts: number; kind: string; actor: string; summary: string }
export interface HomeToken { id: string; title: string; tags: string[]; status: string }
export interface ProjectInput { active: { name: string; repo: string | null; tag: string | null } | null; changes: HomeChange[]; runs: HomeRun[]; audit: HomeEvent[]; tokens: HomeToken[]; now: number }

const REPO_EVENTS = new Set(['draft_pr', 'changes_undone', 'agent_repo_changed']);
const NOTE = 'Runs are counted from the point this page was added: runs from before that have no repository recorded and are not attributed.';

export function buildProject(i: ProjectInput) {
  if (!i.active) {
    return { repo: null, note: 'No repository is chosen. In Files, pick a cloned repository and press "Use for agent".', changes: { count: 0, files: [] as HomeChange[] }, runs: { count: 0, failed: 0, total_usd: 0, today_usd: 0, recent: [] as Array<{ id: string; goal: string; status: string; cost_usd: number; files: number; started_at: number }> }, tokens: { repo_scoped: 0, titles: [] as string[] }, events: [] as HomeEvent[], next: [] as string[] };
  }
  const mine = i.runs.filter((r) => r.repo === i.active!.name).sort((a, b) => b.started_at - a.started_at);
  const dayStart = i.now - (i.now % 86_400_000);
  const scoped = i.active.tag ? i.tokens.filter((t) => t.status === 'accepted' && t.tags.includes(i.active!.tag!)) : [];
  const next: string[] = [];
  if (i.changes.length) next.push(`Review the ${i.changes.length} uncommitted ${i.changes.length === 1 ? 'change' : 'changes'} (Files > Changes); undo what you do not want or open a draft PR.`);
  if (!mine.length) next.push('Give the agent a goal about this repository to get started.');
  return {
    repo: { name: i.active.name, repo: i.active.repo },
    note: NOTE,
    changes: { count: i.changes.length, files: i.changes.slice(0, 8) },
    runs: {
      count: mine.length,
      failed: mine.filter((r) => r.status === 'failed').length,
      total_usd: mine.reduce((s, r) => s + (r.cost_usd ?? 0), 0),
      today_usd: mine.filter((r) => r.started_at >= dayStart).reduce((s, r) => s + (r.cost_usd ?? 0), 0),
      recent: mine.slice(0, 5).map((r) => ({ id: r.id, goal: r.goal.slice(0, 100), status: r.status, cost_usd: r.cost_usd ?? 0, files: (r.files ?? []).length, started_at: r.started_at })),
    },
    tokens: { repo_scoped: scoped.length, titles: scoped.slice(0, 3).map((t) => t.title) },
    events: i.audit.filter((e) => REPO_EVENTS.has(e.kind)).sort((a, b) => b.ts - a.ts).slice(0, 5),
    next,
  };
}
