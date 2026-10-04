// Unit tests for the window manager's pure core (public/js/window-manager-core.js): keys, placement, clamping and storage.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const src = fs.readFileSync(path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../public/js/window-manager-core.js'), 'utf8');
const sandbox: Record<string, unknown> = {};
vm.createContext(sandbox);
vm.runInContext(src, sandbox, { filename: 'window-manager-core.js' });
const core = sandbox.WindowManagerCore as {
  slugify(s: unknown): string;
  clamp(n: unknown, min: number, max: number): number;
  defaultLayout(i: number, w: number, h: number, top?: number): { x: number; y: number; w: number; h: number; maximized: boolean; minimized: boolean };
  normalizeLayout(raw: unknown): { x: number; y: number; w: number; h: number; maximized: boolean; minimized: boolean } | null;
  parseLayouts(json: string): Record<string, { x: number; y: number; w: number; h: number }>;
  serializeLayouts(map: Record<string, unknown>): string;
  resolveKey(id: string | undefined, title: string): string;
};

test('slugify produces a stable key and falls back for empty input', () => {
  assert.equal(core.slugify('Advanced Search!'), 'advanced-search');
  assert.equal(core.slugify('   '), 'window');
  assert.equal(core.slugify(undefined), 'window');
});

test('resolveKey prefers an element id and otherwise derives one from the title', () => {
  assert.equal(core.resolveKey('search-modal', 'Advanced Search'), 'search-modal');
  assert.equal(core.resolveKey('', 'Advanced Search'), 'title:advanced-search');
});

test('clamp keeps a value inside a range and tolerates garbage', () => {
  assert.equal(core.clamp(5, 0, 10), 5);
  assert.equal(core.clamp(-3, 0, 10), 0);
  assert.equal(core.clamp(99, 0, 10), 10);
  assert.equal(core.clamp('nope', 1, 10), 1);
  assert.equal(core.clamp(NaN, 2, 1), 2);
});

test('defaultLayout keeps a window on screen and cascades successive windows', () => {
  const first = core.defaultLayout(0, 1200, 800);
  const second = core.defaultLayout(1, 1200, 800);
  assert.ok(first.x >= 8 && first.y >= 8);
  assert.ok(first.x + first.w <= 1200);
  assert.ok(first.y + first.h <= 800);
  assert.ok(second.x > first.x && second.y > first.y);
  const tiny = core.defaultLayout(0, 320, 240);
  assert.ok(tiny.w <= 320 && tiny.h <= 240);
});

test('normalizeLayout rejects non-numeric input and floors the size', () => {
  assert.equal(core.normalizeLayout(null), null);
  assert.equal(core.normalizeLayout('x'), null);
  assert.equal(core.normalizeLayout({ x: 1, y: 2, w: 'no', h: 4 }), null);
  const small = core.normalizeLayout({ x: 10, y: 20, w: 5, h: 5 })!;
  assert.equal(small.w, 220);
  assert.equal(small.h, 120);
  assert.equal(small.x, 10);
});

test('parseLayouts treats corrupt storage as empty and drops invalid entries', () => {
  assert.equal(JSON.stringify(core.parseLayouts('{not json')), '{}');
  assert.equal(JSON.stringify(core.parseLayouts('null')), '{}');
  const mixed = core.parseLayouts(JSON.stringify({ good: { x: 1, y: 2, w: 300, h: 200 }, bad: { x: 1 } }));
  assert.equal(Object.keys(mixed).join(','), 'good');
});

test('serializeLayouts round-trips through parseLayouts and drops unknown fields', () => {
  const map = { 'search-modal': { x: 12, y: 34, w: 300, h: 200, maximized: true, minimized: false, junk: 1 } };
  const json = core.serializeLayouts(map);
  const back = core.parseLayouts(json);
  assert.equal(JSON.stringify(back['search-modal']), JSON.stringify({ x: 12, y: 34, w: 300, h: 200, maximized: true, minimized: false, open: false, opener: null }));
  assert.equal(json.includes('junk'), false);
});

test('defaultLayout opens below the header when told where it ends, and still stays on screen', () => {
  const below = core.defaultLayout(0, 1440, 900, 140);
  assert.ok(below.y >= 140, `window starts at y=${below.y}, over the header`);
  assert.ok(below.y + below.h <= 900);
  assert.equal(core.defaultLayout(0, 1440, 900).y, 72, 'without an offset it keeps the old position');
  const low = core.defaultLayout(0, 600, 400, 390);
  assert.ok(low.y + low.h <= 400, 'a header that is too tall cannot push the window off the bottom');
});
