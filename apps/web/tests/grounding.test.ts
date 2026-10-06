// The one grounding validator: every number, link, id, branch and state claim must trace to the returned tool evidence.
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { presentAnswer, validateGrounding } from '../grounding.ts';
import { normalizeLookup, withTotal, type LookupEvidence, type LookupRecipe } from '../live-lookup.ts';

const REPO = 'Acme/widgets';
const evidenceOf = (recipe: LookupRecipe, body: unknown, branch?: string): LookupEvidence => {
  const r = normalizeLookup({ recipe, repo: REPO, branch }, { status: 200, text: JSON.stringify(body), url: `https://api.github.com/repos/${REPO}/x`, fetched_at: '2026-10-04T12:00:00Z', latency_ms: 5 });
  assert.ok(r.ok);
  return (r as any).evidence;
};
const pr = (number: number, title: string, o: Record<string, unknown> = {}) => ({ number, title, state: 'closed', merged_at: '2026-10-04T10:00:00Z', draft: false, user: { login: 'dev' }, head: { ref: `feat/pr${number}` }, updated_at: '2026-10-04T10:00:00Z', html_url: `https://github.com/Acme/widgets/pull/${number}`, ...o });
const latest = evidenceOf('latest_pr', [pr(361, 'router and recipes'), pr(360, 'dashboard live verify', { merged_at: null, state: 'open', draft: true }), pr(359, 'profiles import', { merged_at: null })]);
const claims = (answer: string, ev: LookupEvidence[]) => validateGrounding(answer, ev).unsupported.map((u) => `${u.kind}:${u.claim}`);

describe('validateGrounding: a sentence that matches the evidence', () => {
  it('passes, and reports how many claims it actually checked', () => {
    const r = validateGrounding('The last PR is #361, router and recipes, and it is merged: https://github.com/Acme/widgets/pull/361', [latest]);
    assert.equal(r.status, 'GROUNDED');
    assert.equal(r.classification, 'ok');
    assert.ok(r.checked.ids >= 1 && r.checked.urls === 1 && r.checked.states >= 1);
  });
  it('accepts the other forms of the same facts', () => {
    for (const a of ['PR 361 (router and recipes) is merged.', 'The newest pull request is #361, merged, on branch feat/pr361.', 'The last PR is #361, which was merged.']) assert.equal(validateGrounding(a, [latest]).status, 'GROUNDED', a);
    assert.equal(validateGrounding('There are 3 recent pull requests, newest is #361.', [latest]).status, 'GROUNDED');
  });
});

describe('validateGrounding: unsupported claims are named', () => {
  it('an invented id, link, number, branch', () => {
    assert.deepEqual(claims('The last PR is #999.', [latest]).filter((c) => c.startsWith('id')), ['id:#999']);
    assert.ok(claims('See https://example.org/pull/361 for #361.', [latest]).includes('url:https://example.org/pull/361'));
    assert.ok(claims('PR #361 changed 47 files.', [latest]).includes('number:47'));
    assert.ok(claims('PR #361 is on branch feat/other.', [latest]).includes('branch:feat/other'));
    assert.ok(claims('PR #361 is on feat/never-existed.', [latest]).includes('branch:feat/never-existed'));
    assert.ok(claims('There are five recent PRs, newest #361.', [latest]).some((c) => c.startsWith('number:five')));
  });
  it('an id of the wrong kind (a run number used as a PR)', () => {
    const ci = evidenceOf('ci_status', { workflow_runs: [{ name: 'CI', head_branch: 'main', event: 'push', status: 'completed', conclusion: 'success', run_number: 812, html_url: 'u', updated_at: 't' }] });
    assert.deepEqual(claims('PR 812 passed.', [ci]).filter((c) => c.startsWith('id')), ['id:pr 812']);
    assert.equal(validateGrounding('The newest run, run 812, passed.', [ci]).status, 'GROUNDED');
  });
  it('a denial is not a claim ("no PR like #304")', () => {
    assert.equal(validateGrounding('There is no PR like #304; the newest is #361, merged.', [latest]).status, 'GROUNDED');
  });
});

