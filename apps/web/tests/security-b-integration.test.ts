// Security batch B on the real server: the data folder is locked at start, an oversized WebSocket frame closes that connection, a flood is answered with
// "slow down" instead of work, a normal client still works, and /api/doctor reports.
import assert from 'node:assert/strict';
import { spawn, type ChildProcess } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { WebSocket } from 'ws';
import { freePort } from './helpers/free-port.ts';

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

test('locked data folder, frame cap, message flood limit and the doctor route', async () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-secb-'));
  const data = path.join(tmp, 'data');
  fs.mkdirSync(data, { mode: 0o755 });
  fs.chmodSync(data, 0o755);
  fs.writeFileSync(path.join(data, 'runs.json'), '[]', { mode: 0o644 });
  const port = await freePort(); const base = `http://127.0.0.1:${port}`; const dead = 'http://127.0.0.1:9';
  const env = { ...process.env, PORT: String(port), HOST: '127.0.0.1', INCEPTION_API_KEY: '', DEEPSEEK_API_KEY: '', XAI_API_KEY: '', OLLAMA_BASE_URL: dead, JANUS_BASE_URL: dead, UPSTASH_VECTOR_REST_URL: dead, UPSTASH_VECTOR_REST_TOKEN: 'none', THINKBOX_EMBEDDINGS: 'off', KUDBEE_DATA_DIR: data, KUDBEE_LEARNING_DB: path.join(tmp, 'l.db'), KUDBEE_WORKSPACE_DIR: path.join(tmp, 'ws') };
  const server: ChildProcess = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], { cwd: appDir, stdio: 'ignore', env });
  const open = async (): Promise<WebSocket> => {
    const ws = new WebSocket(`ws://127.0.0.1:${port}/ws`, { origin: base });
    await new Promise<void>((resolve, reject) => { ws.on('open', () => resolve()); ws.on('error', reject); });
    return ws;
  };
  try {
    for (let i = 0; ; i++) { try { if ((await fetch(`${base}/api/health`)).ok) break; } catch { /* starting */ } if (i > 100) throw new Error('server did not start'); await new Promise((r) => setTimeout(r, 150)); }
    assert.equal(fs.statSync(data).mode & 0o777, 0o700, 'the data folder is private to the owner');
    assert.equal(fs.statSync(path.join(data, 'runs.json')).mode & 0o777, 0o600);

    const big = await open();
    const closed = new Promise<number>((resolve) => big.on('close', (code) => resolve(code)));
    big.send(JSON.stringify({ type: 'ping', pad: 'x'.repeat(1_100_000) }));
    assert.equal(await closed, 1009, 'a frame over 1 MB is refused at the protocol level');

    const flood = await open();
    const replies: string[] = [];
    flood.on('message', (raw) => { const m = JSON.parse(raw.toString()); if (m.type === 'error') replies.push(String(m.data)); });
    for (let i = 0; i < 400; i++) flood.send(JSON.stringify({ type: 'nope' }));
    await new Promise((r) => setTimeout(r, 1500));
    assert.ok(replies.some((r) => /slow down/.test(r)), 'a flood is told to slow down');
    assert.ok(replies.length <= 400);
    flood.close();

    const good = await open();
    assert.equal(good.readyState, WebSocket.OPEN, 'a fresh connection is not affected by the noisy one');
    good.close();

    const doctor = await (await fetch(`${base}/api/doctor`)).json() as { checks: Array<{ id: string; status: string }>; ok: boolean };
    assert.equal(doctor.checks.find((c) => c.id === 'data-permissions')?.status, 'ok');
    assert.equal(doctor.checks.find((c) => c.id === 'dependency-audit')?.status, 'skipped');
  } finally { server.kill(); fs.rmSync(tmp, { recursive: true, force: true }); }
});
