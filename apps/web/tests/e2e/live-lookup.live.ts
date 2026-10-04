// Opt-in live proof (npm run test:live-lookup): every live_lookup recipe against the REAL GitHub API for this repository, through the governed tool
// path, with no model involved. Writes docs/evidence/p3.22-model-integration/live-lookup.json.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { newRunContext, runGovernedTool } from '../../agent.ts';
import { LOOKUP_RECIPES, renderFacts } from '../../live-lookup.ts';
import { lookupHooks } from '../helpers/lookup-hooks.ts';

const here = path.dirname(fileURLToPath(import.meta.url));
process.env.KUDBEE_REPO = process.env.KUDBEE_REPO || 'Kudbee-Studio/think-box-ai';
delete process.env.KUDBEE_GITHUB_API;
const { hooks, approvals } = lookupHooks();
const results: unknown[] = [];
for (const recipe of LOOKUP_RECIPES) {
  const g = await runGovernedTool('live_lookup', { recipe }, hooks, newRunContext(), 1);
  const evidence = (g.output as any).evidence;
  results.push({ recipe, ok: g.output.ok, error: g.output.ok ? undefined : g.output.error, latency_ms: g.latency_ms, approval: g.approval ?? null, items: evidence?.items?.length, evidence, facts: evidence ? renderFacts(evidence) : undefined });
  console.log(`${g.output.ok ? 'ok  ' : 'FAIL'} ${recipe.padEnd(12)} ${g.latency_ms}ms ${evidence ? `${evidence.items.length} item(s)` : g.output.error}`);
}
const out = path.resolve(here, '../../../../docs/evidence/p3.22-model-integration/live-lookup.json');
fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, `${JSON.stringify({ generated_at: new Date().toISOString(), repo: process.env.KUDBEE_REPO, source: 'https://api.github.com (unauthenticated)', approvals, results }, null, 2)}\n`);
console.log(`wrote ${out}`);
process.exit(results.every((r: any) => r.ok) ? 0 : 1);
