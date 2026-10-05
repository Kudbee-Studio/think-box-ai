// Opt-in A/B (npm run test:live-token-ab): does adding a lesson to a local model's prompt change the eval result?
// Same model, same tasks, same fixture world as local-eval; only the system prompt differs between arms:
//   baseline  nothing added
//   lesson    ONE specific lesson, written from the failure that was actually observed (what a verified Think Token would carry)
//   control   a generic "be careful" lesson of the same size (guards against "any added text helps")
// Usage: node ... local-token-ab.live.ts <model> [--trials N]
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { newRunContext } from '../../agent.ts';
import { EVAL_TASKS, scoreTrial, type Trial } from '../../local-eval.ts';
import { lookupSpec, repoSpec, runLocalToolLoop, type LoopSpec } from '../../local-tools.ts';
import { createModelClients } from '../../ollama-client.ts';
import { writeEvidence } from '../helpers/evidence-file.ts';
import { EVAL_REPO, startEvalWorld } from '../helpers/local-eval-fixture.ts';
import { lookupHooks } from '../helpers/lookup-hooks.ts';

const here = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const model = args.find((a) => !a.startsWith('--')) ?? 'qwen2.5:3b';
const ti = args.indexOf('--trials');
const trials = Math.max(1, Number(ti < 0 ? 6 : args[ti + 1]));

const LESSONS: Record<string, { task: string; lesson: string; control: string }> = {
  'untested-function': {
    task: 'untested-function',
    lesson: 'A claim that a function has no test is only accepted with a search that was run in the tests folder. Run repo_search with the exact function name and path "tests", then pass that same query and path "tests" as absence_search. A search over src proves nothing about tests.',
    control: 'Be careful and double check your work before reporting. Prefer accurate answers over fast ones and make sure every statement you make is correct.',
  },
  ci: {
    task: 'ci',
    lesson: 'For a question about CI, call live_lookup with recipe ci_status first, then answer in one sentence that states the run number and its conclusion exactly as the tool returned them. Do not mention branches or workflows the tool did not list.',
    control: 'Be careful and double check your work before answering. Prefer accurate answers over fast ones and make sure every statement you make is correct.',
  },
};

const withLesson = <E>(spec: LoopSpec<E>, text: string | null): LoopSpec<E> => text ? { ...spec, system: `${spec.system}\nLEARNED LESSON: ${text}`, constrainedSystem: `${spec.constrainedSystem}\nLEARNED LESSON: ${text}` } : spec;

const world = await startEvalWorld();
process.env.KUDBEE_REPO = EVAL_REPO; process.env.KUDBEE_GITHUB_API = world.github.url; process.env.KUDBEE_REPO_ROOT = world.root;
const clients = createModelClients({ ollamaBaseUrl: process.env.OLLAMA_BASE_URL || 'http://127.0.0.1:11434', janusBaseUrl: 'http://127.0.0.1:9', janusEnabled: () => false });
const rows: Array<Trial & { arm: string }> = [];
for (const key of Object.keys(LESSONS)) {
  const task = EVAL_TASKS.find((t) => t.id === LESSONS[key]!.task)!;
  for (const arm of ['baseline', 'lesson', 'control'] as const) {
    const text = arm === 'baseline' ? null : arm === 'lesson' ? LESSONS[key]!.lesson : LESSONS[key]!.control;
    for (let n = 1; n <= trials; n += 1) {
      const h = lookupHooks(task.class === 'repo' ? { allowedTools: ['repo_search', 'repo_read'] } : {});
      const result = task.class === 'repo'
        ? await runLocalToolLoop({ model, goal: task.goal, hooks: h.hooks, context: newRunContext(), chat: clients, repo: null, spec: withLesson(repoSpec(), text), maxSteps: 4 })
        : await runLocalToolLoop({ model, goal: task.goal, hooks: h.hooks, context: newRunContext(), chat: clients, repo: EVAL_REPO, spec: withLesson(lookupSpec(EVAL_REPO), text), maxSteps: 3 });
      const t = scoreTrial(task, result);
      rows.push({ ...t, arm });
      console.log(`${task.id.padEnd(18)} ${arm.padEnd(8)} #${n} ${t.outcome.padEnd(10)} ${t.latency_ms}ms :: ${t.why.slice(0, 90)}`);
    }
  }
}
await world.close();
const table = Object.keys(LESSONS).flatMap((key) => (['baseline', 'lesson', 'control'] as const).map((arm) => {
  const g = rows.filter((r) => r.task === key && r.arm === arm); const c = (o: string) => g.filter((r) => r.outcome === o).length;
  return { task: key, arm, trials: g.length, pass: c('pass'), wrong: c('wrong'), ungrounded: c('ungrounded'), failed: c('failed') };
}));
console.log('\n| Task | Arm | Trials | Pass | Wrong | Ungrounded | Failed |\n|---|---|---|---|---|---|---|');
for (const r of table) console.log(`| ${r.task} | ${r.arm} | ${r.trials} | ${r.pass} | ${r.wrong} | ${r.ungrounded} | ${r.failed} |`);
const out = path.resolve(here, '../../../../docs/evidence/model-integration/local-token-ab.json');
await writeEvidence(path.dirname(out), out, { generated_at: new Date().toISOString(), model, trials_per_arm: trials, source: 'real Ollama against the deterministic fixture world; lessons written by hand from the observed failure (not stored Think Tokens)', lessons: LESSONS, table, trials: rows });
process.exit(0);
