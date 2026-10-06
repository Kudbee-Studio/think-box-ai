// Local recipes (Layer 4: tools glue, pure, no I/O). A 360M local model cannot decide to call a tool, but it can word an answer when it is handed the
// data. For a short, fixed list of common questions the SERVER makes the tool call (through the same governed path as the worker agent: approval,
// confinement, audit) and the local model only writes a sentence from the result. The sentence is checked against the data; if it states a number
// or link that is not in the data, the data itself is shown instead. Nothing here runs a tool or calls a model.

import { lookupMaxChars, lookupUrl, normalizeLookup, parseJsonArrayPrefix, renderFacts, type LookupEvidence, type LookupRecipe } from './live-lookup.ts';
export { parseJsonArrayPrefix };

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
const MUTATION = /\b(re-?run|re-?start|trigger|cancel|retry|merge|close|create|make|approve|comment on|review|fix|delete|revert|rebase|open a|open an|submit|push|update|edit|write|rename|remove|change|replace|modify|correct|rewrite|implement|refactor|insert|add|adjust|tweak|amend)\b/i;
// "the last PR", "the newest pull request": the most recent one in ANY state (a merged PR is not "open").
const LATEST = /\b(last|latest|most recent|newest|previous|recent(ly)?)\b/i;
const CI = /\b(ci|continuous integration|github actions|workflow runs?|checks?|build status|pipeline)\b/i;
const CI_QUESTION = /\b(what|which|how|did|does|is|are|was|were|status|pass(ed|ing)?|fail(ed|ing)?|green|red|broken|running)\b/i;
const ISSUE = /\bissues?\b/i;
const BRANCHES = /\b(list|show|which|what|how many)\b.{0,40}\bbranches\b/i;
const FILE_NAME = /(?<![\w/@.:-])([\w][\w.-]*\.(?:md|txt|json|ts|js|mjs|py|csv|html|ya?ml|xml|log))\b/i;
const FILE_VERB = /\b(read|show|print|display|open|what'?s in|what is in|contents? of|summari[sz]e|tell me about|in)\b/i;
const LIST_FILES = /\b(list|show|what|which)\b.{0,40}\b(files?|workspace|folder)\b/i;

const REPO_VERB = /\b(find|inspect|investigate|audit|locate|identify|look for|search|which|list|check)\b/i;
const REPO_THING = /\b(functions?|files?|modules?|exports?|tests?|untested|unused|code ?base|source|repo(sitory)? code|todo|fixme|dead code|duplicat\w+)\b/i;
/** A goal that asks to INVESTIGATE this repository's source (read-only), not a live GitHub question and not a change request. */
export function matchRepoGoal(goal: string): boolean {
  const text = String(goal ?? '');
  if (!text.trim() || text.length > 600 || MUTATION.test(text) || /https?:\/\//i.test(text)) return false;
  const recipe = matchRecipe(text);
  // Live GitHub questions and workspace file recipes (read a named file, list the workspace) have their own governed path.
  if (recipe && (isGithubRecipe(recipe) || recipe.id === 'read_file' || (recipe.id === 'list_files' && /\b(workspace|folder)\b/i.test(text)))) return false;
  return REPO_VERB.test(text) && REPO_THING.test(text);
}

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

/** The GitHub recipes run through the shared live_lookup tool (one governed path, normalized evidence, the shared grounding validator). */
export const isGithubRecipe = (match: RecipeMatch): boolean => GITHUB_RECIPES.has(match.id);

/** Whether this recipe can run here: the PR recipe needs to know which GitHub repository to ask. */
export function recipeAvailable(match: RecipeMatch, repo: string | null | undefined): boolean {
  return !GITHUB_RECIPES.has(match.id) || Boolean(repo && /^[\w.-]+\/[\w.-]+$/.test(repo));
}

export function recipeToolArgs(match: RecipeMatch, repo: string | null | undefined, githubBase = 'https://api.github.com'): Record<string, unknown> {
  if (GITHUB_RECIPES.has(match.id)) return { url: lookupUrl({ recipe: match.id as LookupRecipe, repo: String(repo) }, githubBase), max_chars: lookupMaxChars(match.id as LookupRecipe) };
  if (match.id === 'read_file') return { path: match.path };
  return {};
}

export type Facts = { facts: string } | { error: string };

const oneLine = (text: unknown, max: number): string => String(text ?? '').replace(/\s+/g, ' ').trim().slice(0, max);

/** The structured evidence for a GitHub recipe (one normalizer for every model), or the explicit reason there is none. null for the file recipes. */
export function buildEvidence(match: RecipeMatch, output: Record<string, unknown>, repo?: string | null, latencyMs = 0): { evidence: LookupEvidence } | { error: string } | null {
  if (!GITHUB_RECIPES.has(match.id)) return null;
  const normalized = normalizeLookup({ recipe: match.id as LookupRecipe, repo: String(repo ?? '') }, { status: output.status, text: output.text, url: String(output.url ?? ''), fetched_at: new Date().toISOString(), latency_ms: latencyMs });
  return normalized.ok ? { evidence: normalized.evidence } : { error: normalized.error };
}

/** The data, as plain lines, built by code from the tool output (never by the model). */
export function buildFacts(match: RecipeMatch, output: Record<string, unknown>, repo?: string | null): Facts {
  if (GITHUB_RECIPES.has(match.id)) {
    const built = buildEvidence(match, output, repo);
    return built && 'evidence' in built ? { facts: renderFacts(built.evidence) } : { error: (built as { error: string }).error };
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
const URL_RE = /https?:\/\/[^\s)"']+/g;

/**
 * Accept the model's sentence only if every number and link it states is in the data. A sentence that invents a PR number, a size or a URL is
 * dropped (the caller shows the data itself). An error-looking, empty or very long reply is dropped too.
 */
export function groundedAnswer(answer: string, facts: string, opts: { cite?: 'file' } = {}): { ok: true; text: string } | { ok: false; why: string } {
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
  return { ok: true, text };
}
