import assert from 'node:assert/strict';
import fs from 'node:fs';
import { test } from 'node:test';
import vm from 'node:vm';

const mod = { exports: {} as { render(p: unknown, doc: unknown): unknown } };
vm.runInNewContext(fs.readFileSync(new URL('../public/js/project-panel.js', import.meta.url), 'utf8'), { module: mod });
type El = { className: string; textContent: string; children: El[]; appendChild(c: El): El };
const doc = { createElement: (_t: string): El => ({ className: '', textContent: '', children: [], appendChild(c) { this.children.push(c); return c; } }) };
const flat = (e: El): string[] => [e.textContent, ...e.children.flatMap(flat)];
const text = (p: unknown) => flat(mod.exports.render(p, doc) as El).join('|');

test('with no repository it shows the note only', () => {
  const t = text({ repo: null, note: 'No repository is chosen.' });
  assert.ok(t.includes('No repository is chosen.')); assert.ok(!t.includes('Recent runs'));
});

test('a repository shows its name, changes, spend, recent runs, tokens, decisions and next steps', () => {
  const t = text({
    repo: { name: 'demo', repo: 'acme/demo' }, note: 'Runs are counted from...',
    changes: { count: 2, files: [{ path: 'a.ts', status: 'modified' }, { path: 'b.ts', status: 'added' }] },
    runs: { count: 3, failed: 1, total_usd: 0.1234, today_usd: 0.02, recent: [{ id: 'abcdef123456', goal: 'fix the bug', status: 'failed', cost_usd: 0.03, files: 2, started_at: 0 }] },
    tokens: { repo_scoped: 1, titles: ['Use pnpm here'] },
    events: [{ ts: 0, kind: 'draft_pr', actor: 'human', summary: 'draft PR opened: https://x/pull/1' }],
    next: ['Review the 2 uncommitted changes'],
  });
  for (const part of ['demo', 'acme/demo', '2 uncommitted', 'a.ts', 'modified', '3 runs', '1 failed', '$0.1234', 'fix the bug', 'abcdef12', 'Use pnpm here', 'draft pr', 'Review the 2 uncommitted']) assert.ok(t.toLowerCase().includes(part.toLowerCase()), part);
});

test('goal and summary text are shown as text, never HTML', () => {
  const t = text({ repo: { name: 'd', repo: null }, note: '', changes: { count: 0, files: [] }, runs: { count: 1, failed: 0, total_usd: 0, today_usd: 0, recent: [{ id: 'x', goal: '<img src=x onerror=alert(1)>', status: 'completed', cost_usd: 0, files: 0, started_at: 0 }] }, tokens: { repo_scoped: 0, titles: [] }, events: [], next: [] });
  assert.ok(t.includes('<img src=x onerror=alert(1)>'));
});

test('the page has the Project button, panel and script', () => {
  const html = fs.readFileSync(new URL('../public/index.html', import.meta.url), 'utf8');
  for (const id of ['project-button', 'project-panel', 'close-project', 'project-container']) assert.ok(html.includes(`id="${id}"`), id);
  assert.ok(html.includes('/js/project-panel.js'));
});
