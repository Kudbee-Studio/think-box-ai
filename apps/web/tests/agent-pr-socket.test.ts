// The dashboard socket message that opens a draft pull request from the agent's changes: with KUDBEE_DRAFT_PR off (the default) it is refused plainly and nothing is asked.
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

test('repo_open_draft_pr is refused with a plain reason when draft pull requests are off', async () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-pr-socket-'));
  const port = await freePort(); const base = `http://127.0.0.1:${port}`; const dead = 'http://127.0.0.1:9';
  const s: ChildProcess = spawn(process.execPath, ['--experimental-strip-types', '--no-warnings', 'server.ts'], { cwd: appDir, stdio: 'ignore', env: { ...process.env, PORT: String(port), HOST: '127.0.0.1', INCEPTION_API_KEY: '', DEEPSEEK_API_KEY: '', XAI_API_KEY: '', KUDBEE_DRAFT_PR: 'off', OLLAMA_BASE_URL: dead, JANUS_BASE_URL: dead, UPSTASH_VECTOR_REST_URL: dead, UPSTASH_VECTOR_REST_TOKEN: 'none', THINKBOX_EMBEDDINGS: 'off', KUDBEE_DATA_DIR: path.join(tmp, 'data'), KUDBEE_LEARNING_DB: path.join(tmp, 'l.db'), KUDBEE_WORKSPACE_DIR: path.join(tmp, 'ws') } });
  try {
    for (let i = 0; ; i++) { try { if ((await fetch(`${base}/api/health`)).ok) break; } catch { /* starting */ } if (i > 100) throw new Error('server did not start'); await new Promise((r) => setTimeout(r, 150)); }
    const ws = new WebSocket(`ws://127.0.0.1:${port}/ws`, { origin: base });
    const result = await new Promise<{ ok: boolean; error?: string }>((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('no answer')), 15000);
      ws.on('error', reject);
      ws.on('open', () => ws.send(JSON.stringify({ type: 'repo_open_draft_pr' })));
      ws.on('message', (raw) => { const m = JSON.parse(raw.toString()); if (m.type === 'repo_pr_result') { clearTimeout(timer); resolve(m.data); } });
    });
    ws.close();
    assert.equal(result.ok, false); assert.match(result.error ?? '', /KUDBEE_DRAFT_PR=on/);
  } finally { s.kill(); fs.rmSync(tmp, { recursive: true, force: true }); }
});
