// Opt-in live check for P3.37 (npm run test:live-true-counts): the criteria in docs/evidence/p3.37-true-counts/PLAN.md. Real GitHub (read-only), real Ollama, no Mercury.
// Output: docs/evidence/p3.37-true-counts/live.json
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { newRunContext, runGovernedTool } from '../../agent.ts';
import { LOOKUP_RECIPES, type LookupEvidence } from '../../live-lookup.ts';
import { runLocalToolLoop, type LocalChat } from '../../local-tools.ts';
import { createModelClients } from '../../ollama-client.ts';
import { writeEvidence } from '../helpers/evidence-file.ts';
import { lookupHooks } from '../helpers/lookup-hooks.ts';

const REPO = 'Kudbee-Studio/think-box-ai';
const OUT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../../docs/evidence/p3.37-true-counts');
process.env.KUDBEE_REPO = REPO; delete process.env.KUDBEE_GITHUB_API;
void LOOKUP_RECIPES;

// independent count through the authenticated gh CLI: paginate the REST lists, not the search endpoint
const ghRows = (p: string, jq: string): string[] => execFileSync('gh', ['api', '--paginate', p, '--jq', jq], { encoding: 'utf8' }).split('\n').filter(Boolean);
const ghIssues = (): number => ghRows(`repos/${REPO}/issues?state=open&per_page=100`, '.[] | select(.pull_request == null) | .number').length;
const ghPrs = (): number => ghRows(`repos/${REPO}/pulls?state=open&per_page=100`, '.[] | .number').length;
const ghBranches = (): number => ghRows(`repos/${REPO}/branches?per_page=100`, '.[] | .name').length;

const results: Record<string, any> = { generated_at: new Date().toISOString(), repo: REPO };
const tool = async (recipe: string): Promise<LookupEvidence> => {
  const g = await runGovernedTool('live_lookup', { recipe }, lookupHooks().hooks, newRunContext(), 1);
  if (g.output.ok !== true) throw new Error(String(g.output.error));
  return (g.output as { evidence: LookupEvidence }).evidence;
};

// 1. totals against an independent count
const issuesEv = await tool('open_issues'); const prsEv = await tool('open_prs');
const indep = { open_issues: ghIssues(), open_prs: ghPrs() };
results.totals = { open_issues: { tool_total: issuesEv.total ?? null, independent: indep.open_issues, match: issuesEv.total === indep.open_issues }, open_prs: { tool_total: prsEv.total ?? null, independent: indep.open_prs, match: prsEv.total === indep.open_prs } };
console.log('totals', JSON.stringify(results.totals));

// 2. real local models on the count questions
const clients = createModelClients({ ollamaBaseUrl: process.env.OLLAMA_BASE_URL || 'http://127.0.0.1:11434', janusBaseUrl: 'http://127.0.0.1:9', janusEnabled: () => false });
const chat: LocalChat = { modelCapabilities: clients.modelCapabilities, chatOnce: (m, msgs, o = {}) => clients.chatOnce(m, msgs, o) };
const truth = { issues: ghIssues(), prs: ghPrs(), branches: ghBranches() };
const questions: Array<{ q: string; kind: 'issues' | 'prs' | 'branches' }> = [{ q: 'How many issues are open?', kind: 'issues' }, { q: 'How many pull requests are open?', kind: 'prs' }, { q: 'How many branches are there?', kind: 'branches' }];
const rows: any[] = [];
for (const model of ['gemma3:4b', 'qwen2.5:3b']) {
  for (const { q, kind } of questions) {
    const h = lookupHooks();
    const r = await runLocalToolLoop({ model, goal: q, hooks: h.hooks, context: newRunContext(), chat, repo: REPO, maxSteps: 3 });
    const answer = r.answer ?? '';
    const numbers = [...answer.matchAll(/\b\d+\b/g)].map((m) => Number(m[0]));
    const grounded = r.success && r.grounding?.status === 'GROUNDED';
    const states = kind === 'branches' ? 'a count of branches' : `the true total ${truth[kind]}`;
    // a stated count of what the question asked about: for 0, "no"/"none"/"zero" says it; for branches, a number or number word directly before "branches" (digits inside branch names are not counts)
    const statesTruth = kind !== 'branches' && (numbers.includes(truth[kind]) || (truth[kind] === 0 && /\b(no|none|zero|not any)\b/i.test(answer)));
    const statesAnyCount = /\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|twenty)\s+(?:\w+\s+)?branches\b/i.test(answer);
    const partial = /\b(at least|more than|first|only|showing|shown|up to|so far|most recent|latest|newest)\b/i.test(answer);
    const ok = !grounded || (kind === 'branches' ? !statesAnyCount || partial : statesTruth);
    rows.push({ model, question: q, answer: answer.slice(0, 220), success: r.success, failure: r.failure?.kind ?? null, verdict: r.grounding?.status ?? null, grounded, numbers, true_value: kind === 'branches' ? 'unknown (100+)' : truth[kind], criterion_ok: ok, expects: states, tool_total: (r.evidence[0] as LookupEvidence | undefined)?.total ?? null });
    console.log(`${model.padEnd(12)} ${q.padEnd(34)} ${grounded ? 'GROUNDED' : (r.grounding?.status ?? r.failure?.kind ?? 'no answer').padEnd(8)} numbers=${JSON.stringify(numbers)} true=${kind === 'branches' ? '?' : truth[kind]} ok=${ok}`);
  }
}
results.answers = rows;
results.independent_at_answers = truth;
results.criteria = {
  c1_totals_match: results.totals.open_issues.match && results.totals.open_prs.match,
  c2_no_wrong_count_verified: rows.every((r) => r.criterion_ok),
  c3_grounded_correct_counts: { issues_prs: rows.filter((r) => r.question !== 'How many branches are there?' && r.grounded && r.criterion_ok).length, of: rows.filter((r) => r.question !== 'How many branches are there?').length },
};
results.verdict = results.criteria.c1_totals_match && results.criteria.c2_no_wrong_count_verified ? 'PASS' : 'FAIL';
await writeEvidence(OUT, path.join(OUT, 'live.json'), results);
console.log(JSON.stringify(results.criteria), results.verdict);
process.exit(results.verdict === 'PASS' ? 0 : 1);
