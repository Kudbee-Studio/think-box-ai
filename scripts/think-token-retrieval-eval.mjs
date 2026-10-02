// Held-out retrieval metrics (no model, no weight changes). Usage:
//   node --experimental-strip-types scripts/think-token-retrieval-eval.mjs <seed.db> <goals-module.mjs> [out.json]
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const [seed, goalsModule, outFile] = process.argv.slice(2);
if (!seed || !goalsModule) throw new Error('usage: think-token-retrieval-eval.mjs <seed.db> <goals.mjs> [out.json]');

const { SqliteTokenStore } = await import(pathToFileURL(path.join(root, 'apps/web/think-token-store.ts')).href);
const { GOALS } = await import(path.resolve(goalsModule));

const store = SqliteTokenStore.openReadOnly(path.resolve(seed));
const slugInTitle = (title, slug) => title.includes(`[lesson:${slug}]`);

const related = GOALS.filter((g) => g.related && g.expectedLesson);
const perGoal = [];
let hit1 = 0;
let hit3 = 0;
for (const g of related) {
  const top3 = store.retrieve(g.goal, 3);
  const ids = top3.map((t) => t.id);
  const titles = top3.map((t) => t.title);
  const rank = top3.findIndex((t) => slugInTitle(t.title, g.expectedLesson));
  const h1 = rank === 0;
  const h3 = rank >= 0;
  if (h1) hit1 += 1;
  if (h3) hit3 += 1;
  perGoal.push({ id: g.id, expectedLesson: g.expectedLesson, hit1: h1, hit3: h3, rank: rank < 0 ? null : rank + 1, top3: titles });
}
store.close();

const report = {
  seed: path.basename(seed),
  goals_module: path.basename(goalsModule),
  related_goals: related.length,
  hit_at_1: hit1,
  hit_at_3: hit3,
  hit_at_1_rate: related.length ? hit1 / related.length : 0,
  hit_at_3_rate: related.length ? hit3 / related.length : 0,
  per_goal: perGoal,
};
const text = `${JSON.stringify(report, null, 2)}\n`;
if (outFile) fs.writeFileSync(outFile, text);
else process.stdout.write(text);
console.error(`hit@1 ${hit1}/${related.length} hit@3 ${hit3}/${related.length}`);
