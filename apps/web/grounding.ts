// One grounding validator for live-data answers (Layer 1, foundation: pure, no I/O, no model).
// Whatever model wrote the sentence (Mercury, Qwen, Gemma, a recipe), every checkable claim in it must be traceable to the tool evidence that came back:
// numbers, links, PR / issue / run ids, branch names and state claims (merged, open, closed, draft, passed, failed, running). A sentence with an
// unsupported claim is marked GROUNDING FAILED, the claims are named, and it is never shown as verified (presentAnswer shows the evidence instead).
// This is a claim check against evidence, not a view into the model's reasoning: nothing here reads or displays chain of thought.

import { PAGE_SIZE, renderFacts, type LookupEvidence, type LookupItem } from './live-lookup.ts';
import type { RepoEvidence } from './repo-tools.ts';
import type { AbsenceCheck } from './absence.ts';

export type ClaimKind = 'number' | 'url' | 'id' | 'branch' | 'state' | 'citation' | 'file' | 'line' | 'quote' | 'identifier' | 'absence';
export interface UnsupportedClaim { kind: ClaimKind; claim: string; why: string }

export interface GroundingResult {
  status: 'GROUNDED' | 'GROUNDING FAILED';
  /** ok | unsupported_claim | no_evidence | empty_answer | unreadable_answer */
  classification: 'ok' | 'unsupported_claim' | 'no_evidence' | 'empty_answer' | 'unreadable_answer' | 'needs_escalation';
  unsupported: UnsupportedClaim[];
  /** How many claims of each kind were found and checked (a count of what was verified, so "GROUNDED" is not an empty claim). */
  checked: { numbers: number; urls: number; ids: number; branches: number; states: number; quotes?: number; identifiers?: number; absence?: number };
}

