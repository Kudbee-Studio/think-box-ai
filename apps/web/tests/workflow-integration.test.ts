// Static guard for the workflow save/load + Actions wiring: the pieces must stay connected.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const pub = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'public');
const read = (p: string) => fs.readFileSync(path.join(pub, p), 'utf8');
const html = read('index.html');
const app = read('js/app.js');
const builder = read('js/workflow-builder.js');
const action = read('js/action-button.js');

test('index.html wires the workflow store, the Actions menu and the Load button', () => {
  assert.match(html, /<script src="\/js\/workflow-store\.js"><\/script>/);
  assert.match(html, /<script src="\/js\/action-button\.js"><\/script>/);
  assert.match(html, /<link rel="stylesheet" href="\/css\/workflow-actions\.css">/);
  assert.match(html, /id="load-workflow"/);
  // The stylesheet loads before the last one, which must stay enterprise-polish.css.
  const sheets = [...html.matchAll(/<link rel="stylesheet" href="\/(css\/[^"]+)"/g)].map((m) => m[1]);
  assert.equal(sheets.at(-1), 'css/enterprise-polish.css');
  assert.ok(sheets.indexOf('css/workflow-actions.css') < sheets.length - 1);
});

test('the Actions button is no longer shipped disabled, and the menu enables it', () => {
  assert.doesNotMatch(html, /id="bulk-actions"[^>]*\bdisabled\b/);
  assert.match(action, /\.disabled = false/);
});

test('app.js saves on workflow:created and runs on workflow:created / workflow:run', () => {
  assert.match(app, /window\.addEventListener\('workflow:created'/);
  assert.match(app, /window\.addEventListener\('workflow:run'/);
  assert.match(app, /saveWorkflow\(localStorage/);
  assert.match(app, /function submitGoal\(/);
  assert.match(app, /type: 'run_goal'/);
  assert.match(app, /function runWorkflow\(/);
  assert.match(app, /composeGoal\(/);
});

test('the workflow builder dispatches workflow:created and can load a saved workflow', () => {
  assert.match(builder, /new CustomEvent\('workflow:created', \{ detail: workflow \}\)/);
  assert.match(builder, /loadWorkflow\(\)\s*\{/);
  assert.match(builder, /applyWorkflow\(/);
  assert.match(builder, /WorkflowStore/);
  assert.doesNotMatch(builder, /\balert\(/, 'the builder no longer uses alert()');
  assert.doesNotMatch(builder, /console\.log\('Workflow saved/);
});

test('the Actions menu builds its items with createElement/textContent, not innerHTML', () => {
  assert.doesNotMatch(action, /\.innerHTML\s*=/, 'the menu never writes HTML strings');
  assert.match(action, /createElement\('button'\)/);
  assert.match(action, /textContent =/);
});
