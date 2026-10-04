// Workspace confinement past symlinks and races, update_config limits, and private-network requests.
// Boots the REAL server.ts on random loopback ports (never 3000); no external network.
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawn, type ChildProcess } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import type { AddressInfo } from 'node:net';
import { WebSocket } from 'ws';
import { fetchChecked, isPrivateAddress } from '../net-guard.ts';
import { startMockInception, say, call, type MockInception } from './helpers/mock-inception.ts';
import { freePort } from './helpers/free-port.ts';

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const DEAD = 'http://127.0.0.1:9';
let tmp: string;
let outside: string;
const procs: ChildProcess[] = [];

interface Server { url: string; port: number; workspaces: string }

async function start(extra: Record<string, string> = {}): Promise<Server> {
  const port = await freePort();
  const dir = fs.mkdtempSync(path.join(tmp, 's-'));
  const workspaces = path.join(dir, 'w');
  const proc = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], {
    cwd: appDir,
    env: {
      ...process.env, PORT: String(port), INCEPTION_API_KEY: 'test', INCEPTION_API_KEY_2: '', OLLAMA_BASE_URL: DEAD, JANUS_BASE_URL: DEAD,
      UPSTASH_VECTOR_REST_URL: DEAD, UPSTASH_VECTOR_REST_TOKEN: 'none', KUDBEE_DAILY_BUDGET_USD: '0',
      KUDBEE_DATA_DIR: path.join(dir, 'd'), KUDBEE_WORKSPACE_DIR: workspaces, KUDBEE_MEMORY_DIR: path.join(dir, 'm'),
      THINKBOX_BACKEND_URL: DEAD, DASHBOARD_ENABLE_SHELL_EXEC: '', DASHBOARD_ALLOW_NO_ORIGIN: '', ...extra,
    },
    stdio: 'ignore',
  });
  procs.push(proc);
  const url = `http://127.0.0.1:${port}`;
  for (const end = Date.now() + 15000; Date.now() < end; await new Promise((r) => setTimeout(r, 150))) {
    try { if ((await fetch(`${url}/api/health`)).ok) return { url, port, workspaces }; } catch { /* starting */ }
  }
  throw new Error('server did not start');
}

interface Client {
  sessionId: string; ws: string; send(msg: object, reply: string, approve?: boolean): Promise<any>; approvals: string[]; close(): void;
  // Resolves with whichever of `replies` arrives first, so a wrong reply type fails an assertion instead of hanging.
  sendAny(msg: object | string, replies: string[]): Promise<{ type: string; data: Record<string, unknown> }>;
}

async function connect(s: Server): Promise<Client> {
  const sock = new WebSocket(`ws://127.0.0.1:${s.port}/ws`, { origin: s.url });
  const queue: any[] = [];
  const waiters: Array<(m: any) => void> = [];
  sock.on('message', (raw) => { const m = JSON.parse(raw.toString()); const w = waiters.shift(); if (w) w(m); else queue.push(m); });
  const next = async (types: string[]) => {
    for (;;) {
      const m = queue.length ? queue.shift() : await new Promise<any>((r) => waiters.push(r));
      if (types.includes(m.type)) return m;
    }
  };
  const init = await next(['init']);
  const approvals: string[] = [];
  const workspace = path.join(s.workspaces, init.data.sessionId);
  fs.mkdirSync(workspace, { recursive: true });
  return {
    sessionId: init.data.sessionId,
    ws: workspace,
    approvals,
    async send(msg, reply, approve) {
      sock.send(JSON.stringify(msg));
      for (;;) {
        const m = await next([reply, 'approval_request']);
        if (m.type === reply) return m.data;
        approvals.push(m.data.reason);
        if (approve === undefined) throw new Error(`unexpected approval_request: ${m.data.reason}`);
        sock.send(JSON.stringify({ type: 'approval_response', id: m.data.id, approved: approve }));
      }
    },
    sendAny(msg, replies) {
      sock.send(typeof msg === 'string' ? msg : JSON.stringify(msg));
      return next(replies);
    },
    close: () => sock.close(),
  };
}

