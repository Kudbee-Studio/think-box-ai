// Startup time: rarely used libraries are loaded on first use, not at boot. These tests prove the lazy paths still work end to end
// (the first upload loads multer, the next reuses it) and that nobody re-adds the eager imports.
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawn, type ChildProcess } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { WebSocket } from 'ws';

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
let tmp: string;
const procs: ChildProcess[] = [];
before(() => { tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-lazy-')); });
after(() => { for (const p of procs) p.kill('SIGKILL'); fs.rmSync(tmp, { recursive: true, force: true }); });

test('server.ts does not eagerly import the startup-heavy modules (http facade, multer, fast-xml-parser)', () => {
  const src = fs.readFileSync(path.join(appDir, 'server.ts'), 'utf8');
  const staticImports = [...src.matchAll(/^import\s(?!type\s)[^;]*?from\s+'([^']+)';/gm)].map((m) => m[1]); // `import type` is erased and costs nothing
  for (const heavy of ['http', 'node:http', 'multer', 'fast-xml-parser']) {
    assert.ok(!staticImports.includes(heavy), `server.ts statically imports '${heavy}' again (costs 30-55 ms at every start)`);
  }
  assert.match(src, /createRequire\(import\.meta\.url\)\('node:http'\)/, 'http comes through require(), which skips the ESM facade');
});

async function start(): Promise<{ url: string; port: number; workspaces: string }> {
  const port = 20000 + Math.floor(Math.random() * 20000);
  const dead = 'http://127.0.0.1:9';
  const workspaces = path.join(tmp, 'w');
  const proc = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], {
    cwd: appDir,
    env: {
      ...process.env, PORT: String(port), INCEPTION_API_KEY: 'test', INCEPTION_API_KEY_2: '', OLLAMA_BASE_URL: dead, JANUS_BASE_URL: dead,
      UPSTASH_VECTOR_REST_URL: dead, UPSTASH_VECTOR_REST_TOKEN: 'none', KUDBEE_DAILY_BUDGET_USD: '0', THINKBOX_BACKEND_URL: dead,
      KUDBEE_DATA_DIR: path.join(tmp, 'd'), KUDBEE_WORKSPACE_DIR: workspaces,
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

async function sessionId(s: { url: string; port: number }): Promise<string> {
  return new Promise((resolve, reject) => {
    const sock = new WebSocket(`ws://127.0.0.1:${s.port}/ws`, { origin: s.url });
    sock.on('message', (raw) => { const m = JSON.parse(raw.toString()); if (m.type === 'init') { resolve(m.data.sessionId); } });
    sock.on('error', reject);
    setTimeout(() => reject(new Error('no init message')), 8000);
  });
}

test('real server: the first multipart upload loads multer lazily and works; later uploads and the image routes work too', async () => {
  const s = await start();
  const id = await sessionId(s);
  const files = `${s.url}/api/sessions/${id}/files`;

  const form1 = new FormData();
  form1.append('files', new Blob(['hello lazy upload']), 'a.txt');
  const first = await fetch(files, { method: 'POST', body: form1 });
  assert.equal(first.status, 201, await first.clone().text());
  assert.deepEqual(((await first.json()) as { uploaded: unknown[] }).uploaded.length, 1);

  const form2 = new FormData();
  form2.append('files', new Blob(['second']), 'b.txt');
  form2.append('files', new Blob(['third']), 'c.txt');
  const second = await fetch(files, { method: 'POST', body: form2 });
  assert.equal(second.status, 201);
  assert.equal(((await second.json()) as { uploaded: unknown[] }).uploaded.length, 2, 'the cached multer instance handles a multi-file upload');

  const listing = (await (await fetch(files)).json()) as { files: Array<{ path: string }> };
  assert.deepEqual(listing.files.map((f) => f.path).sort(), ['a.txt', 'b.txt', 'c.txt']);
  const content = await (await fetch(`${files}/content?path=a.txt`)).json() as { content: string };
  assert.equal(content.content, 'hello lazy upload');

  // The single-file image routes go through the same lazy loader: with no file the handler (not multer) answers.
  const noImage = await fetch(`${s.url}/api/sessions/${id}/images/analyze`, { method: 'POST', body: new FormData() });
  assert.equal(noImage.status, 400, 'multer ran, found no image, and the handler refused it');
});

test('real server: reading an RSS feed loads fast-xml-parser on demand (feed to a loopback server needs the approval path, so call the parser the way the tool does)', async () => {
  const { XMLParser } = await import('fast-xml-parser');
  const doc = new XMLParser({ ignoreAttributes: false, attributeNamePrefix: '@_' }).parse('<rss><channel><title>t</title><item><title>one</title></item></channel></rss>') as { rss: { channel: { title: string } } };
  assert.equal(doc.rss.channel.title, 't');
  const src = fs.readFileSync(path.join(appDir, 'server.ts'), 'utf8');
  assert.match(src, /await import\('fast-xml-parser'\)/, 'the rss_feed tool imports the parser when it is first used');
});
