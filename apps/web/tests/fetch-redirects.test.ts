// fetch_url follows a redirect only to a host the human has approved: a page that bounces the agent to another host (or to a private address) is asked about, never followed silently.
import assert from 'node:assert/strict';
import http from 'node:http';
import { after, before, test } from 'node:test';
import { startMockInception, type MockInception } from './helpers/mock-inception.ts';
import type { AgentEvent, AgentHooks } from '../agent.ts';

let mock: MockInception; let agent: typeof import('../agent.ts'); let redirector: http.Server; let target: http.Server;
let targetHits = 0; let redirectorPort = 0; let targetPort = 0;
const listen = (s: http.Server): Promise<number> => new Promise((r) => s.listen(0, '127.0.0.1', () => r((s.address() as { port: number }).port)));

before(async () => {
  mock = await startMockInception(); process.env.INCEPTION_BASE_URL = mock.baseUrl; process.env.INCEPTION_API_KEY = 'test-key'; agent = await import('../agent.ts');
  target = http.createServer((_req, res) => { targetHits += 1; res.setHeader('content-type', 'text/plain'); res.end('LOCAL-ONLY-SECRET'); });
  targetPort = await listen(target);
  redirector = http.createServer((req, res) => {
    const to = (loc: string): void => { res.statusCode = 302; res.setHeader('location', loc); res.end(); };
    if (req.url === '/to-other-host') return to(`http://localhost:${targetPort}/secret`);
    if (req.url === '/to-same-host') return to(`http://127.0.0.1:${targetPort}/secret`);
    if (req.url === '/to-file') return to('file:///etc/hostname');
    if (req.url === '/loop') return to(`http://127.0.0.1:${redirectorPort}/loop`);
    res.setHeader('content-type', 'text/plain'); res.end('plain page');
  });
  redirectorPort = await listen(redirector);
});
after(async () => { await mock.close(); await new Promise((r) => redirector.close(r)); await new Promise((r) => target.close(r)); });

function run(url: string, answer: boolean): Promise<{ output: Record<string, unknown>; asked: Array<{ reason: string; args: Record<string, unknown> }>; approved: Set<string> }> {
  const asked: Array<{ reason: string; args: Record<string, unknown> }> = []; const approved = new Set<string>(['127.0.0.1']); // the human already approved 127.0.0.1
  const hooks = {
    workspace: '/tmp', resolvePath: (p: string) => p, onThought: () => {}, onEvent: (_e: AgentEvent) => {}, onFilesChanged: () => {}, signal: new AbortController().signal, checkBudget: () => null,
    approvedDomains: approved, requestApproval: async (_t: string, args: Record<string, unknown>, reason: string) => { asked.push({ reason, args }); return answer; },
    remember: async () => ({}), recall: async () => ({}), rssFeed: async () => ({}),
  } as AgentHooks;
  return agent.runGovernedTool('fetch_url', { url }, hooks, agent.newRunContext(), 1).then((r) => ({ output: r.output, asked, approved }));
}

test('a page on an approved host is fetched with no extra question', async () => {
  targetHits = 0; const r = await run(`http://127.0.0.1:${redirectorPort}/plain`, false);
  assert.equal(r.output.ok, true); assert.match(String(r.output.text), /plain page/); assert.equal(r.asked.length, 0);
});

test('a redirect to the same host needs no question', async () => {
  targetHits = 0; const r = await run(`http://127.0.0.1:${redirectorPort}/to-same-host`, false);
  assert.equal(r.output.ok, true); assert.match(String(r.output.text), /LOCAL-ONLY-SECRET/); assert.equal(r.asked.length, 0); assert.equal(targetHits, 1);
});

test('a redirect to another host is asked about, naming both hosts; denied means the target is never contacted', async () => {
  targetHits = 0; const r = await run(`http://127.0.0.1:${redirectorPort}/to-other-host`, false);
  assert.equal(targetHits, 0, 'the other host received no request'); assert.equal(r.output.ok, false); assert.match(String(r.output.error), /Denied by human reviewer/);
  assert.equal(r.asked.length, 1); assert.match(r.asked[0]!.reason, /Redirected from 127\.0\.0\.1 to localhost/); assert.match(r.asked[0]!.reason, /local or private network/i);
  assert.equal(r.approved.has('localhost'), false);
});

test('approved: the redirect is followed once and the new host is remembered for this session', async () => {
  targetHits = 0; const r = await run(`http://127.0.0.1:${redirectorPort}/to-other-host`, true);
  assert.equal(r.output.ok, true); assert.match(String(r.output.text), /LOCAL-ONLY-SECRET/); assert.equal(targetHits, 1); assert.equal(r.approved.has('localhost'), true);
});

test('a redirect to a non-web address and a redirect loop are refused', async () => {
  const file = await run(`http://127.0.0.1:${redirectorPort}/to-file`, true);
  assert.equal(file.output.ok, false); assert.match(String(file.output.error), /Only http\(s\)/);
  const loop = await run(`http://127.0.0.1:${redirectorPort}/loop`, true);
  assert.equal(loop.output.ok, false); assert.match(String(loop.output.error), /Too many redirects/);
});
