// What an agent may SAY about a `run_checks` report (Layer 4: pure). Same rule as the grounding validator for lookups, applied to check results: a claim that
// everything passes, that the change is verified or safe to merge, that a named check passes, or how many tests passed must be supported by the LATEST report,
// and a patch that edits tests or gates must be said to. Stating that something failed is never flagged (it is the cautious direction). Deterministic: no model.
import type { ScratchReport } from './scratch-runner.ts';

export interface ClaimResult { ok: boolean; problems: string[] }

const NEGATION = /\b(no|not|never|without|neither|nor|cannot|can't)\b|n't\b/i;
const PASS = '(?:pass(?:es|ed|ing)?|succeed(?:s|ed)?|green|clean|ok)';
const NAMED: Array<[RegExp, string, string[]]> = [
  [/\blint(?:ing)?\b/i, 'lint', ['lint']],
  [/\btype ?check(?:ing|s)?\b/i, 'typecheck', ['typecheck']],
  [/\btsc\b/i, 'tsc', ['tsc']],
  [/\b(?:unit )?tests?(?: suite)?\b/i, 'tests', ['test', 'test_file']],
];

const clauseBefore = (text: string, index: number): string => text.slice(0, index).split(/[.;:!?\n]/).pop() ?? '';

/** The latest report, in one line a person can check. */
export function describeReport(r: ScratchReport | undefined): string {
  if (!r) return 'no check was run';
  const checks = r.checks.map((c) => `${c.check}${c.file ? ` ${c.file}` : ''} ${c.timed_out ? 'TIMED OUT' : c.passed ? 'passed' : `FAILED (exit ${c.exit_code})`}${c.tests ? ` (${c.tests.pass} passed, ${c.tests.fail} failed)` : ''}`).join('; ');
  return `commit ${r.sha.slice(0, 8)}${r.patch_sha256 ? ` with patch ${r.patch_sha256.slice(0, 8)}` : ''}: ${checks}; verified: ${r.verified ? 'yes' : 'NO'}${r.flags.length ? `; flags: ${r.flags.join(', ')}` : ''}`;
}

/** Judges an answer against every report this run produced (the latest one decides what is true now). Pure. */
export function validateCheckClaims(answer: string, reports: ScratchReport[]): ClaimResult {
  const text = String(answer ?? '').replace(/\s+/g, ' ').trim();
  const latest = reports.at(-1);
  const problems: string[] = [];
  const add = (p: string): void => { if (!problems.includes(p)) problems.push(p); };
  // negation before the claim ("no tests passed") or inside it ("tests did not pass")
  const negated = (index: number, span = ''): boolean => NEGATION.test(clauseBefore(text, index).slice(-35)) || NEGATION.test(span);

  // 1. "everything passes", "verified", "safe to merge": needs a verified report
  const overall: RegExp[] = [
    new RegExp(`\\b(?:all(?: of)?(?: the)?(?: \\w+){0,2} checks?|everything|all of them|all green)\\b[^.\\n]{0,25}\\b${PASS}\\b`, 'gi'),
    /(?<![\w-])(?<!un)verified\b(?!\W*(?:(?:flag|field|value|status)\W*(?:is|=|:)?|(?:is|=|:))\W*(?:false|no)\b)/gi,
    /\b(?:safe|ready) to merge\b/gi,
  ];
  let claimsOverall = false;
  // the word "verified" in backticks or quotes ("the `verified` flag is false") names a field; it is a claim only if it is then said to be true
  const quotedMention = (index: number, span: string): boolean => /^verified\b/i.test(span) && /[`"'‘“]$/.test(text.slice(0, index)) && /^[`"'’”]/.test(text.slice(index + span.length));
  const saidTrue = (index: number, span: string): boolean => /^[`"'’”]?\s*(?:flag|field|value|status)?\s*(?:is|=|:)\s*\**\s*(?:true|yes|✅)/i.test(text.slice(index + span.length, index + span.length + 30));
  for (const re of overall) for (const m of text.matchAll(re)) { if (quotedMention(m.index!, m[0]) && !saidTrue(m.index!, m[0])) continue; if (!negated(m.index!, m[0])) { claimsOverall = true; if (!latest?.verified) add(`it says the change is verified or everything passes, but ${latest ? 'the latest report is not verified' : 'no check was run'}`); } }

  // 2. a named check passes
  const passMentions = [...text.matchAll(new RegExp(`\\b(lint(?:ing)?|type ?check(?:ing|s)?|tsc|(?:unit )?tests?(?: suite)?)\\b[^.\\n]{0,25}?\\b${PASS}\\b`, 'gi'))];
  for (const m of passMentions) {
    // a number right before the word makes it a count (judged in step 3), not a claim that the whole check passes
    if (negated(m.index!, m[0]) || /\b\d[\d,]*\s+(?:\w+\s+)?$/.test(text.slice(0, m.index!)) || /\b(?:if|when|once|until|should|must|to)\b/i.test(clauseBefore(text, m.index!).slice(-25))) continue;
    const [, label, names] = NAMED.find(([re]) => re.test(m[1]!)) ?? [];
    const ran = latest?.checks.filter((c) => (names as string[] | undefined)?.includes(c.check)) ?? [];
    if (!label) continue;
    if (!ran.length) add(`it says ${m[1]!.toLowerCase()} passes, but that check was not run`);
    else if (ran.some((c) => !c.passed)) add(`it says ${m[1]!.toLowerCase()} passes, but the report says it ${ran.find((c) => !c.passed)!.timed_out ? 'timed out' : 'failed'}`);
  }

  // 3. how many tests passed
  const counts = latest?.checks.flatMap((c) => (c.tests ? [c.tests] : [])) ?? [];
  for (const m of text.matchAll(/\b(\d{1,6})\s+(?:\w+\s+)?tests?\s+(?:\w+\s+)?(pass(?:ed|ing)?|fail(?:ed|ing)?)\b|\b(\d{1,6})\s+(?:passing|failing)\b/gi)) {
    const n = Number(m[1] ?? m[3]); const kind = /pass/i.test(m[0]) ? 'pass' : 'fail';
    if (negated(m.index!, m[0])) continue;
    if (!counts.some((c) => c[kind] === n)) add(`it says ${n} tests ${kind === 'pass' ? 'passed' : 'failed'}, but the report ${counts.length ? `counts ${counts.map((c) => c[kind]).join(' / ')}` : 'has no test count'}`);
  }

  // 4. a patch that edits the tests or the gates that judge it must be said to, whenever the answer vouches for the change
  if (claimsOverall && latest?.verified) {
    const edits = '(?:touch|edit|chang|modif|updat|add|delet|remov|rewrit)\\w*';
    if (latest.flags.includes('touches_tests') && !new RegExp(`\\b${edits}\\b[^.]{0,50}\\btests?\\b|\\btests?\\b[^.]{0,50}\\b${edits}\\b|touches_tests`, 'i').test(text)) add('it vouches for a patch that edits tests without saying so (flag touches_tests)');
    if (latest.flags.includes('touches_ci_or_gates') && !new RegExp(`\\b${edits}\\b[^.]{0,60}\\b(?:gates?|ci\\b|workflows?|package\\.json|tsconfig|config\\w*)\\b|\\b(?:gates?|ci\\b|workflows?|package\\.json|tsconfig|config\\w*)\\b[^.]{0,60}\\b${edits}\\b|touches_ci_or_gates`, 'i').test(text)) add('it vouches for a patch that edits CI, gates or configuration without saying so (flag touches_ci_or_gates)');
  }
  return { ok: problems.length === 0, problems };
}

/** What replaces an answer that claimed more than the report shows. */
export function flaggedAnswer(problems: string[], latest: ScratchReport | undefined): string {
  return `FLAGGED: my answer claimed more than the check report supports (${problems.join('; ')}). What the report says: ${describeReport(latest)}`;
}
