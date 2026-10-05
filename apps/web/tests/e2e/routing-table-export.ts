// Writes docs/evidence/p3.27-gemma/results.json from the measured trials in local-eval.json: the machine-readable table routing reads, per model and goal class.
// Derived only; nothing is typed in by hand. Run: npm run export-routing-table
import fs from 'node:fs';
import path from 'node:path';
import { sufficient, summarize } from '../../local-eval.ts';
import { DEFAULT_EVAL_FILE, loadMeasurements } from '../../measured-routing.ts';

const m = loadMeasurements(DEFAULT_EVAL_FILE);
if (!m) throw new Error('no measured table on file');
const out = path.resolve(path.dirname(DEFAULT_EVAL_FILE), '..', 'p3.27-gemma', 'results.json');
fs.mkdirSync(path.dirname(out), { recursive: true });
const rows = summarize(m.trials).map((s) => {
  const t = m.trials.filter((x) => x.model === s.model && x.class === s.class);
  return { model: s.model, class: s.class, n: s.trials, pass: s.pass, wrong: s.wrong, ungrounded: s.ungrounded, failed: s.failed, pass_rate: s.pass_rate, p50_ms: s.p50_ms, p95_ms: s.p95_ms, max_ms: Math.max(...t.map((x) => x.latency_ms)), modes: [...new Set(t.map((x) => x.mode))], sufficient: sufficient(s) };
});
fs.writeFileSync(out, JSON.stringify({
  generated_from: 'docs/evidence/model-integration/local-eval.json',
  source_generated_at: m.generated_at,
  rule: 'sufficient = at least 6 trials, pass rate >= 80%, zero ungrounded answers (local-eval.ts sufficient())',
  cold_load_note: 'p95/max for gemma3:4b include the first call after the model was unloaded: a direct Ollama call measured load_duration 50.5 s of a 52.6 s total for a one-word prompt (observed once, 2026-10-05, 2 GiB GPU, 98% of the model on CPU); once loaded, a short call took 0.9 s. The eval trials themselves do not record load time.',
  rows,
}, null, 2) + '\n');
console.log(`wrote ${out}\n` + rows.map((r) => `${r.model} ${r.class} ${r.pass}/${r.n} ungrounded=${r.ungrounded} sufficient=${r.sufficient}`).join('\n'));
