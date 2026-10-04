import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { agentRoute, escalatedRoute, localChatRoute, recipeRoute, refusedRoute, routeLabel } from '../route-decision.ts';

// The dashboard file is a classic script: run it the way a browser does and read what it puts on window.
const win: Record<string, any> = {};
vm.runInNewContext(fs.readFileSync(new URL('../public/js/route-label.js', import.meta.url), 'utf8'), { window: win, globalThis: win });
const browser = win as { routeLabel: (r: unknown) => string };

describe('route decision', () => {
  const all = [
    recipeRoute('smollm2:360m', 'latest_pr', 'latest pull request (any state)'),
    localChatRoute('smollm2:360m'),
    agentRoute('mercury-2'),
    escalatedRoute('smollm2:360m', 'mercury-2', 'it asks about live state'),
    refusedRoute('smollm2:360m', 'no worker agent is configured'),
  ];
  it('says the same thing for every path in the server, the CLI and the dashboard', () => {
    assert.deepEqual(all.map(routeLabel), [
      'route: recipe · smollm2:360m · latest_pr',
      'route: local chat · smollm2:360m',
      'route: worker agent · mercury-2',
      'route: escalated · smollm2:360m → mercury-2',
      'route: refused · no model',
    ]);
    for (const r of all) assert.equal(browser.routeLabel(r), routeLabel(r));
  });
  it('always carries a reason, and an escalation names both models', () => {
    for (const r of all) assert.ok(r.reason.length > 10, r.path);
    const e = all[3]!;
    assert.equal(e.requested_model, 'smollm2:360m');
    assert.match(e.reason, /live state; a local chat has no tools/);
  });
  it('shows nothing for a missing or malformed record', () => {
    for (const bad of [undefined, null, 'x', 7, {}, { path: 'nope' }, { path: '__proto__' }]) {
      assert.equal(routeLabel(bad), '');
      assert.equal(browser.routeLabel(bad), '');
    }
  });
});
