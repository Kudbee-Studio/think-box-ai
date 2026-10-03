// Local recipes (Layer 4: tools glue, pure, no I/O). A 360M local model cannot decide to call a tool, but it can word an answer when it is handed the
// data. For a short, fixed list of common questions the SERVER makes the tool call (through the same governed path as the worker agent: approval,
// confinement, audit) and the local model only writes a sentence from the result. The sentence is checked against the data; if it states a number
// or link that is not in the data, the data itself is shown instead. Nothing here runs a tool or calls a model.

export type RecipeId = 'open_prs' | 'list_files' | 'read_file';

export interface RecipeMatch {
  id: RecipeId;
  tool: 'fetch_url' | 'list_files' | 'read_file';
  label: string;
  /** read_file only: the workspace-relative path named in the goal. */
  path?: string;
}

const PR = /\b(prs?|pull[- ]requests?)\b/i;
const PR_QUESTION = /\b(what|which|how many|are we|any|list|show|current|currently|open|latest|working on|status|number)\b/i;
// A goal that asks to CHANGE something is never a read-only recipe: it goes to the worker agent.
const MUTATION = /\b(merge|close|create|make|approve|comment on|review|fix|delete|revert|rebase|open a|open an|submit|push|update|edit|write|rename|remove)\b/i;
const FILE_NAME = /(?<![\w/@.:-])([\w][\w.-]*\.(?:md|txt|json|ts|js|mjs|py|csv|html|ya?ml|xml|log))\b/i;
const FILE_VERB = /\b(read|show|print|display|open|what'?s in|what is in|contents? of|summari[sz]e|tell me about|in)\b/i;
const LIST_FILES = /\b(list|show|what|which)\b.{0,40}\b(files?|workspace|folder)\b/i;

/** The recipe for this goal, or null (the goal then goes to the worker agent). */
export function matchRecipe(goal: string): RecipeMatch | null {
  const text = String(goal ?? '');
  if (!text.trim() || text.length > 300 || MUTATION.test(text) || /https?:\/\//i.test(text)) return null;
  if (PR.test(text) && PR_QUESTION.test(text)) return { id: 'open_prs', tool: 'fetch_url', label: 'open pull requests' };
  const file = text.match(FILE_NAME)?.[1];
  if (file && FILE_VERB.test(text) && !file.includes('..')) return { id: 'read_file', tool: 'read_file', label: `read ${file}`, path: file };
  if (LIST_FILES.test(text)) return { id: 'list_files', tool: 'list_files', label: 'list the workspace files' };
  return null;
}

/** Whether this recipe can run here: the PR recipe needs to know which GitHub repository to ask. */
export function recipeAvailable(match: RecipeMatch, repo: string | null | undefined): boolean {
  return match.id !== 'open_prs' || Boolean(repo && /^[\w.-]+\/[\w.-]+$/.test(repo));
}

export function recipeToolArgs(match: RecipeMatch, repo: string | null | undefined, githubBase = 'https://api.github.com'): Record<string, unknown> {
  if (match.id === 'open_prs') return { url: `${githubBase.replace(/\/$/, '')}/repos/${repo}/pulls?state=open&per_page=5`, max_chars: 120000 };
  if (match.id === 'read_file') return { path: match.path };
  return {};
}

export type Facts = { facts: string } | { error: string };

/**
 * The complete objects of a JSON array, even when the text was cut off mid-way (a real GitHub pull-request object is 10 KB or more, so a few of
 * them can exceed the fetch limit). Quote- and escape-aware; returns what parsed and whether the whole array was there.
 */
export function parseJsonArrayPrefix(text: string): { items: unknown[]; complete: boolean } | null {
  const src = String(text ?? '');
  const open = src.indexOf('[');
  if (open < 0 || src.slice(0, open).trim()) return null;
  const items: unknown[] = [];
  let depth = 0;
  let inString = false;
  let escaped = false;
  let start = -1;
  for (let i = open; i < src.length; i += 1) {
    const ch = src[i]!;
    if (inString) {
      if (escaped) escaped = false;
      else if (ch === '\\') escaped = true;
      else if (ch === '"') inString = false;
      continue;
    }
    if (ch === '"') inString = true;
    else if (ch === '[' || ch === '{') {
      depth += 1;
      if (depth === 2 && ch === '{') start = i;
    } else if (ch === ']' || ch === '}') {
      depth -= 1;
      if (depth === 1 && ch === '}' && start >= 0) {
        try { items.push(JSON.parse(src.slice(start, i + 1))); } catch { return items.length ? { items, complete: false } : null; }
        start = -1;
      }
      if (depth === 0) return { items, complete: true };
    }
  }
  return { items, complete: false };
}

const oneLine = (text: unknown, max: number): string => String(text ?? '').replace(/\s+/g, ' ').trim().slice(0, max);

/** The data, as plain lines, built by code from the tool output (never by the model). */
export function buildFacts(match: RecipeMatch, output: Record<string, unknown>, repo?: string | null): Facts {
  if (match.id === 'open_prs') {
    if (Number(output.status) !== 200) return { error: `GitHub answered HTTP ${String(output.status)} for ${repo}'s open pull requests, so there is nothing to report.` };
    const text = String(output.text ?? '');
    const parsed = parseJsonArrayPrefix(text);
    if (!parsed) return { error: /^\s*\{/.test(text) ? 'The GitHub reply was not a list of pull requests.' : 'The GitHub reply could not be read as JSON (it was cut off or malformed).' };
    const list = parsed.items;
    if (!list.length) return parsed.complete ? { facts: `Open pull requests in ${repo} (live from GitHub just now): none.` } : { error: 'The GitHub reply could not be read as JSON (it was cut off or malformed).' };
    const lines = list.slice(0, 5).map((pr: any) => `- #${Number(pr?.number)} "${oneLine(pr?.title, 120)}"${pr?.draft ? ' (draft)' : ''} by ${oneLine(pr?.user?.login, 40) || 'unknown'}, updated ${oneLine(pr?.updated_at, 20)} ${oneLine(pr?.html_url, 120)}`.trim());
    const head = parsed.complete ? `${list.length}.` : `showing the first ${list.length} (the reply was longer than the limit and was cut off).`;
    return { facts: `Open pull requests in ${repo} (live from GitHub just now): ${head}\n${lines.join('\n')}` };
  }
  if (match.id === 'list_files') {
    const files = Array.isArray(output.files) ? (output.files as Array<{ path: string; size: number }>) : [];
    if (!files.length) return { facts: 'The workspace is empty.' };
    return { facts: `Workspace files (${files.length}):\n${files.slice(0, 40).map((f) => `- ${oneLine(f.path, 120)} (${Number(f.size) || 0} B)`).join('\n')}` };
  }
  const content = String(output.content ?? '');
  return { facts: `File ${oneLine(output.path, 120)} (first ${Math.min(content.length, 1500)} characters):\n${content.slice(0, 1500)}` };
}

/** The message sent to the local model: plain chat, the data first, then the question. No tool talk. */
export function buildPrompt(goal: string, facts: string, match?: RecipeMatch): string {
  const cite = match?.id === 'open_prs' && /#\d+/.test(facts) ? ' Name the pull request number(s) exactly as written above.' : '';
  return `Here is live data from a lookup just now:\n\n${facts}\n\nUsing only this data, answer in one or two sentences: ${String(goal).slice(0, 300)}${cite}`;
}

export interface SentenceRule {
  /** Nothing to word (no pull requests, an empty workspace): the data alone is the answer, the model is not asked. */
  skipModel: boolean;
  cite?: 'pr' | 'file';
  /** Shown before a sentence that can only be checked for numbers and links. */
  uncheckedLabel?: boolean;
}

/** What the model's sentence must satisfy for this recipe, given the data. */
export function sentenceRule(match: RecipeMatch, facts: string): SentenceRule {
  if (match.id === 'open_prs') return { skipModel: !/^- #\d+ /m.test(facts), cite: 'pr' };
  if (match.id === 'list_files') return { skipModel: !/^- .+ \(\d+ B\)$/m.test(facts), cite: 'file' };
  return { skipModel: !facts.split('\n').slice(1).join('').trim(), uncheckedLabel: true };
}

const NUMBER = /\d+(?:\.\d+)?/g;
/** Distinctive lower-case words (5+ letters) of a title or sentence. */
function titleWords(text: string): Set<string> {
  return new Set((text.toLowerCase().match(/[a-z][a-z0-9-]{4,}/g) ?? []).filter((w) => !COMMON.has(w)));
}
const COMMON = new Set(['about', 'after', 'being', 'could', 'first', 'their', 'there', 'these', 'those', 'which', 'would', 'where', 'while', 'with', 'pull', 'request', 'requests', 'based', 'open', 'data', 'live', 'github', 'working', 'currently', 'listed', 'number']);
const URL_RE = /https?:\/\/[^\s)"']+/g;

/**
 * Accept the model's sentence only if every number and link it states is in the data. A sentence that invents a PR number, a size or a URL is
 * dropped (the caller shows the data itself). An error-looking, empty or very long reply is dropped too.
 */
export function groundedAnswer(answer: string, facts: string, opts: { cite?: 'pr' | 'file' } = {}): { ok: true; text: string } | { ok: false; why: string } {
  const text = String(answer ?? '').replace(/```[\s\S]*?```/g, ' ').replace(/\s+/g, ' ').trim();
  if (!text) return { ok: false, why: 'the model returned nothing' };
  if (/^\[Error:/i.test(text)) return { ok: false, why: 'the model call failed' };
  if (text.length > 500) return { ok: false, why: 'the sentence was too long to check' };
  const known = new Set(facts.match(NUMBER) ?? []);
  for (const n of text.match(NUMBER) ?? []) if (!known.has(n)) return { ok: false, why: `it stated "${n}", which is not in the data` };
  for (const u of text.match(URL_RE) ?? []) if (!facts.includes(u.replace(/[.,;]+$/, ''))) return { ok: false, why: `it gave a link that is not in the data` };
  // When the data lists pull requests, a sentence that names none of them is a vague paraphrase of one of several: not good enough.
  if (opts.cite === 'file') {
    const names = [...facts.matchAll(/^- (.+) \(\d+ B\)$/gm)].map((m) => m[1]!.toLowerCase());
    const lower = text.toLowerCase();
    if (names.length && !names.some((n) => lower.includes(n) || lower.includes(n.split('/').pop()!))) return { ok: false, why: 'it named none of the listed files' };
  }
  if (opts.cite === 'pr') {
    const prs = [...facts.matchAll(/^- #(\d+) "([^"\n]*)"/gm)].map((m) => ({ n: m[1]!, words: titleWords(m[2]!) }));
    const listed = prs.map((p) => p.n);
    const cited = listed.filter((n) => new RegExp(`(^|[^\\d])${n}([^\\d]|$)`).test(text));
    if (listed.length && !cited.length) return { ok: false, why: 'it named none of the listed pull requests' };
    // A small model often pairs one PR's number with another PR's title. A distinctive word that belongs only to PRs the sentence does not cite is that mix-up.
    for (const w of titleWords(text)) {
      const owners = prs.filter((p) => p.words.has(w));
      if (owners.length && !owners.some((p) => cited.includes(p.n))) return { ok: false, why: `it mixed "${w}" (from #${owners[0]!.n}) with a different pull request` };
    }
  }
  return { ok: true, text };
}
