// Local recipes (Layer 4: tools glue, pure, no I/O). A 360M local model cannot decide to call a tool, but it can word an answer when it is handed the
// data. For a short, fixed list of common questions the SERVER makes the tool call (through the same governed path as the worker agent: approval,
// confinement, audit) and the local model only writes a sentence from the result. The sentence is checked against the data; if it states a number
// or link that is not in the data, the data itself is shown instead. Nothing here runs a tool or calls a model.

export type RecipeId = 'open_prs' | 'latest_pr' | 'ci_status' | 'open_issues' | 'branches' | 'list_files' | 'read_file';

/** Recipes that ask GitHub (fetch_url) about the known repository. */
const GITHUB_RECIPES: ReadonlySet<RecipeId> = new Set(['open_prs', 'latest_pr', 'ci_status', 'open_issues', 'branches']);

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
const MUTATION = /\b(re-?run|re-?start|trigger|cancel|retry|merge|close|create|make|approve|comment on|review|fix|delete|revert|rebase|open a|open an|submit|push|update|edit|write|rename|remove)\b/i;
// "the last PR", "the newest pull request": the most recent one in ANY state (a merged PR is not "open").
const LATEST = /\b(last|latest|most recent|newest|previous|recent(ly)?)\b/i;
const CI = /\b(ci|continuous integration|github actions|workflow runs?|checks?|build status|pipeline)\b/i;
const CI_QUESTION = /\b(what|which|how|did|does|is|are|was|were|status|pass(ed|ing)?|fail(ed|ing)?|green|red|broken|running)\b/i;
const ISSUE = /\bissues?\b/i;
const BRANCHES = /\b(list|show|which|what|how many)\b.{0,40}\bbranches\b/i;
const FILE_NAME = /(?<![\w/@.:-])([\w][\w.-]*\.(?:md|txt|json|ts|js|mjs|py|csv|html|ya?ml|xml|log))\b/i;
const FILE_VERB = /\b(read|show|print|display|open|what'?s in|what is in|contents? of|summari[sz]e|tell me about|in)\b/i;
const LIST_FILES = /\b(list|show|what|which)\b.{0,40}\b(files?|workspace|folder)\b/i;

/** The recipe for this goal, or null (the goal then goes to the worker agent). */
export function matchRecipe(goal: string): RecipeMatch | null {
  const text = String(goal ?? '');
  if (!text.trim() || text.length > 300 || MUTATION.test(text) || /https?:\/\//i.test(text)) return null;
  if (PR.test(text) && LATEST.test(text) && PR_QUESTION.test(text)) return { id: 'latest_pr', tool: 'fetch_url', label: 'latest pull request (any state)' };
  if (CI.test(text) && CI_QUESTION.test(text)) return { id: 'ci_status', tool: 'fetch_url', label: 'latest CI runs' };
  if (ISSUE.test(text) && PR_QUESTION.test(text)) return { id: 'open_issues', tool: 'fetch_url', label: 'open issues' };
  if (BRANCHES.test(text)) return { id: 'branches', tool: 'fetch_url', label: 'branches' };
  if (PR.test(text) && PR_QUESTION.test(text)) return { id: 'open_prs', tool: 'fetch_url', label: 'open pull requests' };
  const file = text.match(FILE_NAME)?.[1];
  if (file && FILE_VERB.test(text) && !file.includes('..')) return { id: 'read_file', tool: 'read_file', label: `read ${file}`, path: file };
  if (LIST_FILES.test(text)) return { id: 'list_files', tool: 'list_files', label: 'list the workspace files' };
  return null;
}

/** Whether this recipe can run here: the PR recipe needs to know which GitHub repository to ask. */
export function recipeAvailable(match: RecipeMatch, repo: string | null | undefined): boolean {
  return !GITHUB_RECIPES.has(match.id) || Boolean(repo && /^[\w.-]+\/[\w.-]+$/.test(repo));
}

export function recipeToolArgs(match: RecipeMatch, repo: string | null | undefined, githubBase = 'https://api.github.com'): Record<string, unknown> {
  const api = `${githubBase.replace(/\/$/, '')}/repos/${repo}`;
  if (match.id === 'open_prs') return { url: `${api}/pulls?state=open&per_page=5`, max_chars: 120000 };
  if (match.id === 'latest_pr') return { url: `${api}/pulls?state=all&sort=created&direction=desc&per_page=5`, max_chars: 120000 };
  if (match.id === 'ci_status') return { url: `${api}/actions/runs?per_page=5&exclude_pull_requests=true`, max_chars: 120000 };
  if (match.id === 'open_issues') return { url: `${api}/issues?state=open&per_page=10`, max_chars: 120000 };
  if (match.id === 'branches') return { url: `${api}/branches?per_page=10`, max_chars: 40000 };
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

const GITHUB_BAD = (repo: string | null | undefined, what: string, status: unknown): string => `GitHub answered HTTP ${String(status)} for ${repo}'s ${what}, so there is nothing to report.`;
const CUT_OFF = 'The GitHub reply could not be read as JSON (it was cut off or malformed).';

/** Pull requests (any state), issues and branches: one numbered or named line per item, built by code. */
function listFacts(match: RecipeMatch, output: Record<string, unknown>, repo?: string | null): Facts {
  const what = match.id === 'latest_pr' ? 'latest pull requests' : match.id === 'open_issues' ? 'open issues' : 'branches';
  if (Number(output.status) !== 200) return { error: GITHUB_BAD(repo, what, output.status) };
  const parsed = parseJsonArrayPrefix(String(output.text ?? ''));
  if (!parsed) return { error: /^\s*\{/.test(String(output.text ?? '')) ? `The GitHub reply was not a list of ${what}.` : CUT_OFF };
  // The issues endpoint also returns pull requests; they are not issues.
  const items = (match.id === 'open_issues' ? parsed.items.filter((i: any) => !i?.pull_request) : parsed.items) as any[];
  const note = parsed.complete ? '' : ' (the reply was longer than the limit and was cut off)';
  if (!items.length) return parsed.complete ? { facts: `${what[0]!.toUpperCase()}${what.slice(1)} in ${repo} (live from GitHub just now): none.` } : { error: CUT_OFF };
  if (match.id === 'branches') {
    const lines = items.slice(0, 10).map((b) => `- ${oneLine(b?.name, 100)}${b?.protected ? ' (protected)' : ''}`);
    return { facts: `Branches in ${repo} (live from GitHub just now, the first ${lines.length}${note}):\n${lines.join('\n')}` };
  }
  if (match.id === 'open_issues') {
    const lines = items.slice(0, 5).map((i) => `- #${Number(i?.number)} "${oneLine(i?.title, 120)}" by ${oneLine(i?.user?.login, 40) || 'unknown'}, updated ${oneLine(i?.updated_at, 20)} ${oneLine(i?.html_url, 120)}`);
    return { facts: `Open issues in ${repo} (live from GitHub just now, newest first, showing ${lines.length}${note}):\n${lines.join('\n')}` };
  }
  const state = (pr: any): string => (pr?.merged_at ? 'merged' : pr?.state === 'open' ? (pr?.draft ? 'open, draft' : 'open') : 'closed without merging');
  const lines = items.slice(0, 5).map((pr) => `- #${Number(pr?.number)} "${oneLine(pr?.title, 120)}" (${state(pr)}) by ${oneLine(pr?.user?.login, 40) || 'unknown'}, updated ${oneLine(pr?.updated_at, 20)} ${oneLine(pr?.html_url, 120)}`);
  return { facts: `Most recent pull requests in ${repo}, any state, newest first (live from GitHub just now, showing ${lines.length}${note}). The first line is the newest:\n${lines.join('\n')}` };
}

/** The newest workflow runs, with the verdict of the newest one stated by code so a model cannot flip it. */
function ciFacts(output: Record<string, unknown>, repo?: string | null): Facts {
  if (Number(output.status) !== 200) return { error: GITHUB_BAD(repo, 'workflow runs', output.status) };
  let body: any;
  try { body = JSON.parse(String(output.text ?? '')); } catch { return { error: CUT_OFF }; }
  const runs: any[] = Array.isArray(body?.workflow_runs) ? body.workflow_runs : [];
  if (!runs.length) return { facts: `CI runs in ${repo} (live from GitHub just now): none.` };
  const verdict = (r: any): string => (r?.status === 'completed' ? oneLine(r?.conclusion, 20) || 'completed' : oneLine(r?.status, 20) || 'unknown');
  const lines = runs.slice(0, 5).map((r) => `- "${oneLine(r?.name, 60)}" on ${oneLine(r?.head_branch, 60)} (${oneLine(r?.event, 20)}): ${verdict(r)}, run ${Number(r?.run_number)}, updated ${oneLine(r?.updated_at, 20)} ${oneLine(r?.html_url, 120)}`);
  return { facts: `Latest CI runs in ${repo}, newest first (live from GitHub just now). The newest run: ${verdict(runs[0])}.\n${lines.join('\n')}` };
}

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
  if (match.id === 'latest_pr' || match.id === 'open_issues' || match.id === 'branches') return listFacts(match, output, repo);
  if (match.id === 'ci_status') return ciFacts(output, repo);
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
  const numbered = /^- #\d+ /m.test(facts);
  const cite = numbered ? ` Name the ${match?.id === 'open_issues' ? 'issue' : 'pull request'} number(s) exactly as written above.`
    + (match?.id === 'latest_pr' ? ' The first one listed is the newest; say whether it is merged, open or closed.' : '')
    : match?.id === 'ci_status' ? ' Say whether the newest run passed, failed or is still running.'
    : match?.id === 'branches' ? ' Name the branches exactly as written above.' : '';
  return `Here is live data from a lookup just now:\n\n${facts}\n\nUsing only this data, answer in one or two sentences: ${String(goal).slice(0, 300)}${cite}`;
}

export interface SentenceRule {
  /** Nothing to word (no pull requests, an empty workspace): the data alone is the answer, the model is not asked. */
  skipModel: boolean;
  cite?: 'pr' | 'pr_newest' | 'file' | 'branch' | 'ci';
  /** Shown before a sentence that can only be checked for numbers and links. */
  uncheckedLabel?: boolean;
}

/** What the model's sentence must satisfy for this recipe, given the data. */
export function sentenceRule(match: RecipeMatch, facts: string): SentenceRule {
  if (match.id === 'open_prs' || match.id === 'open_issues') return { skipModel: !/^- #\d+ /m.test(facts), cite: 'pr' };
  if (match.id === 'latest_pr') return { skipModel: !/^- #\d+ /m.test(facts), cite: 'pr_newest' };
  if (match.id === 'ci_status') return { skipModel: !/^- "/m.test(facts), cite: 'ci' };
  if (match.id === 'branches') return { skipModel: !/^- \S/m.test(facts), cite: 'branch' };
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
export function groundedAnswer(answer: string, facts: string, opts: { cite?: SentenceRule['cite'] } = {}): { ok: true; text: string } | { ok: false; why: string } {
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
  if (opts.cite === 'branch') {
    const names = [...facts.matchAll(/^- (\S+)/gm)].map((m) => m[1]!.toLowerCase());
    const lower = text.toLowerCase();
    if (names.length && !names.some((n) => lower.includes(n))) return { ok: false, why: 'it named none of the listed branches' };
  }
  if (opts.cite === 'ci') {
    // The newest run's verdict is stated in the data; a sentence that says the opposite is wrong, not just vague.
    const verdict = facts.match(/The newest run: ([a-z_]+)\./)?.[1] ?? '';
    const says = { pass: /\b(pass(ed|es|ing)?|green|succe(ss|eded|ssful(ly)?)|succeeds)\b/i.test(text), fail: /\b(fail(ed|s|ing|ure)?|red|broken)\b/i.test(text), running: /\b(running|in progress|queued|pending)\b/i.test(text) };
    const actual = verdict === 'success' ? 'pass' : ['failure', 'timed_out', 'startup_failure'].includes(verdict) ? 'fail' : ['in_progress', 'queued', 'waiting', 'pending'].includes(verdict) ? 'running' : '';
    if (actual && (['pass', 'fail', 'running'] as const).some((k) => says[k] && k !== actual)) return { ok: false, why: `it contradicts the data (the newest run is "${verdict}")` };
    if (actual && !says[actual]) return { ok: false, why: `it did not state the newest run's result ("${verdict}")` };
  }
  if (opts.cite === 'pr' || opts.cite === 'pr_newest') {
    const prs = [...facts.matchAll(/^- #(\d+) "([^"\n]*)"/gm)].map((m) => ({ n: m[1]!, words: titleWords(m[2]!) }));
    const listed = prs.map((p) => p.n);
    const cited = listed.filter((n) => new RegExp(`(^|[^\\d])${n}([^\\d]|$)`).test(text));
    if (listed.length && !cited.length) return { ok: false, why: 'it named none of the listed items' };
    if (opts.cite === 'pr_newest' && listed.length && !cited.includes(listed[0]!)) return { ok: false, why: `it did not name the newest one (#${listed[0]})` };
    // A small model often pairs one PR's number with another PR's title. A distinctive word that belongs only to PRs the sentence does not cite is that mix-up.
    for (const w of titleWords(text)) {
      const owners = prs.filter((p) => p.words.has(w));
      if (owners.length && !owners.some((p) => cited.includes(p.n))) return { ok: false, why: `it mixed "${w}" (from #${owners[0]!.n}) with a different pull request` };
    }
  }
  return { ok: true, text };
}
