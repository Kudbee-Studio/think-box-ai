// The Timeline, Share & Export and Analytics panels build HTML from run data (step names, tool output, goals, model names, share links).
// Run data is untrusted: tool results can contain text fetched from the web. These tests load the REAL panel modules into a node:vm
// sandbox with a tiny fake DOM, feed them hostile values, and require the rendered HTML to be inert. Same convention as git-panel-escaping.test.ts.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const src = (p: string) => fs.readFileSync(path.join(appDir, p), 'utf8');

/** ES module -> vm script: drop imports, drop `export`. */
const asScript = (s: string) => s.replace(/^import .*$/gm, '').replace(/^export /gm, '');

const HOSTILE = [
  '<img src=x onerror=alert(1)>',
  '"><script>alert(2)</script>',
  "'><svg onload=alert(3)>",
];
const PAYLOAD = HOSTILE[0];

function render(modulePath: string, className: string, service: Record<string, unknown>, serviceGetter: string, ids: Record<string, string>, call: string, extraGlobals: Record<string, unknown> = {}): string {
  const els = new Map<string, any>();
  const el = (id: string) => {
    if (!els.has(id)) els.set(id, { id, hidden: false, innerHTML: '', textContent: '', dataset: {}, addEventListener() {}, remove() {}, querySelectorAll: () => [], querySelector: () => null, classList: { add() {}, remove() {}, toggle() {} } });
    return els.get(id);
  };
  const sandbox: Record<string, unknown> = {
    document: { getElementById: (id: string) => el(id), querySelectorAll: () => [], querySelector: () => null, createElement: () => ({ style: {}, set textContent(_v: string) {}, innerHTML: '' }), addEventListener() {} },
    window: { location: { search: '' }, addEventListener() {}, dispatchEvent() {} },
    localStorage: { getItem: (k: string) => (k === 'openRunId' ? PAYLOAD : null), setItem() {}, removeItem() {} },
    setInterval: () => 0, clearInterval() {}, console, Date, Math, Number, String, JSON, Array, Object, URLSearchParams, alert() {},
    [serviceGetter]: () => service,
    TerminalDashboard: class { displayAnalytics() {} displayTimeline() {} displayStats() {} },
    ...extraGlobals,
  };
  vm.createContext(sandbox);
  vm.runInContext(asScript(src('public/js/escape-html.js')), sandbox);
  vm.runInContext(`${asScript(src(modulePath))}\nglobalThis.__ui = new ${className}(); globalThis.__ui.${call};`, sandbox);
  return el(ids.container).innerHTML;
}

function assertInert(html: string, label: string) {
  assert.ok(html.length > 50, `${label}: rendered something`);
  for (const bad of ['<img', '<script', '<svg']) assert.ok(!html.includes(bad), `${label}: raw "${bad}" survived in the HTML`);
  assert.match(html, /&lt;img src=x onerror=alert\(1\)&gt;/, `${label}: the hostile text is shown escaped, not dropped`);
}

test('escape-html.js escapes the five HTML metacharacters and tolerates null/undefined/numbers', () => {
  const sandbox: Record<string, unknown> = {};
  vm.createContext(sandbox);
  vm.runInContext(asScript(src('public/js/escape-html.js')), sandbox);
  const escapeHtml = sandbox.escapeHtml as (v: unknown) => string;
  assert.equal(escapeHtml(`<a href="x" title='y'>&</a>`), '&lt;a href=&quot;x&quot; title=&#39;y&#39;&gt;&amp;&lt;/a&gt;');
  assert.equal(escapeHtml(null), '');
  assert.equal(escapeHtml(undefined), '');
  assert.equal(escapeHtml(42), '42');
});

test('Timeline panel: run id (from storage/URL), step name, status, tool, result, error and approval wait are inert', () => {
  const step = { name: PAYLOAD, status: HOSTILE[1], tool: HOSTILE[2], result: { note: PAYLOAD }, error: HOSTILE[1], approvalWaitTime: HOSTILE[0], startTime: 1, endTime: 2 };
  const html = render('public/js/timeline-ui.js', 'TimelineUI',
    { getSteps: () => [step], getCriticalPath: () => 5 }, 'getTimelineService', { container: 'timeline-container' }, 'openTimeline()');
  assertInert(html, 'timeline');
  assert.match(html, /data-status="&quot;&gt;&lt;script&gt;/, 'attribute value is escaped');
});

test('Share & Export panel: run id, share link, access level and share id are inert', () => {
  const share = { shareLink: HOSTILE[1] + PAYLOAD, accessLevel: HOSTILE[2] + PAYLOAD, id: HOSTILE[1] + PAYLOAD, viewCount: HOSTILE[0], expiresAt: null };
  const html = render('public/js/sharing-ui.js', 'SharingUI',
    { getSharesForRun: () => [share] }, 'getRunSharingService', { container: 'sharing-container' }, 'openSharing()');
  assertInert(html, 'sharing');
});

test('Analytics panel: KPI fields, model names and failure categories are inert', () => {
  const html = render('public/js/analytics-ui.js', 'AnalyticsDashboardUI', {
    getKPICards: () => [{ title: PAYLOAD, icon: HOSTILE[2], value: HOSTILE[1], color: HOSTILE[1], trend: 1 }],
    getModelDistribution: () => [{ model: PAYLOAD, percentage: HOSTILE[1] }],
    getFailureAnalysis: () => [{ category: PAYLOAD, count: HOSTILE[0] }],
    getWeekComparison: () => ({ thisWeek: 1, lastWeek: 2, improvement: 3 }),
  }, 'getAnalyticsService', { container: 'analytics-container' }, 'openDashboard()');
  assertInert(html, 'analytics');
});

test('exported HTML report: goal, model, role and message content are escaped', async () => {
  const store = new Map<string, string>();
  (globalThis as any).localStorage = { getItem: (k: string) => store.get(k) ?? null, setItem: (k: string, v: string) => { store.set(k, v); }, removeItem: (k: string) => { store.delete(k); } };
  const { RunSharingService } = await import('../services/run-sharing.ts');
  const svc = new RunSharingService();
  const snap = svc.createSnapshot({
    runId: 'r1', goal: `</title><script>alert('g')</script>`, model: PAYLOAD, success: true, duration: 1000,
    messages: [{ role: 'assistant" onmouseover="x', content: `<script>alert('m')</script>`, timestamp: 1 }],
  } as never);
  const html = svc.exportHTML(snap.id);
  for (const bad of ['<script', '<img', '" onmouseover="']) assert.ok(!html.includes(bad), `raw ${bad} in exported report`);
  assert.match(html, /&lt;script&gt;alert\(&#39;m&#39;\)&lt;\/script&gt;/);
  assert.match(html, /<title>Run Report - &lt;\/title&gt;&lt;script&gt;/);
});
