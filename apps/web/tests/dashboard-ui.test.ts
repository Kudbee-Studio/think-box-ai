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

test('escapeHtml escapes quotes so a value cannot break out of an HTML attribute', () => {
  const fn = read('js/app.js').match(/function escapeHtml\(text\) \{[\s\S]*?\n\}/);
  assert.ok(fn, 'escapeHtml not found in app.js');
  const escapeHtml = new Function(`${fn[0]}; return escapeHtml;`)() as (text: unknown) => string;
  assert.equal(escapeHtml('x" onmouseover="alert(1)'), 'x&quot; onmouseover=&quot;alert(1)');
  assert.equal(escapeHtml("<a href='x'>&</a>"), '&lt;a href=&#39;x&#39;&gt;&amp;&lt;/a&gt;');
  assert.equal(escapeHtml(undefined), '');
  assert.equal(escapeHtml(42), '42');
});

test('every capped-height region scrolls: a max-height always comes with overflow auto/scroll', () => {
  const scrollsIn = (body: string) => /overflow(-y)?\s*:\s*(auto|scroll)/.test(body);
  const rules = stylesheets.flatMap((sheet) =>
    [...read(sheet).replace(/\/\*[\s\S]*?\*\//g, '').matchAll(/([^{}]+)\{([^{}]*)\}/g)]
      .map((m) => ({ sheet, selectors: m[1].trim().split(',').map((s) => s.trim()), body: m[2] })));
  const scrolling = new Set(rules.filter((r) => scrollsIn(r.body)).flatMap((r) => r.selectors));
  const capped = rules.filter((r) => /max-height\s*:\s*(?!none)/.test(r.body) && !/text-overflow/.test(r.body));
  for (const rule of capped) {
    for (const selector of rule.selectors) {
      assert.ok(scrollsIn(rule.body) || scrolling.has(selector), `${rule.sheet}: "${selector}" has a max-height but never scrolls`);
    }
  }
  assert.doesNotMatch(read('css/polish.css'), /\.modal > :not\(\.modal-header\):not\(\.modal-actions\)\s*\{[^}]*overflow-x:\s*hidden/,
    'modal bodies must scroll sideways, not clip wide content');
});

test('model and agent pickers stay visible below 1024px', () => {
  const block = read('css/polish.css').match(/@media \(max-width: 1023px\) \{([\s\S]*?)\n\}/);
  assert.ok(block, 'polish.css needs a max-width: 1023px block');
  assert.match(block[1], /\.header-center\s*\{[^}]*display:\s*flex/);
});

test('command buttons and shortcuts never overwrite the goal being typed', () => {
  const clobbers = read('js/app.js').split('\n').filter((l) => /getElementById\('goal-input'\)\.value = '\//.test(l));
  assert.deepEqual(clobbers, [], 'use runCommand() instead of writing a slash command into the goal input');
});

test('the terminal panel fills .center so its own overflow:auto can actually scroll', () => {
  // .center is display:flex; flex-direction:column; overflow:hidden (main-pro.css). .terminal-panel
  // is its only flex child and .terminal inside it is flex:1; overflow-y:auto. Without flex:1 and
  // min-height:0 on .terminal-panel itself, it sizes to its content instead of filling .center, so
  // the terminal never hits a height ceiling to scroll against — it just grows past the viewport and
  // gets silently clipped by .center's overflow:hidden. Verified live: before this rule, flooding the
  // terminal with 80 messages left panelHeight 8579px (== content) vs centerHeight 584px, scrollable
  // false; after, panelHeight == centerHeight and scrollable true.
  const rule = read('css/polish.css').match(/\.terminal-panel\s*\{([^}]*)\}/);
  assert.ok(rule, '.terminal-panel needs a sizing rule in polish.css');
  assert.match(rule[1], /flex\s*:\s*1\b/, '.terminal-panel must flex:1 to fill .center');
  assert.match(rule[1], /min-height\s*:\s*0\b/, '.terminal-panel must min-height:0 so it can shrink below its content size');
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