const plugin = (c: Client, name: string, input: object, approve?: boolean) =>
  c.send({ type: 'plugin_execute', plugin: name, input }, 'plugin_result', approve).then((d) => d.result);

function rawRequest(s: Server, method: string, p: string, body?: string, headers: Record<string, string> = {}): Promise<{ code: number; body: string }> {
  return new Promise((resolve, reject) => {
    // Node doesn't chunk-encode DELETE bodies, so always frame the body with Content-Length.
    const framed = body === undefined ? headers : { ...headers, 'Content-Length': String(Buffer.byteLength(body)) };
    const r = http.request({ host: '127.0.0.1', port: s.port, method, path: p, headers: framed }, (res) => {
      let d = ''; res.on('data', (c) => (d += c)); res.on('end', () => resolve({ code: res.statusCode!, body: d }));
    });
    r.on('error', reject);
    r.end(body);
  });
}

before(() => {
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-confine-'));
  outside = path.join(tmp, 'outside');
  fs.mkdirSync(outside);
  fs.writeFileSync(path.join(outside, 'secret.txt'), 'OUTSIDE_SECRET');
  fs.writeFileSync(path.join(outside, 'secret.png'), 'OUTSIDE_SECRET');
});
after(() => { for (const p of procs) p.kill(); fs.rmSync(tmp, { recursive: true, force: true }); });

test('REST file routes refuse symlinks that lead out of the workspace (403)', async () => {
  const s = await start();
  const c = await connect(s);
  try {
    fs.symlinkSync(outside, path.join(c.ws, 'escape'));
    fs.symlinkSync(path.join(outside, 'secret.txt'), path.join(c.ws, 'link.txt'));
    const base = `/api/sessions/${c.sessionId}/files`;
    for (const p of ['escape/secret.txt', 'link.txt']) {
      const r = await rawRequest(s, 'GET', `${base}/content?path=${encodeURIComponent(p)}`);
      assert.equal(r.code, 403, `content ${p}`);
      assert.doesNotMatch(r.body, /OUTSIDE_SECRET/);
    }
    const raw = await rawRequest(s, 'GET', `${base}/raw?path=escape/secret.png`);
    assert.equal(raw.code, 403, 'raw');
    assert.doesNotMatch(raw.body, /OUTSIDE_SECRET/);

    const boundary = 'B0UND';
    const upload = await rawRequest(s, 'POST', base,
      `--${boundary}\r\nContent-Disposition: form-data; name="files"; filename="link.txt"\r\nContent-Type: text/plain\r\n\r\nOVERWRITTEN\r\n--${boundary}--\r\n`,
      { 'Content-Type': `multipart/form-data; boundary=${boundary}` });
    assert.equal(upload.code, 403, 'upload through a symlink');
    assert.equal(fs.readFileSync(path.join(outside, 'secret.txt'), 'utf8'), 'OUTSIDE_SECRET');

    const del = await rawRequest(s, 'DELETE', base, JSON.stringify({ path: 'escape/secret.txt' }), { 'Content-Type': 'application/json' });
    assert.equal(del.code, 403, 'delete through a symlinked directory');
    assert.ok(fs.existsSync(path.join(outside, 'secret.txt')), 'outside file survives');

    const delLink = await rawRequest(s, 'DELETE', base, JSON.stringify({ path: 'link.txt' }), { 'Content-Type': 'application/json' });
    assert.equal(delLink.code, 200, 'deleting the link itself is allowed');
    assert.ok(!fs.existsSync(path.join(c.ws, 'link.txt')) && fs.existsSync(path.join(outside, 'secret.txt')), 'only the link is removed');

    fs.writeFileSync(path.join(c.ws, 'ok.txt'), 'INSIDE');
    const ok = await rawRequest(s, 'GET', `${base}/content?path=ok.txt`);
    assert.equal(ok.code, 200);
    assert.equal(JSON.parse(ok.body).content, 'INSIDE');
  } finally { c.close(); }
});

