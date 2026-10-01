// kudbEE premium terminal — pure logic (no DOM), so it is unit-tested under plain Node (tests/terminal-core.test.ts).
// Everything here treats message text as DATA: lines hold plain strings and the view renders them with text nodes only.

export const PREFIXES = Object.freeze(['runtime', 'tool', 'policy', 'gate', 'ledger', 'memory', 'model']);

export const SYSTEMS = Object.freeze([
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'runtime', label: 'Agent runtime' },
  { id: 'tools', label: 'Tools & plugins' },
  { id: 'models', label: 'Local models' },
  { id: 'memory', label: 'Memory' },
  { id: 'security', label: 'Security gate' },
  { id: 'tokens', label: 'Think Tokens' },
]);

export const LIMITS = Object.freeze({ maxLinesPerMessage: 400, maxCharsPerLine: 2000, maxMatches: 5000, bufferChoices: [1000, 5000, 20000, 50000], defaultBuffer: 5000 });
export const FOLLOW_THRESHOLD_PX = 24;

const SYSTEM_IDS = new Set(SYSTEMS.map((s) => s.id));
const PREFIX_SET = new Set(PREFIXES);

/** Clamp a stored/typed buffer size to something sane. */
export function normalizeMaxBuffer(value) {
  const n = Math.floor(Number(value));
  if (!Number.isFinite(n)) return LIMITS.defaultBuffer;
  return Math.min(100000, Math.max(200, n));
}

// ─── Classification: a real WebSocket message (or local dashboard line) → terminal line descriptors ──

/**
 * @param {{type?: string, data?: any, timestamp?: number}} msg a message exactly as received from the server
 * @param {{provider?: string}} [ctx] session context; provider decides whether model lines belong to Local models
 * @returns {Array<{prefix: string, system: string, text: string, level: 'info'|'warn'|'error', group?: 'start'|'end'|'keep'|null, groupKind?: string}>}
 */
export function classifyMessage(msg, ctx = {}) {
  const d = msg?.data;
  const modelSystem = ctx.provider === 'ollama' ? 'models' : 'runtime';
  const str = (v) => (typeof v === 'string' ? v : v === undefined || v === null ? '' : JSON.stringify(v));
  switch (msg?.type) {
    case 'thought': {
      const t = d?.type;
      const text = str(d?.content);
      const failed = d?.status === 'error';
      switch (t) {
        case 'goal': return [{ prefix: 'runtime', system: 'runtime', text, level: 'info', group: 'end' }];
        case 'reasoning': case 'plan': case 'answer':
          return [{ prefix: 'model', system: modelSystem, text, level: failed ? 'error' : 'info' }];
        case 'tool_call': case 'plugin_call':
          return [{ prefix: 'tool', system: 'tools', text: `▸ ${text}`, level: 'info', group: 'start', groupKind: 'tool' }];
        case 'tool_result': case 'plugin_result':
          return [{ prefix: 'tool', system: 'tools', text, level: failed ? 'error' : 'info', group: 'end' }];
        case 'approval':
          return [{ prefix: 'policy', system: 'security', text, level: 'warn', group: 'keep' }];
        case 'memory':
          return [{ prefix: 'memory', system: 'memory', text, level: failed ? 'error' : 'info' }];
        case 'think_token':
          return [{ prefix: /receipt/i.test(text) ? 'ledger' : 'memory', system: 'tokens', text, level: failed ? 'error' : 'info' }];
        case 'specialist_validation':
          return [{ prefix: 'gate', system: 'security', text, level: failed ? 'error' : 'info' }];
        case 'error':
          return [{ prefix: 'runtime', system: 'runtime', text, level: 'error' }];
        default:
          return [{ prefix: 'runtime', system: 'runtime', text: text || str(t), level: failed ? 'error' : 'info' }];
      }
    }
    case 'approval_request':
      return [{ prefix: 'policy', system: 'security', text: `▸ approval needed: ${str(d?.tool)} — ${str(d?.reason)}`, level: 'warn', group: 'start', groupKind: 'approval' }];
    case 'approval_resolved':
      return [{ prefix: 'gate', system: 'security', text: d?.approved ? 'approved by operator' : 'denied by operator', level: d?.approved ? 'info' : 'warn', group: 'end' }];
    case 'memory_changed':
      return [{ prefix: 'memory', system: 'memory', text: `memory changed${d?.id ? ` ${str(d.id)}` : ''}`, level: 'info' }];
    case 'think_tokens_changed':
      return [{ prefix: 'memory', system: 'tokens', text: `${Number(d?.count) || 0} Think Token candidate(s) saved for review`, level: 'info' }];
    case 'think_token_result':
      return [{ prefix: d?.ok ? 'ledger' : 'gate', system: 'tokens', text: d?.ok ? `${str(d.action)} ${str(d.id)} applied · receipt ${str(d.receipt?.receipt_id)}` : `${str(d?.action)} ${str(d?.id)} not applied: ${str(d?.error)}`, level: d?.ok ? 'info' : 'warn' }];
    case 'think_token_error':
      return [{ prefix: 'gate', system: 'tokens', text: `rejected: ${str(d?.error)}`, level: 'warn' }];
    case 'status':
      return [{ prefix: 'runtime', system: 'runtime', text: `status: ${str(d)}`, level: 'info' }];
    default:
      return [];
  }
}

