// Opt-in grounding AUDIT (npm run test:live-grounding-audit): real models answer real lookups against the REAL GitHub repo, and every verdict of the grounding
// validator is recorded next to the raw evidence so it can be adjudicated by hand (false alarm: a correct answer rejected; false pass: a wrong answer accepted).
// The full evidence is stored so any verdict can be replayed exactly. Models: mercury-2 through the worker agent (the key is loaded from the repo .env by code and never printed; spend is tiny and capped), gemma3:4b and qwen2.5:3b
// through the local tool loop. Appends one JSON row per run to docs/evidence/p3.30-grounding-audit/runs.jsonl (nothing is edited afterwards).
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { newRunContext, runToolAgent } from '../../agent.ts';
import { validateGrounding } from '../../grounding.ts';
import type { LookupEvidence } from '../../live-lookup.ts';
import { lookupSpec, runLocalToolLoop } from '../../local-tools.ts';
import { createModelClients } from '../../ollama-client.ts';
import { writeConfined } from '../../workspace-fs.ts';
import { lookupHooks } from '../helpers/lookup-hooks.ts';

const here = path.dirname(fileURLToPath(import.meta.url));
for (const p of [path.resolve(here, '../../.env'), path.resolve(here, '../../../../.env')]) { try { process.loadEnvFile(p); } catch { /* none here */ } }
const REPO = 'Kudbee-Studio/think-box-ai';
process.env.KUDBEE_REPO = REPO; delete process.env.KUDBEE_GITHUB_API;
const out = path.resolve(here, '../../../../docs/evidence/p3.30-grounding-audit/runs.jsonl');
fs.mkdirSync(path.dirname(out), { recursive: true });
const written: string[] = [];
const oneLine = (t: unknown): string => String(t ?? '').replace(/\r?\n|\r/g, ' ');
const GOALS = [
  'What is the last PR?', 'Who wrote the newest pull request and when was it updated?', 'Tell me about the three most recent PRs.', 'Is PR 367 merged?',
  'Are any pull requests still open?', 'Which pull requests are drafts?', 'Did the last CI run pass?', 'What is the status of the latest workflow run?',
  'What branches exist?', 'How many branches are there, and is main protected?', 'Are there any open issues?', 'How many issues are open?',
];
const models = process.argv.slice(2).filter((a) => !a.startsWith('--')); const chosen = models.length ? models : ['mercury-2', 'gemma3:4b', 'qwen2.5:3b'];
const clients = createModelClients({ ollamaBaseUrl: process.env.OLLAMA_BASE_URL || 'http://127.0.0.1:11434', janusBaseUrl: 'http://127.0.0.1:9', janusEnabled: () => false });
if (chosen.includes('mercury-2') && !process.env.INCEPTION_API_KEY) { console.error('mercury-2 requested but no INCEPTION_API_KEY is configured; refusing to run it'); process.exit(2); }
let n = 0;
for (const model of chosen) for (const goal of GOALS) {
  const evidence: LookupEvidence[] = [];
  const { hooks } = lookupHooks({ allowedTools: ['live_lookup'] });
  hooks.onToolOutput = (name, _a, o) => { if (name === 'live_lookup' && o.ok === true && (o as { evidence?: LookupEvidence }).evidence) evidence.push((o as { evidence: LookupEvidence }).evidence); };
  const t0 = Date.now(); let answer = ''; let cost = 0; let failure: string | null = null;
  try {
    if (model === 'mercury-2') {
      const r = await runToolAgent(goal, model, 4, 0.2, [], hooks);
      cost = r.cost_usd; if (r.success) answer = r.result ?? ''; else failure = r.error ?? 'agent failed';
    } else {
      const r = await runLocalToolLoop({ model, goal, hooks, context: newRunContext(), chat: clients, repo: REPO, spec: lookupSpec(REPO), maxSteps: 3 });
      if (r.success) answer = r.answer ?? ''; else failure = `${r.failure?.kind}: ${r.failure?.message}`;
    }
  } catch (e) { failure = String((e as Error).message ?? e).slice(0, 300); }
  const g = answer && evidence.length ? validateGrounding(answer, evidence, { goal }) : null;
  written.push(JSON.stringify({ model, goal, answer, failure, grounding: g && { status: g.status, classification: g.classification, unsupported: g.unsupported, checked: g.checked }, evidence, latency_ms: Date.now() - t0, cost_usd: cost, at: new Date().toISOString() })); await writeConfined(path.dirname(out), out, `${written.join('\n')}\n`, { mkdirs: true });
  n += 1;
  console.log(oneLine(`[${n}/${chosen.length * GOALS.length}] ${model.padEnd(13)} ${goal.slice(0, 44).padEnd(44)} ${g ? g.status : (failure ?? 'no evidence').slice(0, 50)} ${g?.unsupported.map((u) => `${u.kind}:${u.claim}`).join('; ').slice(0, 80) ?? ''}`));
}
process.exit(0);