describe('validateGrounding: state claims are attributed to the right item', () => {
  it('rejects "merged" for an item that is open, closed without merging, or not listed', () => {
    assert.ok(claims('PR #360 is merged.', [latest]).includes('state:#360 merged'));
    assert.ok(claims('PR #359 was merged.', [latest]).includes('state:#359 merged'));
    assert.equal(validateGrounding('The newest is #361, merged; #359 was closed without being merged.', [latest]).status, 'GROUNDED');
    assert.equal(validateGrounding('The newest is #361, merged; #360 is an open draft.', [latest]).status, 'GROUNDED');
    assert.ok(claims('PR #361 is still open.', [latest]).includes('state:#361 open'));
    assert.ok(claims('The newest is #361, merged; #359 was merged too.', [latest]).includes('state:#359 merged'));
    const merged = evidenceOf('latest_pr', [pr(1, 'only one')]);
    assert.ok(claims('PR #1 is a draft.', [merged]).includes('state:#1 draft'));
  });
  it('checks each clause on its own', () => {
    assert.equal(validateGrounding('#361 is merged, and #360 is an open draft.', [latest]).status, 'GROUNDED');
    assert.ok(claims('#361 is open, and #360 is merged.', [latest]).length >= 2);
  });
  it('a state word with no item to carry it is unsupported ("merged" when nothing merged)', () => {
    const none = evidenceOf('latest_pr', [pr(7, 'wip', { merged_at: null, state: 'open' })]);
    assert.ok(claims('The newest PR was merged: #7.', [none]).some((c) => c.startsWith('state:')));
  });
  it('"open pull requests" in an open-PR list is the list name, not an unsupported claim', () => {
    const open = evidenceOf('open_prs', [pr(5, 'Bump undici', { merged_at: null, state: 'open' })]);
    assert.equal(validateGrounding('There is 1 open pull request: #5 (Bump undici).', [open]).status, 'GROUNDED');
  });
});

describe('validateGrounding: the sentence must name something that was returned', () => {
  it('rejects a vague sentence for a list of PRs, and requires the newest one for "last PR"', () => {
    assert.ok(claims('We are working on a compiler fix.', [latest]).includes('citation:(no listed item named)'));
    assert.ok(claims('The last PR was #359, closed without merging.', [latest]).includes('citation:#361'));
  });
  it('rejects a PR number paired with another PR\'s title (real mix-ups from the small model)', () => {
    const real = evidenceOf('open_prs', [
      pr(37745, 'Bump undici from 6.23.0 to 6.29.0 in /compiler', { merged_at: null, state: 'open' }),
      pr(37744, "[Compiler] Fix use-before-initialization crash in the snap runner's non-watch mode", { merged_at: null, state: 'open' }),
      pr(37743, "[Perf Track] Don't re-diff the same value pair when it is aliased under multiple props", { merged_at: null, state: 'open' }),
      pr(37742, '[DevTools] Resolve MemoComponent wrappers in inspectHooksOfFiber', { merged_at: null, state: 'open' }),
    ]);
    assert.notEqual(validateGrounding("Our pull request, #37742, is related to resolving the use-before-initialization issue in snap runner's non-watch mode", [real]).status, 'GROUNDED');
    assert.notEqual(validateGrounding('We are working on the #37742 [Perf Track] PR from the 6.29.0 branch.', [real]).status, 'GROUNDED');
    for (const ok of ['We are on PR #37742.', 'We are on PR #37744, which fixes a use-before-initialization crash in the snap runner.', 'The open pull requests are #37745 (Bump undici) and #37744 (Fix use-before-initialization crash).', 'We are on PR #37745 and PR #37744.']) assert.equal(validateGrounding(ok, [real]).status, 'GROUNDED', ok);
  });
  it('branches: must name a listed one', () => {
    const b = evidenceOf('branches', [{ name: 'main', protected: true }, { name: 'feat/router' }]);
    assert.equal(validateGrounding('There are two branches: main and feat/router.', [b]).status, 'GROUNDED');
    assert.ok(claims('There are a couple of branches.', [b]).includes('citation:(no listed branch named)'));
    assert.ok(claims('There are 3 branches: main, feat/router and dev.', [b]).includes('number:3'));
  });
});

