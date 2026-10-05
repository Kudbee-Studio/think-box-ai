// The frozen world and goal set for the Think Token A/B (docs/evidence/p3.24-ab/PLAN.md): the eval world's fake GitHub plus five repo modules,
// each with one function that has a test and one that does not. Goals are NOT the phrasings the earlier eval or the hand-written lessons used.
import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
import type { LocalToolResult } from '../../local-tools.ts';
import { EVAL_TASKS } from '../../local-eval.ts';
import { startEvalWorld, type EvalWorld } from './local-eval-fixture.ts';

const MODULES = [
  { file: 'billing', tested: 'chargeCard', untested: 'refundCard', constant: 'MAX_RETRIES', value: '3' },
  { file: 'cache', tested: 'getCache', untested: 'purgeCache', constant: 'TTL_SECONDS', value: '300' },
  { file: 'auth', tested: 'login', untested: 'rotateKey', constant: 'TOKEN_BITS', value: '256' },
  { file: 'queue', tested: 'enqueue', untested: 'drainAll', constant: 'QUEUE_DEPTH', value: '64' },
  { file: 'render', tested: 'draw', untested: 'flushFrame', constant: 'FRAME_MS', value: '16' },
] as const;
const MISSING = ['chargeBitcoin', 'purgeEverything', 'rotateMoon', 'drainOcean', 'flushToilet'] as const;

export async function startAbWorld(): Promise<EvalWorld> {
  const world = await startEvalWorld();
  const w = (rel: string, text: string): void => { fs.mkdirSync(path.dirname(path.join(world.root, rel)), { recursive: true }); fs.writeFileSync(path.join(world.root, rel), text); };
  for (const m of MODULES) {
    w(`src/${m.file}.ts`, `export const ${m.constant} = ${m.value};\nexport function ${m.tested}(x: number): number {\n  return x + 1;\n}\nexport function ${m.untested}(x: number): number {\n  return x - 1;\n}\n`);
    w(`tests/${m.file}.test.ts`, `import { ${m.tested} } from "../src/${m.file}.ts";\ntest("${m.tested}", () => ${m.tested}(1));\n`);
  }
  return world;
}

export interface AbGoal { id: string; class: 'lookup' | 'repo'; goal: string; check: (r: LocalToolResult<any>) => { ok: boolean; why: string } }
const has = (t: string | undefined, re: RegExp): boolean => re.test(t ?? '');
const lookup = (base: string, goals: string[]): AbGoal[] => goals.map((goal, i) => ({ id: `${base}-${i + 1}`, class: 'lookup' as const, goal, check: EVAL_TASKS.find((t) => t.id === base)!.check }));

export const AB_GOALS: AbGoal[] = [
  ...lookup('last-pr', ['Show me the most recent pull request.', 'Which PR is the newest one, and what state is it in?', 'Tell me about the latest PR in this repo.']),
  ...lookup('open-prs', ['List the open PRs.', 'What PRs are still open right now?', 'Give me every pull request that has not been merged or closed.']),
  ...lookup('ci', ['Is CI green?', 'What was the result of the latest CI run?', 'Did the most recent workflow run succeed?']),
  ...lookup('branches', ['List the repository branches.', 'Which branches does the repo have?', 'Name all the branches.']),
  ...lookup('no-issues', ['How many issues are open?', 'Is anything in the issue tracker still open?', 'Do we have unresolved issues?']),
  ...MODULES.map((m) => ({ id: `untested-${m.file}`, class: 'repo' as const, goal: `Find an exported function in src/${m.file}.ts that has no test.`, check: (r: LocalToolResult<any>) => r.finding?.found && r.finding.file === `src/${m.file}.ts` && String(r.finding.quote ?? '').includes(m.untested) ? { ok: true, why: `${m.untested} in src/${m.file}.ts` } : { ok: false, why: `reported ${r.finding?.found ? `${r.finding.file}: ${String(r.finding.quote ?? '').slice(0, 40)}` : 'nothing'}` } })),
  ...MODULES.map((m) => ({ id: `constant-${m.file}`, class: 'repo' as const, goal: `Which file defines ${m.constant} and what is its value?`, check: (r: LocalToolResult<any>) => r.finding?.found && r.finding.file === `src/${m.file}.ts` && has(r.finding.quote, new RegExp(`\\b${m.value}\\b`)) ? { ok: true, why: `src/${m.file}.ts = ${m.value}` } : { ok: false, why: `reported ${r.finding?.found ? r.finding.file : 'nothing'}` } })),
  ...MISSING.map((name) => ({ id: `missing-${name}`, class: 'repo' as const, goal: `Find a function named ${name}.`, check: (r: LocalToolResult<any>) => r.finding && r.finding.found === false ? { ok: true, why: 'reported that it does not exist' } : { ok: false, why: 'invented a finding for a function that is not there' } })),
];

/** Fingerprint of the frozen goal set (ids and wording, not the check functions); recorded in the raw results and in PLAN.md. */
export const goalsHash = (): string => createHash('sha256').update(JSON.stringify(AB_GOALS.map((g) => [g.id, g.class, g.goal]))).digest('hex');
