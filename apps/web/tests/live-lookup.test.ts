// Phase 1 proof: the live-data recipes as one governed tool contract, proven on their own (no model involved).
import { after, before, describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { runGovernedTool, newRunContext } from '../agent.ts';
import { LOOKUP_RECIPES, PAGE_SIZE, countUrl, lookupUrl, normalizeLookup, parseTotal, renderFacts, validateLookupArgs, withTotal } from '../live-lookup.ts';
import { lookupHooks, startFakeGithub, type FakeGithub } from './helpers/lookup-hooks.ts';

const REPO = 'Acme/widgets';
const pr = (number: number, o: Record<string, unknown> = {}) => ({ number, title: `PR ${number}`, state: 'closed', merged_at: '2026-10-04T10:00:00Z', draft: false, user: { login: 'dev' }, head: { ref: `feat/pr${number}` }, updated_at: '2026-10-04T10:00:00Z', html_url: `https://github.com/Acme/widgets/pull/${number}`, ...o });
const reply = (body: unknown, status = 200) => ({ status, text: typeof body === 'string' ? body : JSON.stringify(body), url: 'https://api.github.com/x', fetched_at: '2026-10-04T12:00:00Z', latency_ms: 42 });

describe('validateLookupArgs', () => {
  it('accepts each recipe and defaults the repo to the configured one', () => {
    for (const recipe of LOOKUP_RECIPES) assert.deepEqual(validateLookupArgs({ recipe }, REPO), { ok: true, args: { recipe, repo: REPO } });
    assert.deepEqual(validateLookupArgs({ recipe: 'ci_status', branch: 'feat/x-1.2' }, REPO), { ok: true, args: { recipe: 'ci_status', repo: REPO, branch: 'feat/x-1.2' } });
    assert.equal(validateLookupArgs({ recipe: 'branches', repo: 'acme/WIDGETS' }, REPO).ok, true);
  });
  it('rejects bad requests with a reason instead of guessing', () => {
    const bad: Array<[unknown, RegExp]> = [
      [null, /must be an object/], [[], /must be an object/], ['latest_pr', /must be an object/],
      [{}, /recipe must be one of/], [{ recipe: 'merge_pr' }, /recipe must be one of/], [{ recipe: 7 }, /recipe must be one of/],
      [{ recipe: 'latest_pr', url: 'http://evil' }, /unknown argument\(s\): url/],
      [{ recipe: 'latest_pr', repo: 'evil/other' }, /only the configured repository/],
      [{ recipe: 'latest_pr', repo: '../../etc' }, /owner\/name/],
      [{ recipe: 'ci_status', branch: '../x' }, /not a valid branch/], [{ recipe: 'ci_status', branch: 'a b' }, /not a valid branch/],
      [{ recipe: 'latest_pr', branch: 'main' }, /only used with ci_status/],
    ];
    for (const [raw, why] of bad) { const r = validateLookupArgs(raw, REPO); assert.equal(r.ok, false, JSON.stringify(raw)); assert.match((r as any).error, why); }
    assert.match((validateLookupArgs({ recipe: 'latest_pr' }, null) as any).error, /no GitHub repository is configured/);
  });
});

describe('lookupUrl', () => {
  it('builds one URL per recipe and encodes the branch', () => {
    const u = (recipe: any, branch?: string) => lookupUrl({ recipe, repo: REPO, branch }, 'http://127.0.0.1:9/');
    assert.equal(u('latest_pr'), 'http://127.0.0.1:9/repos/Acme/widgets/pulls?state=all&sort=created&direction=desc&per_page=5');
    assert.equal(u('ci_status', 'feat/a b'), 'http://127.0.0.1:9/repos/Acme/widgets/actions/runs?per_page=5&exclude_pull_requests=true&branch=feat%2Fa%20b');
    assert.equal(u('branches'), 'http://127.0.0.1:9/repos/Acme/widgets/branches?per_page=10');
  });
});

describe('a list that may hold more than it shows says so (evidence.more)', () => {
  const issue = (n: number, o: Record<string, unknown> = {}) => ({ number: n, title: `issue ${n}`, state: 'open', user: { login: 'a' }, updated_at: 't', ...o });
  it('every recipe asks GitHub for exactly PAGE_SIZE entries', () => {
    for (const recipe of LOOKUP_RECIPES) assert.match(lookupUrl({ recipe, repo: REPO }), new RegExp(`per_page=${PAGE_SIZE[recipe]}(&|$)`), recipe);
  });
  it('a full page counts as "more" even when pull requests are filtered out of an issues list (the real GitHub case: 10 entries, 5 issues)', () => {
    const page = [...Array.from({ length: 5 }, (_, i) => issue(i + 1)), ...Array.from({ length: 5 }, (_, i) => issue(100 + i, { pull_request: {} }))];
    const r = normalizeLookup({ recipe: 'open_issues', repo: REPO }, reply(page)) as any;
    assert.equal(r.evidence.items.length, 5); assert.equal(r.evidence.more, true);
  });
  it('a short list is complete; a full page of branches, and items dropped to the display limit, are "more"', () => {
    assert.equal((normalizeLookup({ recipe: 'open_issues', repo: REPO }, reply([issue(1), issue(2)])) as any).evidence.more, false);
    assert.equal((normalizeLookup({ recipe: 'branches', repo: REPO }, reply(Array.from({ length: 10 }, (_, i) => ({ name: `b${i}` })))) as any).evidence.more, true);
    assert.equal((normalizeLookup({ recipe: 'open_issues', repo: REPO }, reply(Array.from({ length: 7 }, (_, i) => issue(i + 1)))) as any).evidence.more, true, '7 issues, 5 shown');
  });
});

describe('normalizeLookup: structured evidence, preserved fields, explicit failure', () => {
  it('keeps ids, urls, state, timestamps, head branch, source and timing for pull requests', () => {
    const r = normalizeLookup({ recipe: 'latest_pr', repo: REPO }, reply([pr(361), pr(360, { merged_at: null, state: 'open', draft: true })]));
    assert.ok(r.ok);
    const e = (r as any).evidence;
    assert.deepEqual({ recipe: e.recipe, repo: e.repo, http_status: e.http_status, complete: e.complete, tool_calls: e.tool_calls, latency_ms: e.latency_ms, fetched_at: e.fetched_at, source_url: e.source_url }, { recipe: 'latest_pr', repo: REPO, http_status: 200, complete: true, tool_calls: 1, latency_ms: 42, fetched_at: '2026-10-04T12:00:00Z', source_url: 'https://api.github.com/x' });
    assert.deepEqual(e.items[0], { kind: 'pr', number: 361, title: 'PR 361', state: 'merged', draft: false, author: 'dev', head_ref: 'feat/pr361', url: 'https://github.com/Acme/widgets/pull/361', updated_at: '2026-10-04T10:00:00Z' });
    assert.equal(e.items[1].state, 'open');
    assert.equal(e.items[1].draft, true);
  });
  it('closed-without-merging is its own state, and issues exclude pull requests', () => {
    const e = (normalizeLookup({ recipe: 'latest_pr', repo: REPO }, reply([pr(5, { merged_at: null })])) as any).evidence;
    assert.equal(e.items[0].state, 'closed');
    const i = (normalizeLookup({ recipe: 'open_issues', repo: REPO }, reply([{ number: 1, title: 'bug', state: 'open', user: { login: 'a' }, html_url: 'u', updated_at: 't' }, { number: 2, title: 'a pr', pull_request: {} }])) as any).evidence;
    assert.deepEqual(i.items.map((x: any) => x.number), [1]);
  });
  it('states the CI verdict of the newest run, with the branch filter recorded', () => {
    const run = (conclusion: string | null, status = 'completed') => ({ workflow_runs: [{ name: 'CI', head_branch: 'main', event: 'push', status, conclusion, run_number: 9, html_url: 'u', updated_at: 't' }] });
    assert.equal((normalizeLookup({ recipe: 'ci_status', repo: REPO, branch: 'main' }, reply(run('failure'))) as any).evidence.verdict, 'failure');
    assert.equal((normalizeLookup({ recipe: 'ci_status', repo: REPO }, reply(run(null, 'in_progress'))) as any).evidence.verdict, 'in_progress');
    assert.equal((normalizeLookup({ recipe: 'ci_status', repo: REPO, branch: 'main' }, reply(run('success'))) as any).evidence.branch, 'main');
  });
  it('fails explicitly: HTTP error, unreadable, wrong shape, cut off with nothing complete. No fabricated list.', () => {
    const n = (recipe: any, rep: any) => normalizeLookup({ recipe, repo: REPO }, rep) as any;
    assert.match(n('latest_pr', reply({ message: 'rate limited' }, 403)).error, /HTTP 403 for Acme\/widgets's latest pull requests/);
    assert.match(n('latest_pr', reply('<html>')).error, /cut off or malformed/);
    assert.match(n('latest_pr', reply({ message: 'x' })).error, /not a list of latest pull requests/);
    assert.match(n('latest_pr', reply('[{"number": 1, "title": "cut')).error, /cut off or malformed/);
    assert.match(n('ci_status', reply('{"workflow_runs":[{"name"')).error, /cut off or malformed/);
    assert.match(n('ci_status', reply({ nope: 1 })).error, /not a list of workflow runs/);
    assert.equal(n('latest_pr', reply([])).ok, true);
    assert.equal(n('latest_pr', reply([])).evidence.items.length, 0);
  });
  it('keeps the complete leading items of a cut-off reply and says it was cut off', () => {
    const big = (n: number) => JSON.stringify({ ...pr(n), body: 'x'.repeat(3000) });
    const e = (normalizeLookup({ recipe: 'latest_pr', repo: REPO }, reply(`[${big(3)},${big(2)},${big(1).slice(0, 800)}`)) as any).evidence;
    assert.equal(e.complete, false);
    assert.deepEqual(e.items.map((x: any) => x.number), [3, 2]);
    assert.match(renderFacts(e), /cut off/);
  });
});

describe('the live_lookup tool through the governed path (fake GitHub)', () => {
  let gh: FakeGithub;
  let prev: string | undefined;
  before(async () => {
    gh = await startFakeGithub({ 'pulls?': { body: [pr(361), pr(360)] }, 'actions/runs': { body: { workflow_runs: [] } }, branches: { status: 500, body: 'boom' } });
    prev = process.env.KUDBEE_GITHUB_API; process.env.KUDBEE_GITHUB_API = gh.url; process.env.KUDBEE_REPO = REPO;
  });
  after(async () => { if (prev === undefined) delete process.env.KUDBEE_GITHUB_API; else process.env.KUDBEE_GITHUB_API = prev; delete process.env.KUDBEE_REPO; await gh.close(); });

  it('asks for approval on first network access, then returns normalized evidence with tool-call count and latency', async () => {
    gh.hits.length = 0;
    const { hooks, approvals, events } = lookupHooks();
    const g = await runGovernedTool('live_lookup', { recipe: 'latest_pr' }, hooks, newRunContext(), 1);
    assert.equal(approvals.length, 1);
    assert.match(approvals[0]!.reason, /First network access to 127\.0\.0\.1/);
    assert.equal(g.output.ok, true);
    const e = (g.output as any).evidence;
    assert.equal(e.recipe, 'latest_pr');
    assert.deepEqual(e.items.map((i: any) => i.number), [361, 360]);
    assert.equal(e.tool_calls, 1);
    assert.ok(e.latency_ms >= 0 && Number.isFinite(e.latency_ms));
    assert.match(e.source_url, /\/repos\/Acme\/widgets\/pulls\?state=all/);
    assert.deepEqual(gh.hits, ['/repos/Acme/widgets/pulls?state=all&sort=created&direction=desc&per_page=5']);
    assert.equal(events.at(-1)?.kind, 'tool');
    // a second lookup in the same session does not ask again
    await runGovernedTool('live_lookup', { recipe: 'open_prs' }, hooks, newRunContext(), 2);
    assert.equal(approvals.length, 1);
  });
  it('a denied approval is a failure with no GitHub call', async () => {
    gh.hits.length = 0;
    const { hooks } = lookupHooks({}, false);
    const g = await runGovernedTool('live_lookup', { recipe: 'latest_pr' }, hooks, newRunContext(), 1);
    assert.equal(g.output.ok, false);
    assert.match(String(g.output.error), /Denied by human reviewer/);
    assert.equal(g.approval, 'denied');
    assert.equal(gh.hits.length, 0);
  });
  it('invalid requests and GitHub failures are explicit errors, never made-up data', async () => {
    const { hooks } = lookupHooks();
    const ctx = newRunContext();
    for (const [args, why] of [[{ recipe: 'drop_table' }, /recipe must be one of/], [{ recipe: 'latest_pr', repo: 'evil/x' }, /only the configured repository/], [{ recipe: 'latest_pr', url: 'http://x' }, /unknown argument/], [{ recipe: 'branches' }, /HTTP 500/]] as const) {
      const g = await runGovernedTool('live_lookup', args as any, hooks, ctx, 1);
      assert.equal(g.output.ok, false, JSON.stringify(args));
      assert.match(String(g.output.error), why);
      assert.equal((g.output as any).evidence, undefined);
    }
  });
  it('an empty CI list is evidence of "none", not an error', async () => {
    const { hooks } = lookupHooks();
    const g = await runGovernedTool('live_lookup', { recipe: 'ci_status', branch: 'main' }, hooks, newRunContext(), 1);
    assert.equal(g.output.ok, true);
    assert.deepEqual((g.output as any).evidence.items, []);
    assert.match(renderFacts((g.output as any).evidence), /none\./);
  });
});

describe('exact totals (P3.37): a list is one page, GitHub\'s own count is the total', () => {
  const issue = (n: number) => ({ number: n, title: `bug ${n}`, state: 'open', user: { login: 'a' }, html_url: `https://github.com/Acme/widgets/issues/${n}`, updated_at: '2026-10-04T10:00:00Z' });
  const evidence = (recipe: any, body: unknown) => (normalizeLookup({ recipe, repo: REPO }, reply(body)) as any).evidence;
  it('countUrl exists only for open issues and open PRs, asks the search endpoint, and encodes the query', () => {
    const u = (recipe: any) => countUrl({ recipe, repo: REPO }, 'http://127.0.0.1:9/');
    assert.equal(u('open_issues'), 'http://127.0.0.1:9/search/issues?q=repo%3AAcme%2Fwidgets%20type%3Aissue%20state%3Aopen&per_page=1');
    assert.equal(u('open_prs'), 'http://127.0.0.1:9/search/issues?q=repo%3AAcme%2Fwidgets%20type%3Apr%20state%3Aopen&per_page=1');
    for (const r of ['latest_pr', 'ci_status', 'branches']) assert.equal(u(r), null, r);
    assert.match(countUrl({ recipe: 'open_issues', repo: REPO })!, /^https:\/\/api\.github\.com\/search\/issues/);
  });
  it('parseTotal accepts only a clean, complete, whole, non-negative count; everything else is "unknown"', () => {
    const t = (status: unknown, text: unknown) => parseTotal({ status, text });
    assert.equal(t(200, JSON.stringify({ total_count: 12, incomplete_results: false, items: [] })), 12);
    assert.equal(t(200, '{"total_count":0}'), 0);
    for (const [st, tx] of [[403, '{"total_count":5}'], [200, 'nope'], [200, '[]'], [200, '{"total_count":5,"incomplete_results":true}'], [200, '{"total_count":"5"}'], [200, '{"total_count":2.5}'], [200, '{"total_count":-1}'], [200, '{"total_count":99999999}'], [200, '{}'], [200, undefined]] as Array<[number, unknown]>) assert.equal(t(st, tx), null, `${st} ${String(tx)}`);
  });
  it('withTotal makes `more` mean exactly "GitHub holds more than shown"', () => {
    const e = evidence('open_issues', Array.from({ length: 7 }, (_, i) => issue(i + 1)));
    assert.equal(e.items.length, 5);
    assert.equal(withTotal(e, 7, 'u').more, true, '7 exist, 5 shown');
    assert.equal(withTotal(e, 5, 'u').more, false, 'exactly the 5 shown exist');
    assert.deepEqual([withTotal(e, 12, 'http://x').total, withTotal(e, 12, 'http://x').total_url], [12, 'http://x']);
  });
  it('renderFacts states the exact total next to the shown items; without a total the wording is unchanged', () => {
    const e = evidence('open_issues', Array.from({ length: 10 }, (_, i) => issue(i + 1)));
    assert.match(renderFacts(withTotal(e, 10, 'u')), /^Open issues in Acme\/widgets \(live from GitHub just now\): 10 open in total\. Newest first, showing 5:/);
    assert.match(renderFacts(e), /^Open issues in Acme\/widgets \(live from GitHub just now, newest first, showing 5\):/);
    assert.match(renderFacts(withTotal(evidence('open_issues', []), 0, 'u')), /: none\.$/);
    assert.match(renderFacts(withTotal(evidence('open_issues', [{ number: 9, title: 'a pr', pull_request: {} }]), 4, 'u')), /: 4 open in total; none of them is in the first page fetched\.$/);
    const prs = withTotal(evidence('open_prs', [pr(361, { state: 'open', merged_at: null }), pr(360, { state: 'open', merged_at: null })]), 9, 'u');
    assert.match(renderFacts(prs), /Open pull requests in Acme\/widgets \(live from GitHub just now\): 9 open in total\. Newest first, showing 2\.\n- #361/);
    assert.match(renderFacts(withTotal(evidence('open_prs', []), 0, 'u')), /: none\.$/);
  });
});

describe('the live_lookup tool reads the exact total (fake GitHub, P3.37)', () => {
  let gh: FakeGithub; let prev: string | undefined;
  const issue = (n: number, o: Record<string, unknown> = {}) => ({ number: n, title: `bug ${n}`, state: 'open', user: { login: 'a' }, html_url: `https://github.com/Acme/widgets/issues/${n}`, updated_at: '2026-10-04T10:00:00Z', ...o });
  before(async () => {
    // order matters: the fake matches by substring, and "search/issues" contains "issues"
    gh = await startFakeGithub({ 'search/issues': { body: { total_count: 12, incomplete_results: false, items: [] } }, 'repos/Acme/widgets/issues': { body: Array.from({ length: 10 }, (_, i) => (i < 3 ? issue(i + 1, { pull_request: {} }) : issue(i + 1))) } });
    prev = process.env.KUDBEE_GITHUB_API; process.env.KUDBEE_GITHUB_API = gh.url; process.env.KUDBEE_REPO = REPO;
  });
  after(async () => { if (prev === undefined) delete process.env.KUDBEE_GITHUB_API; else process.env.KUDBEE_GITHUB_API = prev; delete process.env.KUDBEE_REPO; await gh.close(); });
  const look = async (recipe: string) => (await runGovernedTool('live_lookup', { recipe }, lookupHooks().hooks, newRunContext(), 1)).output as any;

  it('attaches the total GitHub reports, after the list, with both URLs on the record', async () => {
    gh.hits.length = 0;
    const o = await look('open_issues');
    assert.equal(o.ok, true);
    assert.equal(o.evidence.total, 12);
    assert.match(o.evidence.total_url, /\/search\/issues\?q=repo%3AAcme%2Fwidgets%20type%3Aissue%20state%3Aopen/);
    assert.equal(o.evidence.items.length, 5);
    assert.equal(o.evidence.more, true);
    assert.equal(gh.hits.length, 2);
    assert.match(gh.hits[0]!, /\/repos\/Acme\/widgets\/issues\?state=open/);
    assert.match(gh.hits[1]!, /^\/search\/issues/);
  });
  it('a failed, rate-limited, unreadable or incomplete count leaves the list alone and claims no total; recipes without a count make no second request', async () => {
    for (const bad of [{ status: 403, body: { message: 'rate limit' } }, { status: 200, body: 'not json' }, { status: 200, body: { total_count: 12, incomplete_results: true } }, { status: 200, body: { total_count: 'many' } }]) {
      gh.routes['search/issues'] = bad;
      const o = await look('open_issues');
      assert.equal(o.ok, true); assert.equal(o.evidence.total, undefined, JSON.stringify(bad)); assert.equal(o.evidence.items.length, 5);
    }
    gh.routes['search/issues'] = { body: { total_count: 12, incomplete_results: false } };
    gh.hits.length = 0;
    gh.routes['branches'] = { body: [{ name: 'main', protected: true }] };
    await look('branches');
    assert.deepEqual(gh.hits.filter((h) => h.includes('search')), []);
  });
  it('a dead count endpoint (connection error) does not fail the lookup', async () => {
    const saved = gh.routes['search/issues']!;
    const realFetch = globalThis.fetch;
    globalThis.fetch = (async (url: any, init: any) => { if (String(url).includes('/search/issues')) throw new Error('connect ECONNREFUSED'); return realFetch(url, init); }) as typeof fetch;
    try { const o = await look('open_issues'); assert.equal(o.ok, true); assert.equal(o.evidence.total, undefined); } finally { globalThis.fetch = realFetch; gh.routes['search/issues'] = saved; }
  });
});

