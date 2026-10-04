// Hooks for driving the governed tool path in tests (the same shape the worker agent gets), plus a fake GitHub API.
import http from 'node:http';
import type { AgentEvent, AgentHooks } from '../../agent.ts';

export function lookupHooks(overrides: Partial<AgentHooks> = {}, approve: boolean | ((tool: string) => boolean) = true) {
  const events: AgentEvent[] = [];
  const thoughts: Array<Record<string, unknown>> = [];
  const approvals: Array<{ tool: string; reason: string }> = [];
  const hooks: AgentHooks = {
    workspace: process.cwd(),
    resolvePath: (rel) => rel,
    onThought: (t) => thoughts.push(t),
    onEvent: (e) => events.push(e),
    onFilesChanged: () => {},
    signal: new AbortController().signal,
    checkBudget: () => null,
    approvedDomains: new Set(),
    requestApproval: async (tool, _a, reason) => { approvals.push({ tool, reason }); return typeof approve === 'function' ? approve(tool) : approve; },
    remember: async () => ({}),
    recall: async () => ({ results: [] }),
    rssFeed: async () => ({}),
    ...overrides,
  };
  return { hooks, events, thoughts, approvals };
}

export interface FakeGithub { url: string; hits: string[]; routes: Record<string, { status?: number; body: unknown }>; close: () => Promise<void> }

/** A fake GitHub API: answers by path prefix (pulls, actions/runs, issues, branches) with whatever `routes` holds. */
export async function startFakeGithub(routes: FakeGithub['routes']): Promise<FakeGithub> {
  const hits: string[] = [];
  const server = http.createServer((req, res) => {
    hits.push(String(req.url));
    const key = Object.keys(fake.routes).find((k) => String(req.url).includes(k));
    const hit = key ? fake.routes[key]! : { status: 404, body: { message: 'Not Found' } };
    res.statusCode = hit.status ?? 200;
    res.setHeader('content-type', 'application/json');
    res.end(typeof hit.body === 'string' ? hit.body : JSON.stringify(hit.body));
  });
  await new Promise<void>((r) => server.listen(0, '127.0.0.1', r));
  const fake: FakeGithub = { url: `http://127.0.0.1:${(server.address() as { port: number }).port}`, hits, routes, close: () => new Promise((r) => server.close(() => r())) };
  return fake;
}
