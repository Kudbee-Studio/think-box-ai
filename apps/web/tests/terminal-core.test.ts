// Premium terminal logic (public/js/terminal-core.js): classification, escaping/XSS posture, auto-follow, search,
// grouping, max buffer, and large-buffer performance. The DOM view is covered by static guards plus a headless-browser run.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
// @ts-expect-error plain browser ES module without types
import * as core from '../public/js/terminal-core.js';

const pub = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'public');
const read = (p: string) => fs.readFileSync(path.join(pub, p), 'utf8');
const { TerminalBuffer, classifyMessage, classifyLocal, findMatches, stepMatch, segmentLine, nextFollow, normalizeMaxBuffer, PREFIXES, SYSTEMS, LIMITS, FOLLOW_THRESHOLD_PX } = core;

const thought = (type: string, content: string, extra: Record<string, unknown> = {}) => ({ type: 'thought', data: { type, content, ...extra }, timestamp: 1 });

test('classification: real server events map to the seven prefixes and seven system parts', () => {
  const cases: Array<[any, string, string]> = [
    [thought('goal', 'Worker agent starting: x'), 'runtime', 'runtime'],
    [thought('reasoning', 'Step 1: asking mercury-2…'), 'model', 'runtime'],
    [thought('tool_call', 'write_file {}', { plugin: 'write_file' }), 'tool', 'tools'],
    [thought('tool_result', 'write_file ✓ ok', { status: 'success' }), 'tool', 'tools'],
    [thought('approval', 'Waiting for approval: x'), 'policy', 'security'],
    [thought('memory', 'Recalled 1 memory'), 'memory', 'memory'],
    [thought('think_token', 'Saved 1 Think Token candidate for review (receipt ttr_abc)'), 'ledger', 'tokens'],
    [thought('think_token', 'Using 1 Think Token: tt:abc'), 'memory', 'tokens'],
    [{ type: 'approval_request', data: { tool: 'fetch_url', reason: 'new domain' } }, 'policy', 'security'],
    [{ type: 'approval_resolved', data: { approved: false } }, 'gate', 'security'],
    [{ type: 'memory_changed', data: { id: 'm1' } }, 'memory', 'memory'],
    [{ type: 'think_token_result', data: { ok: true, id: 'tt_1', action: 'accept', receipt: { receipt_id: 'ttr_1' } } }, 'ledger', 'tokens'],
    [{ type: 'think_token_error', data: { error: 'bad' } }, 'gate', 'tokens'],
  ];
  for (const [msg, prefix, system] of cases) {
    const [line] = classifyMessage(msg, { provider: 'inception' });
    assert.equal(line.prefix, prefix, JSON.stringify(msg));
    assert.equal(line.system, system, JSON.stringify(msg));
    assert.ok(PREFIXES.includes(line.prefix) && SYSTEMS.some((s: any) => s.id === line.system));
  }
  assert.equal(classifyMessage(thought('reasoning', 'x'), { provider: 'ollama' })[0].system, 'models', 'ollama sessions highlight Local models');
  assert.deepEqual(classifyMessage({ type: 'unknown_type', data: {} }), [], 'unrelated messages produce nothing; no scripted lines');
  assert.deepEqual(classifyMessage(null as any), []);
  assert.equal(classifyLocal('user', 'hi').system, 'dashboard');
  assert.equal(classifyLocal('error', 'e').level, 'error');
});

