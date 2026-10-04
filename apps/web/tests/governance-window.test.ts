// Behaviour for the governance window (public/js/governance-window.js): open/refresh/close and the approval buttons.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { bootScripts } from './helpers/fake-dom.ts';

const jsDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../public/js');

function setup(): { win: any; doc: any; gw: any } {
  const { win, doc } = bootScripts(jsDir, ['agent-registry.js', 'governance-window.js']) as { win: any; doc: any };
  const gw = new win.GovernanceWindow({ document: doc, window: win });
  gw.mount();
  return { win, doc, gw };
}

function running(win: any, id = 'run-1', goal = 'Deploy'): void {
  win.agentRegistry.ingest({ type: 'run_update', data: { id, status: 'running', goal, current_step: 2 } });
}

test('open returns false for an unknown agent and creates nothing', () => {
  const { doc, gw } = setup();
  assert.equal(gw.open('nope'), false);
  assert.equal(doc.getElementById('governance-nope'), null);
});

test('open builds a window-manager-compatible modal with the agent fields and an approval', () => {
  const { win, doc, gw } = setup();
  running(win);
  win.agentRegistry.ingest({ type: 'approval_request', data: { id: 'ap1', reason: 'overwrite file' } });
  assert.equal(gw.open('run-1'), true);
  const el = doc.getElementById('governance-run-1');
  assert.ok(el);
  assert.equal(el.classList.contains('modal-backdrop'), true, 'the window manager adopts .modal-backdrop');
  assert.equal(el.classList.contains('governance-window'), true);
  assert.equal(el.querySelector('.gov-title').textContent, 'Agent run-1');
  const rows = el.querySelectorAll('.gov-row');
  const value = (label: string) => rows.find((r: any) => r.children[0].textContent === label)?.children[1].textContent;
  assert.equal(value('Goal'), 'Deploy');
  assert.equal(value('Status'), 'running');
  assert.match(el.querySelector('.gov-approval-text').textContent, /Approval required: overwrite file/);
  assert.ok(el.querySelector('.gov-approve'));
  assert.ok(el.querySelector('.gov-reject'));
});

test('Approve dispatches approval:resolved and clears the pending flag', () => {
  const { win, doc, gw } = setup();
  running(win);
  win.agentRegistry.ingest({ type: 'approval_request', data: { id: 'ap1', reason: 'overwrite' } });
  gw.open('run-1');
  doc.getElementById('governance-run-1').querySelector('.gov-approve').click();
  const resolved = win.events.find((e: any) => e.type === 'approval:resolved');
  assert.ok(resolved);
  assert.deepEqual({ ...resolved.detail }, { id: 'ap1', approved: true });
  assert.equal(win.agentRegistry.get('run-1').approval_pending, false);
});

test('Reject dispatches approval:resolved with approved:false', () => {
  const { win, doc, gw } = setup();
  running(win);
  win.agentRegistry.ingest({ type: 'approval_request', data: { id: 'ap2', reason: 'delete' } });
  gw.open('run-1');
  doc.getElementById('governance-run-1').querySelector('.gov-reject').click();
  const resolved = win.events.find((e: any) => e.type === 'approval:resolved');
  assert.equal(resolved.detail.approved, false);
  assert.equal(resolved.detail.id, 'ap2');
});

test('the window refreshes live as agents:changed arrives', () => {
  const { win, doc, gw } = setup();
  running(win, 'run-1', 'Deploy');
  gw.open('run-1');
  win.agentRegistry.ingest({ type: 'run_update', data: { id: 'run-1', status: 'running', goal: 'Deploy v2' } });
  const el = doc.getElementById('governance-run-1');
  const rows = el.querySelectorAll('.gov-row');
  const goalRow = rows.find((r: any) => r.children[0].textContent === 'Goal');
  assert.equal(goalRow.children[1].textContent, 'Deploy v2');
});

test('a Think Box renders as a token tree when no cube renderer is present', () => {
  const { win, doc, gw } = setup();
  running(win);
  win.agentRegistry.ingest({ type: 'think_token_cube', data: { thinkBoxId: 'box-7', tokens: [1, 2] } });
  gw.open('run-1');
  const el = doc.getElementById('governance-run-1');
  const tree = el.querySelector('.gov-thinkbox-tree');
  assert.ok(tree);
  const text = tree.querySelectorAll('li').map((li: any) => li.textContent).join(' ');
  assert.match(text, /box-7/);
});

test('close removes the window', () => {
  const { win, doc, gw } = setup();
  running(win);
  gw.open('run-1');
  assert.ok(doc.getElementById('governance-run-1'));
  gw.close('run-1');
  assert.equal(doc.getElementById('governance-run-1'), null);
});