/** Dashboard-local lines (typed input, slash-command output, connection events). Roles are the old terminal roles. */
export function classifyLocal(role, text) {
  switch (role) {
    case 'user': return { prefix: 'runtime', system: 'dashboard', text: `› ${text}`, level: 'info' };
    case 'error': return { prefix: 'runtime', system: 'dashboard', text, level: 'error' };
    case 'assistant': return { prefix: 'model', system: 'runtime', text, level: 'info' };
    case 'plugin': return { prefix: 'tool', system: 'tools', text, level: 'info' };
    default: return { prefix: 'runtime', system: 'dashboard', text, level: 'info' };
  }
}

// ─── Line buffer with wrap-aware row layout (monospace → row counts are exact, so scrolling can be virtualized) ──

let nextId = 1;

function clipText(text) {
  const s = String(text ?? '').replace(/\r/g, '').replace(/\t/g, '  ');
  return s.length > LIMITS.maxCharsPerLine ? `${s.slice(0, LIMITS.maxCharsPerLine - 1)}…` : s;
}

export class TerminalBuffer {
  constructor(maxLines = LIMITS.defaultBuffer) {
    this.maxLines = normalizeMaxBuffer(maxLines);
    this.lines = [];
    this.cols = 80;
    this.rows = []; // visual rows per line (0 when hidden in a collapsed group)
    this.offsets = [0]; // offsets[i] = rows before line i; offsets[n] = total rows
    this.collapsed = new Set(); // group ids
    this.trimmed = 0; // lines dropped from the front, for the "older lines trimmed" notice
    this.openGroup = null;
    this.streaming = null; // the line currently receiving model stream tokens
    this.version = 0;
  }

  get length() { return this.lines.length; }
  get totalRows() { return this.offsets[this.lines.length]; }

  setCols(cols) {
    const c = Math.max(8, Math.floor(cols) || 80);
    if (c === this.cols) return false;
    this.cols = c;
    this.relayout(0);
    return true;
  }

  rowsFor(line) {
    if (line.group && !line.head && this.collapsed.has(line.group)) return 0;
    // prefix gutter is a separate column in the view, so only the text wraps
    return Math.max(1, Math.ceil(line.text.length / this.cols));
  }

  relayout(from) {
    const n = this.lines.length;
    this.rows.length = n;
    this.offsets.length = n + 1;
    let acc = this.offsets[from] ?? 0;
    this.offsets[from] = acc;
    for (let i = from; i < n; i++) {
      const r = this.rowsFor(this.lines[i]);
      this.rows[i] = r;
      acc += r;
      this.offsets[i + 1] = acc;
    }
    this.version++;
  }

