import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import { test } from 'node:test';
import express from 'express';
import { registerJobTemplateRoutes } from '../routes/job-templates.ts';

const listen = (s: http.Server): Promise<number> => new Promise((r) => s.listen(0, '127.0.0.1', () => r((s.address() as { port: number }).port)));

test('GET /api/job-templates lists them; POST fills one; a bad id or missing input is a 400', async () => {
  const app = express(); app.use(express.json()); registerJobTemplateRoutes(app);
  const s = http.createServer(app); const port = await listen(s); const base = `http://127.0.0.1:${port}`;
  try {
    const list = await (await fetch(`${base}/api/job-templates`)).json() as { templates: Array<{ id: string; name: string; param?: { required: boolean } }> };
    assert.ok(list.templates.length >= 6); assert.ok(list.templates.every((t) => !('goal' in t)), 'the goal builder is code, not data');
    const post = (id: string, input?: string) => fetch(`${base}/api/job-templates/${id}`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ input }) });
    const free = list.templates.find((t) => !t.param)!; const ok = await post(free.id);
    assert.equal(ok.status, 200); assert.match((await ok.json() as { goal: string }).goal, /cannot run/i);
    const need = list.templates.find((t) => t.param?.required)!;
    assert.equal((await post(need.id, '')).status, 400); assert.equal((await post('nope')).status, 400);
  } finally { s.close(); }
});

test('the page has the Job templates button, panel and script; the goal box is the one the panel fills', () => {
  const html = fs.readFileSync(new URL('../public/index.html', import.meta.url), 'utf8');
  for (const id of ['jobs-button', 'jobs-panel', 'close-jobs', 'jobs-container', 'goal-input']) assert.ok(html.includes(`id="${id}"`), id);
  assert.ok(html.includes('/js/job-templates-panel.js'));
});
