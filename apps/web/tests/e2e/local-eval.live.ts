// Opt-in measurement (npm run test:live-eval): REAL Ollama models run the deterministic eval suite (local-eval.ts) against the fixture world
// (fake GitHub API + a tiny repo on disk; no network beyond localhost, no cost). Appends to docs/evidence/model-integration/local-eval.json and prints the table.
// Usage: node ... local-eval.live.ts [model ...] [--trials N] [--only lookup|repo]
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { newRunContext } from '../../agent.ts';
import { EVAL_TASKS, renderTable, scoreTrial, summarize, type Trial } from '../../local-eval.ts';
import { lookupSpec, repoSpec, runLocalToolLoop } from '../../local-tools.ts';
import { createModelClients } from '../../ollama-client.ts';
import { readJsonIfPresent, writeEvidence } from '../helpers/evidence-file.ts';
import { EVAL_REPO, startEvalWorld } from '../helpers/local-eval-fixture.ts';
import { lookupHooks } from '../helpers/lookup-hooks.ts';

const here = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const flag = (name: string): string | undefined => { const i = args.indexOf(name); return i < 0 ? undefined : args[i + 1]; };
const trials = Math.max(1, Number(flag('--trials') ?? 2));
const only = flag('--only');
const models = args.filter((a, i) => !a.startsWith('--') && !(i > 0 && args[i - 1]!.startsWith('--')));
const chosen = models.length ? models : ['qwen2.5:3b', 'gemma3:4b'];
const tasks = EVAL_TASKS.filter((t) => !only || t.class === only);

const world = await startEvalWorld();
process.env.KUDBEE_REPO = EVAL_REPO; process.env.KUDBEE_GITHUB_API = world.github.url; process.env.KUDBEE_REPO_ROOT = world.root;
const clients = createModelClients({ ollamaBaseUrl: process.env.OLLAMA_BASE_URL || 'http://127.0.0.1:11434', janusBaseUrl: 'http://127.0.0.1:9', janusEnabled: () => false });
const out = path.resolve(here, '../../../../docs/evidence/model-integration/local-eval.json');
const all: Trial[] = [];
for (const model of chosen) {
  for (const task of tasks) {
    for (let n = 1; n <= trials; n += 1) {
      const h = lookupHooks(task.class === 'repo' ? { allowedTools: ['repo_search', 'repo_read'] } : {});
      const result = task.class === 'repo'
        ? await runLocalToolLoop({ model, goal: task.goal, hooks: h.hooks, context: newRunContext(), chat: clients, repo: null, spec: repoSpec(), maxSteps: 4 })
        : await runLocalToolLoop({ model, goal: task.goal, hooks: h.hooks, context: newRunContext(), chat: clients, repo: EVAL_REPO, spec: lookupSpec(EVAL_REPO), maxSteps: 3 });
      const t = scoreTrial(task, result);
      all.push(t);
      console.log(`${t.outcome.padEnd(10)} ${model} ${task.id} #${n} ${t.latency_ms}ms tools=${t.tool_calls} :: ${t.why.slice(0, 110)}`);
    }
  }
}
await world.close();
const prev = readJsonIfPresent<{ trials?: Trial[] }>(out, { trials: [] });
const merged = [...(prev.trials ?? []).filter((p) => !chosen.includes(p.model)), ...all];
const summary = summarize(merged);
console.log(`\n${renderTable(summary)}`);
await writeEvidence(path.dirname(out), out, { generated_at: new Date().toISOString(), source: 'real Ollama against the deterministic fixture world (fake GitHub API, tiny repo); no cost', trials_per_task: trials, summary, table: renderTable(summary), trials: merged });
process.exit(0);
