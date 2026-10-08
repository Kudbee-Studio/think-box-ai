// The sandbox caps a check's memory: a check that allocates without end is stopped by the limit instead of eating the machine. The probe stops by itself at 1.6 GB, so a missing limit
// cannot hurt the host. (A fork bomb is deliberately NOT run: without a cgroup it can freeze the machine, which is why it is documented as not mitigated.)
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { after, before, describe, it } from 'node:test';
import { probeSandbox, runScratch } from '../scratch-runner.ts';

const HOG = `
const chunks = []; let mb = 0;
try { while (mb < 1600) { chunks.push(Buffer.alloc(32 * 1024 * 1024, 1)); mb += 32; } console.log('REACHED_STOP ' + mb); } catch (e) { console.log('MEMORY_LIMIT_HIT_AT ' + mb); }
`;
describe('sandbox resource limits', async () => {
  const probe = await probeSandbox(); const skip = probe.ok ? false : `no proven sandbox here: ${(probe as { reason: string }).reason}`;
  let repo = ''; const gitq = (...a: string[]): string => execFileSync('git', a, { cwd: repo, encoding: 'utf8' }).trim();
  before(() => {
    repo = fs.mkdtempSync(path.join(os.tmpdir(), 'sandbox-limits-'));
    const w = (rel: string, text: string): void => { fs.mkdirSync(path.dirname(path.join(repo, rel)), { recursive: true }); fs.writeFileSync(path.join(repo, rel), text); };
    w('package.json', JSON.stringify({ name: 'limits', scripts: { lint: 'node scripts/hog.js', typecheck: 'node -e "console.log(\'quiet ok\')"' } })); w('scripts/hog.js', HOG);
    gitq('init', '-q', '-b', 'main'); gitq('add', '-A'); execFileSync('git', ['-c', 'user.email=t@t', '-c', 'user.name=t', 'commit', '-qm', 'fixture'], { cwd: repo });
  });
  after(() => fs.rmSync(repo, { recursive: true, force: true }));

  it('a check that allocates without end hits the memory limit long before the probe\'s own stop', { skip }, async () => {
    const report = await runScratch({ repoRoot: repo, ref: 'main', checks: [{ check: 'lint' }], memoryLimitBytes: 2 * 1024 ** 3 });
    const out = report.checks[0]!.output_tail; assert.match(out, /MEMORY_LIMIT_HIT_AT \d+/, out);
    assert.ok(Number(/MEMORY_LIMIT_HIT_AT (\d+)/.exec(out)![1]) < 1600);
  });

  it('an ordinary check still runs under the default limit', { skip }, async () => {
    const report = await runScratch({ repoRoot: repo, ref: 'main', checks: [{ check: 'typecheck' }] });
    assert.equal(report.checks[0]!.exit_code, 0); assert.match(report.checks[0]!.output_tail, /quiet ok/);
  });
});
