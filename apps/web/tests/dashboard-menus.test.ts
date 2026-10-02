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
