// P3.20 bake-off. Runs the locked eval set (local-model-eval-p3.20.ts) on every model Ollama has among CANDIDATES, 2 reps each, with the server's
// exact call (plain chat, LOCAL_CHAT_OPTIONS). Applies the pre-locked default-model rule. Usage:
//   node --experimental-strip-types --no-warnings scripts/local-model-bakeoff.ts [out.json]
import fs from 'node:fs';
import { EVAL_SET, LOCAL_THRESHOLD } from './local-model-eval-p3.20.ts';
import { buildPrompt, groundedAnswer } from '../apps/web/local-recipes.ts';
import { LOCAL_CHAT_OPTIONS } from '../apps/web/local-model.ts';
import { localConfidence } from '../apps/web/goal-routing.ts';

const base = (process.env.OLLAMA_BASE_URL || 'http://127.0.0.1:11434').replace(/\/$/, '');
const CANDIDATES = ['smollm2:360m', 'qwen2.5:1.5b', 'qwen2.5:3b']; // ordered smallest first: ties go to the smaller
const REPS = 2;
const out = process.argv[2] || 'docs/evidence/p320-local-bakeoff-results.json';

const installed = new Set(((await (await fetch(`${base}/api/tags`)).json()) as any).models.map((m: any) => m.name));
const models = CANDIDATES.filter((m) => installed.has(m));
const missing = CANDIDATES.filter((m) => !installed.has(m));
if (missing.length) console.log('NOT INSTALLED (skipped):', missing.join(', '));

async function ask(model: string, content: string) {
  const t0 = Date.now();
  try {
    const r = await fetch(`${base}/api/chat`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ model, stream: false, messages: [{ role: 'user', content }], options: LOCAL_CHAT_OPTIONS }) });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return { text: String(((await r.json()) as any)?.message?.content ?? ''), ms: Date.now() - t0, failed: false };
  } catch (e) {
    return { text: '', ms: Date.now() - t0, failed: true };
  }
}

const pct = (xs: number[], p: number) => { const s = [...xs].sort((a, b) => a - b); return s[Math.min(s.length - 1, Math.ceil(p * s.length) - 1)] ?? 0; };
const rows: any[] = [];
const stats: any[] = [];

for (const model of models) {
  console.log(`\n== ${model}`);
  await ask(model, 'hi'); // load into memory; not measured
  const mine: any[] = [];
  for (let rep = 0; rep < REPS; rep += 1) {
    for (const g of EVAL_SET.filter((x) => x.kind !== 'escalate')) {
      const r = await ask(model, g.kind === 'data' ? buildPrompt(g.goal, g.facts!) : g.goal);
      let pass = false;
      let why = '';
      if (r.failed) why = 'model call failed';
      else if (g.kind === 'knowledge') { pass = g.expect!.test(r.text); if (!pass) why = 'wrong answer'; }
      else {
        const gr = groundedAnswer(r.text, g.facts!);
        pass = gr.ok && g.must!.test(r.text);
        if (!pass) why = gr.ok ? 'did not use the data' : gr.why;
      }
      const row = { model, rep, kind: g.kind, goal: g.goal, pass, ...(pass ? {} : { why }), ms: r.ms, failed: r.failed, answer: r.text.replace(/\s+/g, ' ').slice(0, 200) };
      mine.push(row); rows.push(row);
      console.log(`${pass ? 'PASS' : 'fail'} ${String(r.ms).padStart(5)}ms [${g.kind}] ${g.goal}${pass ? '' : `  <- ${why}: ${row.answer.slice(0, 90)}`}`);
    }
  }
  const ps = (await (await fetch(`${base}/api/ps`)).json() as any).models?.find((m: any) => m.name === model);
  const s = {
    model, runs: mine.length, passed: mine.filter((r) => r.pass).length,
    pass_rate: mine.filter((r) => r.pass).length / mine.length,
    knowledge_pass: mine.filter((r) => r.kind === 'knowledge' && r.pass).length / mine.filter((r) => r.kind === 'knowledge').length,
    data_pass: mine.filter((r) => r.kind === 'data' && r.pass).length / mine.filter((r) => r.kind === 'data').length,
    p50_ms: pct(mine.map((r) => r.ms), 0.5), p95_ms: pct(mine.map((r) => r.ms), 0.95),
    gpu_pct: ps ? Math.round((100 * ps.size_vram) / ps.size) : null, loaded_mb: ps ? Math.round(ps.size / 1e6) : null,
    failed_calls: mine.filter((r) => r.failed).length,
  };
  stats.push(s);
}

// Router check (no model): every escalate goal must be refused by localConfidence.
const routerChecks = EVAL_SET.filter((g) => g.kind === 'escalate').map((g) => ({ goal: g.goal, confidence: localConfidence(g.goal), refused: localConfidence(g.goal) < LOCAL_THRESHOLD }));

const eligible = stats.filter((s) => s.p95_ms <= 5000);
const winner = [...eligible].sort((a, b) => b.pass_rate - a.pass_rate || models.indexOf(a.model) - models.indexOf(b.model))[0] ?? null;
const report = { timestamp: new Date().toISOString(), rule: 'highest pass rate with p95 <= 5000 ms; tie -> smaller model', threshold: LOCAL_THRESHOLD, models, missing, reps: REPS, stats, router_checks: routerChecks, winner: winner?.model ?? null, rows };
fs.writeFileSync(out, JSON.stringify(report, null, 1));

console.log('\nmodel          pass   knowledge  data   p50     p95     GPU   RAM      failed');
for (const s of stats) console.log(`${s.model.padEnd(14)} ${(s.pass_rate * 100).toFixed(0).padStart(3)}%   ${(s.knowledge_pass * 100).toFixed(0).padStart(4)}%     ${(s.data_pass * 100).toFixed(0).padStart(3)}%  ${String(s.p50_ms).padStart(5)}ms ${String(s.p95_ms).padStart(6)}ms  ${s.gpu_pct ?? '?'}%  ${s.loaded_mb ?? '?'}MB  ${s.failed_calls}`);
console.log('\nrouter refuses escalate goals:', routerChecks.map((r) => `${r.refused ? 'yes' : 'NO'}(${r.confidence})`).join(' '));
console.log('winner:', winner?.model ?? 'none eligible (p95 > 5 s for all)');