describe('validateGrounding: the repository name is not a clue about which PR (real Mercury answer, 2026-10-05)', () => {
  const REAL = 'Kudbee-Studio/think-box-ai';
  const ev = (() => {
    const r = normalizeLookup({ recipe: 'latest_pr', repo: REAL }, { status: 200, text: JSON.stringify([pr(367, '#367 P3.28: route live-data lookups to gemma3:4b from the measured table', { html_url: `https://github.com/${REAL}/pull/367` }), pr(365, '#365 P3.24: grounded absence claims + real Think Token A/B (learning benefit UNPROVEN)')]), url: `https://api.github.com/repos/${REAL}/x`, fetched_at: '2026-10-05T12:00:00Z', latency_ms: 5 });
    assert.ok(r.ok); return (r as any).evidence as LookupEvidence;
  })();
  it('the correct answer, with non-breaking hyphens in the repo name, is GROUNDED (it was flagged as a mixed-up pull request because of the word "think")', () => {
    const answer = 'The most recent pull request in the **Kudbee\u2011Studio/think\u2011box\u2011ai** repository is #367, merged: https://github.com/Kudbee-Studio/think-box-ai/pull/367';
    assert.equal(validateGrounding(answer, [ev]).status, 'GROUNDED', JSON.stringify(validateGrounding(answer, [ev]).unsupported));
    assert.equal(validateGrounding('The newest PR in the think box ai repo is #367, merged.', [ev]).status, 'GROUNDED');
  });
  it('a real mix-up is still caught: #367 paired with words only #365 owns', () => {
    assert.notEqual(validateGrounding('The newest PR is #367, merged, about grounded absence claims.', [ev]).status, 'GROUNDED');
  });
});

