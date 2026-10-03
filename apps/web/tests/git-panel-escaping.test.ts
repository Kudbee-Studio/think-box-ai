// The Git panel renders names and paths from a cloned public repository: attacker-chosen text. Its escapeHtml must be safe
// inside quoted attributes too, and no repository text may reach innerHTML or inline handlers unescaped.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const file = path.join(path.dirname(fileURLToPath(import.meta.url)), '../public/js/git-integration.js');
const src = fs.readFileSync(file, 'utf8');

function anything(own: Record<string, unknown> = {}): any {
  return new Proxy(function () {}, {
    get: (_t, p) => (typeof p === 'symbol' ? undefined : p in own ? own[p] : p === 'length' ? 0 : anything()),
    apply: () => anything(),
    construct: () => anything(),
    set: () => true,
  });
}

function panel(): any {
  const handlers: Array<() => void> = [];
  const window: Record<string, unknown> = { addEventListener() {} };
  const sandbox: Record<string, unknown> = {
    window,
    document: anything({ addEventListener: (t: string, fn: () => void) => { if (t === 'DOMContentLoaded') handlers.push(fn); } }),
    console: { log() {}, warn() {}, error() {} },
    setTimeout: () => 0,
  };
  vm.createContext(sandbox);
  vm.runInContext(src, sandbox, { filename: 'git-integration.js' });
  for (const h of handlers) h();
  return window.gitIntegration;
}

test('git panel escapeHtml escapes quotes as well as < > &, so it is safe inside value="..." and class="..."', () => {
  const p = panel();
  assert.equal(p.escapeHtml(`a"b'c<d>&e`), 'a&quot;b&#39;c&lt;d&gt;&amp;e');
  assert.equal(p.escapeHtml(undefined), '');
});

test('the file tree escapes file and folder names (a repository can contain a file named <img src=x onerror=...>)', () => {
  const fn = src.slice(src.indexOf('renderFileTree(node'), src.indexOf('handleFileTreeClick(event)'));
  assert.ok(!fn.includes('<span class="name">${item.name}</span>'), 'item.name reaches innerHTML raw');
  assert.ok(fn.includes('<span class="name">${this.escapeHtml(item.name)}</span>'));
  assert.ok(fn.includes('<div class="repo-name">${this.escapeHtml(prefix)}</div>'));
});
