// Routing from measurements: which installed local model is MEASURED good enough for a class of goal? The answer comes from the eval table
// (docs/evidence/model-integration/local-eval.json, written by `npm run test:live-eval`) and the `sufficient` rule in local-eval.ts, not from a guess.
// Nothing here pulls a model, calls a network, or invents a number: no table, an unknown installed list, or no qualifying model all say so and return null,
// and the caller keeps its existing behaviour.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { sameLocalModel } from './local-model.ts';
import { sufficient, summarize, type ModelSummary, type TaskClass, type Trial } from './local-eval.ts';

export interface Measurements { trials: Trial[]; generated_at: string | null; file: string }
export interface MeasuredPick {
  /** The installed model the table qualifies for this class, or null. */
  model: string | null;
  /** Why: names the evidence, or what was missing. Always set. */
  reason: string;
  summary: ModelSummary | null;
}

const here = path.dirname(fileURLToPath(import.meta.url));
export const DEFAULT_EVAL_FILE = path.resolve(here, '..', '..', 'docs', 'evidence', 'model-integration', 'local-eval.json');

/** The measured trials, or null when the file is missing or not a table (never throws). */
export function loadMeasurements(file: string = process.env.KUDBEE_LOCAL_EVAL || DEFAULT_EVAL_FILE): Measurements | null {
  try {
    const d = JSON.parse(fs.readFileSync(file, 'utf8')) as { trials?: unknown; generated_at?: unknown };
    if (!Array.isArray(d.trials) || !d.trials.length) return null;
    const trials = d.trials.filter((t): t is Trial => !!t && typeof (t as Trial).model === 'string' && typeof (t as Trial).outcome === 'string' && ((t as Trial).class === 'lookup' || (t as Trial).class === 'repo'));
    return trials.length ? { trials, generated_at: typeof d.generated_at === 'string' ? d.generated_at : null, file } : null;
  } catch { return null; }
}

/**
 * The best installed model for a class: measured sufficient (enough trials, a high pass rate, zero ungrounded answers), ranked by pass rate then median latency.
 * Repository investigation needs native tool calling, so only a model whose trials ran in native tool mode can be picked for it: a JSON-prompted model is
 * allowed for lookups only.
 */
export function pickMeasured(cls: TaskClass, installed: string[] | null, m: Measurements | null): MeasuredPick {
  if (!m) return { model: null, reason: 'no measurements on file, so nothing is measured sufficient', summary: null };
  if (!installed) return { model: null, reason: 'the installed local models are not known yet', summary: null };
  const eligible = m.trials.filter((t) => cls !== 'repo' || t.mode === 'native');
  const rows = summarize(eligible).filter((s) => s.class === cls);
  const here = rows.filter((s) => installed.some((i) => sameLocalModel(s.model, i)));
  const ok = here.filter((s) => sufficient(s)).sort((a, b) => b.pass_rate - a.pass_rate || a.p50_ms - b.p50_ms)[0];
  if (ok) return { model: installed.find((i) => sameLocalModel(ok.model, i)) ?? ok.model, reason: `${ok.model} measured ${ok.pass}/${ok.trials} on ${cls} goals with ${ok.ungrounded} ungrounded (p50 ${(ok.p50_ms / 1000).toFixed(1)}s; ${path.basename(m.file)}${m.generated_at ? `, ${m.generated_at.slice(0, 10)}` : ''})`, summary: ok };
  const best = [...here].sort((a, b) => b.pass_rate - a.pass_rate)[0];
  return { model: null, reason: best ? `no installed model is measured sufficient for ${cls} goals (best: ${best.model} ${best.pass}/${best.trials}, ${best.ungrounded} ungrounded)` : `no installed model has been measured on ${cls} goals`, summary: best ?? null };
}

/** A goal class from the goal text, using the same matchers the Mayor uses. Pure. */
export function goalClassOf(isRepoGoal: boolean): TaskClass { return isRepoGoal ? 'repo' : 'lookup'; }
