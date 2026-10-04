// One grounding validator for live-data answers (Layer 1, foundation: pure, no I/O, no model).
// Whatever model wrote the sentence (Mercury, Qwen, Gemma, a recipe), every checkable claim in it must be traceable to the tool evidence that came back:
// numbers, links, PR / issue / run ids, branch names and state claims (merged, open, closed, draft, passed, failed, running). A sentence with an
// unsupported claim is marked GROUNDING FAILED, the claims are named, and it is never shown as verified (presentAnswer shows the evidence instead).
// This is a claim check against evidence, not a view into the model's reasoning: nothing here reads or displays chain of thought.

import { renderFacts, type LookupEvidence, type LookupItem } from './live-lookup.ts';

export type ClaimKind = 'number' | 'url' | 'id' | 'branch' | 'state' | 'citation';
export interface UnsupportedClaim { kind: ClaimKind; claim: string; why: string }

export interface GroundingResult {
  status: 'GROUNDED' | 'GROUNDING FAILED';
  /** ok | unsupported_claim | no_evidence | empty_answer | unreadable_answer */
  classification: 'ok' | 'unsupported_claim' | 'no_evidence' | 'empty_answer' | 'unreadable_answer';
  unsupported: UnsupportedClaim[];
  /** How many claims of each kind were found and checked (a count of what was verified, so "GROUNDED" is not an empty claim). */
  checked: { numbers: number; urls: number; ids: number; branches: number; states: number };
}

const MAX_ANSWER_CHARS = 700;
const URL_RE = /https?:\/\/[^\s)"'<>]+/g;
const NEGATION = /\b(no|not|never|none|without|isn't|wasn't|aren't|weren't|hasn't|haven't|didn't|doesn't|cannot|can't|neither|nor)\b|n't\b|\bun$/i;
const STOP = new Set(['the', 'is', 'of', 'was', 'for', 'in', 'on', 'and', 'has', 'that', 'which', 'with', 'are', 'a', 'an', 'name', 'names', 'list', 'lists', 'to', 'it', 'its', 'this', 'there', 'as', 'at', 'by', 'from', 'be', 'or']);
const COMMON = new Set(['about', 'after', 'being', 'could', 'first', 'their', 'there', 'these', 'those', 'which', 'would', 'where', 'while', 'with', 'pull', 'request', 'requests', 'based', 'open', 'data', 'live', 'github', 'working', 'currently', 'listed', 'number', 'newest', 'latest', 'merged', 'closed', 'branch']);
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
const titleWords = (text: string): Set<string> => new Set((text.toLowerCase().match(/[a-z][a-z0-9-]{4,}/g) ?? []).filter((w) => !COMMON.has(w)));
const mask = (text: string, start: number, len: number): string => text.slice(0, start) + ' '.repeat(len) + text.slice(start + len);

/**
 * Check `answer` against the evidence it claims to come from. `GROUNDED` means every number, link, id, branch name and state claim in the sentence
 * was found in (and, for states, attributed correctly to) the returned evidence, and that the sentence names something that was actually returned.
 */
export function validateGrounding(answer: string, evidence: LookupEvidence[]): GroundingResult {
  const checked = { numbers: 0, urls: 0, ids: 0, branches: 0, states: 0 };
  const fail = (classification: GroundingResult['classification'], unsupported: UnsupportedClaim[]): GroundingResult => ({ status: 'GROUNDING FAILED', classification, unsupported, checked });
  const text = String(answer ?? '').replace(/```[\s\S]*?```/g, ' ').replace(/\s+/g, ' ').trim();
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
  for (const m of [...rest.matchAll(/\bbranch(?:es)?\s+(?:named\s+|called\s+)?[`'"]?([\w][\w./-]*)/gi)]) { claimBranch(m[1]!); rest = mask(rest, m.index!, m[0].length); }
  for (const m of [...rest.matchAll(/(?<![\w/:.-])[\w.-]+(?:\/[\w.-]+)+/g)]) { claimBranch(m[0]); rest = mask(rest, m.index!, m[0].length); }

  // 4. counts in words ("two open PRs") and plain numbers
  const knownNumbers = new Set(facts.match(/\d+(?:\.\d+)*/g) ?? []);
  for (const e of evidence) knownNumbers.add(String(e.items.length));
  for (const m of [...rest.matchAll(/\b(one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:open\s+|recent\s+|latest\s+)?(prs?|pull requests?|issues?|branches|runs?|workflow runs?)\b/gi)]) {
    checked.numbers += 1;
    const n = WORD_NUMBER[m[1]!.toLowerCase()]!;
    if (!knownNumbers.has(n)) add('number', `${m[1]!.toLowerCase()} ${m[2]!.toLowerCase()}`, `${n} is not a count or value in the tool evidence`);
  }
  for (const m of [...rest.matchAll(/\d+(?:\.\d+)*/g)]) {
    checked.numbers += 1;
    if (!knownNumbers.has(m[0])) add('number', m[0], 'this number is not in the tool evidence');
  }

  // 5. state claims, attributed per clause: a clause naming exactly one item must state that item's state
  const claimed: Array<{ state: State; clause: string }> = [];
  const clauses = text.split(/(?<=[.!?;])\s+|,\s+(?:and|but|while)\s+|\s+(?:and|but|while)\s+/i);
  const clauseIds = (clause: string): string[] => [...clause.matchAll(/(?:(?:pull requests?|prs?|issues?|runs?)\s+#?|#)(\d{1,7})\b/gi)].map((m) => m[1]!).filter((n) => anyId.has(n));
  for (const clause of clauses) {
    for (const { state, re } of STATE_WORDS) {
      for (const m of [...clause.matchAll(re)]) {
        if (NEGATION.test(clause.slice(Math.max(0, m.index! - 25), m.index!)) || /\b(not|un)\s*$/i.test(clause.slice(0, m.index!))) continue;
        // "open pull requests" is a noun phrase naming the list, not a claim about one item
        if (state === 'open' && /^\s*(pull|prs?|issues?)\b/i.test(clause.slice(m.index! + m[0].length))) { if (!recipes.has('open_prs') && !recipes.has('open_issues') && !items.some((i) => itemSupports(i, 'open', ''))) { checked.states += 1; add('state', 'open', 'no open item is in the tool evidence'); } continue; }
        claimed.push({ state, clause });
      }
    }
  }
  for (const { state, clause } of claimed) {
    checked.states += 1;
    const named = clauseIds(clause);
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
    if (!citedListed.length) add('citation', '(no listed item named)', 'the sentence names none of the listed pull requests or issues');
    const first = evidence.find((e) => e.recipe === 'latest_pr')?.items[0];
    if (first && first.kind === 'pr' && !cited.has(String(first.number))) add('citation', `#${first.number}`, `the sentence does not name the newest pull request (#${first.number})`);
    // A small model often pairs one PR's number with another PR's title: a distinctive word that belongs only to PRs the sentence does not cite is that mix-up.
    if (numbered.length > 1) {
      for (const w of titleWords(text)) {
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
