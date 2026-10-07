// Think Tokens per repository: the tag, who may recall what, and that what a run on a chosen repository learns is scoped to it.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { SqliteTokenStore, type TokenDraft } from '../think-token-store.ts';
import { processFinishedRun, type PipelineDeps } from '../think-token-pipeline.ts';
import { inRepoScope, repoTag, repoTagOf, withRepoTag } from '../think-token-repo.ts';

test('repoTag: lower-case owner/name, none for anything that is not a GitHub name, short enough to be a tag, distinct when long', () => {
  assert.equal(repoTag('Kudbee-Studio/Kudbee-Demo'), 'repo:kudbee-studio:kudbee-demo');
  for (const bad of [null, undefined, '', 'nope', 'a/b/c', 'a b/c']) assert.equal(repoTag(bad), null, String(bad));
  const a = repoTag('kudbee-studio/kudbee-demo-bugs')!; const b = repoTag('kudbee-studio/kudbee-demo-bugz')!;
  assert.ok(a.length <= 32 && b.length <= 32); assert.notEqual(a, b); assert.match(a, /:[0-9a-f]{6}$/);
  assert.equal(repoTag('kudbee-studio/kudbee-demo-bugs'), a, 'stable');
});

test('inRepoScope: general tokens are recalled everywhere; a repository token only in its own repository; with no repository, only general ones', () => {
  const mine = 'repo:acme:demo';
  assert.equal(inRepoScope(['lesson'], mine), true); assert.equal(inRepoScope(['lesson'], null), true);
  assert.equal(inRepoScope([mine, 'x'], mine), true); assert.equal(inRepoScope([mine], 'repo:acme:other'), false); assert.equal(inRepoScope([mine], null), false); assert.equal(inRepoScope([mine], undefined), false);
  assert.equal(repoTagOf(['a', mine]), mine); assert.equal(repoTagOf(['a']), null);
});

test('withRepoTag: adds the tag, keeps it within 8 tags, never twice, leaves tags alone with no repository', () => {
  const eight = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'];
  assert.deepEqual(withRepoTag(['a'], 'repo:x:y'), ['a', 'repo:x:y']);
  const full = withRepoTag(eight, 'repo:x:y'); assert.equal(full.length, 8); assert.equal(full.at(-1), 'repo:x:y');
  assert.deepEqual(withRepoTag(['repo:x:y', 'a'], 'repo:other:z'), ['repo:x:y', 'a']);
  assert.deepEqual(withRepoTag(['a'], null), ['a']);
});

function accepted(store: SqliteTokenStore, title: string, tags: string[]): string {
  const draft: TokenDraft = { source_run_id: 'r', kind: 'lesson', title, content: `${title}: run the pagination tests before editing the pagination code.`, tags, evidence_ref: 'run:r', extractor: 'template' };
  const w = store.write(draft, 't'); assert.equal(w.ok, true); const id = (w as { id: string }).id; store.setStatus(id, 'accepted', 't'); return id;
}

test('retrieval: a token learned in one repository is not recalled in another, or with none chosen; general tokens always are', () => {
  const store = new SqliteTokenStore();
  const general = accepted(store, 'Pagination general advice', ['pagination']);
  const demo = accepted(store, 'Pagination demo repo advice', ['pagination', 'repo:acme:demo']);
  const other = accepted(store, 'Pagination other repo advice', ['pagination', 'repo:acme:other']);
  const ids = (repo: string | null | undefined): string[] => store.retrieve('fix the pagination code', 10, { repo, diverse: false }).map((t) => t.id).sort();
  assert.deepEqual(ids('repo:acme:demo'), [general, demo].sort());
  assert.deepEqual(ids('repo:acme:other'), [general, other].sort());
  assert.deepEqual(ids(null), [general]); assert.deepEqual(ids(undefined), [general]);
  store.close();
});

test('pipeline: what a run on a chosen repository learns carries that repository tag; a run with none stays general', async () => {
  const run = (repo: string | null) => ({ id: repo ? 'run-a' : 'run-b', goal: repo ? 'fix the pagination bug' : 'summarise the rss digest', success: true, repo, steps: (repo
    ? [{ kind: 'tool', name: 'repo_search', args: {}, ok: true, summary: 'ok' }, { kind: 'tool', name: 'repo_read', args: {}, ok: true, summary: 'ok' }]
    : [{ kind: 'tool', name: 'read_rss', args: {}, ok: true, summary: 'ok' }, { kind: 'tool', name: 'fetch_url', args: {}, ok: true, summary: 'ok' }]) as never });
  const store = new SqliteTokenStore();
  const deps: PipelineDeps = { store, models: { mercury: null, local: null }, knownTools: ['repo_search', 'repo_read', 'read_rss', 'fetch_url'] };
  const scoped = await processFinishedRun(deps, run('repo:acme:demo'), 'agent');
  const general = await processFinishedRun(deps, run(null), 'agent');
  assert.ok(scoped.tokens.length > 0 && general.tokens.length > 0);
  for (const t of scoped.tokens) assert.ok(store.get(t.id)!.tags.includes('repo:acme:demo'), t.id);
  for (const t of general.tokens) assert.equal(repoTagOf(store.get(t.id)!.tags), null);
  store.close();
});
