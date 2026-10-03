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
