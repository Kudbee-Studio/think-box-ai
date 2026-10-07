// The dashboard header: the 14 tool buttons live in the labeled Tools menu (same ids, so their handlers still bind), the toolbar has no hidden scroll box
// (that clipped "Clear" at wide widths), and the menu closes on a tool click, an outside click and Escape.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const pub = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'public');
const html = fs.readFileSync(path.join(pub, 'index.html'), 'utf8');
const css = fs.readFileSync(path.join(pub, 'css', 'polish.css'), 'utf8');
const TOOL_IDS = ['advanced-search-button', 'agent-templates-button', 'convoys-button', 'approval-workflow-button', 'performance-analytics-button', 'timeline-button', 'share-button', 'templates-button', 'execution-logs-button', 'integrations-button', 'collaboration-button', 'settings-button', 'copy-session', 'command-help'];

test('all 14 tool buttons are inside the Tools menu, each with a visible label, and the always-visible controls stay outside it', () => {
  const menu = html.slice(html.indexOf('<details id="tools-menu"'), html.indexOf('</details>', html.indexOf('<details id="tools-menu"')));
  assert.ok(menu.includes('<summary'), 'the menu has a summary');
  for (const id of TOOL_IDS) {
    assert.ok(menu.includes(`id="${id}"`), `${id} is in the menu`);
    const button = menu.slice(menu.indexOf(`id="${id}"`)).split('</button>')[0]!;
    assert.match(button, /<span class="tool-label">[^<]+<\/span>/, `${id} has a label`);
  }
  const outside = html.replace(menu, '');
  for (const id of ['clear-chat', 'think-token-button', 'site-link', 'header-connection']) assert.ok(outside.includes(`id="${id}"`), `${id} stays in the header`);
  for (const id of TOOL_IDS) assert.ok(!outside.includes(`id="${id}"`), `${id} is not duplicated outside the menu`);
});

test('the toolbar does not scroll inside itself (the hidden scroll box clipped Clear), and the panel is not clipped', () => {
  const block = css.slice(css.indexOf('.header-right {'), css.indexOf('}', css.indexOf('.header-right {')));
  assert.ok(!/overflow-x:\s*auto/.test(block), 'no overflow-x:auto on .header-right');
  assert.match(block, /overflow:\s*visible/);
  assert.ok(html.includes('src="/js/header-menu.js"'));
});

test('the header wraps to a second row below 1860 px, where the Model and Agent pickers would otherwise shrink to a few pixels', () => {
  const m = css.match(/@media \(max-width: (\d+)px\) \{\s*\.header \{ flex-wrap: wrap;/);
  assert.ok(m, 'a wrap rule exists'); assert.ok(Number(m![1]) >= 1859, `wraps up to ${m![1]}px`);
});

test('the menu closes when a tool is chosen, on an outside click, and on Escape; a click on the summary does not close it', () => {
  const listeners: Record<string, Array<(e: unknown) => void>> = {}; const menuListeners: Record<string, Array<(e: unknown) => void>> = {};
  let open = true; let focused = false;
  const button = { tagName: 'BUTTON', parentNode: null as unknown };
  const summary = { tagName: 'SUMMARY', parentNode: null as unknown, focus: () => { focused = true; } };
  const menu = { hasAttribute: (n: string) => n === 'open' && open, removeAttribute: (n: string) => { if (n === 'open') open = false; }, addEventListener: (t: string, f: (e: unknown) => void) => { (menuListeners[t] ??= []).push(f); }, contains: (n: unknown) => n === button || n === summary, querySelector: () => summary, tagName: 'DETAILS' };
  button.parentNode = menu; summary.parentNode = menu;
  const doc = { getElementById: (id: string) => (id === 'tools-menu' ? menu : null), addEventListener: (t: string, f: (e: unknown) => void) => { (listeners[t] ??= []).push(f); } };
  vm.runInNewContext(fs.readFileSync(path.join(pub, 'js', 'header-menu.js'), 'utf8'), { document: doc });
  menuListeners.click![0]!({ target: summary }); assert.equal(open, true, 'summary click leaves it open');
  menuListeners.click![0]!({ target: button }); assert.equal(open, false, 'a tool click closes it');
  open = true; listeners.click![0]!({ target: { nodeType: 1 } }); assert.equal(open, false, 'an outside click closes it');
  open = true; listeners.keydown![0]!({ key: 'a' }); assert.equal(open, true, 'other keys do nothing');
  listeners.keydown![0]!({ key: 'Escape' }); assert.equal(open, false); assert.ok(focused, 'focus returns to the summary');
});
