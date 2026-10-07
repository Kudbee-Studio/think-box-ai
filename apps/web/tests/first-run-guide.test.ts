// What a new customer sees in the dashboard: a plain first-run guide instead of the developer banner, and a model picker that says what each cloud agent costs and how fast it is.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';
import { createModelClients } from '../ollama-client.ts';

const app = fs.readFileSync(path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'public', 'js', 'app.js'), 'utf8');

test('the first-run guide says how to start in three steps and the approval promise, and the developer banner is gone', () => {
  const block = app.slice(app.indexOf("'🐝 kudbEE Agent OS — agents propose, you decide.'"), app.indexOf("].join('\\n'));", app.indexOf("agents propose, you decide")));
  for (const part of ['Get started:', '1. Pick a model above', '2. Optional: paste a GitHub repository link under Files', 'use for agent', '3. Type a goal in plain English', 'asks you first', '/help']) assert.ok(block.includes(part), part);
  assert.ok(!app.includes('— Enterprise Edition                     ║'), 'the box-drawing developer banner is gone');
});

function noteFn(): (m: unknown) => string {
  const src = app.slice(app.indexOf('function modelMeasureNote'), app.indexOf('function renderAgents'));
  return vm.runInNewContext(`${src}; modelMeasureNote`) as (m: unknown) => string;
}

test('the model picker label adds cost per task and time for a measured model, marks an estimated price, and adds nothing for an unmeasured one', () => {
  const note = noteFn();
  assert.equal(note({ measured: { usd: 0.002052, secs: 2.6, estimated: false } }), ' · ~$0.0021/task · 2.6 s');
  assert.equal(note({ measured: { usd: 0.002758, secs: 5.4, estimated: true } }), ' · ~$0.0028/task (est.) · 5.4 s');
  assert.equal(note({ measured: { usd: 0.0127, secs: 5.9, estimated: false } }), ' · ~$0.013/task · 5.9 s');
  assert.equal(note({}), ''); assert.equal(note(null), ''); assert.equal(note({ measured: undefined }), '');
  assert.match(app, /`⚡ \$\{m\.name\} — \$\{m\.vendor \|\| 'Inception'\}\$\{modelMeasureNote\(m\)\}`/);
});

test('the model list the dashboard fetches carries each cloud agent\'s measured numbers', async () => {
  const keep = { i: process.env.INCEPTION_API_KEY, d: process.env.DEEPSEEK_API_KEY, x: process.env.XAI_API_KEY };
  process.env.INCEPTION_API_KEY = 'i'; process.env.DEEPSEEK_API_KEY = 'd'; process.env.XAI_API_KEY = 'x';
  try {
    const clients = createModelClients({ ollamaBaseUrl: 'http://127.0.0.1:9', janusBaseUrl: 'http://127.0.0.1:9', janusEnabled: () => false });
    const list = (await clients.listModels()) as Array<{ name: string; agent?: boolean; measured?: { verified: number; tasks: number; usd: number; secs: number; estimated: boolean } }>;
    const by = Object.fromEntries(list.filter((m) => m.agent).map((m) => [m.name, m.measured]));
    assert.deepEqual(by['mercury-2'], { verified: 64, tasks: 66, usd: 0.002052, secs: 2.6, estimated: false });
    assert.equal(by['deepseek-flash']?.estimated, true);
    assert.equal(by['grok-4.3']?.estimated, false);
    assert.equal(Object.values(by).filter((m) => m).length, 5, 'all five registered cloud agents are measured');
  } finally { for (const [k, v] of [['INCEPTION_API_KEY', keep.i], ['DEEPSEEK_API_KEY', keep.d], ['XAI_API_KEY', keep.x]] as const) { if (v === undefined) delete process.env[k]; else process.env[k] = v; } }
});
