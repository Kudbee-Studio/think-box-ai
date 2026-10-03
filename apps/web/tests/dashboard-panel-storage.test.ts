// Header panels keep state in localStorage. Corrupt, wrong-shaped or blocked storage must not stop a panel from being created
// (a throw in its DOMContentLoaded handler left the header button dead).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const js = path.join(path.dirname(fileURLToPath(import.meta.url)), '../public/js');
const PANELS: Array<[file: string, instance: string]> = [
  ['approval-workflow.js', 'approvalWorkflow'],
  ['performance-analytics.js', 'performanceAnalytics'],
  ['execution-logs.js', 'executionLogs'],
  ['integration-connectors.js', 'integrationConnectors'],
  ['collaboration-dashboard.js', 'collaborationDashboard'],
  ['settings-panel.js', 'settingsPanel'],
];

// An object that tolerates any property read or call, standing in for the DOM.
function anything(own: Record<string, unknown> = {}): any {
  return new Proxy(function () {}, {
    get: (_t, p) => (typeof p === 'symbol' ? undefined : p in own ? own[p] : p === 'length' ? 0 : anything()),
    apply: () => anything(),
    construct: () => anything(),
    set: () => true,
  });
}

function load(file: string, storage: { getItem(key: string): string | null; setItem(): void }): Record<string, unknown> {
  const handlers: Array<() => void> = [];
  const document = anything({ addEventListener: (type: string, fn: () => void) => { if (type === 'DOMContentLoaded') handlers.push(fn); } });
  const window: Record<string, unknown> = { addEventListener() {}, removeEventListener() {}, dispatchEvent() {}, matchMedia: () => anything() };
  const sandbox: Record<string, unknown> = { window, document, localStorage: storage, console: { log() {}, warn() {}, error() {} }, setTimeout: () => 0, setInterval: () => 0, navigator: anything(), Notification: anything(), CustomEvent: anything(), Event: anything() };
  vm.createContext(sandbox);
  for (const f of ['enterprise.js', file]) vm.runInContext(fs.readFileSync(path.join(js, f), 'utf8'), sandbox, { filename: f });
  for (const h of handlers) h();
  return window;
}

const modes: Array<[string, { getItem(key: string): string | null; setItem(): void }]> = [
  ['corrupt JSON', { getItem: () => '{not valid json', setItem() {} }],
  ['valid JSON of the wrong shape (null)', { getItem: () => 'null', setItem() {} }],
  ['storage that throws (blocked)', { getItem: () => { throw new Error('SecurityError'); }, setItem() {} }],
];

for (const [file, instance] of PANELS) {
  for (const [label, storage] of modes) {
    test(`${file} still starts when localStorage holds ${label}`, () => {
      const win = load(file, storage);
      assert.ok(win[instance], `${instance} was not created`);
    });
  }
}
