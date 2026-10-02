// P3.15: can the small local model (Ollama, on the GPU) challenge Think Token lessons? Runs the REAL challengeLesson code path with
// the local model only (no Mercury, so $0) on the same fixed run record and the same 10 true + 10 plausible-but-false lessons that
// tuned the Mercury challenge (docs/evidence/adr-029-p3/challenge-tune.ts.txt; Mercury got 17 pass / 1 wrong reject / 0 wrong accept /
// 19 reject / 3 unjudged there). Usage:
//   THINKBOX_LOCAL_MODEL=smollm2:360m node --experimental-strip-types scripts/think-token-local-challenge-eval.ts [out.json]
//
// DECISION RULE (fixed before any local run):
//   The local model may become a first-pass REJECTOR (its "fail" stops a lesson; its "pass" never accepts anything; Mercury still decides
//   every accept) only if, on the lessons that get past the deterministic checks:
//     (a) it rejects at least 60% of the bad lessons,
//     (b) it wrongly rejects at most 10% of the good lessons, and
//     (c) at most 10% of its replies are unusable (not the expected JSON).
//   Otherwise it is not wired into the challenge. It is never allowed to accept.
import fs from 'node:fs';
import { buildRunView, checkGrounding, checkSpecificity, challengeLesson } from '../apps/web/think-token-pipeline.ts';
import { createLocalCaller } from '../apps/web/think-token-model.ts';
import { resolveLocalModel } from '../apps/web/local-model.ts';
import { SqliteTokenStore } from '../apps/web/think-token-store.ts';

const t = (name: string, args: any, output: string, ok = true, error?: string) => ({ kind: 'tool', step: 1, name, args, ok, error, latency_ms: 4, output }) as any;
const RUN = { id: 'tune-run', goal: 'Read config.json, then write a summary of its keys to summary.md and confirm the file.', success: true, files: ['summary.md'], result: 'Wrote summary.md (3 keys: port, debug, name).',
  steps: [t('read_file', { path: 'config.json' }, '{"port":8080,"debug":false,"name":"demo"}'), t('read_file', { path: 'config.yaml' }, '', false, 'ENOENT: no such file config.yaml'), t('write_file', { path: 'summary.md', content: '# Keys\n- port\n- debug\n- name' }, 'ok: wrote 31 bytes to summary.md'), t('list_files', { path: '.' }, 'config.json 44 bytes\nsummary.md 31 bytes')] };
const view = buildRunView(RUN);
const known = [{ id: 'TT-000010', title: 'Verify file creation with list_files', lesson: 'After write_file, call list_files to confirm the file exists and check its size.' }];
const GOOD = [
 'The read_file call on config.yaml failed with ENOENT; read the exact filename config.json the goal names instead of guessing another extension.',
 'config.json held three keys (port, debug, name); listing each key as a bullet in summary.md kept the summary short and complete.',
 'write_file reported 31 bytes for summary.md and list_files showed 31 bytes: matching the two numbers confirms the whole content was written.',
 'Parse the JSON returned by read_file on config.json before summarizing; the output was a single-line object so key names can be taken directly from it.',
 'A failed read_file (ENOENT on config.yaml) did not stop the run; continuing with the file that exists (config.json) completed the task.',
 'For a config summary, read the source file first and only then call write_file, so the summary lists keys that actually appear in the output.',
 'summary.md was written with a markdown heading plus one bullet per key; this format needed a single write_file call.',
 'list_files showed config.json at 44 bytes next to summary.md; use that listing to check both the input and the output file in one call.',
 'When read_file returns an ENOENT error for a guessed name, note the error text and fall back to the filename from the goal rather than retrying the same path.',
 'Counting keys in the read_file output (three) and stating that count in the final answer made the result easy to verify against summary.md.',
];
const BAD = [
 'read_file on config.yaml succeeded and returned the port, so YAML is the preferred config format.',
 'write_file automatically backs up the previous version of summary.md, so overwriting is always safe.',
 'list_files reports file checksums, so comparing them is the best way to verify write_file output.',
 'Always call read_file twice on config.json because the first read is cached and incomplete.',
 'The debug key being false means write_file should be called with debug mode off to avoid log noise.',
 'Run list_files before write_file to make sure the directory exists, because write_file fails on missing folders.',
 'After read_file, call fetch_url on the config port to confirm the service is running.',
 'Summarizing config keys works best when summary.md is written in JSON rather than markdown.',
 'Verify a written file by calling list_files afterwards to confirm it exists and check its size.',
 'Config files should always be read with a timeout argument of 30 seconds to avoid hangs in read_file.',
];

