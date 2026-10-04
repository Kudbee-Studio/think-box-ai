// Unit tests for the profile switcher (public/js/profile-switcher.js): the pure ProfileStore.
// The DOM half (mountProfileSwitcher) is exercised through the store; a full fake-DOM pass lives with
// the other dashboard UI tests if needed. This keeps the API-shape and switching logic deterministic.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const src = fs.readFileSync(path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../public/js/profile-switcher.js'), 'utf8');
const sandbox: Record<string, unknown> = {};
vm.createContext(sandbox);
vm.runInContext(src, sandbox, { filename: 'profile-switcher.js' });
const ProfileStore = sandbox.ProfileStore as new (o: { request: (url: string, init?: RequestInit) => Promise<any>; onChange?: (s: unknown) => void }) => {
  refresh(): Promise<any>;
  snapshot(): any;
  activeProfile(): any;
  create(name: string): Promise<any>;
  setActive(id: string): Promise<any>;
  rename(id: string, name: string): Promise<any>;
  remove(id: string): Promise<any>;
  exportProfile(id: string): Promise<any>;
  importProfile(bundle: unknown): Promise<any>;
};

/** A fake API: in-memory profiles, recording each request. */
function fakeApi(initial?: { profiles?: any[]; active?: string }) {
  const state = { profiles: initial?.profiles ?? [{ id: 'p1', name: 'Default' }], active: initial?.active ?? 'p1' };
  const calls: Array<{ url: string; method: string }> = [];
  const request = async (url: string, init?: RequestInit) => {
    const method = init?.method ?? 'GET';
    calls.push({ url, method });
    const body = init?.body ? JSON.parse(String(init.body)) : {};
    if (url === '/api/profiles' && method === 'GET') return { profiles: state.profiles, active: state.active };
    if (url === '/api/profiles' && method === 'POST') {
      const profile = { id: 'p' + (state.profiles.length + 1), name: body.name };
      state.profiles.push(profile);
      return profile;
    }
    const activate = url.match(/^\/api\/profiles\/([^/]+)\/activate$/);
    if (activate && method === 'POST') { state.active = activate[1]; return { id: activate[1] }; }
    const exportMatch = url.match(/^\/api\/profiles\/([^/]+)\/export$/);
    if (exportMatch) return { format: 'kudbee-profile', version: 1, profile: { name: 'Default' }, memory: {}, runs: [] };
    const item = url.match(/^\/api\/profiles\/([^/]+)$/);
    if (item && method === 'PATCH') { state.profiles = state.profiles.map((p) => (p.id === item[1] ? { ...p, name: body.name } : p)); return { id: item[1], name: body.name }; }
    if (item && method === 'DELETE') { state.profiles = state.profiles.filter((p) => p.id !== item[1]); if (state.active === item[1]) state.active = state.profiles[0]?.id ?? null; return { success: true }; }
    if (url === '/api/profiles/import' && method === 'POST') { const profile = { id: 'imported1', name: 'Default (imported)' }; state.profiles.push(profile); return profile; }
    throw new Error('unexpected ' + method + ' ' + url);
  };
  return { request, calls, state };
}

test('refresh loads profiles and the active id and notifies onChange', async () => {
  const api = fakeApi({ profiles: [{ id: 'a', name: 'Alpha' }, { id: 'b', name: 'Beta' }], active: 'b' });
  const seen: any[] = [];
  const store = new ProfileStore({ request: api.request, onChange: (s) => seen.push(s) });
  const snap = await store.refresh();
  assert.equal(snap.profiles.length, 2);
  assert.equal(snap.active, 'b');
  assert.equal(store.activeProfile().name, 'Beta');
  assert.equal(seen.length, 1);
});

test('setActive switches and refreshes; create makes a profile then activates it', async () => {
  const api = fakeApi();
  const store = new ProfileStore({ request: api.request });
  await store.refresh();
  await store.setActive('p1');
  assert.equal(store.snapshot().active, 'p1');

  await store.create('Gamma');
  assert.ok(api.calls.some((c) => c.method === 'POST' && c.url === '/api/profiles'));
  assert.ok(api.calls.some((c) => /\/activate$/.test(c.url)), 'create activates the new profile');
  assert.ok(store.snapshot().profiles.some((p: any) => p.name === 'Gamma'));
});

test('rename, remove, export and import hit the right endpoints', async () => {
  const api = fakeApi();
  const store = new ProfileStore({ request: api.request });
  await store.refresh();
  await store.rename('p1', 'Renamed');
  assert.ok(store.snapshot().profiles.some((p: any) => p.name === 'Renamed'));

  const bundle = await store.exportProfile('p1');
  assert.equal(bundle.format, 'kudbee-profile');

  const imported = await store.importProfile(bundle);
  assert.equal(imported.id, 'imported1');
  assert.ok(store.snapshot().profiles.some((p: any) => p.id === 'imported1'));

  await store.remove('imported1');
  assert.ok(!store.snapshot().profiles.some((p: any) => p.id === 'imported1'));
});

test('a non-ok response surfaces the server error', async () => {
  const request = async () => { throw new Error('Profile not found: nope'); };
  const store = new ProfileStore({ request });
  await assert.rejects(() => store.refresh(), /Profile not found/);
});
