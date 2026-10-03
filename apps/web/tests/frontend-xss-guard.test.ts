// Guard for the front end: every ${...} that lands inside an HTML template literal must be escaped (escapeHtml), numeric (Number, .length,
// toFixed, ...), a nested HTML builder (.map(...).join('')), or listed below as reviewed. Run data (step names, tool output, goals, memory
// text, model names, file names, URLs, error messages) is untrusted, and tool output can contain text fetched from the web.
//
// This is a static check on template literals, not a proof: it cannot see data flowing through string concatenation or DOM APIs. The
// behavioural proof for the panels is panel-xss.test.ts. This guard exists so a new raw ${row.name} in an HTML template fails the build.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const pub = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'public', 'js');

interface Interp { file: string; line: number; expr: string }

/** Walk JS source and report every ${...} of every template literal whose literal text looks like HTML. */
export function interpolationsInHtmlTemplates(file: string, src: string): Interp[] {
  const out: Interp[] = [];
  const lineAt = (i: number) => src.slice(0, i).split('\n').length;

  // Skip a string/regex/comment starting at i; return index after it (or i when nothing to skip).
  const skipLiteral = (i: number): number => {
    const c = src[i];
    if (c === '/' && src[i + 1] === '/') { const e = src.indexOf('\n', i); return e < 0 ? src.length : e; }
    if (c === '/' && src[i + 1] === '*') { const e = src.indexOf('*/', i + 2); return e < 0 ? src.length : e + 2; }
    if (c === '"' || c === "'") {
      let j = i + 1;
      while (j < src.length && src[j] !== c && src[j] !== '\n') j += src[j] === '\\' ? 2 : 1;
      return j + 1;
    }
    return i;
  };

  // Parse a template literal starting at the backtick at `start`; returns the index after the closing backtick.
  const parseTemplate = (start: number): number => {
    let i = start + 1;
    let text = '';
    const exprs: Array<{ expr: string; at: number }> = [];
    while (i < src.length && src[i] !== '`') {
      if (src[i] === '\\') { text += src.slice(i, i + 2); i += 2; continue; }
      if (src[i] === '$' && src[i + 1] === '{') {
        let depth = 1;
        let j = i + 2;
        while (j < src.length && depth > 0) {
          const skipped = skipLiteral(j);
          if (skipped !== j) { j = skipped; continue; }
          if (src[j] === '`') { j = parseTemplate(j); continue; }
          if (src[j] === '{') depth++;
          else if (src[j] === '}') depth--;
          j++;
        }
        exprs.push({ expr: src.slice(i + 2, j - 1).trim(), at: i });
        text += '\u0000';
        i = j;
        continue;
      }
      text += src[i];
      i++;
    }
    const looksLikeHtml = /<\/?[a-zA-Z][\w-]*[\s>/]|<\/?[a-zA-Z][\w-]*$|\s(?:class|id|data-[\w-]+|href|src|style|title|value|onclick)=["']?\u0000/.test(text);
    if (looksLikeHtml) for (const e of exprs) out.push({ file, line: lineAt(e.at), expr: e.expr });
    return i + 1;
  };

  for (let i = 0; i < src.length;) {
    const skipped = skipLiteral(i);
    if (skipped !== i) { i = skipped; continue; }
    if (src[i] === '`') { i = parseTemplate(i); continue; }
    i++;
  }
  return out;
}

const SAFE_CALLEE = /^(?:this\.)?(?:escapeHtml|escape|ttEl)\(|^Number\(|^Math\.\w+\(|^(?:this\.)?format(?:Bytes|Usd|Time|Date|Duration|Number|Cost|Percent|Ms)\(|^parseInt\(|^parseFloat\(/;
const SAFE_SUFFIX = /(?:\.length|\.size|\.count|\.toFixed\(\d*\)|\.toLocaleString\([^)]*\)|\.toISOString\(\)|\.getTime\(\))$/;
// Builders that return markup this file assembled and escaped itself, plus the literal pieces of an HTML structure.
const SAFE_STRUCTURE = /\.map\([\s\S]*\)\s*\.join\(|^this\.build\w+\(|^this\.render\w+\(|^this\.get\w*(?:Html|HTML|Markup)\(/;
const SAFE_IDENT = /^(?:i|j|k|idx|index|n|count|total|percent|percentage|duration|elapsed|width|height|size|score|pct|left|right|top|bottom|x|y)$/;

function isSafe(expr: string): boolean {
  const e = expr.replace(/\s+/g, ' ').trim();
  if (e.includes('escapeHtml(') || e.includes('escape(')) return true; // escaped somewhere in the expression, e.g. a ternary of escaped values
  if (SAFE_CALLEE.test(e) || SAFE_SUFFIX.test(e) || SAFE_STRUCTURE.test(e) || SAFE_IDENT.test(e)) return true;
  if (/^[\d.]+$/.test(e) || /^['"][^'"]*['"]$/.test(e)) return true; // a literal
  if (/^\(?[^()?:]*\)? ?[+\-*/%] ?[^()?:]*$/.test(e) && !/[A-Za-z_$][\w$]*\.[A-Za-z_$]/.test(e.replace(/(?:Math|Number|Date)\.\w+/g, ''))) return true; // plain arithmetic on locals
  // A ternary is safe when its branches are literals, nested templates (checked on their own) or safe values.
  const t = /^(.+?) \? (.+) : (.+)$/.exec(e);
  if (t) {
    const isQuoted = (b: string) => (b.startsWith("'") && b.endsWith("'")) || (b.startsWith('"') && b.endsWith('"'));
    const branch = (b: string) => isQuoted(b.trim()) || b.trim().startsWith('`') || isSafe(b.trim());
    if (branch(t[2]) && branch(t[3])) return true;
  }
  if (/^[a-z]+ ?(?:\|\||\?\?) ?(?:\d+|''|""|'[^']*'|"[^"]*")$/.test(e) && SAFE_IDENT.test(e.split(/ ?(?:\|\||\?\?) ?/)[0])) return true;
  return false;
}

// Reviewed raw interpolations: `file :: expression` -> why it is not attacker-influenced. Keep this list short and honest.
const REVIEWED_RAW: Record<string, string> = {
  'advanced-search.js :: this.getTypeIcon(result.type)': 'a fixed value picked from a constant map or list in the same file',
  'advanced-search.js :: this.highlightQuery(result.title)': 'returns markup whose text pieces are escaped one by one (the query is regex-escaped too)',
  'analytics-ui.js :: weekComparison.thisWeek': 'a number or count computed in this file from stored data',
  'analytics-ui.js :: weekComparison.lastWeek': 'a number or count computed in this file from stored data',
  'analytics-ui.js :: trendClass': "'trend-up', 'trend-down' or ''",
  'app.js :: new Date().toLocaleTimeString()': 'a locale time string from a Date, no user text',
  'app.js :: attachments': 'a local variable assembled in this file with every untrusted part already escaped where it was built',
  'app.js :: runProgressLine(task)': 'a local variable assembled in this file with every untrusted part already escaped where it was built',
  'app.js :: actions': 'a local variable assembled in this file with every untrusted part already escaped where it was built',
  'app.js :: formatThoughtTime(thought.timestamp)': 'a locale time string from a Date, no user text',
  'app.js :: action': 'one of the fixed git actions status/log/diff/branch',
  'app.js :: label': 'a hard-coded row label in refreshSystemHealth',
  'app.js :: title': 'built with escapeHtml(...) on the line above',
  'app.js :: fail': 'computed CSS numbers',
  'app.js :: cls': 'one of two fixed class names',
  'app.js :: tag': 'a local variable assembled in this file with every untrusted part already escaped where it was built',
  'app.js :: part': 'each part is escapeHtml(...) where the array is built',
  'collaboration-dashboard.js :: this.getCompletedToday()': 'a number or count computed in this file from stored data',
  'execution-logs.js :: new Date(log.timestamp).toLocaleTimeString()': 'a locale time string from a Date, no user text',
  'execution-logs.js :: this.getSuccessRate()': 'a number or count computed in this file from stored data',
  'git-integration.js :: this.formatSize(item.size)': 'a number or count computed in this file from stored data',
  'git-integration.js :: toggle': 'a fixed arrow glyph',
  'git-integration.js :: icon': 'a fixed file/folder glyph',
  'integration-connectors.js :: connector.icon': 'connectors are a constant list in this file',
  'performance-analytics.js :: s.impact': 'suggestions are string constants in this file',
  'performance-analytics.js :: s.text': 'suggestions are string constants in this file',
  'sharing-ui.js :: expiryText': "built from a number of minutes: 'Expires in Nm', 'Expired' or 'Never expires'",
  'template-browser-ui.js :: categoryColor': 'a fixed value picked from a constant map or list in the same file',
  'template-browser-ui.js :: ratingStars': 'built with String.repeat from a clamped number',
  'timeline-ui.js :: criticalPath': 'a number or count computed in this file from stored data',
  'timeline-ui.js :: this.calculateSuccessRate(steps)': 'a number or count computed in this file from stored data',
  'timeline-ui.js :: statusColor': 'a fixed value picked from a constant map or list in the same file',
  'workflow-builder.js :: this.getIcon(templateType)': 'a fixed value picked from a constant map or list in the same file',
};

test('the HTML-template scanner finds interpolations, nested templates and ignores non-HTML templates', () => {
  const found = interpolationsInHtmlTemplates('x.js', [
    'const a = `<div class="${cls}">${row.name}</div>`;',
    "const b = `plain ${row.name} text`;",
    'const c = `<ul>${items.map(i => `<li>${i.title}</li>`).join(\'\')}</ul>`;',
    "const s = '`<b>${notReal}</b>`'; // a quoted backtick is not a template",
  ].join('\n'));
  assert.deepEqual(found.map((f) => f.expr).sort(), ['cls', 'i.title', "items.map(i => `<li>${i.title}</li>`).join('')", 'row.name']);
  assert.deepEqual(found.map((f) => f.line).sort(), [1, 1, 3, 3]);
});

test('the safety classifier accepts escaped, numeric and structural expressions and rejects raw data', () => {
  for (const ok of ['escapeHtml(row.name)', 'this.escapeHtml(x.title)', 'Number(a.cost) || 0', 'steps.length', 'v.toFixed(2)', "items.map(x => `<li>${x}</li>`).join('')", 'a ? escapeHtml(b) : ""', 'index + 1', '`<b>${x}</b>`'.slice(0, 0) || '3', 'idx']) assert.equal(isSafe(ok), true, ok);
  for (const bad of ['row.name', 'template.description', 'err.message', 'step.tool', 'result.content.substring(0, 120)', 'this.highlightQuery(result.title)', 'task.status', 'a ? b.name : ""']) assert.equal(isSafe(bad), false, bad);
});

test('no HTML template in public/js interpolates raw data (escape it, or review it into REVIEWED_RAW with a reason)', () => {
  const skip = new Set(['app-mock.js', 'escape-html.js', 'escape-html-global.js']);
  const raw: string[] = [];
  const reviewedUsed = new Set<string>();
  for (const file of fs.readdirSync(pub).filter((f) => f.endsWith('.js') && !skip.has(f)).sort()) {
    for (const it of interpolationsInHtmlTemplates(file, fs.readFileSync(path.join(pub, file), 'utf8'))) {
      if (isSafe(it.expr)) continue;
      const key = `${file} :: ${it.expr.replace(/\s+/g, ' ')}`;
      if (key in REVIEWED_RAW) { reviewedUsed.add(key); continue; }
      raw.push(`${file}:${it.line}  \${${it.expr.replace(/\s+/g, ' ').slice(0, 80)}}`);
    }
  }
  assert.deepEqual(raw, [], `raw interpolations in HTML templates:\n  ${raw.join('\n  ')}`);
  const stale = Object.keys(REVIEWED_RAW).filter((k) => !reviewedUsed.has(k));
  assert.deepEqual(stale, [], 'REVIEWED_RAW entries that no longer match anything: remove them');
});
