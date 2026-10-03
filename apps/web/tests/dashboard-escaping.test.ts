// Dashboard values that reach innerHTML must be escaped (CodeQL js/xss). Source-level checks, like the other dashboard tests: the scripts need a browser.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const js = path.join(path.dirname(fileURLToPath(import.meta.url)), '../public/js');
const read = (f: string): string => fs.readFileSync(path.join(js, f), 'utf8');

test('the git clone dialog escapes the pasted URL before putting it in the input value', () => {
  const src = read('git-integration.js');
  assert.ok(!src.includes('value="${url}"'), 'the URL is interpolated raw into an attribute');
  assert.ok(src.includes('value="${this.escapeHtml(url)}"'));
});

test('a thought\'s status is escaped before it is used in the thought-item class attribute', () => {
  const src = read('app.js');
  assert.ok(!src.includes('class="thought-item ${thought.status'), 'thought.status is interpolated raw into a class attribute');
  assert.ok(src.includes("class=\"thought-item ${escapeHtml(thought.status || 'info')}\""));
});

test('run progress is kept in a prototype-less object, so a run id like __proto__ or constructor cannot touch or inherit from Object.prototype', () => {
  const src = read('app.js');
  assert.ok(src.includes('runProgress: Object.create(null)'), 'state.runProgress must not be a plain {}');
});

test('the offline page shows message text with textContent, never as HTML', () => {
  const html = fs.readFileSync(path.join(js, '../index-offline.html'), 'utf8');
  assert.ok(!html.includes('<div class="message-content">${text}</div>'), 'message text is interpolated raw into innerHTML');
  assert.ok(html.includes("querySelector('.message-content').textContent = text"));
});

test('the mock dashboard shows a thought\'s text with textContent, never as HTML', () => {
  const src = read('app-mock.js');
  assert.ok(!src.includes('${thought.text || \'thinking...\'}'), 'thought.text is interpolated raw into innerHTML');
  assert.ok(src.includes("textContent = thought.text || 'thinking...'"));
});

test('the middleware test reports an HTTP or malformed reply clearly instead of crashing on result.checks.map', () => {
  const src = read('app.js');
  const i = src.indexOf('/api/middleware/test');
  const body = src.slice(i, i + 700);
  assert.match(body, /!response\.ok \|\| !Array\.isArray\(result\.checks\)/);
});
