import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import type { AddressInfo } from 'node:net';
import { MemoryStore, tokenize, type MemoryHit } from '../memory.ts';

const LOCAL_ENV = { KUDBEE_VECTOR_NAMESPACE: 'test' } as NodeJS.ProcessEnv;
const tmp = () => fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-memory-test-'));

async function seeded(root = tmp(), env = LOCAL_ENV) {
  const store = new MemoryStore(root, env);
  await store.write('org', { title: 'Hacker News RSS is reliable', content: 'Use https://hnrss.org/frontpage for the front page.', tags: ['news', 'rss'] });
  await store.write('org', { title: 'User prefers markdown reports', content: 'Deliver reports as .md files with links.', tags: ['preference'] });
  await store.write('task', { title: 'Summarize Algorand docs', content: 'Goal: summarize\nOutcome: completed\n\nAnswer given (unverified):\nAlgorand is fast.', slug: 'ep-1' });
  return { store, root };
}

test('tokenize drops stopwords and folds simple plurals', () => {
  assert.deepEqual(tokenize('The reports are in the folders!'), ['report', 'folder']);
  assert.deepEqual(tokenize('a an the'), []);
});

test('layers are folders of Markdown files with front matter, plus a README', async () => {
  const { store, root } = await seeded();
  assert.deepEqual(store.counts(), { task: 1, org: 2, verified: 0 });
  assert.ok(fs.existsSync(path.join(root, 'README.md')));
  const raw = fs.readFileSync(path.join(root, 'org/hacker-news-rss-is-reliable.md'), 'utf8');
  assert.match(raw, /^---\nid: org\/hacker-news-rss-is-reliable\nlayer: org\ntitle: Hacker News RSS is reliable\ntags: news, rss\n/);
});

test('files are the source of truth: a new store reloads them, including hand edits', async () => {
  const { root } = await seeded();
  fs.writeFileSync(path.join(root, 'verified', 'hand-written.md'), '---\ntitle: Hand written\ntags: manual\n---\nWritten by a human in an editor.');
  const reloaded = new MemoryStore(root, LOCAL_ENV);
  assert.deepEqual(reloaded.counts(), { task: 1, org: 2, verified: 1 });
  assert.equal(reloaded.get('verified/hand-written')?.content, 'Written by a human in an editor.');
});

test('search ranks by relevance and honours the layer filter', async () => {
  const { store } = await seeded();
  const hits = await store.search('where do I get hacker news stories');
  assert.equal(hits.backend, 'local-bm25');
  assert.equal(hits.hits[0].item.id, 'org/hacker-news-rss-is-reliable');
  const tasks = await store.search('algorand', { layers: ['task'] });
  assert.deepEqual(tasks.hits.map((h) => h.item.id), ['task/ep-1']);
  const none = await store.search('algorand', { layers: ['verified'] });
  assert.equal(none.hits.length, 0);
});

test('a colliding title does not overwrite an existing memory', async () => {
  const { store } = await seeded();
  const second = await store.write('org', { title: 'User prefers markdown reports', content: 'Different note.' });
  assert.notEqual(second.id, 'org/user-prefers-markdown-reports');
  assert.equal(store.get('org/user-prefers-markdown-reports')?.content, 'Deliver reports as .md files with links.');
});

test('promote moves org → verified; other layers cannot be promoted', async () => {
  const { store, root } = await seeded();
  const promoted = await store.promote('org/user-prefers-markdown-reports');
  assert.equal(promoted.id, 'verified/user-prefers-markdown-reports');
  assert.match(promoted.source, /promoted by human/);
  assert.equal(fs.existsSync(path.join(root, 'org/user-prefers-markdown-reports.md')), false);
  assert.equal(fs.existsSync(path.join(root, 'verified/user-prefers-markdown-reports.md')), true);
  await assert.rejects(store.promote('task/ep-1'), /Only org memories/);
  await assert.rejects(store.promote('org/missing'), /not found/);
});

test('remove deletes the file and the index entry', async () => {
  const { store, root } = await seeded();
  assert.equal(await store.remove('task/ep-1'), true);
  assert.equal(fs.existsSync(path.join(root, 'task/ep-1.md')), false);
  assert.equal((await store.search('algorand')).hits.length, 0);
  assert.equal(await store.remove('task/ep-1'), false);
});

test('prompt context labels trust and strips past-run answers', async () => {
  const { store } = await seeded();
  const hits: MemoryHit[] = ['org/hacker-news-rss-is-reliable', 'task/ep-1'].map((id) => ({ item: store.get(id)!, score: 1 }));
  const text = MemoryStore.formatForPrompt(hits);
  assert.match(text, /\[ORG \(unverified note, has evidence\)\] Hacker News RSS is reliable/);
  assert.match(text, /\[PAST RUN \(history only — its answer is not evidence\)\]/);
  assert.doesNotMatch(text, /Algorand is fast/);
  assert.equal(MemoryStore.formatForPrompt([]), '');
});

