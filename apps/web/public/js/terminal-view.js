// kudbEE premium terminal — view. Renders the TerminalBuffer (terminal-core.js) into #terminal with a virtualized window.
// Safety: output is only ever placed in the DOM through textContent and Text nodes, never an HTML-string sink.
import { TerminalBuffer, SYSTEMS, LIMITS, classifyMessage, classifyLocal, findMatches, stepMatch, segmentLine, nextFollow, normalizeMaxBuffer } from './terminal-core.js';

const LH = 20; // px per visual row; must match --tw-row in terminal.css
const STORE_KEY = 'kudbee.terminal.maxBuffer';
const $ = (id) => document.getElementById(id);
const reducedMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true;

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function readStoredMax() {
  try { return normalizeMaxBuffer(localStorage.getItem(STORE_KEY) ?? LIMITS.defaultBuffer); } catch { return LIMITS.defaultBuffer; }
}

function init() {
  const viewport = $('terminal');
  if (!viewport || !$('tw-body')) return;

  const buf = new TerminalBuffer(readStoredMax());
  const sizer = el('div', 'tw-sizer');
  const rowsBox = el('div', 'tw-rows');
  sizer.append(rowsBox);
  viewport.append(sizer);

  const probe = el('div', 'tw-line tw-probe');
  const probeText = el('span', 'tw-text');
  const probeCh = el('i', 'tw-ch', '0000000000');
  probeText.append(probeCh);
  probe.append(el('span', 'tw-gutter', ''), probeText);
  viewport.append(probe);

  const counts = Object.fromEntries(SYSTEMS.map((s) => [s.id, 0]));
  const systemItems = new Map();
  for (const s of SYSTEMS) {
    const li = el('li', 'tw-sys');
    li.dataset.system = s.id;
    li.append(el('span', 'tw-sys-dot'), el('span', 'tw-sys-name', s.label), el('span', 'tw-sys-count', '0'));
    $('tw-systems').append(li);
    systemItems.set(s.id, li);
  }

  let following = true;
  let pin = false; // true while the terminal itself is scrolling, so that scroll is not read as the user leaving follow mode
  let prevScrollTop = 0;
  let unseen = 0;
  let activeSystem = null;
  let hoverSystem = null;
  let recentTimer = null;
  let raf = 0;
  let query = '';
  let matches = [];
  let current = -1;
  let byLine = new Map();
  let searchStamp = '';
  let searchTimer = null;
  let toastTimer = null;

  // ── layout ──
  function measure() {
    const cw = probeCh.getBoundingClientRect().width / 10;
    const width = probeText.getBoundingClientRect().width;
    if (cw > 0 && width > 0 && buf.setCols(Math.floor(width / cw) - 1)) schedule();
  }

  function setActive(system) {
    activeSystem = system;
    clearTimeout(recentTimer);
    recentTimer = setTimeout(() => { activeSystem = null; paintSystems(); }, 2500);
    paintSystems();
  }

  function paintSystems() {
    for (const [id, li] of systemItems) {
      li.classList.toggle('active', id === activeSystem);
      li.classList.toggle('pinned', id === hoverSystem);
      li.querySelector('.tw-sys-count').textContent = String(counts[id]);
    }
  }

  function updateMeta() {
    $('tw-meta').textContent = `${buf.length.toLocaleString()} lines${buf.trimmed ? ` · ${buf.trimmed.toLocaleString()} older trimmed` : ''}`;
    $('tw-empty').hidden = buf.length > 0;
  }

  function toast(text) {
    const node = $('tw-toast');
    node.textContent = text;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { node.textContent = ''; }, 1800);
  }

  // ── rendering ──
  function schedule() {
    if (!raf) raf = requestAnimationFrame(() => { raf = 0; render(); });
  }

  function lineNode(line, index) {
    const row = el('div', `tw-line lvl-${line.level}${line.group ? ' in-group' : ''}${line.head ? ' group-head' : ''}`);
    row.style.height = `${buf.rows[index] * LH}px`;
    row.dataset.i = String(index);
    row.dataset.system = line.system;
    const gutter = el('span', 'tw-gutter');
    const t = new Date(line.ts);
    const p = (x) => String(x).padStart(2, '0');
    gutter.append(el('span', 'tw-time', `${p(t.getHours())}:${p(t.getMinutes())}:${p(t.getSeconds())}`), el('span', `tw-prefix px-${line.prefix}`, `[${line.prefix}]`));
    const text = el('span', 'tw-text');
    if (line.head) {
      const chev = el('button', 'tw-chev', buf.collapsed.has(line.group) ? '▸' : '▾');
      chev.type = 'button';
      chev.dataset.group = line.group;
      chev.setAttribute('aria-expanded', String(!buf.collapsed.has(line.group)));
      chev.setAttribute('aria-label', `${buf.collapsed.has(line.group) ? 'Expand' : 'Collapse'} ${line.groupKind || 'step'}`);
      text.append(chev);
    }
    const ranges = byLine.get(index);
    for (const seg of segmentLine(line.text, ranges || [])) {
      if (seg.hit) { const m = el('mark', seg.current ? 'tw-hit tw-current' : 'tw-hit', seg.text); text.append(m); } else text.append(document.createTextNode(seg.text));
    }
    const copy = el('button', 'tw-copy', '⧉');
    copy.type = 'button';
    copy.dataset.copy = String(index);
    copy.title = 'Copy line';
    copy.setAttribute('aria-label', 'Copy line');
    row.append(gutter, text, copy);
    return row;
  }

  function render() {
    const total = buf.totalRows;
    sizer.style.height = `${total * LH}px`;
    const { start, end } = buf.visibleRange(Math.floor(viewport.scrollTop / LH), Math.ceil(viewport.clientHeight / LH));
    const nodes = [];
    for (let i = start; i < end; i++) if (buf.rows[i] > 0) nodes.push(lineNode(buf.lines[i], i));
    if (nodes.length && end === buf.length && following) nodes[nodes.length - 1].querySelector('.tw-text').append(el('span', 'tw-cursor'));
    rowsBox.style.transform = `translateY(${(buf.offsets[start] ?? 0) * LH}px)`;
    rowsBox.replaceChildren(...nodes);
    if (following) pinToBottom();
    updateMeta();
  }

  function pinToBottom() {
    const max = viewport.scrollHeight - viewport.clientHeight;
    if (Math.abs(viewport.scrollTop - max) > 1) { pin = true; viewport.scrollTop = max; }
    prevScrollTop = viewport.scrollTop;
  }

  function jumpToLatest() {
    following = true;
    unseen = 0;
    $('tw-jump').hidden = true;
    const max = viewport.scrollHeight - viewport.clientHeight;
    if (reducedMotion()) { pin = true; viewport.scrollTop = max; } else viewport.scrollTo({ top: max, behavior: 'smooth' });
    schedule();
  }

  function noteAppended(lines) {
    for (const line of lines) { counts[line.system] = (counts[line.system] ?? 0) + 1; }
    if (lines.length) setActive(lines[lines.length - 1].system);
    if (!following) { unseen += lines.length; $('tw-jump-count').textContent = unseen ? `(${unseen} new)` : ''; $('tw-jump').hidden = false; }
    schedule();
    if (query) scheduleSearch();
  }

  viewport.addEventListener('scroll', () => {
    const programmatic = pin;
    pin = false;
    following = nextFollow({ follow: following, scrollTop: viewport.scrollTop, prevScrollTop, scrollHeight: viewport.scrollHeight, clientHeight: viewport.clientHeight, programmatic });
    prevScrollTop = viewport.scrollTop;
    if (following) { unseen = 0; $('tw-jump').hidden = true; } else if (!programmatic) $('tw-jump').hidden = false;
    schedule();
  }, { passive: true });

  // ── interactions: copy, collapse, hover → system highlight ──
  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const area = el('textarea');
      area.value = text; area.style.position = 'fixed'; area.style.opacity = '0';
      document.body.append(area); area.select();
      try { document.execCommand('copy'); } catch { toast('Copy failed'); area.remove(); return; }
      area.remove();
    }
    toast('Copied');
  }

  viewport.addEventListener('click', (event) => {
    const target = event.target;
    if (!(target instanceof Element)) return;
    const copy = target.closest('.tw-copy');
    if (copy) { void copyText(buf.formatLine(buf.lines[Number(copy.dataset.copy)])); return; }
    const chev = target.closest('.tw-chev');
    if (chev) {
      const anchor = Number(chev.closest('.tw-line')?.dataset.i);
      const before = (buf.offsets[anchor] ?? 0) * LH - viewport.scrollTop;
      buf.toggleGroup(chev.dataset.group);
      if (!following) { pin = true; viewport.scrollTop = (buf.offsets[anchor] ?? 0) * LH - before; }
      schedule();
    }
  });
  viewport.addEventListener('mouseover', (event) => {
    const row = event.target instanceof Element ? event.target.closest('.tw-line') : null;
    const next = row ? row.dataset.system : null;
    if (next !== hoverSystem) { hoverSystem = next; paintSystems(); }
  });
  viewport.addEventListener('mouseleave', () => { hoverSystem = null; paintSystems(); });

  $('tw-jump').addEventListener('click', jumpToLatest);
  $('tw-copy-all').addEventListener('click', () => { void copyText(buf.allText()); });
  let allCollapsed = false;
  $('tw-collapse').addEventListener('click', () => {
    allCollapsed = !allCollapsed;
    buf.setAllGroups(allCollapsed);
    $('tw-collapse').setAttribute('aria-pressed', String(allCollapsed));
    schedule();
  });
  const maxSelect = $('tw-max');
  for (const n of LIMITS.bufferChoices) { const o = el('option', '', `${n.toLocaleString()} lines`); o.value = String(n); maxSelect.append(o); }
  if (!LIMITS.bufferChoices.includes(buf.maxLines)) { const o = el('option', '', `${buf.maxLines.toLocaleString()} lines`); o.value = String(buf.maxLines); maxSelect.append(o); }
  maxSelect.value = String(buf.maxLines);
  maxSelect.addEventListener('change', () => {
    buf.setMax(maxSelect.value);
    try { localStorage.setItem(STORE_KEY, String(buf.maxLines)); } catch { /* storage unavailable: the setting just does not persist */ }
    if (query) runSearch();
    schedule();
  });

  // ── search ──
  function runSearch() {
    matches = findMatches(buf.lines, query);
    searchStamp = `${buf.trimmed}:${buf.length}`;
    if (current >= matches.length) current = matches.length - 1;
    byLine = new Map();
    matches.forEach((m, i) => {
      const list = byLine.get(m.line) ?? [];
      list.push({ start: m.start, end: m.end, current: i === current });
      byLine.set(m.line, list);
    });
    $('tw-search-count').textContent = query ? (matches.length ? `${current + 1}/${matches.length}` : '0/0') : '';
    $('tw-search-status').textContent = query ? `${matches.length} matches` : '';
    schedule();
  }

  function scheduleSearch() {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => { if (`${buf.trimmed}:${buf.length}` !== searchStamp) runSearch(); }, 250);
  }

  function gotoMatch(direction) {
    if (!matches.length) return;
    current = stepMatch(current, matches.length, direction);
    const m = matches[current];
    buf.expandGroupOf(m.line);
    runSearch();
    following = false;
    $('tw-jump').hidden = false;
    pin = true;
    viewport.scrollTop = Math.max(0, (buf.offsets[m.line] ?? 0) * LH - viewport.clientHeight / 3);
    prevScrollTop = viewport.scrollTop;
  }

  function openSearch() {
    $('tw-search').hidden = false;
    $('tw-search-input').focus();
    $('tw-search-input').select();
  }
  function closeSearch() {
    $('tw-search').hidden = true;
    query = ''; matches = []; current = -1; byLine = new Map();
    $('tw-search-input').value = '';
    $('tw-search-count').textContent = '';
    schedule();
    viewport.focus({ preventScroll: true });
  }
  $('tw-search-toggle').addEventListener('click', () => ($('tw-search').hidden ? openSearch() : closeSearch()));
  $('tw-search-close').addEventListener('click', closeSearch);
  $('tw-search-next').addEventListener('click', () => gotoMatch(1));
  $('tw-search-prev').addEventListener('click', () => gotoMatch(-1));
  $('tw-search-input').addEventListener('input', () => {
    query = $('tw-search-input').value.slice(0, 200);
    current = -1;
    runSearch();
    if (matches.length) gotoMatch(1);
  });
  $('tw-search-input').addEventListener('keydown', (event) => {
    if (event.key === 'Enter') { event.preventDefault(); gotoMatch(event.shiftKey ? -1 : 1); }
  });

  // ── keyboard: End = latest, / = search, Esc = close ──
  document.addEventListener('keydown', (event) => {
    if (event.ctrlKey || event.metaKey || event.altKey) return;
    const target = event.target instanceof Element ? event.target : document.body;
    const typing = target.matches('input, textarea, select, [contenteditable="true"]');
    if (event.key === 'Escape') {
      if (!$('tw-search').hidden) { event.preventDefault(); closeSearch(); }
      return;
    }
    if (typing) return;
    if (document.querySelector('.modal-backdrop:not([hidden])')) return;
    if (event.key === 'End') { event.preventDefault(); jumpToLatest(); }
    else if (event.key === '/') { event.preventDefault(); openSearch(); }
  });

  new ResizeObserver(() => { measure(); schedule(); }).observe(viewport);
  measure();

  // ── public API used by app.js ──
  const api = {
    ingest(msg, ctx) {
      const added = [];
      for (const d of classifyMessage(msg, ctx)) added.push(...buf.pushText(d, typeof msg.timestamp === 'number' ? msg.timestamp : Date.now()));
      noteAppended(added);
    },
    local(role, text) {
      buf.endStream();
      noteAppended(buf.pushText({ ...classifyLocal(role, String(text ?? '')), group: 'end' }));
    },
    stream(token) {
      const total = () => buf.length + buf.trimmed;
      const before = total();
      buf.pushStream(token);
      const created = total() - before;
      noteAppended(created > 0 ? buf.lines.slice(-created) : []);
      schedule();
    },
    endStream() { buf.endStream(); },
    clear() {
      buf.clear(); matches = []; byLine = new Map(); unseen = 0; following = true;
      $('tw-jump').hidden = true;
      schedule();
    },
  };
  window.KudbeeTerminal = api;
  render();
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
