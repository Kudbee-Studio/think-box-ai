// Live-data lookups as ONE governed tool contract (Layer 4: tools glue, pure, no I/O).
// Every model (Mercury, Qwen, Gemma ...) asks for the same thing the same way: `live_lookup {recipe, branch?, repo?}`. The tool fetches GitHub through
// the normal governed path (approval, confinement, audit) and this module turns the reply into NORMALIZED EVIDENCE: ids, urls, state, timestamps,
// the source url, whether the list was complete, how many tool calls and how long it took. Nothing here fetches or calls a model, and nothing is
// ever invented: a bad reply is an explicit error, never a plausible-looking list.

export const LOOKUP_RECIPES = ['latest_pr', 'open_prs', 'ci_status', 'open_issues', 'branches'] as const;
export type LookupRecipe = (typeof LOOKUP_RECIPES)[number];

export interface LookupArgs { recipe: LookupRecipe; repo: string; branch?: string }

export type LookupItem =
  | { kind: 'pr'; number: number; title: string; state: 'open' | 'merged' | 'closed'; draft: boolean; author: string; head_ref: string; url: string; updated_at: string }
  | { kind: 'issue'; number: number; title: string; state: 'open' | 'closed'; author: string; url: string; updated_at: string }
  | { kind: 'branch'; name: string; protected: boolean }
  | { kind: 'run'; name: string; branch: string; event: string; status: string; conclusion: string | null; run_number: number; url: string; updated_at: string };

export interface LookupEvidence {
  recipe: LookupRecipe;
  repo: string;
  branch?: string;
  source_url: string;
  fetched_at: string;
  http_status: number;
  /** false when the reply was longer than the fetch limit and only the complete leading objects were kept. */
  complete: boolean;
  /** true when GitHub may hold more than the items shown: the reply was cut off, the page came back full (before pull requests were filtered out of an issues list), or items were dropped to the display limit. A count from this list is not a total. */
  more?: boolean;
  items: LookupItem[];
  /** ci_status only: the newest run's result in one word (success, failure, in_progress ...). */
  verdict?: string;
  tool_calls: 1;
  latency_ms: number;
}

const REPO = /^[\w.-]+\/[\w.-]+$/;
const BRANCH = /^[\w][\w./-]{0,99}$/;

export interface RawLookupArgs { recipe?: unknown; repo?: unknown; branch?: unknown; [k: string]: unknown }

/**
 * A model-supplied request, checked strictly: a known recipe, no unknown keys, no path tricks, and only the configured repository (a model cannot
 * point the tool at some other repo or host). The repo may be omitted; it then defaults to the configured one.
 */
export function validateLookupArgs(raw: unknown, knownRepo: string | null | undefined): { ok: true; args: LookupArgs } | { ok: false; error: string } {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return { ok: false, error: 'the tool request must be an object' };
  const r = raw as RawLookupArgs;
  const extra = Object.keys(r).filter((k) => !['recipe', 'repo', 'branch'].includes(k));
  if (extra.length) return { ok: false, error: `unknown argument(s): ${extra.join(', ')}` };
  if (typeof r.recipe !== 'string' || !(LOOKUP_RECIPES as readonly string[]).includes(r.recipe)) return { ok: false, error: `recipe must be one of ${LOOKUP_RECIPES.join(', ')}` };
  if (!knownRepo || !REPO.test(knownRepo)) return { ok: false, error: 'no GitHub repository is configured (set KUDBEE_REPO)' };
  if (r.repo !== undefined && r.repo !== null && r.repo !== '') {
    if (typeof r.repo !== 'string' || !REPO.test(r.repo)) return { ok: false, error: 'repo must look like owner/name' };
    if (r.repo.toLowerCase() !== knownRepo.toLowerCase()) return { ok: false, error: `only the configured repository (${knownRepo}) can be queried` };
  }
  const args: LookupArgs = { recipe: r.recipe as LookupRecipe, repo: knownRepo };
  if (r.branch !== undefined && r.branch !== null && r.branch !== '') {
    if (typeof r.branch !== 'string' || !BRANCH.test(r.branch) || r.branch.includes('..')) return { ok: false, error: 'branch is not a valid branch name' };
    if (args.recipe !== 'ci_status') return { ok: false, error: 'branch is only used with ci_status' };
    args.branch = r.branch;
  }
  return { ok: true, args };
}

/** How many items each recipe asks GitHub for. A list this long may be only the first page: a count taken from it is not a total. */
export const PAGE_SIZE: Record<LookupRecipe, number> = { open_prs: 5, latest_pr: 5, ci_status: 5, open_issues: 10, branches: 10 };

