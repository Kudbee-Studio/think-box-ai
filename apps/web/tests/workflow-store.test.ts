// Unit tests for the workflow store (public/js/workflow-store.js): save/update, list, get, delete, corrupt-safe reads and plan composition.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const src = fs.readFileSync(path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../public/js/workflow-store.js'), 'utf8');
const sandbox: Record<string, unknown> = {};
vm.createContext(sandbox);
vm.runInContext(src, sandbox, { filename: 'workflow-store.js' });
const Store = sandbox.WorkflowStore as {
  PREFIX: string;
  keyFor(id: string): string;
  genId(): string;
  normalize(raw: unknown): Record<string, unknown> | null;
  listWorkflows(storage: unknown): Array<Record<string, unknown>>;
  getWorkflow(storage: unknown, id: string): Record<string, unknown> | null;
  saveWorkflow(storage: unknown, raw: unknown): Record<string, unknown> | null;
  deleteWorkflow(storage: unknown, id: string): boolean;
  composeGoal(wf: unknown): string;
};

class FakeStorage {
  private m: Record<string, string> = {};
  get length(): number { return Object.keys(this.m).length; }
  key(i: number): string | null { return Object.keys(this.m)[i] ?? null; }
  getItem(k: string): string | null { return k in this.m ? this.m[k] : null; }
  setItem(k: string, v: string): void { this.m[k] = String(v); }
  removeItem(k: string): void { delete this.m[k]; }
}

const wf = (over: Record<string, unknown> = {}) => ({ name: 'Deploy', description: 'ship it', nodes: [{ type: 'sequential', name: 'build' }, { type: 'parallel', name: 'test' }], ...over });

test('saveWorkflow assigns an id and timestamps and getWorkflow reads it back', () => {
  const s = new FakeStorage();
  const saved = Store.saveWorkflow(s, wf({ created_at: '2020-01-01T00:00:00.000Z' }))!;
  assert.match(String(saved.id), /^workflow-\d+-[a-z0-9]+$/);
  assert.equal(saved.name, 'Deploy');
  assert.equal(saved.created_at, '2020-01-01T00:00:00.000Z');
  assert.ok(typeof saved.updated_at === 'string' && saved.updated_at);
  assert.equal(s.getItem(Store.keyFor(String(saved.id))) !== null, true);
  assert.equal(Store.getWorkflow(s, String(saved.id))!.description, 'ship it');
});

test('updating an existing id keeps created_at and rewrites the same key', () => {
  const s = new FakeStorage();
  const first = Store.saveWorkflow(s, wf({ created_at: '2020-01-01T00:00:00.000Z' }))!;
  const before = s.length;
  const second = Store.saveWorkflow(s, { id: first.id, name: 'Deploy v2', nodes: [{ type: 'loop', name: 'retry' }] })!;
  assert.equal(second.id, first.id);
  assert.equal(second.created_at, first.created_at);
  assert.equal(second.name, 'Deploy v2');
  assert.equal(s.length, before, 'no new key was created');
});

test('listWorkflows returns saved records newest-first and skips corrupt entries', () => {
  const s = new FakeStorage();
  const a = Store.saveWorkflow(s, wf({ name: 'A' }))!;
  Store.saveWorkflow(s, wf({ name: 'B' }));
  // Force an ordering that does not depend on same-millisecond timestamps.
  const ra = JSON.parse(s.getItem(Store.keyFor(String(a.id)))!);
  ra.updated_at = '2020-01-01T00:00:00.000Z';
  s.setItem(Store.keyFor(String(a.id)), JSON.stringify(ra));
  s.setItem(Store.keyFor('broken'), '{not json');
  s.setItem('unrelated:key', 'x');
  const list = Store.listWorkflows(s);
  assert.equal(list.map((w) => w.name).join(','), 'B,A');
});

test('normalize drops a workflow with no name, clamps unknown node types and drops non-object nodes', () => {
  assert.equal(Store.normalize({ nodes: [] }), null);
  const rec = Store.normalize({ name: 'X', junk: 1, nodes: [{ type: 'nope', name: 'a' }, 'bad', null] })!;
  assert.equal('junk' in rec, false);
  assert.equal((rec.nodes as Array<{ type: string }>).length, 1);
  assert.equal((rec.nodes as Array<{ type: string }>)[0].type, 'sequential');
});

test('getWorkflow on a missing or corrupt key returns null', () => {
  const s = new FakeStorage();
  assert.equal(Store.getWorkflow(s, 'nope'), null);
  s.setItem(Store.keyFor('bad'), 'not json');
  assert.equal(Store.getWorkflow(s, 'bad'), null);
});

test('deleteWorkflow removes the entry', () => {
  const s = new FakeStorage();
  const saved = Store.saveWorkflow(s, wf())!;
  assert.equal(Store.deleteWorkflow(s, String(saved.id)), true);
  assert.equal(Store.getWorkflow(s, String(saved.id)), null);
  assert.equal(Store.deleteWorkflow(s, 'missing'), true);
});

test('composeGoal turns a workflow into a plain-text plan with every step', () => {
  const plan = Store.composeGoal(wf());
  assert.match(plan, /Run this saved workflow: Deploy/);
  assert.match(plan, /ship it/);
  assert.match(plan, /1\. \[sequential\] build/);
  assert.match(plan, /2\. \[parallel\] test/);
  assert.match(plan, /Execute the steps in order/);
  assert.equal(Store.composeGoal(null), '');
});

test('listWorkflows on a storage without key()/length returns empty instead of throwing', () => {
  assert.equal(Store.listWorkflows({ getItem: () => null }).length, 0);
  assert.equal(Store.listWorkflows(null).length, 0);
});