test('escaping/XSS: hostile output stays plain data and the view never uses an HTML sink', () => {
  const hostile = '<img src=x onerror=alert(1)><script>alert(2)</script>"\'&';
  const buf = new TerminalBuffer(1000);
  const [line] = buf.pushText({ prefix: 'tool', system: 'tools', text: hostile });
  assert.equal(line.text, hostile, 'stored verbatim as text; escaping happens by rendering through text nodes');
  // search highlighting hands the view plain segments, never markup
  const segs = segmentLine(hostile, [{ start: 0, end: 4, current: true }]);
  assert.equal(segs.map((s: any) => s.text).join(''), hostile);
  // an unknown prefix/system from a malicious payload cannot become a CSS class or element
  const odd = buf.push({ prefix: '"><img>', system: 'x"y', text: 't' });
  assert.equal(odd.prefix, 'runtime');
  assert.equal(odd.system, 'runtime');
  // the app's escapeHtml (fixed earlier) is unchanged, and the new files use no HTML sinks at all
  assert.match(read('js/app.js'), /function escapeHtml\(text\) \{\s*const entities = \{ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' \};/);
  for (const file of ['js/terminal-core.js', 'js/terminal-view.js']) {
    assert.doesNotMatch(read(file), /innerHTML|outerHTML|insertAdjacentHTML|document\.write|eval\(|new Function/, `${file} uses an HTML sink`);
  }
  // ...and the app.js bridge feeds the terminal only real events and local lines
  assert.match(read('js/app.js'), /window\.KudbeeTerminal\?\.ingest\(msg/);
});

test('auto-follow: pauses when the user scrolls up, resumes at the bottom, ignores its own pinning', () => {
  const base = { scrollHeight: 2000, clientHeight: 500 };
  assert.equal(nextFollow({ ...base, follow: true, scrollTop: 1500, prevScrollTop: 1500 }), true, 'at bottom stays following');
  assert.equal(nextFollow({ ...base, follow: true, scrollTop: 900, prevScrollTop: 1500 }), false, 'user scrolled up');
  assert.equal(nextFollow({ ...base, follow: false, scrollTop: 800, prevScrollTop: 900 }), false, 'stays paused while above the bottom');
  assert.equal(nextFollow({ ...base, follow: false, scrollTop: 1000, prevScrollTop: 900 }), false, 'scrolling down but not at the bottom does not resume');
  assert.equal(nextFollow({ ...base, follow: false, scrollTop: 1500 - FOLLOW_THRESHOLD_PX, prevScrollTop: 1000 }), true, 'returning to the bottom resumes');
  assert.equal(nextFollow({ ...base, follow: true, scrollTop: 900, prevScrollTop: 1500, programmatic: true }), true, 'a programmatic scroll never pauses follow');
  assert.equal(nextFollow({ ...base, follow: false, scrollTop: 900, prevScrollTop: 1500, programmatic: true }), false);
  // growth while following: content grew, scrollTop unchanged => distance > threshold but no upward move => stays following
  assert.equal(nextFollow({ scrollHeight: 2400, clientHeight: 500, follow: true, scrollTop: 1500, prevScrollTop: 1500 }), true);
});

test('search: case-insensitive, all matches, capped, stepping wraps, highlight segments cover the text', () => {
  const buf = new TerminalBuffer(1000);
  ['Alpha beta', 'beta BETA', 'gamma'].forEach((text) => buf.push({ prefix: 'tool', system: 'tools', text }));
  const hits = findMatches(buf.lines, 'beta');
  assert.deepEqual(hits.map((h: any) => [h.line, h.start]), [[0, 6], [1, 0], [1, 5]]);
  assert.deepEqual(findMatches(buf.lines, ''), []);
  assert.deepEqual(findMatches(buf.lines, 'zzz'), []);
  assert.equal(stepMatch(-1, 3, 1), 0);
  assert.equal(stepMatch(-1, 3, -1), 2);
  assert.equal(stepMatch(2, 3, 1), 0, 'wraps forward');
  assert.equal(stepMatch(0, 3, -1), 2, 'wraps backward');
  assert.equal(stepMatch(0, 0, 1), -1);
  const segs = segmentLine('beta BETA', [{ start: 0, end: 4 }, { start: 5, end: 9, current: true }]);
  assert.deepEqual(segs.map((s: any) => [s.text, s.hit]), [['beta', true], [' ', false], ['BETA', true]]);
  assert.equal(segs[2].current, true);
  const many = new TerminalBuffer(100000);
  for (let i = 0; i < 20000; i++) many.push({ prefix: 'tool', system: 'tools', text: 'aaaa' });
  assert.equal(findMatches(many.lines, 'a').length, LIMITS.maxMatches, 'a one-character query is capped');
});

test('buffer: wrap rows, step groups collapse and expand, max buffer trims the oldest lines', () => {
  const buf = new TerminalBuffer(1000);
  buf.setCols(10);
  buf.push({ prefix: 'runtime', system: 'runtime', text: 'x'.repeat(25) });
  assert.equal(buf.rows[0], 3);
  buf.push({ prefix: 'tool', system: 'tools', text: '▸ call', group: 'start', groupKind: 'tool' });
  buf.push({ prefix: 'policy', system: 'security', text: 'waiting', group: 'keep' });
  const end = buf.push({ prefix: 'tool', system: 'tools', text: 'done', group: 'end' });
  const after = buf.push({ prefix: 'runtime', system: 'runtime', text: 'next' });
  assert.equal(buf.lines[1].head, true);
  assert.equal(end.group, buf.lines[1].group);
  assert.equal(after.group, null, 'the group closed at its result');
  const total = buf.totalRows;
  const collapsed = buf.toggleGroup(buf.lines[1].group);
  assert.equal(collapsed, true);
  assert.equal(buf.totalRows, total - 2, 'two child lines hidden, header stays');
  buf.toggleGroup(buf.lines[1].group);
  assert.equal(buf.totalRows, total);
  buf.setAllGroups(true);
  assert.equal(buf.rows[2], 0);
  buf.expandGroupOf(2);
  assert.equal(buf.rows[2], 1);

  const small = new TerminalBuffer(200);
  for (let i = 0; i < 1000; i++) small.push({ prefix: 'tool', system: 'tools', text: `line ${i}` });
  assert.ok(small.length <= 200 * 1.1 + 1 && small.length >= 200);
  assert.equal(small.lines.at(-1)!.text, 'line 999', 'newest is kept');
  assert.equal(small.trimmed + small.length, 1000);
  small.setMax(200);
  assert.equal(small.length, 200);
  assert.equal(normalizeMaxBuffer('abc'), LIMITS.defaultBuffer);
  assert.equal(normalizeMaxBuffer(5), 200);
  assert.equal(normalizeMaxBuffer(10 ** 9), 100000);
});

test('stream: tokens extend one line, newlines start new lines, caps hold', () => {
  const buf = new TerminalBuffer(1000);
  buf.pushStream('Hel'); buf.pushStream('lo\nwor'); buf.pushStream('ld');
  assert.deepEqual(buf.lines.map((l: any) => l.text), ['Hello', 'world']);
  buf.push({ prefix: 'runtime', system: 'runtime', text: 'result' });
  buf.pushStream('again');
  assert.equal(buf.lines.length, 4, 'a new stream starts a new line after other output');
  const big = new TerminalBuffer(1000);
  big.pushText({ prefix: 'tool', system: 'tools', text: Array.from({ length: LIMITS.maxLinesPerMessage + 50 }, (_, i) => `l${i}`).join('\n') });
  assert.equal(big.length, LIMITS.maxLinesPerMessage + 1);
  assert.match(big.lines.at(-1)!.text, /50 more line/);
  big.push({ prefix: 'tool', system: 'tools', text: 'y'.repeat(100000) });
  assert.ok(big.lines.at(-1)!.text.length <= LIMITS.maxCharsPerLine);
  assert.match(buf.formatLine(buf.lines[0]), /^\[\d\d:\d\d:\d\d\] \[model\] Hello$/);
});

test('performance: a 50k-line buffer appends, windows and searches within budget', () => {
  const buf = new TerminalBuffer(50000);
  buf.setCols(80);
  const start = performance.now();
  for (let i = 0; i < 120000; i++) buf.push({ prefix: i % 3 ? 'tool' : 'model', system: 'tools', text: `step ${i}: ${'lorem ipsum '.repeat(i % 7)}` });
  const appendMs = performance.now() - start;
  assert.ok(buf.length <= 50000 * 1.1, 'max buffer enforced under load');
  const t1 = performance.now();
  let windows = 0;
  for (let top = 0; top < buf.totalRows; top += Math.floor(buf.totalRows / 2000)) { const { start: s, end: e } = buf.visibleRange(top, 40); assert.ok(e - s < 200); windows++; }
  const windowMs = performance.now() - t1;
  const t2 = performance.now();
  const hits = findMatches(buf.lines, 'step 119999');
  const searchMs = performance.now() - t2;
  const t3 = performance.now();
  buf.setCols(50);
  const relayoutMs = performance.now() - t3;
  const { start: s0, end: e0 } = buf.visibleRange(0, 40);
  assert.ok(s0 === 0 && e0 > 0);
  assert.ok(hits.length >= 1);
  // generous ceilings (CI machines vary); the point is "milliseconds, not seconds" at 50k+ lines
  assert.ok(appendMs < 4000, `append ${appendMs.toFixed(0)}ms`);
  assert.ok(windowMs < 300, `${windows} window lookups ${windowMs.toFixed(0)}ms`);
  assert.ok(searchMs < 500, `search ${searchMs.toFixed(0)}ms`);
  assert.ok(relayoutMs < 500, `relayout ${relayoutMs.toFixed(0)}ms`);
  console.log(`    perf: append120k=${appendMs.toFixed(0)}ms windows=${windowMs.toFixed(1)}ms search=${searchMs.toFixed(1)}ms relayout=${relayoutMs.toFixed(1)}ms`);
});

test('wiring: markup, stylesheet and module are present; reduced motion and the keyboard contract are in the source', () => {
  const html = read('index.html');
  for (const id of ['terminal', 'tw-jump', 'tw-search', 'tw-search-input', 'tw-systems', 'tw-copy-all', 'tw-collapse', 'tw-max']) assert.match(html, new RegExp(`id="${id}"`), id);
  assert.match(html, /<script type="module" src="\/js\/terminal-view\.js"><\/script>/);
  assert.match(html, /href="\/css\/terminal\.css"/);
  assert.ok(html.indexOf('terminal.css') < html.indexOf('polish.css'), 'polish.css still loads last');
  const css = read('css/terminal.css');
  assert.match(css, /prefers-reduced-motion: reduce/);
  assert.match(css, /@media \(max-width: 560px\)/, 'phone layout');
  const view = read('js/terminal-view.js');
  for (const needle of ["'End'", "'/'", "'Escape'", 'prefers-reduced-motion']) assert.ok(view.includes(needle), needle);
  for (const system of SYSTEMS.map((s: any) => s.label)) assert.ok(system.length > 0);
  assert.deepEqual(SYSTEMS.map((s: any) => s.label), ['Dashboard', 'Agent runtime', 'Tools & plugins', 'Local models', 'Memory', 'Security gate', 'Think Tokens']);
  assert.deepEqual([...PREFIXES], ['runtime', 'tool', 'policy', 'gate', 'ledger', 'memory', 'model']);
});
