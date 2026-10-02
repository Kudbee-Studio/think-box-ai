// P3.19: how often does the local model write a sentence that passes the grounding check, on REAL GitHub data? Fetches a repository's open pull
// requests once, builds the facts the server would, asks the local model N times with the server's exact call (plain chat, num_predict 512,
// num_ctx 2048), and reports the pass rate and the reasons for the failures. A failed sentence is not an error: the server then shows the data itself,
// so this measures how often the model helps, not whether the answer is right. Usage:
//   THINKBOX_LOCAL_MODEL=smollm2:360m node --experimental-strip-types scripts/local-recipe-eval.ts [owner/repo] [runs] [out.json]
import fs from 'node:fs';
import { buildFacts, buildPrompt, groundedAnswer, matchRecipe, recipeToolArgs } from '../apps/web/local-recipes.ts';
import { LOCAL_CHAT_OPTIONS } from '../apps/web/local-model.ts';
import { resolveLocalModel } from '../apps/web/local-model.ts';

const repo = process.argv[2] || 'facebook/react';
const runs = Math.max(1, Number(process.argv[3]) || 10);
const model = resolveLocalModel();
const base = (process.env.OLLAMA_BASE_URL || 'http://127.0.0.1:11434').replace(/\/$/, '');
const goals = ['WHAT PR ARE WE ON', 'which pull requests are open?', 'what PR are we working on?'];

const recipe = matchRecipe(goals[0]!)!;
const args = recipeToolArgs(recipe, repo) as { url: string };
const res = await fetch(args.url, { headers: { 'User-Agent': 'kudbEE-eval', Accept: 'application/vnd.github+json' } });
const text = (await res.text()).slice(0, 120000);
const built = buildFacts(recipe, { status: res.status, text }, repo);
if ('error' in built) throw new Error(built.error);
console.log(built.facts, '\n');

const rows: Array<{ goal: string; ok: boolean; why?: string; sentence: string; ms: number }> = [];
for (let i = 0; i < runs; i += 1) {
  const goal = goals[i % goals.length]!;
  const t0 = Date.now();
  const r = await fetch(`${base}/api/chat`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ model, stream: false, messages: [{ role: 'user', content: buildPrompt(goal, built.facts, recipe) }], options: LOCAL_CHAT_OPTIONS }) });
  const sentence = String(((await r.json()) as any)?.message?.content ?? '');
  const g = groundedAnswer(sentence, built.facts, { cite: 'pr' });
  rows.push({ goal, ok: g.ok, ...(g.ok ? {} : { why: g.why }), sentence: sentence.replace(/\s+/g, ' ').slice(0, 220), ms: Date.now() - t0 });
  console.log(`${g.ok ? 'PASS' : 'drop'} (${rows.at(-1)!.ms} ms) ${g.ok ? '' : `[${g.why}] `}${rows.at(-1)!.sentence}`);
}
const passed = rows.filter((r) => r.ok).length;
const reasons: Record<string, number> = {};
for (const r of rows) if (!r.ok) reasons[r.why!.replace(/"[^"]*"/, '"…"')] = (reasons[r.why!.replace(/"[^"]*"/, '"…"')] || 0) + 1;
const summary = { model, repo, runs, passed, pass_rate: passed / runs, dropped_reasons: reasons, avg_ms: Math.round(rows.reduce((s, r) => s + r.ms, 0) / rows.length) };
console.log('\n' + JSON.stringify(summary, null, 1));
if (process.argv[4]) fs.writeFileSync(process.argv[4], JSON.stringify({ ...summary, facts: built.facts, rows }, null, 1));
