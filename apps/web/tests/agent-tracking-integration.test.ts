// Static guard: the agent tracking chain (WebSocket -> registry -> taskbar -> governance window -> approval) stays wired.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const pub = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'public');
const read = (p: string) => fs.readFileSync(path.join(pub, p), 'utf8');
const html = read('index.html');
const app = read('js/app.js');
const registry = read('js/agent-registry.js');
const taskbar = read('js/agent-taskbar.js');
const governance = read('js/governance-window.js');

test('index.html loads the agent scripts in dependency order and the stylesheet before the last one', () => {
  const order = ['js/agent-registry.js', 'js/agent-taskbar.js', 'js/governance-window.js'].map((f) => html.indexOf(`<script src="/${f}"></script>`));
  assert.ok(order.every((i) => i >= 0), 'all three scripts are referenced');
  assert.ok(order[0] < order[1] && order[1] < order[2], 'registry loads before the taskbar and governance window');
  assert.match(html, /<link rel="stylesheet" href="\/css\/agent-tracking\.css">/);
  const sheets = [...html.matchAll(/<link rel="stylesheet" href="\/(css\/[^"]+)"/g)].map((m) => m[1]);
  assert.equal(sheets.at(-1), 'css/enterprise-polish.css');
  assert.ok(sheets.indexOf('css/agent-tracking.css') < sheets.length - 1);
});

test('app.js feeds every WebSocket message to the registry and answers approvals over the socket', () => {
  assert.match(app, /window\.agentRegistry\) window\.agentRegistry\.ingest\(msg\)/);
  assert.match(app, /window\.addEventListener\('approval:resolved'/);
  assert.match(app, /type: 'approval_response'/);
});

test('the registry dispatches agents:changed and keeps the fields the UI reads', () => {
  assert.match(registry, /new root\.CustomEvent\('agents:changed'/);
  for (const field of ['run_id', 'goal', 'steps_completed', 'tokens_used', 'think_box_id', 'approval_pending', 'approvals']) {
    assert.match(registry, new RegExp(`${field}:`), `agent record keeps ${field}`);
  }
  assert.match(registry, /case 'run_update':/);
  assert.match(registry, /case 'approval_request':/);
  assert.match(registry, /case 'specialist_result':/);
  assert.match(registry, /case 'think_token_cube':/);
});

test('the taskbar subscribes to agents:changed and dispatches agent:open', () => {
  assert.match(taskbar, /addEventListener\('agents:changed'/);
  assert.match(taskbar, /new EventCtor\('agent:open'/);
  assert.match(taskbar, /createElement\('button'\)/);
});

test('the governance window is a .modal-backdrop, dispatches approval:resolved, and never writes innerHTML', () => {
  assert.match(governance, /className = 'modal-backdrop governance-window'/);
  assert.match(governance, /new EventCtor\('approval:resolved'/);
  assert.match(governance, /addEventListener\('agent:open'/);
  for (const [name, src] of [['agent-registry.js', registry], ['agent-taskbar.js', taskbar], ['governance-window.js', governance]] as const) {
    assert.doesNotMatch(src, /\.innerHTML\s*=/, `${name} must not write HTML strings`);
  }
});
