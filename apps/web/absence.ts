// The engine runs the absence search itself. A model that says "this has no test" or "this is unused" no longer has to remember to run the search
// first and quote it back: the claim is checked here against a real, bounded search of the repository, and the searches are attached to the
// run's evidence. A match means the claim is false; no match (and a search that was not cut off) means it is grounded; a claim the engine cannot
// check (no symbol to search for, or the search was truncated) is not guessed at: it is flagged for a stronger lane.
import { repoRoot, repoSearch, type RepoEvidence } from './repo-tools.ts';

type SearchEvidence = Extract<RepoEvidence, { tool: 'repo_search' }>;
import type { RepoFinding } from './grounding.ts';

export type AbsenceKind = 'test' | 'usage';
export interface Hit { path: string; line: number; text: string }
export interface AbsenceCheck {
  /** false: the finding does not claim anything is missing, so there is nothing to check. */
  applies: boolean;
  /** true: the engine searched and reached a verdict (contradicted or not). */
  ran: boolean;
  kinds: AbsenceKind[];
  symbol?: string;
  aliases: string[];
  /** References that make the claim false (empty when the claim holds). */
  contradicted: Hit[];
  /** The searches the engine ran; they are appended to the run's evidence. */
  searches: SearchEvidence[];
  /** Which path ran: 'engine_search' (verdict reached), 'escalate' (could not check, needs a stronger lane) or 'not_applicable'. */
  path: 'engine_search' | 'escalate' | 'not_applicable';
  reason?: string;
}

const TEST_CLAIM = /\b(tests?|tested|untested|coverage|covered|uncovered|spec)\b/i;
const USAGE_CLAIM = /\b(used|unused|called|never called|imported|referenced|unreferenced|callers?|usages?|references?|dead code)\b/i;
const NEGATION = /\b(no|any|without|lacks?|lacking|missing|zero|not|never|none|nothing|isn't|aren't|n't|untested|unused|uncovered|unreferenced|dead code)\b/i;
const UNIVERSAL = /\b(never|none|nothing|all|every|always)\b/i;

/** Does this claim say something does not exist, is not covered or is not used? */
export function claimKinds(claim: string): AbsenceKind[] {
  if (!NEGATION.test(claim)) return [];
  const kinds: AbsenceKind[] = [];
  if (TEST_CLAIM.test(claim)) kinds.push('test');
  if (USAGE_CLAIM.test(claim)) kinds.push('usage');
  return kinds;
}

const escapeRe = (t: string): string => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const IDENT = /^[A-Za-z_$][\w$]{1,79}$/;
/** The symbol a claim is about: a `backticked` name, a name() in the claim, or the name declared on the quoted line. Pure. */
export function extractSymbol(finding: Pick<RepoFinding, 'claim' | 'quote'>): string | null {
  const claim = finding.claim ?? ''; const quote = finding.quote ?? '';
  for (const m of claim.matchAll(/`([^`\n]+)`/g)) { const t = m[1]!.replace(/\(\)$/, ''); if (IDENT.test(t)) return t; }
  const call = claim.match(/\b([A-Za-z_$][\w$]{1,79})\(\)/); if (call) return call[1]!;
  const decl = quote.match(/\b(?:function\*?|class|const|let|var|interface|type|enum|def)\s+([A-Za-z_$][\w$]*)/); if (decl && IDENT.test(decl[1]!)) return decl[1]!;
  return null;
}

/** A test file by location or name. */
export const isTestPath = (p: string): boolean => /(^|\/)(tests?|__tests__|spec|specs)\//i.test(p) || /\.(test|spec)\.[cm]?[jt]sx?$|_test\.py$|(^|\/)test_[^/]+\.py$/i.test(p);

/** Names the symbol is re-bound to: `X as Y`, `const Y = X`. One level; the aliases are searched too. */
export function aliasesIn(symbol: string, hits: Hit[]): string[] {
  const out = new Set<string>(); const s = escapeRe(symbol);
  for (const h of hits) {
    for (const m of h.text.matchAll(new RegExp(`\\b${s}\\s+as\\s+([A-Za-z_$][\\w$]*)`, 'g'))) out.add(m[1]!);
    const bind = h.text.match(new RegExp(`\\b(?:const|let|var)\\s+([A-Za-z_$][\\w$]*)\\s*=\\s*${s}\\s*;?\\s*$`)); if (bind) out.add(bind[1]!);
  }
  out.delete(symbol); out.delete('default');
  return [...out].filter((a) => IDENT.test(a)).slice(0, 5);
}

const wordHit = (symbol: string, text: string): boolean => new RegExp(`(^|[^\\w$])${escapeRe(symbol)}([^\\w$]|$)`).test(text);

const search = async (query: string, root: string): Promise<SearchEvidence> => (await repoSearch({ query, path: '' }, root)) as SearchEvidence;

/** Check an absence claim against the repository. Never throws: a search that fails is "could not check", not "absent". */
export async function runAbsenceCheck(finding: RepoFinding, root: string = repoRoot()): Promise<AbsenceCheck> {
  const none: AbsenceCheck = { applies: false, ran: false, kinds: [], aliases: [], contradicted: [], searches: [], path: 'not_applicable' };
  if (!finding.found) return none;
  const claim = String(finding.claim ?? '');
  const kinds = claimKinds(claim);
  if (!kinds.length) return none;
  const base: AbsenceCheck = { ...none, applies: true, kinds };
  const symbol = extractSymbol(finding);
  if (!symbol) return { ...base, path: 'escalate', reason: UNIVERSAL.test(claim) ? 'a claim about everything or nothing has no single symbol the engine can search for' : 'no symbol could be identified to search for' };
  const searches: SearchEvidence[] = [];
  try {
    const whole = await search(symbol, root);
    searches.push(whole);
    if (whole.truncated) return { ...base, symbol, searches, path: 'escalate', reason: 'the repository search was cut off, so it cannot prove absence' };
    const isDef = (h: Hit): boolean => h.path === finding.file && h.line === finding.line;
    const hits: Hit[] = whole.matches.filter((m) => !isDef(m) && wordHit(symbol, m.text));
    const aliases = aliasesIn(symbol, hits);
    for (const a of aliases) {
      const r = await search(a, root);
      searches.push(r);
      if (r.truncated) return { ...base, symbol, aliases, searches, path: 'escalate', reason: `the search for the alias ${a} was cut off` };
      hits.push(...r.matches.filter((m) => wordHit(a, m.text)));
    }
    const wanted = new Set<string>();
    const contradicted = hits.filter((h) => { const fresh = !wanted.has(`${h.path}:${h.line}`); wanted.add(`${h.path}:${h.line}`); return fresh && (kinds.includes('usage') || (kinds.includes('test') && isTestPath(h.path))); });
    return { ...base, ran: true, symbol, aliases, contradicted, searches, path: 'engine_search' };
  } catch (err) {
    return { ...base, symbol, searches, path: 'escalate', reason: `the search failed: ${err instanceof Error ? err.message : String(err)}` };
  }
}
