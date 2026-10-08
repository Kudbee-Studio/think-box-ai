// Uploads are capped as a whole, not only per file: a request that declares or streams more than the total cap is refused before it is held in memory, and nothing is written.
import assert from 'node:assert/strict';
import { spawn, type ChildProcess } from 'node:child_process';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { after, before, test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { freePort } from './helpers/free-port.ts';

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
let server: ChildProcess; let base = ''; let port = 0; let tmp = ''; let sessionId = '';
before(async () => {
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-upload-')); port = await freePort(); base = `http://127.0.0.1:${port}`; const dead = 'http://127.0.0.1:9';
  server = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], { cwd: appDir, stdio: 'ignore', env: { ...process.env, PORT: String(port), HOST: '127.0.0.1', INCEPTION_API_KEY: '', DEEPSEEK_API_KEY: '', XAI_API_KEY: '', OLLAMA_BASE_URL: dead, JANUS_BASE_URL: dead, UPSTASH_VECTOR_REST_URL: dead, UPSTASH_VECTOR_REST_TOKEN: 'none', THINKBOX_EMBEDDINGS: 'off', KUDBEE_UPLOAD_MAX_MB: '1', KUDBEE_DATA_DIR: path.join(tmp, 'data'), KUDBEE_LEARNING_DB: path.join(tmp, 'l.db'), KUDBEE_WORKSPACE_DIR: path.join(tmp, 'ws') } });
  for (let i = 0; ; i++) { try { if ((await fetch(`${base}/api/health`)).ok) break; } catch { /* starting */ } if (i > 100) throw new Error('server did not start'); await new Promise((r) => setTimeout(r, 150)); }
  const { WebSocket } = await import('ws'); const ws = new WebSocket(`ws://127.0.0.1:${port}/ws`, { origin: base });
  sessionId = await new Promise<string>((resolve, reject) => { ws.on('error', reject); ws.on('message', (raw) => { const m = JSON.parse(raw.toString()); if (m.type === 'init') { resolve(m.data.session_id ?? m.data.sessionId ?? m.data.id); } }); });
});
after(() => { server?.kill(); fs.rmSync(tmp, { recursive: true, force: true }); });

const multipart = (files: Array<[string, number]>): { body: Buffer; type: string } => {
  const b = '----kudbeeboundary'; const parts: Buffer[] = [];
  for (const [name, size] of files) parts.push(Buffer.from(`--${b}\r\nContent-Disposition: form-data; name="files"; filename="${name}"\r\nContent-Type: application/octet-stream\r\n\r\n`), Buffer.alloc(size, 65), Buffer.from('\r\n'));
  parts.push(Buffer.from(`--${b}--\r\n`)); return { body: Buffer.concat(parts), type: `multipart/form-data; boundary=${b}` };
};
const post = (m: { body: Buffer; type: string }, headers: Record<string, string> = {}) => fetch(`${base}/api/sessions/${sessionId}/files`, { method: 'POST', headers: { 'Content-Type': m.type, Origin: base, ...headers }, body: new Uint8Array(m.body) });

test('a small upload still works', async () => {
  const r = await post(multipart([['ok.txt', 1000]])); assert.equal(r.status, 201);
  assert.deepEqual(((await r.json()) as { uploaded: Array<{ path: string }> }).uploaded.map((u) => u.path), ['ok.txt']);
});

test('many files that together exceed the total cap are refused with 413, and none is written', async () => {
  const r = await post(multipart(Array.from({ length: 6 }, (_, i) => [`big${i}.bin`, 300_000] as [string, number]))); // 1.8 MB against a 1 MB cap, each file well under any per-file limit
  assert.equal(r.status, 413);
  const files = (await (await fetch(`${base}/api/sessions/${sessionId}/files`)).json() as { files: Array<{ path: string }> }).files.map((f) => f.path);
  assert.ok(!files.some((f) => f.startsWith('big')), `files were written: ${files.join(', ')}`);
});

test('a body streamed without a length is cut off at the cap', async () => {
  const m = multipart([['stream.bin', 3_000_000]]);
  const status = await new Promise<number>((resolve) => {
    const req = http.request({ host: '127.0.0.1', port, path: `/api/sessions/${sessionId}/files`, method: 'POST', headers: { 'Content-Type': m.type, Origin: base, 'Transfer-Encoding': 'chunked' } }, (res) => { res.resume(); resolve(res.statusCode ?? 0); });
    req.on('error', () => resolve(0)); req.write(m.body.subarray(0, 1_500_000)); setTimeout(() => { try { req.write(m.body.subarray(1_500_000)); req.end(); } catch { /* closed */ } }, 100);
  });
  assert.ok(status === 413 || status === 0, `expected 413 or a closed connection, got ${status}`);
  const files = (await (await fetch(`${base}/api/sessions/${sessionId}/files`)).json() as { files: Array<{ path: string }> }).files.map((f) => f.path);
  assert.ok(!files.includes('stream.bin'));
});

import { EventEmitter } from 'node:events';
import { declaredTooLarge, watchBody } from '../http-security.ts';
const fakeRes = () => { const out = { status: 0, body: undefined as unknown, headers: {} as Record<string, string> }; return { out, res: { setHeader: (k: string, v: string) => { out.headers[k] = v; }, status: (c: number) => ({ json: (b: unknown) => { out.status = c; out.body = b; } }) } }; };

test('declaredTooLarge: refuses an announced size over the cap, lets a smaller or unannounced one through', () => {
  const mk = (len?: string) => Object.assign(new EventEmitter(), { headers: len ? { 'content-length': len } : {}, destroy() {}, resume() {} }) as never;
  const a = fakeRes(); assert.equal(declaredTooLarge(mk('2000'), a.res as never, 1000), true); assert.equal(a.out.status, 413); assert.equal(a.out.headers.Connection, 'close');
  const b = fakeRes(); assert.equal(declaredTooLarge(mk('1000'), b.res as never, 1000), false); assert.equal(b.out.status, 0);
  const c = fakeRes(); assert.equal(declaredTooLarge(mk(), c.res as never, 1000), false);
});

test('watchBody: answers 413 once and closes the request when the streamed size passes the cap', async () => {
  let destroyed = 0; const req = Object.assign(new EventEmitter(), { headers: {}, destroy() { destroyed += 1; }, resume() {} }); const r = fakeRes();
  watchBody(req as never, r.res as never, 1000);
  req.emit('data', Buffer.alloc(600)); assert.equal(r.out.status, 0);
  req.emit('data', Buffer.alloc(600)); req.emit('data', Buffer.alloc(600)); await new Promise((res) => setImmediate(res));
  assert.equal(r.out.status, 413); assert.equal(destroyed, 1);
});