const MAX_ANSWER_CHARS = 1500;
const URL_RE = /https?:\/\/[^\s)"'<>]+/g;
const NEGATION = /\b(no|not|never|none|without|isn't|wasn't|aren't|weren't|hasn't|haven't|didn't|doesn't|cannot|can't|neither|nor)\b|n't\b|\bun$/i;
const STOP = new Set(['the', 'is', 'of', 'was', 'for', 'in', 'on', 'and', 'has', 'that', 'which', 'with', 'are', 'a', 'an', 'name', 'names', 'list', 'lists', 'to', 'it', 'its', 'this', 'there', 'as', 'at', 'by', 'from', 'be', 'or']);
const COMMON = new Set(['about', 'after', 'being', 'could', 'first', 'their', 'there', 'these', 'those', 'which', 'would', 'where', 'while', 'with', 'pull', 'request', 'requests', 'based', 'open', 'data', 'live', 'github', 'working', 'currently', 'listed', 'number', 'newest', 'latest', 'merged', 'closed', 'branch', 'false', 'true', 'null', 'draft', 'drafts']);
const WORD_NUMBER: Record<string, string> = { one: '1', two: '2', three: '3', four: '4', five: '5', six: '6', seven: '7', eight: '8', nine: '9', ten: '10' };

type State = 'merged' | 'open' | 'closed' | 'draft' | 'passed' | 'failed' | 'running';
const STATE_WORDS: Array<{ state: State; re: RegExp }> = [
  { state: 'merged', re: /\bmerged\b/gi },
  { state: 'draft', re: /\bdraft\b/gi },
  { state: 'open', re: /\b(open|opened)\b/gi },
  { state: 'closed', re: /\bclosed\b/gi },
  { state: 'passed', re: /\b(pass(?:ed|es|ing)?|succe(?:ss|eded|ssful(?:ly)?)|succeeds|green)\b/gi },
  { state: 'failed', re: /\b(fail(?:ed|s|ing|ure)?|red|broken)\b/gi },
  { state: 'running', re: /\b(running|in progress|queued|pending)\b/gi },
];

const runClass = (verdict: string | null | undefined): State | null => {
  if (verdict === 'success') return 'passed';
  if (verdict && ['failure', 'timed_out', 'startup_failure', 'cancelled'].includes(verdict)) return 'failed';
  if (verdict && ['in_progress', 'queued', 'waiting', 'pending', 'requested'].includes(verdict)) return 'running';
  return null;
};
const itemVerdict = (i: Extract<LookupItem, { kind: 'run' }>): string => (i.status === 'completed' ? i.conclusion ?? '' : i.status);

/** Whether this evidence item supports the claim that it is `state`. */
function itemSupports(item: LookupItem, state: State, recipe: string): boolean {
  if (item.kind === 'pr') {
    if (state === 'merged') return item.state === 'merged';
    if (state === 'draft') return item.draft;
    if (state === 'open') return item.state === 'open' || recipe === 'open_prs';
    if (state === 'closed') return item.state === 'closed' || item.state === 'merged';
    return false;
  }
  if (item.kind === 'issue') return (state === 'open' && (item.state === 'open' || recipe === 'open_issues')) || (state === 'closed' && item.state === 'closed');
  if (item.kind === 'run') return runClass(itemVerdict(item)) === state;
  return false;
}

const ids = (items: LookupItem[], kind: 'pr' | 'issue' | 'run'): Set<string> => new Set(items.flatMap((i) => (i.kind === kind ? [String(kind === 'run' ? (i as any).run_number : (i as any).number)] : [])));
/** Typographic hyphens (non-breaking, en/em dash, minus) read as the plain hyphen, so "think\u2011box\u2011ai" is one word, not "think". */
const plainHyphens = (s: string): string => s.replace(/[\u2010-\u2015\u2212]/g, '-');
const titleWords = (text: string): Set<string> => new Set((plainHyphens(text).toLowerCase().match(/[a-z][a-z0-9-]{4,}/g) ?? []).filter((w) => !COMMON.has(w)));
/** A plain `a/b` word ("and/or", "creation/update") is not a branch reference; one that starts like a branch name is. */
const BRANCH_PREFIX = /^(feat|feature|fix|bugfix|hotfix|chore|docs|test|tests|refactor|release|dependabot|renovate|revert|codex|claude)\//i;
const escapeRe = (s: string): string => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
/** Blank out verbatim item titles: a PR called "...queued approvals" must not read as a claim that something is queued. */
function maskTitles(text: string, titles: string[]): string {
  let out = text;
  for (const title of titles) if (title.length >= 6) out = out.replace(new RegExp(escapeRe(title).replace(/\s+/g, '\\s+'), 'gi'), (m) => ' '.repeat(m.length));
  return out;
}
const STATE_WORD = '(?:open|opened|closed|merged|draft)';
/** "(open, closed, or merged)" lists the possible states; it asserts nothing about one item. Only a parenthetical list is skipped, so "#359 was merged and closed" is still checked. */
const STATE_ENUMERATION = new RegExp(`\\(\\s*${STATE_WORD}(?:\\s*,\\s*(?:or\\s+|and\\s+)?${STATE_WORD}|\\s+(?:or|and)\\s+${STATE_WORD})+\\s*\\)`, 'gi');
const maskEnumerations = (text: string): string => text.replace(STATE_ENUMERATION, (m) => ' '.repeat(m.length));
/** A markdown field line ("- **State:** Merged", "State: Merged") describes the item named just above it. */
const FIELD_LINE = /^[\s>*•-]*\**[A-Za-z][A-Za-z ]{1,24}:\**\s/;
const mask = (text: string, start: number, len: number): string => text.slice(0, start) + ' '.repeat(len) + text.slice(start + len);

/**
 * Check `answer` against the evidence it claims to come from. `GROUNDED` means every number, link, id, branch name and state claim in the sentence
 * was found in (and, for states, attributed correctly to) the returned evidence, and that the sentence names something that was actually returned.
 */
/** What the question asked, read from its words. Only used to decide which checks make sense; never to excuse a wrong fact. */
export function readGoal(goal: string | undefined): { given: boolean; specificNumber: string | null; asksNewest: boolean; asksSet: boolean; askedCount: number | null } {
  const g = String(goal ?? '');
  return {
    given: Boolean(g.trim()),
    specificNumber: g.match(/(?:#|\b(?:pr|pull request|issue)\s*)(\d{1,7})\b/i)?.[1] ?? null,
    asksNewest: /\b(last|latest|newest|most recent|current)\b/i.test(g),
    asksSet: /\b(which|are there|are any|is there|how many|any|list|drafts?|all)\b/i.test(g),
    // "the three most recent PRs": the question itself fixes a count, which the answer may repeat ("all three PRs")
    askedCount: (() => { const m = g.match(/\b(one|two|three|four|five|six|seven|eight|nine|ten|\d{1,2})\s+(?:most\s+recent|latest|newest|recent|open|draft)\b/i); return m ? Number(WORD_NUMBER[m[1]!.toLowerCase()] ?? m[1]) : null; })(),
  };
}
const HEDGE = /\b(at least|first|latest|most recent|newest|recent|shown|listed|top|only|up to|so far)\b/i;
/** For "how many" on a capped list with no exact total, only wording that says the number is partial counts as a hedge ("ten branches currently listed" reads as a total). */
const PARTIAL = /\b(at least|more than|first|latest|most recent|newest|top|shown|showing|only|up to|so far)\b/i;

export function validateGrounding(answer: string, evidence: LookupEvidence[], opts: { goal?: string } = {}): GroundingResult {
  const ask = readGoal(opts.goal);
  const checked = { numbers: 0, urls: 0, ids: 0, branches: 0, states: 0 };
  const fail = (classification: GroundingResult['classification'], unsupported: UnsupportedClaim[]): GroundingResult => ({ status: 'GROUNDING FAILED', classification, unsupported, checked });
  const text = String(answer ?? '').replace(/```[\s\S]*?```/g, ' ').replace(/\s+/g, ' ').trim();
  // Same text with its line breaks kept: a markdown list is read line by line when attributing states.
  const lined = String(answer ?? '').replace(/```[\s\S]*?```/g, ' ').replace(/[ \t]+/g, ' ').replace(/\s*\n\s*/g, '\n').trim();
  if (!text) return fail('empty_answer', [{ kind: 'citation', claim: '(empty)', why: 'the model returned nothing' }]);
  if (/^\[Error:/i.test(text)) return fail('unreadable_answer', [{ kind: 'citation', claim: text.slice(0, 80), why: 'the model call failed' }]);
  if (text.length > MAX_ANSWER_CHARS) return fail('unreadable_answer', [{ kind: 'citation', claim: `(${text.length} characters)`, why: 'the answer is too long to check claim by claim' }]);
  if (!evidence.length) return fail('no_evidence', [{ kind: 'citation', claim: '(whole answer)', why: 'no tool evidence was returned, so nothing in the answer can be verified' }]);

  const items = evidence.flatMap((e) => e.items);
  const facts = evidence.map(renderFacts).join('\n');
  const recipes = new Set(evidence.map((e) => e.recipe));
  const unsupported: UnsupportedClaim[] = [];
  const add = (kind: ClaimKind, claim: string, why: string): void => { if (!unsupported.some((u) => u.kind === kind && u.claim === claim)) unsupported.push({ kind, claim, why }); };

  // 1. links
  let rest = text;
  const known = new Set<string>();
  for (const e of evidence) { known.add(e.source_url); known.add(`https://github.com/${e.repo}`); for (const i of e.items) if ('url' in i && i.url) known.add(i.url); }
  for (const m of [...text.matchAll(URL_RE)]) {
    const url = m[0].replace(/[.,;:!?]+$/, '');
    checked.urls += 1;
    if (!known.has(url)) add('url', url, 'this link is not in the tool evidence');
    rest = mask(rest, m.index!, m[0].length);
  }

  // 2. ids: #N, "PR 12", "issue 4", "run 812" (checked against the right kind of item)
  const prIds = ids(items, 'pr'); const issueIds = ids(items, 'issue'); const runIds = ids(items, 'run');
  const anyId = new Set([...prIds, ...issueIds, ...runIds]);
  const cited = new Set<string>();
  const idRe = /(?:(pull requests?|prs?|issues?|runs?)\s+#?|#)(\d{1,7})\b/gi;
  for (const m of [...rest.matchAll(idRe)]) {
    const kindWord = (m[1] ?? '').toLowerCase();
    const n = m[2]!;
    // Only the current clause counts: a denial earlier in the sentence ("no PR like #304; the newest is #361") must not hide a later claim.
    const before = rest.slice(Math.max(0, m.index! - 45), m.index!).split(/[.;!?,]/).pop() ?? '';
    if (NEGATION.test(before)) { rest = mask(rest, m.index!, m[0].length); continue; }
    checked.ids += 1;
    const pool = kindWord.startsWith('run') ? runIds : kindWord.startsWith('issue') ? issueIds : kindWord ? prIds : anyId;
    if (!pool.has(n)) add('id', kindWord ? `${kindWord.replace(/s$/, '')} ${n}` : `#${n}`, `${kindWord ? kindWord.replace(/s$/, '') : 'id'} ${n} is not in the tool evidence`);
    else cited.add(n);
    rest = mask(rest, m.index!, m[0].length);
  }

  // a markdown table names an item by its bare number in a cell: `| 59 | Title |`
  for (const m of [...rest.matchAll(/\|\s*[*_`#]*(\d{1,7})[*_`]*\s*\|/g)]) if (anyId.has(m[1]!)) { cited.add(m[1]!); checked.ids += 1; rest = mask(rest, m.index!, m[0].length); }

  // Verbatim titles are quoted data, not claims: from here on they are blanked for the branch, number and state checks (ids were read above, so naming a PR by its title still counts).
  const titles = items.flatMap((i) => ('title' in i ? [i.title] : []));
  rest = maskTitles(rest, titles);

  // 3. branch names
  const branches = new Set<string>();
  for (const e of evidence) if (e.branch) branches.add(e.branch.toLowerCase());
  for (const i of items) { if (i.kind === 'pr' && i.head_ref) branches.add(i.head_ref.toLowerCase()); if (i.kind === 'branch') branches.add(i.name.toLowerCase()); if (i.kind === 'run') branches.add(i.branch.toLowerCase()); }
  const claimBranch = (name: string): void => {
    const n = name.replace(/[.,;:!?)]+$/, '');
    if (!n || STOP.has(n.toLowerCase())) return;
    checked.branches += 1;
    if (!branches.has(n.toLowerCase()) && !facts.toLowerCase().includes(n.toLowerCase())) add('branch', n, 'this branch name is not in the tool evidence');
  };
  for (const m of [...rest.matchAll(/\bbranch(?:es)?\s+(named\s+|called\s+)?([`'"])?([\w][\w./-]*)/gi)]) {
    // "branches currently present", "branch failed": an English word after "branch" is not a branch name. A name counts when it is introduced ("named X"), quoted, or shaped like one.
    const nm = m[3]!.replace(/[.,;:!?)]+$/, '');
    if (m[1] || m[2] || /[/_.\-\d]/.test(nm) || /^(main|master|develop|dev|trunk)$/i.test(nm)) claimBranch(nm);
    // mask what follows the word "branch(es)" but leave the word itself, so "ten branches currently listed" still reaches the count check
    const after = m[0].search(/\s/);
    rest = mask(rest, m.index! + after, m[0].length - after);
  }
  for (const m of [...rest.matchAll(/(?<![\w/:.-])[\w.-]+(?:\/[\w.-]+)+/g)]) { if (BRANCH_PREFIX.test(m[0])) claimBranch(m[0]); rest = mask(rest, m.index!, m[0].length); }

  // 4. counts in words ("two open PRs") and plain numbers
  const knownNumbers = new Set(facts.match(/\d+(?:\.\d+)*/g) ?? []);
  for (const e of evidence) knownNumbers.add(String(e.items.length));
  const KIND_OF: Array<[RegExp, (i: LookupItem) => boolean]> = [[/^(prs?|pull requests?)$/i, (i) => i.kind === 'pr'], [/^issues?$/i, (i) => i.kind === 'issue'], [/^branches$/i, (i) => i.kind === 'branch'], [/^(runs?|workflow runs?)$/i, (i) => i.kind === 'run']];
  for (const m of [...rest.matchAll(/\b(one|two|three|four|five|six|seven|eight|nine|ten|\d{1,3})\s+(?:(?:most\s+)?recent\s+|open\s+|latest\s+|newest\s+|draft\s+)?(prs?|pull requests?|issues?|branches|runs?|workflow runs?)\b/gi)]) {
    checked.numbers += 1;
    const n = WORD_NUMBER[m[1]!.toLowerCase()] ?? m[1]!;
    // a count of a kind of item is a claim about that list: it must be the list's length (a hedged "the 3 most recent" may be fewer), and a list that fills its page is not a total
    const pred = KIND_OF.find(([re]) => re.test(m[2]!))?.[1];
    const lists = evidence.filter((e) => e.items.some((i) => pred?.(i)));
    if (!pred || !lists.length) {
      if (!knownNumbers.has(n)) add('number', `${m[1]!.toLowerCase()} ${m[2]!.toLowerCase()}`, `${n} is not a count or value in the tool evidence`);
      continue;
    }
    rest = mask(rest, m.index! + m[0].search(/\S/), m[1]!.length); // judged here against the list; not again as a bare number
    const len = lists[0]!.items.filter(pred).length;
    const total = lists.find((e) => e.total !== undefined)?.total;
    const capped = lists.some((e) => e.more ?? e.items.length >= PAGE_SIZE[e.recipe]);
    const hedgeWords = ask.given && /\bhow many\b/i.test(opts.goal ?? '') && capped && total === undefined ? PARTIAL : HEDGE;
    // the window is read from the original sentence (the masks keep lengths, so positions agree): a hedge word that an earlier step masked is still a hedge
    const hedged = hedgeWords.test(text.slice(Math.max(0, m.index! - 40), m.index! + m[0].length + 25)) || (ask.askedCount === Number(n));
    const label = /^\d/.test(m[1]!) ? m[1]! : `${m[1]!.toLowerCase()} ${m[2]!.toLowerCase()}`;
    if (total !== undefined && Number(n) === total) continue; // the exact total GitHub reported
    if (Number(n) > len || (!hedged && Number(n) !== len)) add('number', label, `the tool evidence lists ${len} of that kind${total !== undefined ? ` and GitHub's total is ${total}` : ''}, not ${n}`);
    else if (!hedged && capped) add('number', label, total !== undefined ? `the lookup shows only the first ${len}, and GitHub's total is ${total}` : `the lookup returns only the first ${len}, so this is not a total (there may be more)`);
  }
  // "main is not listed" / "no such branch" from a list that stops at its page size is not proof the branch does not exist
  if (evidence.some((e) => e.recipe === 'branches' && (e.more ?? e.items.length >= PAGE_SIZE.branches)) && /\b(not listed|isn'?t listed|is not (?:in|among)|does not exist|doesn'?t exist|no such branch|not present)\b/i.test(rest)) add('absence', 'a branch is "not listed"', 'the lookup returns only the first page of branches, so a branch missing from it may still exist');
  for (const m of [...rest.matchAll(/\d+(?:\.\d+)*/g)]) {
    checked.numbers += 1;
    if (!knownNumbers.has(m[0])) add('number', m[0], 'this number is not in the tool evidence');
  }

  // a flat denial ("no open issues", "no draft pull requests") while the evidence lists some is a contradiction
  const listed = (recipe: string, kind: LookupItem['kind']): number => Math.max(evidence.filter((e) => e.recipe === recipe).flatMap((e) => e.items).filter((i) => i.kind === kind).length, ...evidence.filter((e) => e.recipe === recipe).map((e) => e.total ?? 0));
  if (listed('open_prs', 'pr') && /\b(?:no|zero|not any|none of)\b[^.\n]{0,20}\bopen\b[^.\n]{0,15}\b(?:pull requests?|prs?)\b/i.test(text)) add('state', 'no open pull requests', `the tool evidence lists ${listed('open_prs', 'pr')} open pull request(s)`);
  if (listed('open_issues', 'issue') && /\b(?:no|zero|not any|none of)\b[^.\n]{0,20}\bopen\b[^.\n]{0,15}\bissues?\b/i.test(text)) add('state', 'no open issues', `the tool evidence lists ${listed('open_issues', 'issue')} open issue(s)`);
  if (items.some((i) => i.kind === 'pr' && i.draft) && /\bno\s+drafts?\b|\bno\s+draft\s+(?:pull requests?|prs?)\b|\bnone\b[^.\n]{0,30}\bdrafts?\b/i.test(text)) add('state', 'no draft pull requests', 'the tool evidence lists a draft pull request');

  // 5. state claims, attributed per clause: a clause naming exactly one item must state that item's state
  const claimed: Array<{ state: State; clause: string; named?: string[] }> = [];
  let lastNamed: string[] = [];
  // a field printed as `"draft": false` states that the state is NOT the case: it is not a claim of that state
  const clauses = maskEnumerations(maskTitles(lined, titles).replace(/["'`]?\b(?:draft|merged|open|closed)\b["'`]?(?:\s+(?:flag|field|status|state|value))?\s*(?:[:=]|\bis\b|\bare\b)\s*["'`]?false\b/gi, (m) => ' '.repeat(m.length))).split(/\n+|(?<=[.!?;])\s+|,\s+(?:and|but|while)\s+|\s+(?:and|but|while)\s+/i).filter((c) => c.trim());
  const clauseIds = (clause: string): string[] => [...clause.matchAll(/(?:(?:pull requests?|prs?|issues?|runs?)\s+#?|#)(\d{1,7})\b/gi)].map((m) => m[1]!).filter((n) => anyId.has(n));
  for (const clause of clauses) {
    const own = clauseIds(clause);
    const attributed = own.length ? own : FIELD_LINE.test(clause) ? lastNamed : [];
    if (own.length) lastNamed = own;
    for (const { state, re } of STATE_WORDS) {
      for (const m of [...clause.matchAll(re)]) {
        if (NEGATION.test(clause.slice(Math.max(0, m.index! - 25), m.index!)) || /^\s*(?:none\b|nothing\b|neither\b|no\s+[a-z])/i.test(clause) || /\b(not|un)\s*$/i.test(clause.slice(0, m.index!))) continue;
        // "open pull requests" is a noun phrase naming the list, not a claim about one item
        if (state === 'open' && /^\s*(pull|prs?|issues?)\b/i.test(clause.slice(m.index! + m[0].length))) { if (!recipes.has('open_prs') && !recipes.has('open_issues') && !items.some((i) => itemSupports(i, 'open', ''))) { checked.states += 1; add('state', 'open', 'no open item is in the tool evidence'); } continue; }
        claimed.push({ state, clause, named: attributed });
      }
    }
  }
  for (const { state, named = [] } of claimed) {
    checked.states += 1;
    const pool = named.length ? items.filter((i) => (i.kind === 'run' ? named.includes(String(i.run_number)) : 'number' in i && named.includes(String(i.number)))) : items;
    const recipe = evidence.find((e) => e.items.some((i) => pool.includes(i)))?.recipe ?? [...recipes][0]!;
    if (!pool.some((i) => itemSupports(i, state, recipe))) {
      add('state', named.length ? `${named.map((n) => `#${n}`).join(', ')} ${state}` : state, named.length ? `the tool evidence does not say ${named.map((n) => `#${n}`).join(', ')} is ${state}` : `no item in the tool evidence is ${state}`);
    }
  }

  // 6. the sentence must name something that was actually returned (and the newest one / the CI verdict when that is what was asked)
  const numbered = items.filter((i): i is Extract<LookupItem, { kind: 'pr' | 'issue' }> => i.kind === 'pr' || i.kind === 'issue');
  const lowered = text.toLowerCase();
  if (numbered.length) {
    const listed = numbered.map((i) => String(i.number));
    const citedListed = listed.filter((n) => cited.has(n));
    if (!citedListed.length && !(ask.given && ask.asksSet)) add('citation', '(no listed item named)', 'the sentence names none of the listed pull requests or issues');
    const first = evidence.find((e) => e.recipe === 'latest_pr')?.items[0];
    // the newest PR must be named when the question is about the newest one (or nothing is known about the question); a question about PR #N need not
    const newestMatters = !ask.given || (ask.asksNewest && !ask.specificNumber);
    if (newestMatters && first && first.kind === 'pr' && !cited.has(String(first.number))) add('citation', `#${first.number}`, `the sentence does not name the newest pull request (#${first.number})`);
    // A small model often pairs one PR's number with another PR's title: a distinctive word that belongs only to PRs the sentence does not cite is that mix-up.
    if (numbered.length > 1) {
      // a word that is part of the repository's own name ("think" in think-box-ai) is not a clue about which PR a sentence means
      const repoWords = new Set(evidence.flatMap((e) => plainHyphens(e.repo).toLowerCase().split(/[^a-z0-9]+/)).filter(Boolean));
      for (const w of titleWords(text)) {
        if (repoWords.has(w)) continue;
        const owners = numbered.filter((i) => titleWords(i.title).has(w));
        if (owners.length && !owners.some((o) => cited.has(String(o.number)))) { add('citation', w, `"${w}" belongs to #${owners[0]!.number}, which the sentence does not cite (a mixed-up pull request)`); break; }
      }
    }
  } else {
    const names = items.filter((i): i is Extract<LookupItem, { kind: 'branch' }> => i.kind === 'branch').map((b) => b.name.toLowerCase());
    if (names.length && !names.some((n) => lowered.includes(n))) add('citation', '(no listed branch named)', 'the sentence names none of the listed branches');
  }
  const ci = evidence.find((e) => e.recipe === 'ci_status' && e.items.length);
  if (ci) {
    const actual = runClass(ci.verdict);
    const said = claimed.map((c) => c.state).filter((s) => s === 'passed' || s === 'failed' || s === 'running');
    if (actual && !(said as State[]).includes(actual)) add('state', ci.verdict ?? '', `the sentence does not state the newest run's result ("${ci.verdict}")`);
    for (const s of new Set(said)) if (actual && s !== actual) add('state', s, `contradicts the newest run ("${ci.verdict}")`);
  }

  return unsupported.length ? fail('unsupported_claim', unsupported) : { status: 'GROUNDED', classification: 'ok', unsupported: [], checked };
}

export interface PresentedAnswer {
  /** The sentence, only when it passed. Never set for a failed answer. */
  verified: string | null;
  /** What the user is shown: a verified sentence plus the evidence, or GROUNDING FAILED with the claims and the evidence. */
  display: string;
}

/** A failed sentence is never shown as the answer: the user gets the failure, the unsupported claims, and the evidence itself. */
export function presentAnswer(answer: string, evidence: LookupEvidence[], result: GroundingResult): PresentedAnswer {
  const facts = evidence.map(renderFacts).join('\n\n');
  if (result.status === 'GROUNDED') return { verified: String(answer).trim(), display: `${String(answer).trim()}\n\n${facts}` };
  const claims = result.unsupported.map((u) => `- ${u.kind}: ${u.claim} (${u.why})`).join('\n');
  return { verified: null, display: `GROUNDING FAILED (${result.classification}). The model's sentence was not used because these claims are not supported by the evidence:\n${claims}\n\n${facts || 'No evidence was returned.'}` };
}

// ─── Repository findings ────────────────────────────────────────────────────
// A worker that looked at the real repository reports a FINDING: a file, a line, an exact quote and a short claim. The same rule applies as for live
// data: every part of it must trace to what the tools returned in this run (not to the model's memory), and a claim of absence ("no test covers this")
// is only grounded by a recorded search that found nothing.

export interface RepoFinding {
  found: boolean;
  file?: string;
  line?: number;
  quote?: string;
  claim?: string;
  /** For a claim that something does NOT exist: the search the worker ran to show it. Must be in the evidence with zero matches. */
  absence_search?: { query: string; path: string };
  /** When nothing was found: why, in the worker's words. */
  reason?: string;
}

/** A finding from a model's raw arguments, strictly shaped. */
export function parseFinding(raw: unknown): { ok: true; finding: RepoFinding } | { ok: false; error: string } {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return { ok: false, error: 'the finding must be an object' };
  const r = raw as Record<string, unknown>;
  const extra = Object.keys(r).filter((k) => !['found', 'file', 'line', 'quote', 'claim', 'absence_search', 'reason'].includes(k));
  if (extra.length) return { ok: false, error: `unknown field(s): ${extra.join(', ')}` };
  if (typeof r.found !== 'boolean') return { ok: false, error: 'found must be true or false' };
  const text = (v: unknown, max: number): string | undefined => (typeof v === 'string' && v.trim() && v.length <= max ? v : undefined);
  if (!r.found) {
    const reason = text(r.reason, 400);
    return reason ? { ok: true, finding: { found: false, reason } } : { ok: false, error: 'when nothing was found, give a reason (up to 400 characters)' };
  }
  const file = text(r.file, 300); const quote = text(r.quote, 240); const claim = text(r.claim, 400);
  if (!file) return { ok: false, error: 'file is required' };
  if (typeof r.line !== 'number' || !Number.isInteger(r.line) || r.line < 1) return { ok: false, error: 'line must be a whole number of 1 or more' };
  if (!quote) return { ok: false, error: 'quote is required (up to 240 characters, copied exactly from the line)' };
  if (!claim) return { ok: false, error: 'claim is required (up to 400 characters)' };
  let absence: RepoFinding['absence_search'];
  if (r.absence_search !== undefined && r.absence_search !== null) {
    const a = r.absence_search as Record<string, unknown>;
    if (typeof a !== 'object' || typeof a.query !== 'string' || typeof a.path !== 'string') return { ok: false, error: 'absence_search must be {query, path}' };
    absence = { query: a.query, path: a.path };
  }
  return { ok: true, finding: { found: true, file, line: r.line, quote, claim, ...(absence ? { absence_search: absence } : {}) } };
}

const norm = (s: string): string => s.replace(/\s+/g, ' ').trim().toLowerCase();
const ABSENCE_CLAIM = /\b(no|any|without|lacks?|lacking|missing|zero|not|never|isn't|aren't|n't)\b[^.;]{0,40}\b(tests?|tested|coverage|covered|used|called|imported|referenced|callers?|usages?|references?)\b|\b(untested|unused|uncovered|unreferenced|dead code)\b/i;

/** Check a finding against the repo evidence the worker's own tool calls returned. */
export function validateFinding(finding: RepoFinding, evidence: RepoEvidence[], engine?: AbsenceCheck): GroundingResult {
  const checked = { numbers: 0, urls: 0, ids: 0, branches: 0, states: 0, quotes: 0, identifiers: 0, absence: 0 };
  if (!finding.found) return { status: 'GROUNDED', classification: 'ok', unsupported: [], checked };
  const unsupported: UnsupportedClaim[] = [];
  const add = (kind: ClaimKind, claim: string, why: string): void => { unsupported.push({ kind, claim, why }); };
  const file = String(finding.file ?? '').replaceAll('\\', '/').replace(/^\.\//, '');
  const line = Number(finding.line);
  const quote = String(finding.quote ?? '');
  // every line a tool returned, by file
  const seen = new Map<string, Map<number, string>>();
  const note = (p: string, n: number, t: string): void => { if (!seen.has(p)) seen.set(p, new Map()); seen.get(p)!.set(n, t); };
  for (const e of evidence) {
    if (e.tool === 'repo_read') for (const l of e.lines) note(e.path, l.n, l.text);
    else for (const m of e.matches) note(m.path, m.line, m.text);
  }
  const everything = norm([...seen.values()].flatMap((m) => [...m.values()]).join('\n'));
  if (!evidence.length) { add('citation', '(whole finding)', 'no repository tool was used, so nothing in the finding can be verified'); return { status: 'GROUNDING FAILED', classification: 'no_evidence', unsupported, checked }; }

  checked.quotes += 1;
  const lines = seen.get(file);
  if (!lines) add('file', file, 'this file was never returned by a tool in this run');
  else if (!lines.has(line)) add('line', `${file}:${line}`, `line ${line} of this file was not returned by any tool in this run`);
  else {
    // the quote may sit on the cited line or run across the next two
    const window = norm([line, line + 1, line + 2].map((n) => lines.get(n) ?? '').join(' '));
    if (!window.includes(norm(quote))) add('quote', quote.slice(0, 80), `this exact text is not at ${file}:${line} in the tool output`);
  }

  // identifiers the claim puts in backticks must appear in what the tools returned
  for (const m of finding.claim?.matchAll(/`([^`\n]{2,80})`/g) ?? []) {
    checked.identifiers += 1;
    if (!everything.includes(norm(m[1]!))) add('identifier', m[1]!, 'this name does not appear anywhere in the tool output');
  }

  // a claim of absence needs a recorded search that found nothing
  const claimsAbsence = ABSENCE_CLAIM.test(String(finding.claim ?? ''));
  let escalate = false;
  if (engine?.applies) {
    // the engine ran the search itself: its verdict replaces the model's own absence_search
    checked.absence += 1;
    if (!engine.ran) { escalate = true; add('absence', String(finding.claim).slice(0, 80), `the engine could not check this claim: ${engine.reason ?? 'unknown'}`); }
    else if (engine.contradicted.length) {
      const h = engine.contradicted[0]!;
      add('absence', String(finding.claim).slice(0, 80), `the engine searched for ${engine.symbol}${engine.aliases.length ? ` (and ${engine.aliases.join(', ')})` : ''} and found ${engine.contradicted.length} reference(s), e.g. ${h.path}:${h.line}, so the claim is false`);
    }
  } else if (claimsAbsence && !finding.absence_search) add('absence', String(finding.claim).slice(0, 80), 'a claim that something is missing or unused needs an absence_search that was run and found nothing');
  if (finding.absence_search && !engine?.applies) {
    checked.absence += 1;
    const want = { query: norm(finding.absence_search.query), path: finding.absence_search.path.replaceAll('\\', '/').replace(/^\.\//, '').replace(/\/$/, '') };
    const proof = evidence.find((e) => e.tool === 'repo_search' && norm(e.query) === want.query && e.path.replace(/\/$/, '') === want.path);
    if (!proof || proof.tool !== 'repo_search') add('absence', `${finding.absence_search.query} in ${want.path || 'the repository'}`, 'no such search was run in this run');
    else if (proof.matches.length) add('absence', finding.absence_search.query, `the search found ${proof.matches.length} match(es), so it is not absent`);
    else if (proof.truncated) add('absence', finding.absence_search.query, 'the search was cut off, so it does not prove absence');
  }
  return unsupported.length ? { status: 'GROUNDING FAILED', classification: escalate && unsupported.length === 1 ? 'needs_escalation' : 'unsupported_claim', unsupported, checked } : { status: 'GROUNDED', classification: 'ok', unsupported: [], checked };
}
