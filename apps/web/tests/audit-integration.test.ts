// The audit log on the real server: an approval round trip is recorded (requested, then approved or denied by the dashboard), the API lists it, the chain verifies,
// and the CLI reads the same file. Uses a Think Token action, which asks for approval before it does anything.
import assert from 'node:assert/strict';
import { execFileSync, spawn, type ChildProcess } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { WebSocket } from 'ws';
import { freePort } from './helpers/free-port.ts';

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

test('approving and denying are recorded with the tool, the reason and the deciding channel; the API, the chain and the CLI agree', async () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-audit-int-'));
  const port = await freePort(); const base = `http://127.0.0.1:${port}`; const dead = 'http://127.0.0.1:9';
  const env = { ...process.env, PORT: String(port), HOST: '127.0.0.1', INCEPTION_API_KEY: '', DEEPSEEK_API_KEY: '', XAI_API_KEY: '', OLLAMA_BASE_URL: dead, JANUS_BASE_URL: dead, UPSTASH_VECTOR_REST_URL: dead, UPSTASH_VECTOR_REST_TOKEN: 'none', THINKBOX_EMBEDDINGS: 'off', KUDBEE_DATA_DIR: path.join(tmp, 'data'), KUDBEE_LEARNING_DB: path.join(tmp, 'l.db'), KUDBEE_WORKSPACE_DIR: path.join(tmp, 'ws') };
  const server: ChildProcess = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], { cwd: appDir, stdio: 'ignore', env });
  try {
    for (let i = 0; ; i++) { try { if ((await fetch(`${base}/api/health`)).ok) break; } catch { /* starting */ } if (i > 100) throw new Error('server did not start'); await new Promise((r) => setTimeout(r, 150)); }
    const ws = new WebSocket(`ws://127.0.0.1:${port}/ws`, { origin: base });
    await new Promise<void>((resolve, reject) => { ws.on('open', () => resolve()); ws.on('error', reject); });
    const decide = (approved: boolean): Promise<void> => new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('no approval request')), 10000);
      const onMessage = (raw: Buffer): void => { const m = JSON.parse(raw.toString()); if (m.type === 'approval_request') { ws.send(JSON.stringify({ type: 'approval_response', id: m.data.id, approved })); } if (m.type === 'approval_resolved') { clearTimeout(timer); ws.off('message', onMessage); resolve(); } };
      ws.on('message', onMessage); ws.send(JSON.stringify({ type: 'think_token_action', action: 'retire', id: 'TT-000001' }));
    });
    await decide(true); await decide(false);
    const { events } = await (await fetch(`${base}/api/audit?limit=20`)).json() as { events: Array<{ kind: string; actor: string; summary: string; detail: Record<string, any> }> };
    const kinds = events.map((e) => e.kind).reverse();
    assert.deepEqual(kinds, ['approval_requested', 'approval_resolved', 'approval_requested', 'approval_resolved']);
    const requested = events.find((e) => e.kind === 'approval_requested')!;
    assert.equal(requested.detail.tool, 'think_token_retire'); assert.match(requested.summary, /Think Token TT-000001/); assert.equal(requested.detail.args.id, 'TT-000001');
    const resolved = events.filter((e) => e.kind === 'approval_resolved').reverse();
    assert.deepEqual(resolved.map((e) => [e.summary, e.actor, e.detail.approved]), [['approved', 'dashboard', true], ['denied', 'dashboard', false]]);
    const verdict = await (await fetch(`${base}/api/audit/verify`)).json() as { ok: boolean; entries: number; head: string };
    assert.deepEqual([verdict.ok, verdict.entries], [true, 4]);
    const cli = execFileSync(process.execPath, ['--experimental-strip-types', '--no-warnings', 'cli.ts', 'audit', '--verify'], { cwd: appDir, encoding: 'utf8', env: { ...process.env, KUDBEE_DATA_DIR: path.join(tmp, 'data') } });
    assert.match(cli, /audit log intact: 4 entries/); assert.ok(cli.includes(verdict.head.slice(0, 16)));
    ws.close();
  } finally { server.kill(); fs.rmSync(tmp, { recursive: true, force: true }); }
});