test('file_read survives a 400-iteration symlink flip race (file and directory swaps): 0 leaks', async () => {
  const s = await start();
  const c = await connect(s);
  try {
    fs.writeFileSync(path.join(c.ws, 'safe.txt'), 'SAFE');
    const inner = path.join(c.ws, 'dir_real');
    fs.mkdirSync(inner);
    fs.writeFileSync(path.join(inner, 'secret.txt'), 'SAFE');
    fs.symlinkSync(outside, path.join(c.ws, 'dir_link'));
    let stop = false;
    let flips = 0;
    const flipper = (async () => {
      for (let i = 0; !stop; i++) {
        try {
          // final component: race.txt → inside file / outside file
          fs.rmSync(path.join(c.ws, 'race.txt'), { force: true });
          fs.symlinkSync(i % 2 ? path.join(outside, 'secret.txt') : path.join(c.ws, 'safe.txt'), path.join(c.ws, 'race.txt'));
          // directory component: dir → real inside dir / symlink to outside
          if (i % 2) { fs.renameSync(path.join(c.ws, 'dir'), inner); fs.renameSync(path.join(c.ws, 'dir_link'), path.join(c.ws, 'dir')); }
          else { if (fs.existsSync(path.join(c.ws, 'dir'))) fs.renameSync(path.join(c.ws, 'dir'), path.join(c.ws, 'dir_link')); fs.renameSync(inner, path.join(c.ws, 'dir')); }
          flips++;
        } catch { /* a missing entry mid-swap is fine */ }
        await new Promise((r) => setImmediate(r));
      }
    })();
    let leaks = 0;
    for (let i = 0; i < 400; i++) {
      for (const p of ['race.txt', 'dir/secret.txt']) {
        const r = await plugin(c, 'file_read', { path: p });
        if (String(r.content ?? '').includes('OUTSIDE')) leaks++;
      }
    }
    stop = true;
    await flipper;
    assert.ok(flips > 100, `the race actually ran (${flips} flips)`);
    assert.equal(leaks, 0, 'no read returned outside content');
  } finally { c.close(); }
});

test('update_config rejects unknown keys and out-of-range values; valid changes still apply', async () => {
  const s = await start();
  const c = await connect(s);
  try {
    const big = await c.send({ type: 'update_config', config: { maxIterations: 9999 } }, 'config_error');
    assert.match(big.error, /maxIterations/);
    const unknown = await c.send({ type: 'update_config', config: { systemPrompt: 'x' } }, 'config_error');
    assert.match(unknown.error, /unknown config key/);
    const proto = await c.send({ type: 'update_config', config: JSON.parse('{"__proto__": {"polluted": true}}') }, 'config_error');
    assert.match(proto.error, /unknown config key/);
    const ok = await c.send({ type: 'update_config', config: { maxIterations: 12, model: 'mercury-2' } }, 'config_updated');
    assert.equal(ok.maxIterations, 12);
    assert.equal(ok.model, 'mercury-2');
  } finally { c.close(); }
});

const CONFIG_REPLIES = ['config_error', 'config_updated'];
const updateConfig = (c: Client, config: unknown) => c.sendAny({ type: 'update_config', config }, CONFIG_REPLIES);

test('update_config refuses prototype-reaching keys, unknown keys and non-object input', async () => {
  const s = await start();
  const c = await connect(s);
  try {
    const rejected: Array<[string, object | string]> = [
      ['__proto__ as an own key (raw JSON)', '{"type":"update_config","config":{"__proto__":{"polluted":true}}}'],
      ['__proto__ beside a valid key', '{"type":"update_config","config":{"model":"mercury-2","__proto__":{"polluted":true}}}'],
      ['constructor', { type: 'update_config', config: { constructor: { prototype: { polluted: true } } } }],
      ['prototype', { type: 'update_config', config: { prototype: { polluted: true } } }],
      ['toString', { type: 'update_config', config: { toString: 1 } }],
      ['null', { type: 'update_config', config: null }],
      ['array', { type: 'update_config', config: [{ maxIterations: 5 }] }],
      ['string', { type: 'update_config', config: 'maxIterations=5' }],
      ['number', { type: 'update_config', config: 42 }],
      ['boolean', { type: 'update_config', config: true }],
      ['missing config', { type: 'update_config' }],
    ];
    for (const [label, msg] of rejected) {
      const r = await c.sendAny(msg, CONFIG_REPLIES);
      assert.equal(r.type, 'config_error', `${label} must be rejected, got ${r.type}`);
      assert.match(String(r.data.error), /unknown config key|config must be an object/, label);
    }
    const after = await updateConfig(c, {});
    assert.equal(after.type, 'config_updated');
    assert.equal(after.data.maxIterations, 20, 'rejected patches left the default untouched');
  } finally { c.close(); }
});

