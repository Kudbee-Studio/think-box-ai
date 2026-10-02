// P3.11 parity: the kudbee CLI and the dashboard terminal must not drift apart without someone deciding so (apps/web/command-parity.ts).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { CORE, MAX_GAPS, PARITY } from '../command-parity.ts';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const cliSrc = fs.readFileSync(path.join(root, 'cli.ts'), 'utf8');
const dashSrc = fs.readFileSync(path.join(root, 'public/js/app.js'), 'utf8');
const commands = (src: string): Set<string> => new Set([...src.matchAll(/case '(\/[a-z]+)'/g)].map((m) => m[1]!));
const cli = commands(cliSrc);
const dash = commands(dashSrc);

test('every slash command on either surface is declared in the parity map, and the map names no command that no longer exists', () => {
  const all = new Set([...cli, ...dash]);
  const undeclared = [...all].filter((c) => !(c in PARITY));
  assert.deepEqual(undeclared, [], `new command(s) without a parity entry (add them to apps/web/command-parity.ts): ${undeclared}`);
  const stale = Object.keys(PARITY).filter((c) => !all.has(c));
  assert.deepEqual(stale, [], `parity entries for commands that no longer exist: ${stale}`);
});

test('"both" commands exist on both surfaces; one-sided commands exist only where declared; claimed counterparts are present in the other surface\'s source', () => {
  for (const [name, p] of Object.entries(PARITY)) {
    if (p.kind === 'both') assert.ok(cli.has(name) && dash.has(name), `${name} is declared "both" but is missing on ${cli.has(name) ? 'the dashboard' : 'the CLI'}`);
    else if (p.kind === 'counterpart') {
      assert.ok(p.side === 'cli' ? cli.has(name) && !dash.has(name) : dash.has(name) && !cli.has(name), `${name} must exist only on the ${p.side}`);
      assert.ok((p.side === 'cli' ? dashSrc : cliSrc).includes(p.proof), `${name}: counterpart "${p.what}" not found (looked for ${p.proof})`);
    } else assert.ok(cli.has(name) !== dash.has(name), `${name} is declared one-sided but exists on ${cli.has(name) && dash.has(name) ? 'both' : 'neither'} surface(s): update the map`);
  }
});

test('the capabilities the founder named are implemented on both surfaces', () => {
  for (const c of CORE) {
    assert.ok(cliSrc.includes(c.cli), `CLI lacks "${c.capability}" (${c.cli})`);
    const dashAll = dashSrc + fs.readFileSync(path.join(root, 'public/js/think-token-dashboard.js'), 'utf8');
    assert.ok(dashAll.includes(c.dashboard), `dashboard lacks "${c.capability}" (${c.dashboard})`);
  }
});

test('known gaps may only shrink', () => {
  const gaps = Object.entries(PARITY).filter(([, p]) => p.kind === 'gap').map(([n]) => n);
  assert.ok(gaps.length <= MAX_GAPS, `gaps grew to ${gaps.length} (${gaps})`);
  assert.ok(gaps.length >= MAX_GAPS - 0, `a gap was closed: lower MAX_GAPS to ${gaps.length} in command-parity.ts so the ratchet stays tight`);
});