// ─── Upstash Vector path, against a local mock ────────────────────
async function mockVector(opts: { failQueries?: boolean } = {}) {
  const upserts: Array<{ id: string; sparseVector: { indices: number[]; values: number[] } }> = [];
  const queries: Array<Record<string, unknown>> = [];
  const server = http.createServer((req, res) => {
    let body = '';
    req.on('data', (c) => (body += c));
    req.on('end', () => {
      const json = body ? JSON.parse(body) : undefined;
      res.setHeader('Content-Type', 'application/json');
      if (req.url?.startsWith('/upsert/')) {
        upserts.push(...json);
        return res.end(JSON.stringify({ result: 'Success' }));
      }
      if (req.url?.startsWith('/query/')) {
        queries.push(json);
        if (opts.failQueries) {
          res.statusCode = 503;
          return res.end(JSON.stringify({ error: 'unavailable' }));
        }
        // Pretend the index only knows the first upserted vector (the rest are still "pending").
        return res.end(JSON.stringify({ result: upserts.slice(0, 1).map((u) => ({ id: u.id, score: 0.9 })) }));
      }
      if (req.url?.startsWith('/delete/')) return res.end(JSON.stringify({ result: { deleted: 1 } }));
      res.statusCode = 404;
      res.end('{}');
    });
  });
  await new Promise<void>((r) => server.listen(0, '127.0.0.1', r));
  const url = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
  return { url, upserts, queries, close: () => new Promise<void>((r) => server.close(() => r())) };
}

test('upstash: sparse vectors are upserted and queries use IDF weighting and layer filters', async () => {
  const vector = await mockVector();
  try {
    const env = { UPSTASH_VECTOR_REST_URL: vector.url, UPSTASH_VECTOR_REST_TOKEN: 't', KUDBEE_VECTOR_NAMESPACE: 'ns' } as NodeJS.ProcessEnv;
    const { store } = await seeded(tmp(), env);
    assert.equal(vector.upserts.length, 3);
    const sv = vector.upserts[0].sparseVector;
    assert.equal(sv.indices.length, sv.values.length);
    assert.ok(sv.indices.every((i) => Number.isInteger(i) && i >= 0 && i < 2 ** 31));
    assert.deepEqual([...sv.indices], [...sv.indices].sort((a, b) => a - b));

    const result = await store.search('markdown report preference', { layers: ['org'] });
    assert.equal(result.backend, 'hybrid (upstash-sparse + local-bm25)');
    assert.equal(vector.queries[0].weightingStrategy, 'IDF');
    assert.equal(vector.queries[0].filter, "layer = 'org'");
    // The mock only "indexed" the first note, yet the fresh one is still found via the local index.
    assert.ok(result.hits.some((h) => h.item.id === 'org/user-prefers-markdown-reports'));
    assert.equal(store.vectorStatus.ok, true);
  } finally {
    await vector.close();
  }
});

test('upstash outage falls back to the local index and reports the vector as offline', async () => {
  const vector = await mockVector({ failQueries: true });
  try {
    const env = { UPSTASH_VECTOR_REST_URL: vector.url, UPSTASH_VECTOR_REST_TOKEN: 't' } as NodeJS.ProcessEnv;
    const { store } = await seeded(tmp(), env);
    const result = await store.search('hacker news');
    assert.equal(result.backend, 'local-bm25 (vector offline)');
    assert.equal(result.hits[0].item.id, 'org/hacker-news-rss-is-reliable');
    assert.equal(store.vectorStatus.ok, false);
    assert.match(String(store.vectorStatus.error), /HTTP 503/);
  } finally {
    await vector.close();
  }
});

test('P3.10: a superseded memory stays on disk but is never recalled, and two identical task episodes recall as one', async () => {
  const root = tmp();
  const store = new MemoryStore(root, LOCAL_ENV);
  await store.write('org', { title: '[SUPERSEDED 2026-10-02] Open PR state 2026-09-30', content: 'Open PRs: #304 (draft). The pull request list as of 2026-09-30.', tags: ['pr', 'superseded'] });
  await store.write('org', { title: 'Open PR check', content: 'List the open pull request list with the GitHub API; do not trust old notes.', tags: ['pr'] });
  await store.write('task', { title: 'WHAT PR ARE WE WORKING ON?', content: 'Goal: WHAT PR ARE WE WORKING ON?\nOutcome: completed', slug: 'ep-1' });
  await store.write('task', { title: 'WHAT PR ARE WE WORKING ON?', content: 'Goal: WHAT PR ARE WE WORKING ON?\nOutcome: completed\nTools: fetch_url, write_file', slug: 'ep-2' });
  const { hits } = await store.search('what open pull request list PR are we working on', { topK: 10 });
  const titles = hits.map((h) => h.item.title);
  assert.ok(!titles.some((t) => t.includes('SUPERSEDED')), `recalled: ${titles}`);
  assert.equal(titles.filter((t) => t === 'WHAT PR ARE WE WORKING ON?').length, 1, 'the two identical episodes collapsed');
  assert.ok(titles.includes('Open PR check'));
  assert.ok(fs.readdirSync(path.join(root, 'org')).some((f) => f.includes('superseded')), 'the superseded file is still on disk');
});