test('update_config enforces the documented bounds exactly (maxIterations 1-50, temperature 0-2, provider, model)', async () => {
  const s = await start();
  const c = await connect(s);
  try {
    const bad: Array<[string, Record<string, unknown>, RegExp]> = [
      ['maxIterations 0', { maxIterations: 0 }, /maxIterations/],
      ['maxIterations 51', { maxIterations: 51 }, /maxIterations/],
      ['maxIterations -1', { maxIterations: -1 }, /maxIterations/],
      ['maxIterations 1.5', { maxIterations: 1.5 }, /maxIterations/],
      ['maxIterations as a string', { maxIterations: '12' }, /maxIterations/],
      ['temperature -0.1', { temperature: -0.1 }, /temperature/],
      ['temperature 2.01', { temperature: 2.01 }, /temperature/],
      ['temperature as a string', { temperature: '1' }, /temperature/],
      ['provider openai', { provider: 'openai' }, /provider/],
      ['provider as a number', { provider: 5 }, /provider/],
      ['empty model', { model: '' }, /model/],
      ['blank model', { model: '   ' }, /model/],
      ['101-character model', { model: 'm'.repeat(101) }, /model/],
      ['model as a number', { model: 42 }, /model/],
    ];
    for (const [label, config, pattern] of bad) {
      const r = await updateConfig(c, config);
      assert.equal(r.type, 'config_error', `${label} must be rejected, got ${r.type}`);
      assert.match(String(r.data.error), pattern, label);
    }
    const good: Array<[string, Record<string, unknown>, string, unknown]> = [
      ['maxIterations 1', { maxIterations: 1 }, 'maxIterations', 1],
      ['maxIterations 50', { maxIterations: 50 }, 'maxIterations', 50],
      ['temperature 0', { temperature: 0 }, 'temperature', 0],
      ['temperature 2', { temperature: 2 }, 'temperature', 2],
      ['provider ollama', { provider: 'ollama' }, 'provider', 'ollama'],
      ['provider inception', { provider: 'inception' }, 'provider', 'inception'],
      ['model is trimmed', { model: '  mercury-2  ' }, 'model', 'mercury-2'],
    ];
    for (const [label, config, key, expected] of good) {
      const r = await updateConfig(c, config);
      assert.equal(r.type, 'config_updated', `${label} must be accepted, got ${r.type}`);
      assert.equal(r.data[key], expected, label);
    }
  } finally { c.close(); }
});

test('update_config applies nothing when any key in the patch is rejected', async () => {
  const s = await start();
  const c = await connect(s);
  try {
    const before = await updateConfig(c, {});
    assert.equal(before.type, 'config_updated');
    const other = before.data.maxIterations === 9 ? 10 : 9;
    const mixed = await updateConfig(c, { maxIterations: other, systemPrompt: 'x' });
    assert.equal(mixed.type, 'config_error', 'a patch with an unknown key is rejected as a whole');
    const after = await updateConfig(c, {});
    assert.equal(after.type, 'config_updated');
    assert.equal(after.data.maxIterations, before.data.maxIterations, 'the valid half of a rejected patch must not be applied');
  } finally { c.close(); }
});

