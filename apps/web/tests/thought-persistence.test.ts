// Thoughts survive a dashboard reload and a server restart: saved per profile, secrets redacted, size-capped, bounded, clearable.
import { after, before, describe, it, test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { spawn, type ChildProcess } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { WebSocket } from 'ws';
import { MAX_THOUGHT_JSON, PersistenceLayer } from '../persistence.ts';
import { freePort } from './helpers/free-port.ts';

describe('PersistenceLayer thoughts', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'thoughts-'));
  const p = new PersistenceLayer(dir);
  after(() => { p.close(); fs.rmSync(dir, { recursive: true, force: true }); });
  const t = (n: number, o: Record<string, unknown> = {}) => ({ id: `t${n}`, timestamp: 1000 + n, type: 'tool_call', status: 'running', content: `step ${n}`, ...o });

  it('returns the newest first-limited thoughts oldest-first, per profile', () => {
    for (let i = 1; i <= 5; i += 1) p.saveThought('a', 's1', { ...t(i), id: `a${i}` });
    p.saveThought('b', 's2', { ...t(99), id: 'b99' });
    assert.deepEqual(p.recentThoughts('a', 3).map((x) => x.id), ['a3', 'a4', 'a5']);
    assert.deepEqual(p.recentThoughts('b').map((x) => x.id), ['b99']);
    assert.deepEqual(p.recentThoughts('nobody'), []);
  });
  it('saving the same id twice keeps one row', () => {
    p.saveThought('c', 's', { ...t(1, { content: 'first' }), id: 'c1' }); p.saveThought('c', 's', { ...t(1, { content: 'second' }), id: 'c1' });
    assert.equal(p.recentThoughts('c').length, 1);
    assert.equal(p.recentThoughts('c')[0]!.content, 'second');
  });
  it('redacts secrets before they reach disk', () => {
    p.saveThought('d', 's', { ...t(1, { content: 'called with Authorization: Bearer abcdefghijklmnopqrstuvwxyz0123456789 and sk-abcdefghijklmnopqrstuvwxyz0123' }), id: 'd1' });
    const raw = JSON.stringify(p.recentThoughts('d'));
    assert.ok(!raw.includes('abcdefghijklmnopqrstuvwxyz0123456789'), raw);
    assert.ok(!/sk-abcdefghijklmnopqrstuvwxyz/.test(raw), raw);
  });
  it('cuts an oversized thought instead of dropping it, and keeps valid JSON', () => {
    p.saveThought('e', 's', { ...t(1, { content: 'x'.repeat(20000), output: 'y'.repeat(20000) }), id: 'e1' });
    const [got] = p.recentThoughts('e');
    assert.ok(got);
    assert.equal(got!.truncated, true);
    assert.ok(JSON.stringify(got).length <= MAX_THOUGHT_JSON);
    assert.equal(got!.id, 'e1');
  });
  it('clear removes only that profile', () => {
    assert.ok(p.clearThoughts('a') >= 5);
    assert.deepEqual(p.recentThoughts('a'), []);
    assert.equal(p.recentThoughts('b').length, 1);
  });
  it('a damaged row is skipped, not fatal, and a write failure never throws', () => {
    (p as any).db.prepare("INSERT INTO thoughts (id, profileId, sessionId, ts, type, status, runId, json) VALUES ('bad','f','s',1,'','','','{not json')").run();
    p.saveThought('f', 's', { ...t(2), id: 'f2' });
    assert.deepEqual(p.recentThoughts('f').map((x) => x.id), ['f2']);
    p.close();
    assert.doesNotThrow(() => p.saveThought('f', 's', { ...t(3), id: 'f3' }));
  });
});