const model = resolveLocalModel();
const base = (process.env.OLLAMA_BASE_URL || 'http://127.0.0.1:11434').replace(/\/$/, '');
const env = { ...process.env, THINKBOX_TOKEN_MODEL_CALLS_PER_RUN: '100000', THINKBOX_TOKEN_MODEL_CALLS_PER_DAY: '100000' };
const store = new SqliteTokenStore();
// Two local configurations are measured; the first is how the production caller works (free-form JSON, reply capped at 160 tokens),
// the second forces the reply to match the verdict schema (Ollama structured output). Pick with EVAL_MODE=free|schema (default schema).
const SCHEMA = { type: 'object', properties: { true: { type: 'boolean' }, specific: { type: 'boolean' }, supported: { type: 'boolean' }, novel: { type: 'boolean' }, reason: { type: 'string' } }, required: ['true', 'specific', 'supported', 'novel', 'reason'] };
const MODE = process.env.EVAL_MODE === 'free' ? 'free' : 'schema';
const realLocal = createLocalCaller(env);
const schemaLocal = async (messages: any[], opts: any = {}) => {
  const started = Date.now();
  const res = await fetch(`${base}/api/chat`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: AbortSignal.timeout(30_000), body: JSON.stringify({ model, stream: false, format: SCHEMA, messages, options: { temperature: 0, num_predict: opts.maxTokens ?? 160 } }) });
  const body: any = await res.json();
  return { text: String(body?.message?.content ?? ''), provider: 'local' as const, model, latency_ms: Date.now() - started, tokens_in: Number(body?.prompt_eval_count) || 0, tokens_out: Number(body?.eval_count) || 0 };
};
const deps = { store, models: { mercury: null, local: (MODE === 'schema' ? schemaLocal : ((m: any, o: any) => realLocal(m, { ...o, maxTokens: 160 }))) as any }, env };
const REPS = 2;

async function gpu() {
  try {
    const ps = (await (await fetch(`${base}/api/ps`)).json()) as { models?: Array<{ name: string; size: number; size_vram: number }> };
    return (ps.models ?? []).map((m) => ({ name: m.name, size_mb: Math.round(m.size / 1e6), vram_mb: Math.round(m.size_vram / 1e6), on_gpu_pct: m.size ? Math.round((100 * m.size_vram) / m.size) : 0 }));
  } catch { return []; }
}

const rows: any[] = [];
const started = Date.now();
for (const [label, list] of [['good', GOOD], ['bad', BAD]] as const) for (const [i, body] of list.entries()) {
  const lesson = { title: body.slice(0, 50), content: body, tools_cited: [] as string[], files_cited: [] as string[], tags: [] as string[] };
  const det = [...checkGrounding(lesson, view).reasons, ...checkSpecificity(lesson, view).reasons];
  if (det.length) { rows.push({ label, i, r: 0, det: true, verdict: 'fail', reason: det.join('; ').slice(0, 100), ms: 0 }); continue; } // the model never sees these
  for (let r = 0; r < REPS; r++) {
    const t0 = Date.now();
    const v = await challengeLesson(deps, view, lesson as any, 'eval', known);
    rows.push({ label, i, r, det: false, verdict: v ? v.verdict : 'none', reason: (v?.reason ?? 'unusable reply or model unreachable').slice(0, 100), ms: Date.now() - t0 });
    console.error(`${label} ${i}.${r} -> ${rows.at(-1).verdict} (${rows.at(-1).ms} ms)`);
  }
}
const seen = rows.filter((x) => !x.det);
const n = (f: (x: any) => boolean) => seen.filter(f).length;
const goodSeen = n((x) => x.label === 'good'), badSeen = n((x) => x.label === 'bad');
const goodWrong = n((x) => x.label === 'good' && x.verdict === 'fail'), badCaught = n((x) => x.label === 'bad' && x.verdict === 'fail');
const badMissed = n((x) => x.label === 'bad' && x.verdict === 'pass'), goodKept = n((x) => x.label === 'good' && x.verdict === 'pass'), none = n((x) => x.verdict === 'none');
const rate = (a: number, b: number) => (b ? a / b : 0);
const rule = { bad_caught_rate: rate(badCaught, badSeen), good_wrong_reject_rate: rate(goodWrong, goodSeen), unusable_rate: rate(none, seen.length) };
const qualifies = badSeen > 0 && rule.bad_caught_rate >= 0.6 && rule.good_wrong_reject_rate <= 0.1 && rule.unusable_rate <= 0.1;
const result = {
  model, mode: MODE, reps: REPS, seconds: Math.round((Date.now() - started) / 100) / 10,
  model_calls: seen.length, avg_ms_per_call: Math.round(seen.reduce((s, x) => s + x.ms, 0) / (seen.length || 1)),
  gpu: await gpu(),
  good: { seen_by_model: goodSeen, kept: goodKept, wrongly_rejected: goodWrong },
  bad: { seen_by_model: badSeen, caught: badCaught, wrongly_accepted: badMissed, rejected_by_deterministic_check_before_the_model: rows.filter((x) => x.det && x.label === 'bad').length },
  unusable: none, ...rule, qualifies_as_first_pass_rejector: qualifies, rows,
};
console.log(JSON.stringify({ ...result, rows: undefined }, null, 1));
if (process.argv[2]) fs.writeFileSync(process.argv[2], JSON.stringify(result, null, 1));