  /** Append one physical line. Returns the stored line. */
  push(desc, ts = Date.now()) {
    this.streaming = null;
    const line = { id: nextId++, ts, prefix: PREFIX_SET.has(desc.prefix) ? desc.prefix : 'runtime', system: SYSTEM_IDS.has(desc.system) ? desc.system : 'runtime', text: clipText(desc.text), level: desc.level || 'info', group: null, head: false, stream: false };
    if (desc.group === 'start') {
      this.openGroup = { id: `g${line.id}`, kind: desc.groupKind || 'step' };
      line.group = this.openGroup.id; line.head = true; line.groupKind = this.openGroup.kind;
    } else if (this.openGroup && (desc.group === 'end' || desc.group === 'keep' || desc.group === undefined || desc.group === null)) {
      line.group = this.openGroup.id;
      if (desc.group === 'end') this.openGroup = null;
    }
    // a goal line (group:'end' with no open group) simply closes nothing
    this.lines.push(line);
    const r = this.rowsFor(line);
    this.rows.push(r);
    this.offsets.push(this.offsets[this.lines.length - 1] + r);
    this.version++;
    this.enforceMax();
    return line;
  }

  /** Split a multi-line message into physical lines, capped. */
  pushText(desc, ts = Date.now()) {
    const parts = String(desc.text ?? '').split('\n');
    const capped = parts.length > LIMITS.maxLinesPerMessage ? [...parts.slice(0, LIMITS.maxLinesPerMessage), `… ${parts.length - LIMITS.maxLinesPerMessage} more line(s) not shown`] : parts;
    const last = capped.length - 1;
    return capped.map((text, i) => {
      let group = desc.group;
      if (group === 'start' && i > 0) group = 'keep'; // only the first line heads the group
      if (group === 'end' && i < last) group = 'keep'; // only the last line closes it
      return this.push({ ...desc, text, group }, ts);
    });
  }

  /** Model stream token(s): extend the open stream line, starting new lines at newlines. */
  pushStream(token, ts = Date.now()) {
    const segments = String(token ?? '').split('\n');
    segments.forEach((seg, i) => {
      if (i > 0 || !this.streaming) {
        const line = this.push({ prefix: 'model', system: 'runtime', text: '', level: 'info' }, ts);
        line.stream = true;
        this.streaming = line;
      }
      const line = this.streaming;
      line.text = clipText(line.text + seg);
      const idx = this.lines.length - 1;
      const r = this.rowsFor(line);
      this.rows[idx] = r;
      this.offsets[idx + 1] = this.offsets[idx] + r;
    });
    this.version++;
    return this.streaming;
  }

  endStream() { this.streaming = null; }

  enforceMax() {
    if (this.lines.length <= this.maxLines * 1.1) return;
    const drop = this.lines.length - this.maxLines;
    this.lines.splice(0, drop);
    this.trimmed += drop;
    const live = new Set(this.lines.map((l) => l.group).filter(Boolean));
    for (const g of this.collapsed) if (!live.has(g)) this.collapsed.delete(g);
    this.offsets = [0];
    this.relayout(0);
  }

  setMax(value) {
    this.maxLines = normalizeMaxBuffer(value);
    if (this.lines.length > this.maxLines) {
      const drop = this.lines.length - this.maxLines;
      this.lines.splice(0, drop);
      this.trimmed += drop;
      this.offsets = [0];
      this.relayout(0);
    }
  }

  toggleGroup(groupId) {
    if (this.collapsed.has(groupId)) this.collapsed.delete(groupId); else this.collapsed.add(groupId);
    const first = this.lines.findIndex((l) => l.group === groupId);
    if (first >= 0) this.relayout(first);
    return this.collapsed.has(groupId);
  }