export function lookupUrl(args: LookupArgs, githubBase = 'https://api.github.com'): string {
  const api = `${githubBase.replace(/\/$/, '')}/repos/${args.repo}`;
  switch (args.recipe) {
    case 'open_prs': return `${api}/pulls?state=open&per_page=${PAGE_SIZE.open_prs}`;
    case 'latest_pr': return `${api}/pulls?state=all&sort=created&direction=desc&per_page=${PAGE_SIZE.latest_pr}`;
    case 'ci_status': return `${api}/actions/runs?per_page=${PAGE_SIZE.ci_status}&exclude_pull_requests=true${args.branch ? `&branch=${encodeURIComponent(args.branch)}` : ''}`;
    case 'open_issues': return `${api}/issues?state=open&per_page=${PAGE_SIZE.open_issues}`;
    case 'branches': return `${api}/branches?per_page=${PAGE_SIZE.branches}`;
  }
}

/** How many characters of the reply the fetch may keep for this recipe. */
export const lookupMaxChars = (recipe: LookupRecipe): number => (recipe === 'branches' ? 40000 : 120000);

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
const CUT_OFF = 'The GitHub reply could not be read as JSON (it was cut off or malformed).';
const WHAT: Record<LookupRecipe, string> = { latest_pr: 'latest pull requests', open_prs: "open pull requests", ci_status: 'workflow runs', open_issues: 'open issues', branches: 'branches' };

export interface LookupReply { status: unknown; text: unknown; url: string; fetched_at: string; latency_ms: number }

