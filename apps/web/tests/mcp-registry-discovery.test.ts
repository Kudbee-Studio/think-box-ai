// Unit tests for mcp-registry.ts discovery: registry parsing, README metadata, category/tag inference, the 24h cache and fallbacks.
// The GitHub API is a fetch stub, so nothing touches the network.
import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import MCPRegistry from '../mcp-registry.ts';

const cacheDirs: string[] = [];
function cacheDir(): string { const d = fs.mkdtempSync(path.join(os.tmpdir(), 'kudbee-mcp-')); cacheDirs.push(d); return d; }
after(() => { for (const d of cacheDirs) fs.rmSync(d, { recursive: true, force: true }); });

const READMES: Record<string, string> = {
  'github-mcp': '# GitHub MCP\n\nManage GitHub repos, issues and files.\n\n## Capabilities\n- Create repositories\n- Fetch files via the api\n',
  'postgres-mcp': '# Postgres MCP\n\nRun SQL on a postgres database.\n\n## Capabilities\n- Execute SQL queries\n- Inspect schema\n',
};

function ok(body: unknown) { return { ok: true, status: 200, json: async () => body }; }
function notOk(status: number) { return { ok: false, status, json: async () => ({}) }; }

function registryFetch(reads: { count: number; fail?: boolean }, extraDirs: string[] = []) {
  return (url: string) => {
    if (reads.fail) throw new Error('offline');
    if (url.includes('/git/trees/main')) {
      reads.count++;
      return ok({ tree: [...Object.keys(READMES), ...extraDirs].map((name) => ({ path: `servers/${name}/` })), truncated: false });
    }
    const m = url.match(/contents\/servers\/([^/]+)\/README\.md/);
    if (m && READMES[m[1]]) return ok({ content: Buffer.from(READMES[m[1]]).toString('base64'), encoding: 'base64' });
    return notOk(404);
  };
}

async function withFetch(impl: (url: string) => unknown, fn: () => Promise<void>): Promise<void> {
  const orig = global.fetch;
  global.fetch = (async (input: unknown) => impl(String(input))) as typeof global.fetch;
  try { await fn(); } finally { global.fetch = orig; }
}

test('discoverServers parses the registry, README description, capabilities, category and tags', async () => {
  const reads = { count: 0 };
  const dir = cacheDir();
  await withFetch(registryFetch(reads), async () => {
    const servers = await new MCPRegistry(undefined, dir).discoverServers();
    assert.equal(servers.length, 2);
    const github = servers.find((s) => s.name === 'github-mcp')!;
    assert.equal(github.description, 'Manage GitHub repos, issues and files.');
    assert.equal(github.category, 'Developer Tools');
    assert.deepEqual(github.capabilities, ['Create repositories', 'Fetch files via the api']);
    assert.ok(github.tags.includes('api'));
    assert.ok(github.tags.includes('filesystem'));
    const postgres = servers.find((s) => s.name === 'postgres-mcp')!;
    assert.equal(postgres.category, 'Database');
    assert.ok(postgres.tags.includes('database'));
  });
  assert.equal(fs.existsSync(path.join(dir, 'servers.json')), true);
});

test('a fresh cache is served without asking GitHub again', async () => {
  const dir = cacheDir();
  const reads = { count: 0 };
  await withFetch(registryFetch(reads), async () => { await new MCPRegistry(undefined, dir).discoverServers(); });
  const before = reads.count;
  await withFetch(() => { throw new Error('should not be called'); }, async () => {
    const servers = await new MCPRegistry(undefined, dir).discoverServers();
    assert.equal(servers.length, 2);
  });
  assert.equal(reads.count, before);
});

test('an expired cache triggers a refetch', async () => {
  const dir = cacheDir();
  const first = { count: 0 };
  await withFetch(registryFetch(first), async () => { await new MCPRegistry(undefined, dir).discoverServers(); });
  const old = new Date(Date.now() - 25 * 60 * 60 * 1000);
  fs.utimesSync(path.join(dir, 'servers.json'), old, old);
  const second = { count: 0 };
  await withFetch(registryFetch(second), async () => {
    const servers = await new MCPRegistry(undefined, dir).discoverServers();
    assert.equal(servers.length, 2);
  });
  assert.ok(second.count >= 1, 'refetched after expiry');
});

test('a corrupt cache is ignored and replaced', async () => {
  const dir = cacheDir();
  fs.writeFileSync(path.join(dir, 'servers.json'), '{ not json');
  await withFetch(registryFetch({ count: 0 }), async () => {
    const servers = await new MCPRegistry(undefined, dir).discoverServers();
    assert.equal(servers.length, 2);
  });
});

test('a server directory without a README is skipped', async () => {
  const dir = cacheDir();
  await withFetch(registryFetch({ count: 0 }, ['ghost-mcp']), async () => {
    const servers = await new MCPRegistry(undefined, dir).discoverServers();
    assert.equal(servers.some((s) => s.name === 'ghost-mcp'), false);
    assert.equal(servers.length, 2);
  });
});

test('a network failure falls back to the built-in server list', async () => {
  const dir = cacheDir();
  await withFetch(registryFetch({ count: 0, fail: true }), async () => {
    const servers = await new MCPRegistry(undefined, dir).discoverServers();
    assert.equal(servers.length, 6);
    assert.ok(servers.some((s) => s.name === 'postgres'));
  });
});

test('discovery still succeeds when the cache cannot be written', async () => {
  const parent = cacheDir();
  const blocker = path.join(parent, 'blocker');
  fs.writeFileSync(blocker, 'not a directory');
  await withFetch(registryFetch({ count: 0 }), async () => {
    const servers = await new MCPRegistry(undefined, path.join(blocker, 'cache')).discoverServers();
    assert.equal(servers.length, 2);
  });
});
