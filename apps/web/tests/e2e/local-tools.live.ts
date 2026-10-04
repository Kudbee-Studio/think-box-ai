// Opt-in live proof (npm run test:live-local-tools): REAL Ollama models call live_lookup against the REAL GitHub API through the governed path.
// Approvals are granted by this script (stand-in for the human reviewer) and each grant is recorded. Writes
// docs/evidence/p3.22-model-integration/local-tools-live.json. Usage: node ... local-tools.live.ts [model ...] [-- goal]
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { newRunContext } from '../../agent.ts';
import { runLocalToolLoop } from '../../local-tools.ts';
import { createModelClients } from '../../ollama-client.ts';
import { lookupHooks } from '../helpers/lookup-hooks.ts';

const here = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const split = args.indexOf('--');
const models = (split < 0 ? args : args.slice(0, split));
const goals = split < 0 ? ['What is the last PR?'] : args.slice(split + 1);
process.env.KUDBEE_REPO = process.env.KUDBEE_REPO || 'Kudbee-Studio/think-box-ai';
delete process.env.KUDBEE_GITHUB_API;
const clients = createModelClients({ ollamaBaseUrl: process.env.OLLAMA_BASE_URL || 'http://127.0.0.1:11434', janusBaseUrl: 'http://127.0.0.1:9', janusEnabled: () => false });
const out = path.resolve(here, '../../../../docs/evidence/p3.22-model-integration/local-tools-live.json');
const previous = fs.existsSync(out) ? JSON.parse(fs.readFileSync(out, 'utf8')) : { runs: [] };
const runs: unknown[] = [];
for (const model of models.length ? models : ['qwen2.5:3b', 'gemma3:4b']) {
  for (const goal of goals) {
    const { hooks, approvals } = lookupHooks();
    const startedAt = Date.now();
    const result = await runLocalToolLoop({ model, goal, hooks, context: newRunContext(), chat: clients, repo: process.env.KUDBEE_REPO!, maxSteps: 3 });
    console.log(`${result.success ? 'ok  ' : 'FAIL'} ${model} [${result.mode}] "${goal}" ${Date.now() - startedAt}ms tools=${result.tool_calls} tokens=${result.prompt_tokens}+${result.completion_tokens} grounding=${result.grounding?.status ?? 'n/a'}${result.failure ? ` failure=${result.failure.kind}: ${result.failure.message}` : ''}\n     answer: ${result.answer ?? '(none)'}`);
    runs.push({ goal, approvals, wall_ms: Date.now() - startedAt, ...result });
  }
}
fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, `${JSON.stringify({ generated_at: new Date().toISOString(), repo: process.env.KUDBEE_REPO, source: 'real Ollama + real GitHub API; approvals granted by the script', runs: [...(previous.runs ?? []), ...runs] }, null, 2)}\n`);
process.exit(0);