  setAllGroups(collapse) {
    this.collapsed.clear();
    if (collapse) for (const l of this.lines) if (l.head && l.group) this.collapsed.add(l.group);
    this.relayout(0);
  }

  expandGroupOf(index) {
    const g = this.lines[index]?.group;
    if (g && this.collapsed.has(g)) this.toggleGroup(g);
  }

  clear() {
    this.lines = []; this.rows = []; this.offsets = [0]; this.collapsed.clear();
    this.trimmed = 0; this.openGroup = null; this.streaming = null; this.version++;
  }

  /** Index range of lines to render for a scroll window (binary search over row offsets), with overscan rows. */
  visibleRange(scrollRows, viewportRows, overscan = 20) {
    const n = this.lines.length;
    if (!n) return { start: 0, end: 0 };
    const top = Math.max(0, scrollRows - overscan);
    const bottom = scrollRows + viewportRows + overscan;
    // first line whose end offset is > top
    let lo = 0, hi = n;
    while (lo < hi) { const mid = (lo + hi) >> 1; if (this.offsets[mid + 1] <= top) lo = mid + 1; else hi = mid; }
    const start = lo;
    lo = start; hi = n;
    while (lo < hi) { const mid = (lo + hi) >> 1; if (this.offsets[mid] < bottom) lo = mid + 1; else hi = mid; }
    return { start, end: lo };
  }

  formatLine(line) {
    const t = new Date(line.ts);
    const p = (x) => String(x).padStart(2, '0');
    return `[${p(t.getHours())}:${p(t.getMinutes())}:${p(t.getSeconds())}] [${line.prefix}] ${line.text}`;
  }

  allText() { return this.lines.map((l) => this.formatLine(l)).join('\n'); }
}

// ─── Search ──────────────────────────────────────────────────────

/** Case-insensitive substring search over every line (collapsed ones too). Capped so a 1-char query cannot freeze the page. */
export function findMatches(lines, query) {
  const q = String(query ?? '').toLowerCase();
  if (!q) return [];
  const out = [];
  for (let i = 0; i < lines.length && out.length < LIMITS.maxMatches; i++) {
    const hay = lines[i].text.toLowerCase();
    let at = hay.indexOf(q);
    while (at !== -1 && out.length < LIMITS.maxMatches) {
      out.push({ line: i, start: at, end: at + q.length });
      at = hay.indexOf(q, at + q.length);
    }
  }
  return out;
}

export function stepMatch(current, total, direction) {
  if (!total) return -1;
  if (current < 0) return direction >= 0 ? 0 : total - 1;
  return (current + (direction >= 0 ? 1 : -1) + total) % total;
}

/** Split text into plain segments for rendering highlights; the view turns these into Text nodes and <mark>s. Never HTML. */
export function segmentLine(text, ranges) {
  const out = [];
  let pos = 0;
  for (const r of ranges) {
    if (r.start > pos) out.push({ text: text.slice(pos, r.start), hit: false });
    out.push({ text: text.slice(r.start, r.end), hit: true, current: Boolean(r.current) });
    pos = r.end;
  }
  if (pos < text.length) out.push({ text: text.slice(pos), hit: false });
  return out.length ? out : [{ text, hit: false }];
}

// ─── Auto-follow ─────────────────────────────────────────────────

/**
 * Follow mode: stay pinned to the newest line until the user scrolls up; resume when they return to the bottom.
 * `programmatic` marks scrolls the terminal itself caused (follow-pinning), which must never flip the mode.
 */
export function nextFollow({ follow, scrollTop, prevScrollTop, scrollHeight, clientHeight, programmatic = false }) {
  const distance = scrollHeight - clientHeight - scrollTop;
  if (distance <= FOLLOW_THRESHOLD_PX) return true;
  if (programmatic) return follow;
  if (scrollTop < prevScrollTop) return false; // user moved up
  return follow;
}
