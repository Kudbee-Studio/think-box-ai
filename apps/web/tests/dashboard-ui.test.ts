// Static guards for the dashboard front end (apps/web/public). Each one pins a bug that shipped:
// header buttons that did nothing, a constructor calling a missing method, hidden buttons still shown,
// and the global .btn-quiet override. Rendering itself is verified with headless Chrome (see AGENTS.md).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const pub = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'public');
const read = (p: string) => fs.readFileSync(path.join(pub, p), 'utf8');
const html = read('index.html');
const pageScripts = [...html.matchAll(/<script src="\/(js\/[^"]+)"/g)].map((m) => m[1]);
const stylesheets = [...html.matchAll(/<link rel="stylesheet" href="\/(css\/[^"]+)"/g)].map((m) => m[1]);

test('panel scripts wire their header button directly, not in a nested DOMContentLoaded', () => {
  // Instances are created inside a DOMContentLoaded handler; a second DOMContentLoaded listener
  // registered from the constructor never fires, so the header button did nothing.
  for (const file of pageScripts) {
    const src = read(file);
    const nested = src.split('\n').filter((l) => /^\s{4,}document\.addEventListener\('DOMContentLoaded'/.test(l));
    assert.deepEqual(nested, [], `${file} registers DOMContentLoaded from inside a class/function`);
  }
});

test('every this.method() a panel constructor calls is defined on its class', () => {
  for (const file of pageScripts) {
    const src = read(file);
    for (const cls of src.matchAll(/class (\w+) \{([\s\S]*?)\n\}/g)) {
      const body = cls[2];
      const ctor = body.match(/constructor\([^)]*\) \{([\s\S]*?)\n  \}/);
      if (!ctor) continue;
      const defined = new Set([...body.matchAll(/^\s{2}(?:async )?(\w+)\([^)]*\) \{/gm)].map((m) => m[1]));
      for (const call of ctor[1].matchAll(/this\.(\w+)\(/g)) {
        assert.ok(defined.has(call[1]), `${file}: ${cls[1]} constructor calls undefined this.${call[1]}()`);
      }
    }
  }
});

test('the hidden attribute wins over component display rules', () => {
  const last = stylesheets.at(-1)!;
  assert.equal(last, 'css/polish.css', 'polish.css must load last');
  assert.match(read(last), /\[hidden\]\s*\{\s*display:\s*none\s*!important;?\s*\}/);
});

test('no secondary stylesheet redefines the shared .btn-quiet globally', () => {
  for (const sheet of stylesheets.filter((s) => s !== 'css/main-pro.css')) {
    assert.doesNotMatch(read(sheet), /^\.btn-quiet\s*[{,:]/m, `${sheet} overrides .btn-quiet for the whole page`);
  }
});

test('every class-based stylesheet and script referenced by index.html exists', () => {
  for (const asset of [...stylesheets, ...pageScripts]) assert.ok(fs.existsSync(path.join(pub, asset)), asset);
});

test('demo panels carry the demo banner and never ask for a secret or claim a connection', () => {
  const banner = '<div class="demo-banner" role="note">Demo data - not connected to real services</div>';
  for (const file of ['js/integration-connectors.js', 'js/collaboration-dashboard.js']) {
    const src = read(file);
    assert.ok(src.includes(banner), `${file} is missing the demo banner`);
    assert.doesNotMatch(src, /<input[^>]*type="password"/i, `${file} renders a password/secret input`);
    assert.doesNotMatch(src, /<input[^>]*id="[^"]*(token|api-?key|secret)[^"]*"/i, `${file} renders a token/API-key input`);
    assert.doesNotMatch(src, /✓ Connected/, `${file} can claim a service is connected`);
    assert.doesNotMatch(src, /credentials are encrypted/i, `${file} makes an unbacked security claim`);
  }
  const css = read('css/polish.css');
  assert.match(css, /\.demo-banner\s*\{/, 'demo banner is styled');
});