// Cases from the real-model grounding audit (docs/evidence/p3.30-grounding-audit): correct answers the validator rejected, and wrong ones it let through.
describe('validateGrounding: audit regressions (real Mercury / gemma / qwen answers, 2026-10-05)', () => {
  const R = 'Kudbee-Studio/think-box-ai';
  const mk = (recipe: LookupRecipe, body: unknown, o: { more?: boolean } = {}): LookupEvidence => {
    const r = normalizeLookup({ recipe, repo: R }, { status: 200, text: JSON.stringify(body), url: `https://api.github.com/repos/${R}/x`, fetched_at: 't', latency_ms: 1 });
    assert.ok(r.ok); const e = (r as any).evidence as LookupEvidence; return o.more === undefined ? e : { ...e, more: o.more };
  };
  const prs = mk('latest_pr', [368, 367, 366, 365, 364].map((n) => pr(n, `#${n} P3.${n - 340}: thing ${n}`, { html_url: `https://github.com/${R}/pull/${n}` })));
  const g = (a: string, ev: LookupEvidence[], goal?: string) => validateGrounding(a, ev, { goal });

  it('a question about PR #367 need not name the newest PR (#368); a question about the newest one still must', () => {
    const a = 'PR #367 has been merged: https://github.com/Kudbee-Studio/think-box-ai/pull/367';
    assert.equal(g(a, [prs], 'Is PR 367 merged?').status, 'GROUNDED');
    assert.ok(g(a, [prs], 'What is the last PR?').unsupported.some((u) => /newest/.test(u.why)));
    assert.ok(g(a, [prs]).unsupported.some((u) => /newest/.test(u.why)), 'no goal given: strict, as before');
  });
  it('"no PR is a draft" is a valid answer to a set question, including `"draft": false` printed from the data; a draft that exists still fails it', () => {
    const none = mk('open_prs', []);
    for (const a of ['There are no draft pull requests in this repository.', 'Each PR has `"draft": false`, so there are no draft pull requests.', 'None of the pull requests listed are in draft state.']) assert.equal(g(a, [prs, none], 'Which pull requests are drafts?').status, 'GROUNDED', a);
    const withDraft = mk('latest_pr', [pr(5, 'five', { draft: true, merged_at: null, state: 'open' })]);
    assert.ok(g('There are no draft pull requests.', [withDraft], 'Which pull requests are drafts?').unsupported.some((u) => u.kind === 'state'));
  });
  it('a flat "no open issues / PRs" while the evidence lists some is rejected', () => {
    const issues = mk('open_issues', [{ number: 59, title: 'Frontend polish', state: 'open', user: { login: 'a' }, updated_at: 't' }]);
    assert.ok(g('There are no open issues.', [issues], 'Are there any open issues?').unsupported.some((u) => u.kind === 'state'));
    const openPrs = mk('open_prs', [pr(9, 'nine', { merged_at: null, state: 'open' })]);
    assert.ok(g('There are no open pull requests.', [openPrs], 'Are any pull requests still open?').unsupported.some((u) => u.kind === 'state'));
  });
  it('an English word after "branch" is not a branch name ("branches currently present", "branch failed")', () => {
    const branches = mk('branches', [{ name: 'main', protected: true }, { name: 'feat/a' }]);
    assert.equal(g('Here are the branches currently present: `main` and `feat/a`.', [branches], 'What branches exist?').status, 'GROUNDED');
    const ci = evidenceOf('ci_status', { workflow_runs: [{ name: 'CI', head_branch: 'main', event: 'push', status: 'completed', conclusion: 'failure', run_number: 9, html_url: 'https://github.com/Acme/widgets/actions/runs/9', updated_at: 't' }] }, 'main');
    assert.equal(g('The latest CI run on the main branch failed, run 9.', [ci], 'Did the last CI run pass?').status, 'GROUNDED');
    assert.ok(g('The latest CI run on branch feat/ghost failed, run 9.', [ci]).unsupported.some((u) => u.kind === 'branch'), 'a real-looking branch name is still checked');
  });
  it('a markdown table names issues by their bare number', () => {
    const issues = mk('open_issues', [{ number: 59, title: 'Frontend: 10x the graphics', state: 'open', user: { login: 'a' }, updated_at: 't' }, { number: 21, title: 'Phase 4 Milestone', state: 'open', user: { login: 'b' }, updated_at: 't' }]);
    const a = 'Yes, there are open issues:\n| # | Title |\n|---|---|\n| 59 | Frontend: 10x the graphics |\n| 21 | Phase 4 Milestone |';
    assert.equal(g(a, [issues], 'Are there any open issues?').status, 'GROUNDED');
  });
  it('a table with bold bare numbers cites its issues, and "all three PRs" repeats the count the question asked for', () => {
    const issues = mk('open_issues', [{ number: 59, title: 'Frontend: 10x the graphics', state: 'open', user: { login: 'a' }, updated_at: 't' }, { number: 21, title: 'Phase 4 Milestone', state: 'open', user: { login: 'b' }, updated_at: 't' }]);
    assert.equal(g('Yes, there are open issues:\n| # | Title |\n|---|---|\n| **59** | Frontend: 10x the graphics |\n| **21** | Phase 4 Milestone |', [issues], 'Are there any open issues?').status, 'GROUNDED');
    assert.equal(g('The three most recent PRs are #368, #367 and #366. All three PRs have been merged.', [prs], 'Tell me about the three most recent PRs.').status, 'GROUNDED');
    assert.ok(g('All three PRs have been merged.', [prs], 'What is the last PR?').unsupported.some((u) => u.kind === 'number' || u.kind === 'citation'), 'without that question the count is not licensed');
  });
  it('a trailing full stop is not part of a branch name ("the main branch failed.")', () => {
    const ci = evidenceOf('ci_status', { workflow_runs: [{ name: 'CI', head_branch: 'main', event: 'push', status: 'completed', conclusion: 'failure', run_number: 9, html_url: 'https://github.com/Acme/widgets/actions/runs/9', updated_at: 't' }] }, 'main');
    assert.equal(g('The last CI run for the main branch failed. The newest failure was run 9.', [ci], 'Did the last CI run pass?').status, 'GROUNDED');
  });
  it('JSON literals (false/true/null) are not title words', () => {
    assert.equal(g('PR #367 is merged and its draft flag is false.', [prs], 'Is PR 367 merged?').status, 'GROUNDED');
  });
  it('a count must equal the list (hedged "the 3 most recent" may be fewer), and a list that may hold more is not a total', () => {
    const issues5 = mk('open_issues', [1, 2, 3, 4, 5].map((n) => ({ number: n, title: `issue ${n}`, state: 'open', user: { login: 'a' }, updated_at: 't' })), { more: true });
    assert.ok(g('There are 3 open issues.', [issues5], 'How many issues are open?').unsupported.some((u) => u.kind === 'number'), 'not the list length');
    assert.ok(g('There are 5 open issues.', [issues5], 'How many issues are open?').unsupported.some((u) => /not a total/.test(u.why)), 'the page may hold more');
    assert.equal(g('The first 5 open issues are #1, #2, #3, #4 and #5.', [issues5], 'Which issues are open?').status, 'GROUNDED');
    const exact = mk('open_issues', [1, 2].map((n) => ({ number: n, title: `issue ${n}`, state: 'open', user: { login: 'a' }, updated_at: 't' })), { more: false });
    assert.equal(g('There are 2 open issues: #1 and #2.', [exact], 'How many issues are open?').status, 'GROUNDED');
    assert.equal(g('The 3 most recent PRs are #368, #367 and #366.', [prs], 'Tell me about the three most recent PRs.').status, 'GROUNDED');
  });
  it('"main is not listed" from a full page of branches is not proof it does not exist', () => {
    const page = mk('branches', Array.from({ length: 10 }, (_, i) => ({ name: `b${i}`, protected: false })), { more: true });
    assert.ok(g('The `main` branch is not listed, so it is not protected. There are 10 branches.', [page], 'How many branches are there, and is main protected?').unsupported.length >= 1);
    assert.ok(g('There are ten branches.', [page], 'How many branches are there?').unsupported.some((u) => /not a total/.test(u.why)));
  });
});