test('http_request / rss_feed to loopback need approval; a caller cannot pre-approve itself', async () => {
  let hits = 0;
  const local = http.createServer((_req, res) => { hits++; res.end('LOCAL'); });
  await new Promise<void>((r) => local.listen(0, '127.0.0.1', r));
  const target = `http://127.0.0.1:${(local.address() as AddressInfo).port}/`;
  const s = await start();
  const c = await connect(s);
  try {
    const denied = await plugin(c, 'http_request', { url: target }, false);
    assert.match(denied.error, /Denied by human reviewer \(reaches a local or private network address\)/);
    const forged = await plugin(c, 'http_request', { url: target, allowPrivateNetwork: true }, false);
    assert.match(forged.error, /Denied by human reviewer/, 'allowPrivateNetwork in the input is ignored');
    const rss = await plugin(c, 'rss_feed', { url: target }, false);
    assert.match(rss.error, /Denied by human reviewer/);
    assert.equal(hits, 0, 'nothing reached the loopback service without approval');
    const approved = await plugin(c, 'http_request', { url: target }, true);
    assert.equal(approved.body, 'LOCAL', 'an explicit approval allows it');
    assert.equal(hits, 1);
  } finally { c.close(); local.close(); }
});

test('fetchChecked re-checks every redirect hop and refuses a bounce into a private address', async () => {
  let privateHits = 0;
  const privateSrv = http.createServer((_q, res) => { privateHits++; res.end('PRIVATE'); });
  await new Promise<void>((r) => privateSrv.listen(0, '127.0.0.1', r));
  const privateUrl = `http://127.0.0.1:${(privateSrv.address() as AddressInfo).port}/`;
  const redirector = http.createServer((_q, res) => { res.writeHead(302, { Location: privateUrl }); res.end(); });
  await new Promise<void>((r) => redirector.listen(0, '127.0.0.1', r));
  const publicUrl = `http://127.0.0.1:${(redirector.address() as AddressInfo).port}/`;
  // Treat the redirector as "public" and the target as "private" (both are loopback in a test).
  const isPrivateUrl = async (u: string) => u.startsWith(privateUrl);
  try {
    await assert.rejects(fetchChecked(publicUrl, {}, false, isPrivateUrl), /private network address/);
    assert.equal(privateHits, 0);
    assert.equal(await (await fetchChecked(publicUrl, {}, true, isPrivateUrl)).text(), 'PRIVATE');
  } finally { privateSrv.close(); redirector.close(); }
});

test('isPrivateAddress covers loopback, RFC 1918, link-local, CGNAT, IPv6 local and IPv4-mapped forms', () => {
  for (const ip of ['127.0.0.1', '127.8.8.8', '10.1.2.3', '172.16.0.1', '172.31.255.255', '192.168.1.1', '169.254.169.254', '100.64.0.1', '0.0.0.0', '::1', '::', 'fd00::1', 'fe80::1', '::ffff:127.0.0.1']) {
    assert.equal(isPrivateAddress(ip), true, ip);
  }
  for (const ip of ['8.8.8.8', '172.32.0.1', '192.169.0.1', '1.1.1.1', '2606:4700::1111']) assert.equal(isPrivateAddress(ip), false, ip);
});

test('the agent\'s own read_file/write_file tools do not follow a symlink out of the workspace', async () => {
  const mock: MockInception = await startMockInception();
  const s = await start({ INCEPTION_BASE_URL: mock.baseUrl });
  const c = await connect(s);
  try {
    fs.symlinkSync(outside, path.join(c.ws, 'escape'));
    mock.script([
      call('read_file', { path: 'escape/secret.txt' }),
      call('write_file', { path: 'escape/planted.txt', content: 'PLANTED' }),
      say('done'),
    ]);
    const result = await c.send({ type: 'run_goal', goal: 'Read escape/secret.txt', model: 'mercury-2' }, 'result', true);
    assert.equal(result.success, true);
    assert.ok(!fs.existsSync(path.join(outside, 'planted.txt')), 'no file written outside');
    const runs = await (await fetch(`${s.url}/api/runs/${result.run_id}`)).text();
    assert.doesNotMatch(runs, /OUTSIDE_SECRET/, 'outside content never reached the run record');
    assert.match(runs, /Path escapes workspace/);
  } finally { c.close(); await mock.close(); }
});
