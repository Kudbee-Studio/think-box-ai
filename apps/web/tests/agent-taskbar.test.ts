// Behaviour for the taskbar agent list (public/js/agent-taskbar.js) over the agent registry.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { bootScripts } from './helpers/fake-dom.ts';

const jsDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../public/js');

function setup(): { win: any; doc: any; slot: any; bar: any } {
  const { win, doc } = bootScripts(jsDir, ['agent-registry.js', 'agent-taskbar.js']) as { win: any; doc: any };
  const taskbar = doc.createElement('div');
  taskbar.id = 'wm-taskbar';
  const slot = doc.createElement('div');
  slot.id = 'wm-taskbar-agents';
  slot.className = 'wm-taskbar-agents';
  taskbar.appendChild(slot);
  doc.body.appendChild(taskbar);
  const bar = new win.AgentTaskbar({ document: doc, window: win });
  bar.mount();
  return { win, doc, slot, bar };
}

test('the badge starts at 0 running and updates on agents:changed', () => {
  const { win, slot } = setup();
  const badge = (): any => slot.querySelector('.wm-agent-badge');
  assert.equal(badge().textContent, '0 running');
  win.agentRegistry.ingest({ type: 'run_update', data: { id: 'run-1', status: 'running', goal: 'Deploy' } });
  assert.equal(badge().textContent, '1 running');
  assert.equal(badge().classList.contains('is-running'), true);
  win.agentRegistry.ingest({ type: 'run_update', data: { id: 'run-2', status: 'running', goal: 'Report' } });
  assert.equal(badge().textContent, '2 running');
  win.agentRegistry.ingest({ type: 'run_update', data: { id: 'run-1', status: 'completed' } });
  assert.equal(badge().textContent, '1 running');
});

test('clicking the badge opens a dropdown listing agents; picking one dispatches agent:open', () => {
  const { win, slot } = setup();
  win.agentRegistry.ingest({ type: 'run_update', data: { id: 'run-1', status: 'running', goal: 'Deploy' } });
  slot.querySelector('.wm-agent-badge').click();
  const items = slot.querySelectorAll('.agent-menu-item');
  assert.equal(items.length, 1);
  assert.match(items[0].textContent, /Deploy · running/);
  assert.match(items[0].textContent, /run-1/);
  items[0].click();
  assert.equal(win.events.filter((e: any) => e.type === 'agent:open').length, 1);
  assert.equal(win.events.find((e: any) => e.type === 'agent:open').detail.id, 'run-1');
  assert.equal(slot.querySelector('.agent-menu'), null, 'the menu closes after picking');
});

test('the empty state shows when no agents are tracked, and Escape closes the menu', () => {
  const { doc, slot } = setup();
  slot.querySelector('.wm-agent-badge').click();
  assert.ok(slot.querySelector('.agent-menu-empty'));
  doc.dispatch('keydown', { key: 'Escape' });
  assert.equal(slot.querySelector('.agent-menu'), null);
});

test('agent status is reflected in the menu item class', () => {
  const { win, slot } = setup();
  win.agentRegistry.ingest({ type: 'run_update', data: { id: 'run-1', status: 'running', goal: 'Deploy' } });
  win.agentRegistry.ingest({ type: 'run_update', data: { id: 'run-2', status: 'failed', goal: 'Broken' } });
  slot.querySelector('.wm-agent-badge').click();
  const items = slot.querySelectorAll('.agent-menu-item');
  assert.ok(items.some((i: any) => i.classList.contains('agent-status-running')));
  assert.ok(items.some((i: any) => i.classList.contains('agent-status-failed')));
});

test('the badge shows the review count and carries has-review while a result waits for a human', () => {
  const { win, slot } = setup();
  win.agentRegistry.ingest({ type: 'run_update', data: { id: 'run-9', status: 'running', goal: 'Deploy' } });
  win.agentRegistry.list = () => [{ id: 'a', lane: 'review', status: 'completed' }];
  win.dispatchEvent(new win.CustomEvent('agents:changed', { detail: { agents: [{ id: 'a', lane: 'review', status: 'completed' }], runningCount: 0 } }));
  const badge = slot.querySelector('.wm-agent-badge');
  assert.match(badge.textContent, /1 to review/);
  assert.equal(badge.classList.contains('has-review'), true);
});