describe('validateGrounding: CI verdict', () => {
  const run = (conclusion: string | null, status = 'completed') => evidenceOf('ci_status', { workflow_runs: [{ name: 'CI', head_branch: 'feat/x', event: 'push', status, conclusion, run_number: 9, html_url: 'https://github.com/Acme/widgets/actions/runs/9', updated_at: 't' }] }, 'feat/x');
  it('must state the newest run\'s verdict, and cannot flip it', () => {
    assert.equal(validateGrounding('CI failed on feat/x (run 9).', [run('failure')]).status, 'GROUNDED');
    assert.ok(claims('CI passed on feat/x.', [run('failure')]).some((c) => c.startsWith('state:passed')));
    assert.ok(claims('There was a CI run on feat/x, run 9.', [run('failure')]).some((c) => c.startsWith('state:failure')));
    assert.equal(validateGrounding('It is still running (run 9).', [run(null, 'in_progress')]).status, 'GROUNDED');
  });
});

describe('validateGrounding: no evidence, empty, error and oversized answers', () => {
  it('nothing can be verified without evidence', () => {
    const r = validateGrounding('The last PR is #361.', []);
    assert.equal(r.status, 'GROUNDING FAILED');
    assert.equal(r.classification, 'no_evidence');
  });
  it('empty, error-looking and huge answers fail with their own class', () => {
    assert.equal(validateGrounding('   ', [latest]).classification, 'empty_answer');
    assert.equal(validateGrounding('[Error: connection refused]', [latest]).classification, 'unreadable_answer');
    assert.equal(validateGrounding('word '.repeat(400), [latest]).classification, 'unreadable_answer');
  });
});

