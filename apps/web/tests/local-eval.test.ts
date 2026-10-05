// The local-model eval harness: the fixture, the checks and the scoring must tell a right answer from a wrong, ungrounded or failed one.
// A scripted "good" model and a scripted "bad" model run the real loops against the fixture world; no real model is called.
import { after, before, describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { newRunContext } from '../agent.ts';
import { EVAL_TASKS, renderTable, scoreTrial, sufficient, summarize, type Trial } from '../local-eval.ts';
import { lookupSpec, repoSpec, runLocalToolLoop, type LocalChat } from '../local-tools.ts';
import type { OllamaChatTurn } from '../ollama-client.ts';
import { EVAL_REPO, startEvalWorld, type EvalWorld } from './helpers/local-eval-fixture.ts';
import { lookupHooks } from './helpers/lookup-hooks.ts';

const turn = (o: Partial<OllamaChatTurn>): OllamaChatTurn => ({ content: '', tool_calls: [], prompt_tokens: 10, completion_tokens: 5, latency_ms: 4, ...o });
const nativeCall = (name: string, args: unknown) => turn({ tool_calls: [{ function: { name, arguments: args } }] });
const scripted = (turns: OllamaChatTurn[]): LocalChat => ({ modelCapabilities: async () => ['tools'], chatOnce: async () => turns.shift() ?? turn({ error: 'script exhausted' }) });

let world: EvalWorld; let prevApi: string | undefined; let prevRoot: string | undefined; let prevRepo: string | undefined;
before(async () => { world = await startEvalWorld(); prevApi = process.env.KUDBEE_GITHUB_API; prevRoot = process.env.KUDBEE_REPO_ROOT; prevRepo = process.env.KUDBEE_REPO; process.env.KUDBEE_REPO = EVAL_REPO; process.env.KUDBEE_GITHUB_API = world.github.url; process.env.KUDBEE_REPO_ROOT = world.root; });
after(async () => { if (prevApi === undefined) delete process.env.KUDBEE_GITHUB_API; else process.env.KUDBEE_GITHUB_API = prevApi; if (prevRoot === undefined) delete process.env.KUDBEE_REPO_ROOT; else process.env.KUDBEE_REPO_ROOT = prevRoot; if (prevRepo === undefined) delete process.env.KUDBEE_REPO; else process.env.KUDBEE_REPO = prevRepo; await world.close(); });

const run = async (id: string, chat: LocalChat) => {
  const task = EVAL_TASKS.find((t) => t.id === id)!;
  const h = lookupHooks(task.class === 'repo' ? { allowedTools: ['repo_search', 'repo_read'] } : {});
  const result = task.class === 'repo'
    ? await runLocalToolLoop({ model: 'scripted', goal: task.goal, hooks: h.hooks, context: newRunContext(), chat, repo: null, spec: repoSpec() })
    : await runLocalToolLoop({ model: 'scripted', goal: task.goal, hooks: h.hooks, context: newRunContext(), chat, repo: EVAL_REPO, spec: lookupSpec(EVAL_REPO) });
  return scoreTrial(task, result);
};

describe('local eval harness', () => {
  it('a lookup answer that is right and grounded passes; a grounded answer about the wrong thing is "wrong"; an invented number is "ungrounded"', async () => {
    const call = () => nativeCall('live_lookup', { recipe: 'latest_pr' });
    { const p = await run('last-pr', scripted([call(), turn({ content: 'The newest PR is #363 and it is open.' })])); assert.equal(p.outcome, 'pass', p.why); }
    const wrong = await run('last-pr', scripted([call(), turn({ content: 'The newest PR is #363.' })]));
    assert.equal(wrong.outcome, 'wrong', wrong.why); assert.match(wrong.why, /open/);
    assert.equal((await run('last-pr', scripted([call(), turn({ content: 'The newest PR is #362 and it is closed.' })]))).outcome, 'ungrounded', 'naming a PR the tool never returned as the newest is caught by grounding');
    assert.equal((await run('last-pr', scripted([call(), turn({ content: 'The newest PR is #999 and it is open.' })]))).outcome, 'ungrounded');
  });
  it('a model that never calls the tool is "failed", not a pass', async () => {
    const t = await run('last-pr', scripted([turn({ content: 'It was #363, I think.' }), turn({ content: 'Probably #363.' }), turn({ content: 'Yes #363.' }), turn({ content: '#363' }), turn({ content: '#363' })]));
    assert.equal(t.outcome, 'failed'); assert.ok(t.failure);
  });
  it('CI and issues checks read the fixture facts (failed run, no issues)', async () => {
    assert.equal((await run('ci', scripted([nativeCall('live_lookup', { recipe: 'ci_status' }), turn({ content: 'The last CI run (#812) failed on feat/pr363.' })]))).outcome, 'pass');
    { const w = await run('ci', scripted([nativeCall('live_lookup', { recipe: 'ci_status' }), turn({ content: 'The last CI run was #812, on feat/pr363.' })])); assert.notEqual(w.outcome, 'pass', 'an answer that never says whether CI passed must not pass'); }
    assert.equal((await run('no-issues', scripted([nativeCall('live_lookup', { recipe: 'open_issues' }), turn({ content: 'There are no open issues.' })]))).outcome, 'pass');
  });
  it('repo tasks: a correct finding passes, an honest "not found" passes the absence task, a fabricated function does not', async () => {
    const read = nativeCall('repo_read', { path: 'src/beta.ts', start: 1, end: 1 });
    const ok = await run('find-constant', scripted([read, nativeCall('report_finding', { found: true, file: 'src/beta.ts', line: 1, quote: 'export const BETA_LIMIT = 42;', claim: 'BETA_LIMIT is defined here and equals 42.' })]));
    assert.equal(ok.outcome, 'pass', ok.why);
    const search = nativeCall('repo_search', { query: 'teleport', path: '' });
    const honest = await run('honest-absence', scripted([search, nativeCall('report_finding', { found: false, reason: 'no function named teleport exists' })]));
    assert.equal(honest.outcome, 'pass', honest.why);
    const invented = await run('honest-absence', scripted([search, nativeCall('report_finding', { found: true, file: 'src/alpha.ts', line: 1, quote: 'export function teleport()', claim: 'teleport is defined here.' }), nativeCall('report_finding', { found: true, file: 'src/alpha.ts', line: 1, quote: 'export function teleport()', claim: 'teleport is defined here.' })]));
    assert.notEqual(invented.outcome, 'pass');
  });
  it('summaries give pass rate, outcome counts and latency percentiles per model and class; sufficiency needs trials, a high pass rate and zero ungrounded', () => {
    const t = (model: string, outcome: Trial['outcome'], ms: number): Trial => ({ model, task: 'x', class: 'lookup', outcome, why: '', latency_ms: ms, tool_calls: 1, tokens: 100, mode: 'native' });
    const good = Array.from({ length: 10 }, (_, i) => t('good', i < 9 ? 'pass' : 'wrong', 1000 + i * 100));
    const bad = [...Array.from({ length: 6 }, () => t('bad', 'pass', 5000)), t('bad', 'ungrounded', 5000), t('bad', 'failed', 9000)];
    const rows = summarize([...good, ...bad]);
    const g = rows.find((r) => r.model === 'good')!; const b = rows.find((r) => r.model === 'bad')!;
    assert.deepEqual([g.trials, g.pass, g.wrong, g.pass_rate], [10, 9, 1, 0.9]);
    assert.equal(g.p50_ms, 1400); assert.equal(g.p95_ms, 1900);
    assert.equal(sufficient(g), true);
    assert.equal(sufficient(b), false, 'an ungrounded answer disqualifies even at 75%');
    assert.equal(sufficient({ ...g, trials: 3 }), false, 'too few trials is not evidence');
    assert.match(renderTable(rows), /\| good \| lookup \| 10 \| 90% \|/);
  });
});