/** The GitHub reply as normalized evidence, or an explicit error (HTTP error, unreadable, wrong shape). Never a guess. */
export function normalizeLookup(args: LookupArgs, reply: LookupReply): { ok: true; evidence: LookupEvidence } | { ok: false; error: string } {
  const status = Number(reply.status);
  if (status !== 200) return { ok: false, error: `GitHub answered HTTP ${String(reply.status)} for ${args.repo}'s ${WHAT[args.recipe]}, so there is nothing to report.` };
  const base = { recipe: args.recipe, repo: args.repo, ...(args.branch ? { branch: args.branch } : {}), source_url: reply.url, fetched_at: reply.fetched_at, http_status: status, tool_calls: 1 as const, latency_ms: reply.latency_ms };
  const text = String(reply.text ?? '');
  if (args.recipe === 'ci_status') {
    let body: any;
    try { body = JSON.parse(text); } catch { return { ok: false, error: CUT_OFF }; }
    if (!body || !Array.isArray(body.workflow_runs)) return { ok: false, error: `The GitHub reply was not a list of ${WHAT.ci_status}.` };
    const items: LookupItem[] = body.workflow_runs.slice(0, 5).map((r: any): LookupItem => ({
      kind: 'run', name: oneLine(r?.name, 60), branch: oneLine(r?.head_branch, 60), event: oneLine(r?.event, 20), status: oneLine(r?.status, 20),
      conclusion: r?.conclusion == null ? null : oneLine(r.conclusion, 20), run_number: Number(r?.run_number), url: oneLine(r?.html_url, 160), updated_at: oneLine(r?.updated_at, 20),
    }));
    const verdict = items.length ? runVerdict(items[0] as Extract<LookupItem, { kind: 'run' }>) : undefined;
    return { ok: true, evidence: { ...base, complete: true, items, ...(verdict ? { verdict } : {}) } };
  }
  const parsed = parseJsonArrayPrefix(text);
  if (!parsed) return { ok: false, error: /^\s*\{/.test(text) ? `The GitHub reply was not a list of ${WHAT[args.recipe]}.` : CUT_OFF };
  // The issues endpoint also returns pull requests; they are not issues.
  const raw = (args.recipe === 'open_issues' ? parsed.items.filter((i: any) => !i?.pull_request) : parsed.items) as any[];
  if (!raw.length && !parsed.complete) return { ok: false, error: CUT_OFF };
  const author = (x: any): string => oneLine(x?.user?.login, 40) || 'unknown';
  let items: LookupItem[];
  if (args.recipe === 'branches') items = raw.slice(0, 10).map((b): LookupItem => ({ kind: 'branch', name: oneLine(b?.name, 100), protected: Boolean(b?.protected) }));
  else if (args.recipe === 'open_issues') items = raw.slice(0, 5).map((i): LookupItem => ({ kind: 'issue', number: Number(i?.number), title: oneLine(i?.title, 120), state: i?.state === 'closed' ? 'closed' : 'open', author: author(i), url: oneLine(i?.html_url, 160), updated_at: oneLine(i?.updated_at, 20) }));
  else items = raw.slice(0, 5).map((pr): LookupItem => ({ kind: 'pr', number: Number(pr?.number), title: oneLine(pr?.title, 120), state: pr?.merged_at ? 'merged' : pr?.state === 'open' ? 'open' : 'closed', draft: Boolean(pr?.draft), author: author(pr), head_ref: oneLine(pr?.head?.ref, 100), url: oneLine(pr?.html_url, 160), updated_at: oneLine(pr?.updated_at, 20) }));
  const more = !parsed.complete || parsed.items.length >= PAGE_SIZE[args.recipe] || raw.length > items.length;
  return { ok: true, evidence: { ...base, complete: parsed.complete, more, items } };
}

export function runVerdict(run: Extract<LookupItem, { kind: 'run' }>): string {
  return run.status === 'completed' ? run.conclusion || 'completed' : run.status || 'unknown';
}

const prState = (pr: Extract<LookupItem, { kind: 'pr' }>): string => (pr.state === 'merged' ? 'merged' : pr.state === 'open' ? (pr.draft ? 'open, draft' : 'open') : 'closed without merging');

/** The evidence as plain lines (what a small model is handed to word an answer, and what the user always sees next to it). */
export function renderFacts(e: LookupEvidence): string {
  const cut = e.complete ? '' : ' (the reply was longer than the limit and was cut off)';
  const none = (title: string): string => `${title} in ${e.repo} (live from GitHub just now): none.`;
  if (e.recipe === 'ci_status') {
    const runs = e.items.filter((i): i is Extract<LookupItem, { kind: 'run' }> => i.kind === 'run');
    if (!runs.length) return `CI runs in ${e.repo}${e.branch ? ` on branch ${e.branch}` : ''} (live from GitHub just now): none.`;
    const lines = runs.map((r) => `- "${r.name}" on ${r.branch} (${r.event}): ${runVerdict(r)}, run ${r.run_number}, updated ${r.updated_at} ${r.url}`);
    return `Latest CI runs in ${e.repo}${e.branch ? ` on branch ${e.branch}` : ''}, newest first (live from GitHub just now). The newest run: ${e.verdict}.\n${lines.join('\n')}`;
  }
  if (e.recipe === 'branches') {
    const bs = e.items.filter((i): i is Extract<LookupItem, { kind: 'branch' }> => i.kind === 'branch');
    if (!bs.length) return none('Branches');
    return `Branches in ${e.repo} (live from GitHub just now, the first ${bs.length}${cut}):\n${bs.map((b) => `- ${b.name}${b.protected ? ' (protected)' : ''}`).join('\n')}`;
  }
  if (e.recipe === 'open_issues') {
    const is = e.items.filter((i): i is Extract<LookupItem, { kind: 'issue' }> => i.kind === 'issue');
    if (!is.length) return none('Open issues');
    return `Open issues in ${e.repo} (live from GitHub just now, newest first, showing ${is.length}${cut}):\n${is.map((i) => `- #${i.number} "${i.title}" by ${i.author}, updated ${i.updated_at} ${i.url}`).join('\n')}`;
  }
  const prs = e.items.filter((i): i is Extract<LookupItem, { kind: 'pr' }> => i.kind === 'pr');
  if (e.recipe === 'open_prs') {
    if (!prs.length) return none('Open pull requests');
    const head = e.complete ? `${prs.length}.` : `showing the first ${prs.length} (the reply was longer than the limit and was cut off).`;
    return `Open pull requests in ${e.repo} (live from GitHub just now): ${head}\n${prs.map((p) => `- #${p.number} "${p.title}"${p.draft ? ' (draft)' : ''} by ${p.author}, updated ${p.updated_at} ${p.url}${p.head_ref ? ` branch ${p.head_ref}` : ''}`.trim()).join('\n')}`;
  }
  if (!prs.length) return none('Latest pull requests');
  return `Most recent pull requests in ${e.repo}, any state, newest first (live from GitHub just now, showing ${prs.length}${cut}). The first line is the newest:\n${prs.map((p) => `- #${p.number} "${p.title}" (${prState(p)}) by ${p.author}, updated ${p.updated_at} ${p.url}${p.head_ref ? ` branch ${p.head_ref}` : ''}`).join('\n')}`;
}