describe('presentAnswer: a failed sentence is never shown as verified', () => {
  it('shows the sentence plus evidence when grounded', () => {
    const a = 'The last PR is #361, merged.';
    const p = presentAnswer(a, [latest], validateGrounding(a, [latest]));
    assert.equal(p.verified, a);
    assert.match(p.display, /^The last PR is #361, merged\.\n\nMost recent pull requests in Acme\/widgets/);
  });
  it('shows GROUNDING FAILED, the unsupported claims and the evidence, and drops the sentence', () => {
    const a = 'The last PR is #999, merged.';
    const p = presentAnswer(a, [latest], validateGrounding(a, [latest]));
    assert.equal(p.verified, null);
    assert.match(p.display, /^GROUNDING FAILED \(unsupported_claim\)/);
    assert.match(p.display, /id: #999/);
    assert.doesNotMatch(p.display, /The last PR is #999/);
    assert.match(p.display, /- #361 "router and recipes" \(merged\)/);
  });
});

describe('validateGrounding: no false alarms on a correct answer (found by the real-browser run with real Mercury)', () => {
  const real = evidenceOf('latest_pr', [
    pr(361, 'Model integration: live_lookup, local tool calling, grounding, convoys, Mayor, queued approvals', { head: { ref: 'feat/live-data-recipes' } }),
    pr(360, '#360 P3.21: dashboard live-verify + flake fix', { head: { ref: 'feat/pr360-p3.21-dashboard-live' } }),
  ]);
  // The exact answer real Mercury gave: correct, but it quotes a title containing "queued" and says "creation/update".
  const mercury = 'The most recent pull request in the **Kudbee‑Studio/think‑box‑ai** repository is:\n\n- **PR #361** – “Model integration: live_lookup, local tool calling, grounding, convoys, Mayor, queued approvals”  \n- **State:** merged  \n- **Author:** dev  \n- **Updated at:** 2026‑10‑04 10:00:00 UTC  \n- **URL:** https://github.com/Acme/widgets/pull/361  \n\nThis is the latest PR (newest by creation/update time).';
  it('a verbatim title with a state word in it ("queued approvals") is not a state claim', () => {
    assert.deepEqual(claims(mercury, [real]), []);
    assert.equal(validateGrounding(mercury, [real]).status, 'GROUNDED');
  });
  it('"and/or" and "creation/update" are not branch names, but an invented branch-looking name still fails', () => {
    assert.equal(validateGrounding('The newest PR is #361, merged, by creation/update time and/or title.', [real]).status, 'GROUNDED');
    assert.ok(claims('The newest PR is #361, merged, on feat/never-existed.', [real]).includes('branch:feat/never-existed'));
    assert.ok(claims('The newest PR is #361, merged, on branch made-up.', [real]).includes('branch:made-up'));
  });
  it('a state word outside the title is still checked, and naming a PR only by its title still counts as naming it', () => {
    assert.ok(claims('PR #361 is still queued for review.', [real]).includes('state:#361 running'));
    assert.equal(validateGrounding('The newest is "Model integration: live_lookup, local tool calling, grounding, convoys, Mayor, queued approvals" (#361), merged.', [real]).status, 'GROUNDED');
    assert.ok(claims('The newest is "#999 some invented title", merged.', [real]).includes('id:#999'), 'a fake id inside quotes is still an invented id');
  });
  it('title masking does not hide a wrong state attached to a quoted title', () => {
    assert.ok(claims('PR #360 "#360 P3.21: dashboard live-verify + flake fix" is open.', [real]).includes('state:#360 open'));
  });
});

describe('validateGrounding: list-style answers (second real Mercury answer from the browser run)', () => {
  const ev = evidenceOf('latest_pr', [
    pr(361, 'Model integration: live_lookup, local tool calling, grounding, convoys, Mayor, queued approvals'),
    pr(360, 'dashboard live verify', { merged_at: null, state: 'open', draft: true }),
  ]);
  const mercury2 = 'The most recent pull request in the **Kudbee‑Studio/think‑box‑ai** repository is:\n\n- **PR #361** – *Model integration: live_lookup, local tool calling, grounding, convoys, Mayor, queued approvals*  \n- **State:** Merged  \n- **Author:** dev  \n- **Updated:** 2026‑10‑04 10:00:00 UTC  \n- **URL:** https://github.com/Acme/widgets/pull/361\n\nThis is the latest PR across all states (open, closed, or merged).';
  it('a generic "(open, closed, or merged)" is not a claim about #361, and the State line is attributed to the PR above it', () => {
    assert.deepEqual(claims(mercury2, [ev]), []);
  });
  it('a State line is checked against the PR named above it: "Merged" under an open draft fails', () => {
    const wrong = '- **PR #360** – dashboard live verify\n- **State:** Merged\n- The newest is #361, merged.';
    assert.ok(claims(wrong, [ev]).includes('state:#360 merged'));
    assert.equal(validateGrounding('- **PR #361** – x\n- **State:** Merged', [ev]).status, 'GROUNDED');
  });
  it('only a parenthetical list is skipped: "#360 was merged and closed" is still checked', () => {
    assert.ok(claims('The newest is #361, merged; #360 was merged and closed.', [ev]).includes('state:#360 merged'));
  });
});

describe('validateGrounding: an exact total from GitHub makes a count answerable (P3.37)', () => {
  const issue = (n: number) => ({ number: n, title: `bug ${n}`, state: 'open', user: { login: 'a' }, html_url: `https://github.com/Acme/widgets/issues/${n}`, updated_at: '2026-10-04T10:00:00Z' });
  const issues10 = evidenceOf('open_issues', Array.from({ length: 10 }, (_, i) => issue(i + 1)));
  const withTen = withTotal(issues10, 10, 'https://api.github.com/search/issues?x');
  const status = (a: string, ev: LookupEvidence) => validateGrounding(a, [ev], { goal: 'How many issues are open?' });
  it('the real total is accepted; the first page\'s length is not, and nothing changes without a total', () => {
    assert.equal(status('There are 10 open issues.', withTen).status, 'GROUNDED');
    assert.equal(status('Ten open issues are open right now.', withTen).status, 'GROUNDED');
    const five = status('There are 5 open issues.', withTen);
    assert.equal(five.status, 'GROUNDING FAILED');
    assert.match(five.unsupported.map((u) => u.why).join(), /shows only the first 5, and GitHub's total is 10/);
    assert.equal(status('There are 5 open issues.', issues10).status, 'GROUNDING FAILED', 'without a total a count from a full page is still refused');
    assert.equal(status('There are 10 open issues.', issues10).status, 'GROUNDING FAILED');
  });
  it('a hedged count of what is shown still passes, and a total larger than the page can be stated while only some are named', () => {
    const big = withTotal(issues10, 42, 'u');
    assert.equal(status('There are 42 open issues; the newest shown is #1.', big).status, 'GROUNDED');
    assert.equal(status('Here are the 3 most recent open issues: #1, #2, #3.', big).status, 'GROUNDED');
    assert.equal(status('There are 41 open issues.', big).status, 'GROUNDING FAILED');
  });
  it('"no open issues" is a contradiction when the total says there are some, even if the first page held none of them', () => {
    const onlyPrsOnPage = withTotal(evidenceOf('open_issues', [{ number: 9, title: 'a pr', pull_request: {} }]), 4, 'u');
    assert.equal(onlyPrsOnPage.items.length, 0);
    const r = status('There are no open issues.', onlyPrsOnPage);
    assert.equal(r.status, 'GROUNDING FAILED');
    assert.ok(r.unsupported.some((u) => /no open issues/.test(u.claim)));
    assert.equal(status('There are 4 open issues.', onlyPrsOnPage).status, 'GROUNDED');
    assert.equal(status('There are no open issues.', withTotal(evidenceOf('open_issues', []), 0, 'u')).status, 'GROUNDED');
  });
  it('open pull requests work the same way', () => {
    const prs = withTotal(evidenceOf('open_prs', [pr(361, 'a', { merged_at: null, state: 'open' }), pr(360, 'b', { merged_at: null, state: 'open' })]), 9, 'u');
    assert.equal(validateGrounding('There are 9 open pull requests; the newest is #361.', [prs]).status, 'GROUNDED');
    assert.equal(validateGrounding('There are 2 open pull requests.', [prs]).status, 'GROUNDING FAILED');
  });
});

