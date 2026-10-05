// The deterministic world the local-model eval runs in: a fake GitHub API and a tiny repository on disk. The facts here are the ones EVAL_TASKS (local-eval.ts) check.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { startFakeGithub, type FakeGithub } from './lookup-hooks.ts';

export const EVAL_REPO = 'Acme/widgets';
const pr = (number: number, o: Record<string, unknown> = {}) => ({ number, title: `PR ${number}`, state: 'closed', merged_at: '2026-10-04T10:00:00Z', draft: false, user: { login: 'dev' }, head: { ref: `feat/pr${number}` }, updated_at: '2026-10-04T10:00:00Z', html_url: `https://github.com/${EVAL_REPO}/pull/${number}`, ...o });
const open = (number: number) => pr(number, { state: 'open', merged_at: null });

export interface EvalWorld { github: FakeGithub; root: string; close: () => Promise<void> }

export async function startEvalWorld(): Promise<EvalWorld> {
  const github = await startFakeGithub({
    'pulls?': { body: [open(363), pr(362), open(361), pr(360)] },
    'actions/runs': { body: { workflow_runs: [{ name: 'CI', head_branch: 'feat/pr363', event: 'push', status: 'completed', conclusion: 'failure', run_number: 812, html_url: `https://github.com/${EVAL_REPO}/actions/runs/1`, updated_at: '2026-10-04T10:00:00Z' }] } },
    issues: { body: [] },
    branches: { body: [{ name: 'main', protected: true }, { name: 'feat/pr363' }] },
  });
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'local-eval-'));
  const w = (rel: string, text: string): void => { fs.mkdirSync(path.dirname(path.join(root, rel)), { recursive: true }); fs.writeFileSync(path.join(root, rel), text); };
  w('src/alpha.ts', 'export function alpha(x: number): number {\n  return x + 1;\n}\nexport function orphan() {\n  return 7;\n}\n');
  w('src/beta.ts', 'export const BETA_LIMIT = 42;\n');
  w('tests/alpha.test.ts', 'import { alpha } from "../src/alpha.ts";\ntest("alpha", () => alpha(1));\n');
  return { github, root, close: async () => { await github.close(); fs.rmSync(root, { recursive: true, force: true }); } };
}
