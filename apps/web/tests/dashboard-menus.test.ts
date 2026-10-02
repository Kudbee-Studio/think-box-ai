// Open menus (native select lists) must be dark on the dark dashboard: they opened white with light text on them.
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const pub = join(dirname(fileURLToPath(import.meta.url)), '../public');
const html = readFileSync(join(pub, 'index.html'), 'utf8');

describe('dashboard menus', () => {
  const sheets = [...html.matchAll(/<link rel="stylesheet" href="(\/css\/[^"]+)"/g)].map((m) => m[1]!);
  const lastSheet = (re: RegExp) => sheets.map((s) => ({ s, css: readFileSync(join(pub, s), 'utf8') })).filter((x) => re.test(x.css)).at(-1);

  it('declares a dark colour scheme so native popups are dark', () => {
    const hit = lastSheet(/:root\s*\{\s*color-scheme:\s*dark;?\s*\}/);
    assert.ok(hit, 'a loaded stylesheet sets color-scheme: dark on :root');
  });

  it('gives every select option an explicit dark background and light text, in the last stylesheet that styles options', () => {
    const hit = lastSheet(/select option/);
    assert.ok(hit);
    const rule = hit!.css.match(/select option, select optgroup \{([^}]*)\}/)?.[1] ?? '';
    assert.match(rule, /background-color:\s*var\(--bg-secondary/);
    assert.match(rule, /color:\s*var\(--text-primary/);
  });

  it('no stylesheet turns the page light (no light colour-scheme)', () => {
    for (const f of readdirSync(join(pub, 'css')).filter((n) => n.endsWith('.css'))) {
      assert.ok(!/^\s*color-scheme:\s*light/m.test(readFileSync(join(pub, 'css', f), 'utf8')), f);
    }
  });
});

describe('System Health', () => {
  it('styles its rows and status badges in a stylesheet the page actually loads (they were only in main.css, which is not linked)', () => {
    const linked = [...html.matchAll(/<link rel="stylesheet" href="(\/css\/[^"]+)"/g)].map((m) => readFileSync(join(pub, m[1]!), 'utf8')).join('\n');
    assert.ok(!html.includes('/css/main.css"'));
    assert.match(linked, /\.health-row \{[^}]*display: flex[^}]*justify-content: space-between/);
    for (const c of ['health-ok', 'health-warn', 'health-error']) assert.match(linked, new RegExp(`\\.badge\\.${c} \\{`), c);
  });

  it('every class app.js builds for health rows and badges has a rule', () => {
    const app = readFileSync(join(pub, 'js/app.js'), 'utf8');
    const linked = [...html.matchAll(/<link rel="stylesheet" href="(\/css\/[^"]+)"/g)].map((m) => readFileSync(join(pub, m[1]!), 'utf8')).join('\n');
    for (const c of new Set([...app.matchAll(/'(health-(?:row|ok|warn|error))'|class="(health-row)"|\b(health-(?:ok|warn|error))\b/g)].flatMap((m) => m.slice(1)).filter(Boolean) as string[])) {
      assert.ok(linked.includes(`.${c}`), `.${c} has no rule in a loaded stylesheet`);
    }
  });
});

describe('thought times and ported component styles (P3.17)', () => {
  const app = readFileSync(join(pub, 'js/app.js'), 'utf8');
  const loaded = [...html.matchAll(/<link rel="stylesheet" href="(\/css\/[^"]+)"/g)].map((m) => readFileSync(join(pub, m[1]!), 'utf8')).join('\n');

  it('a thought keeps the timestamp the server put inside its data, and an invalid one shows nothing instead of "Invalid Date"', async () => {
    const vm = await import('node:vm');
    const fn = app.match(/function formatThoughtTime\(timestamp\) \{[\s\S]*?\n\}/)?.[0];
    assert.ok(fn, 'formatThoughtTime exists');
    const ctx: any = {};
    vm.createContext(ctx);
    vm.runInContext(`${fn}; this.f = formatThoughtTime;`, ctx);
    assert.notEqual(ctx.f(1_700_000_000_000), '');
    assert.doesNotMatch(ctx.f(1_700_000_000_000), /Invalid/);
    for (const bad of [undefined, null, NaN, 'not a date', {}]) assert.equal(ctx.f(bad), '', String(bad));
    assert.match(app, /timestamp: msg\.data\?\.timestamp \?\? msg\.timestamp \?\? Date\.now\(\)/, 'the data timestamp wins over the (absent) message one');
    assert.doesNotMatch(app, /\{ \.\.\.msg\.data, timestamp: msg\.timestamp \}/);
    assert.doesNotMatch(app, /new Date\(thought\.timestamp\)\.toLocaleTimeString/);
  });

  it('every component class app.js builds has a rule in a stylesheet the page loads', () => {
    for (const c of ['plugin-badge', 'permission-note', 'git-repository-item', 'task-priority', 'task-description', 'task-meta', 'task-tags', 'task-attachments', 'task-attachment', 'task-card-actions', 'task-action', 'task-activity', 'task-activity-row', 'task-blocked-reason', 'thought-header', 'thought-type', 'thought-content', 'terminal-image', 'overdue']) {
      assert.match(app + html, new RegExp(c), `${c} is used by the page`);
      assert.match(loaded, new RegExp(`\\.${c}(?![\\w-])`), `.${c} has no rule in a loaded stylesheet`);
    }
  });

  it('the ported rules use only variables the loaded theme defines (the old --border-color is not defined there)', () => {
    const block = loaded.slice(loaded.indexOf('Components whose rules only existed in main.css'));
    const defined = new Set([...loaded.matchAll(/(--[\w-]+)\s*:/g)].map((m) => m[1]));
    for (const v of new Set([...block.matchAll(/var\((--[\w-]+)/g)].map((m) => m[1]))) assert.ok(defined.has(v!), `${v} is defined`);
  });
});