// ── through the real server: reload and restart ──
const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
let ollama: http.Server; let data = ''; let tmp = '';
const start = async (): Promise<{ base: string; stop: () => Promise<void> }> => {
  const port = await freePort();
  const server: ChildProcess = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], { cwd: appDir, stdio: 'ignore',
    env: { ...process.env, PORT: String(port), INCEPTION_API_KEY: '', DEEPSEEK_API_KEY: '', XAI_API_KEY: '', INCEPTION_API_KEY_2: '', OLLAMA_BASE_URL: `http://127.0.0.1:${(ollama.address() as { port: number }).port}`, JANUS_BASE_URL: 'http://127.0.0.1:9', UPSTASH_VECTOR_REST_URL: 'http://127.0.0.1:9', UPSTASH_VECTOR_REST_TOKEN: 'none', THINKBOX_EMBEDDINGS: 'off', KUDBEE_DATA_DIR: data, KUDBEE_LEARNING_DB: path.join(tmp, 'l.db'), KUDBEE_WORKSPACE_DIR: path.join(tmp, 'ws'), THINKBOX_LOCAL_MODEL: 'smollm2:360m' } });
  const base = `http://127.0.0.1:${port}`;
  for (let i = 0; i < 100; i++) { try { if ((await fetch(`${base}/api/health`)).ok) break; } catch { /* starting */ } await new Promise((r) => setTimeout(r, 150)); }
  return { base, stop: () => new Promise((r) => { server.once('exit', () => r()); server.kill(); }) };
};
const connect = (base: string, onMsg?: (m: any) => void) => new Promise<{ ws: WebSocket; init: any; messages: any[] }>((resolve, reject) => {
  const ws = new WebSocket(`${base.replace('http', 'ws')}/ws`, { origin: base });
  const messages: any[] = [];
  ws.on('error', reject);
  ws.on('message', (raw) => { const m = JSON.parse(raw.toString()); messages.push(m); onMsg?.(m); if (m.type === 'init') resolve({ ws, init: m.data, messages }); });
});

describe('thoughts through the real server', () => {
  before(async () => {
    tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'thoughts-srv-')); data = path.join(tmp, 'data');
    ollama = http.createServer((req, res) => { let b = ''; req.on('data', (d) => { b += d; }); req.on('end', () => { res.setHeader('content-type', 'application/x-ndjson'); if (req.url === '/api/tags') return void res.end(JSON.stringify({ models: [{ name: 'smollm2:360m', size: 1 }] })); res.write(`${JSON.stringify({ message: { content: 'It is 4.' }, done: false })}\n`); res.end(`${JSON.stringify({ message: { content: '' }, done: true })}\n`); }); });
    await new Promise<void>((r) => ollama.listen(0, '127.0.0.1', r));
  });
  after(async () => { await new Promise((r) => ollama.close(r)); fs.rmSync(tmp, { recursive: true, force: true }); });

  test('a reload (new session) and a restart both bring the thoughts back, and Clear removes them for good', async () => {
    let s = await start();
    const first = await connect(s.base);
    assert.deepEqual(first.init.thoughts, [], 'a fresh install has none');
    first.ws.send(JSON.stringify({ type: 'run_goal', goal: 'What is 2 plus 2?', model: 'smollm2:360m' }));
    for (const end = Date.now() + 20000; !first.messages.some((m) => m.type === 'result') && Date.now() < end; await new Promise((r) => setTimeout(r, 50)));
    const live = first.messages.filter((m) => m.type === 'thought').map((m) => m.data);
    assert.ok(live.length >= 2, `thoughts were emitted (${live.length})`);
    first.ws.close();
    // reload: a new session of the same server
    const second = await connect(s.base);
    assert.ok(second.init.thoughts.length >= live.length, 'the reloaded dashboard is sent the saved thoughts');
    assert.deepEqual(second.init.thoughts.slice(0, live.length).map((t: any) => t.id), live.map((t: any) => t.id), 'same thoughts, same order');
    second.ws.close();
    // restart: a new process on the same data folder
    await s.stop();
    s = await start();
    const third = await connect(s.base);
    assert.ok(third.init.thoughts.length >= live.length, 'the thoughts survive a server restart');
    assert.ok(third.init.thoughts.some((t: any) => /Starting goal|Answered by/.test(String(t.content))));
    // Clear removes the saved history, so it does not come back
    third.ws.send(JSON.stringify({ type: 'clear_thoughts' }));
    await new Promise<void>((resolve) => { const t = setInterval(() => { if (third.messages.some((m) => m.type === 'thoughts_cleared')) { clearInterval(t); resolve(); } }, 20); });
    third.ws.close();
    const fourth = await connect(s.base);
    assert.deepEqual(fourth.init.thoughts, [], 'cleared for good');
    fourth.ws.close();
    await s.stop();
  });
});
