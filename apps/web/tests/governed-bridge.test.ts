// Hermetic: exercises governed-bridge.ts against a mock backend. No network beyond loopback.
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import type { AddressInfo } from 'node:net';
import express from 'express';
import { submitGovernedRun, getGovernedRun, ALLOWED_REMOTE_COMMANDS, type BridgeConfig } from '../governed-bridge.ts';

type Seen = { method: string; url: string; apiKey?: string; body: any };
let seen: Seen[] = [];
let backend: http.Server;
let web: http.Server;
let webBase: string;
let cfg: BridgeConfig;
let runStatus = 200;

const H = { 'Content-Type': 'application/json', 'X-Kudbee-Client': 'dashboard' };

before(async () => {
  backend = http.createServer((req, res) => {
    let raw = '';
    req.on('data', (c) => (raw += c));
    req.on('end', () => {
      seen.push({ method: req.method!, url: req.url!, apiKey: req.headers['x-api-key'] as string, body: raw ? JSON.parse(raw) : null });
      res.setHeader('Content-Type', 'application/json');
      if (req.url === '/api/v1/run/admission-token') {
        return res.end(JSON.stringify({ agent_id: 'web-dashboard-agent', governance_token: 'SECRET-TOKEN', capability: 'shell:upcloud-ssh:readonly' }));
      }
      if (req.url === '/api/v1/run') {
        res.statusCode = runStatus;
        return res.end(JSON.stringify(runStatus === 200 ? { engine_id: 'engine_abc123', session_id: 's1', summary: { receipt_id: 'rcpt1' } } : { detail: { error: 'governance_denied' } }));
      }
      if (req.url === '/api/v1/run/job/engine_abc123/status') return res.end(JSON.stringify({ status: 'completed', result: { execution_proof: { provider: 'upcloud-ssh' } } }));
      res.statusCode = 404;
      res.end('{}');
    });
  });
  await new Promise<void>((r) => backend.listen(0, '127.0.0.1', r));
  cfg = { backendUrl: `http://127.0.0.1:${(backend.address() as AddressInfo).port}`, apiKey: 'server-side-key' };
  const app = express();
  app.use(express.json());
  app.post('/api/governed/run', submitGovernedRun(cfg));
  app.get('/api/governed/run/:engineId', getGovernedRun(cfg));
  web = http.createServer(app);
  await new Promise<void>((r) => web.listen(0, '127.0.0.1', r));
  webBase = `http://127.0.0.1:${(web.address() as AddressInfo).port}`;
});

after(() => {
  backend.close();
  web.close();
});

const post = (body: unknown, headers: Record<string, string> = H) =>
  fetch(`${webBase}/api/governed/run`, { method: 'POST', headers, body: JSON.stringify(body) });

test('submits allow-listed command through admission token then governed /api/v1/run with upcloud-ssh fixed', async () => {
  seen = [];
  const r = await post({ command: 'hostname' });
  assert.equal(r.status, 202);
  const body: any = await r.json();
  assert.deepEqual(body, { engine_id: 'engine_abc123', receipt_id: 'rcpt1', session_id: 's1', execution_substrate: 'upcloud-ssh', command: 'hostname' });
  assert.equal(JSON.stringify(body).includes('SECRET-TOKEN'), false, 'governance token must not reach the browser');
  assert.deepEqual(seen.map((s) => s.url), ['/api/v1/run/admission-token', '/api/v1/run']);
  assert.ok(seen.every((s) => s.apiKey === 'server-side-key'));
  const run = seen[1].body;
  assert.equal(run.execution_substrate, 'upcloud-ssh');
  assert.equal(run.exec_command, 'hostname');
  assert.equal(run.governance_token, 'SECRET-TOKEN');
});

test('client cannot choose substrate, agent, token or capability', async () => {
  seen = [];
  const r = await post({ command: 'uptime', execution_substrate: 'local', agent_id: 'evil', governance_token: 'x', capability: 'goal:execute:verified' });
  assert.equal(r.status, 202);
  const run = seen[1].body;
  assert.equal(run.execution_substrate, 'upcloud-ssh');
  assert.equal(run.agent_id, 'web-dashboard-agent');
  assert.equal(run.governance_token, 'SECRET-TOKEN');
  assert.equal(run.capability, 'shell:upcloud-ssh:readonly', 'capability fixed server-side, not client-chosen');
});

test('rejects commands outside the allow-list without contacting the backend', async () => {
  for (const command of ['rm -rf /', 'hostname; id', 'hostname && whoami', '', 'cat /etc/shadow', ' HOSTNAME']) {
    seen = [];
    const r = await post({ command });
    assert.equal(r.status, 400, `command ${JSON.stringify(command)}`);
    assert.equal(seen.length, 0);
  }
  assert.ok(ALLOWED_REMOTE_COMMANDS.includes('hostname'));
});

test('rejects requests without the dashboard client header', async () => {
  seen = [];
  const r = await post({ command: 'hostname' }, { 'Content-Type': 'application/json' });
  assert.equal(r.status, 403);
  assert.equal(seen.length, 0);
});

test('surfaces backend governance denial as 403 without leaking the token', async () => {
  runStatus = 403;
  try {
    const r = await post({ command: 'hostname' });
    assert.equal(r.status, 403);
    assert.equal((await r.text()).includes('SECRET-TOKEN'), false);
  } finally {
    runStatus = 200;
  }
});

test('status proxy validates engine id and returns backend status', async () => {
  const bad = await fetch(`${webBase}/api/governed/run/..%2Fadmin`, { headers: H });
  assert.equal(bad.status, 400);
  const ok = await fetch(`${webBase}/api/governed/run/engine_abc123`, { headers: H });
  assert.equal(ok.status, 200);
  assert.equal(((await ok.json()) as any).result.execution_proof.provider, 'upcloud-ssh');
});

test('unconfigured bridge (no API key) fails closed with 503', async () => {
  const app = express();
  app.use(express.json());
  app.post('/x', submitGovernedRun({ backendUrl: cfg.backendUrl, apiKey: '' }));
  const s = http.createServer(app);
  await new Promise<void>((r) => s.listen(0, '127.0.0.1', r));
  try {
    const r = await fetch(`http://127.0.0.1:${(s.address() as AddressInfo).port}/x`, { method: 'POST', headers: H, body: JSON.stringify({ command: 'hostname' }) });
    assert.equal(r.status, 503);
  } finally {
    s.close();
  }
});
