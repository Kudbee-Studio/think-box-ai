// The header Model and Agent dropdowns (public/js/app.js). Source-level checks, like the other dashboard tests: app.js needs a browser.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const app = fs.readFileSync(path.join(path.dirname(fileURLToPath(import.meta.url)), '../public/js/app.js'), 'utf8');

test('choosing a model in the header dropdown updates state.config.model and the server session (so /model, /config and /session agree with it)', () => {
  assert.match(app, /getElementById\('model-select'\)\.addEventListener\('change'[\s\S]{0,400}state\.config\.model = [\s\S]{0,300}type: 'update_config'/);
});

test('renderAgents reads the current selection before it rebuilds the options, so the chosen agent survives a refresh', () => {
  const fn = app.slice(app.indexOf('function renderAgents'), app.indexOf('// ─── Actions'));
  assert.ok(fn.includes('const previous = select.value'), 'renderAgents must remember the selection');
  assert.ok(fn.indexOf('const previous = select.value') < fn.indexOf('select.innerHTML'), 'the selection must be read before innerHTML replaces the options');
});
