// Keyword list vs embedding classifier on the 20 hand-labeled memories (apps/web/tests/fixtures/live-state-labeled.json). Run once. Usage:
//   node --experimental-strip-types scripts/live-state-classifier-eval.mjs <out.json>
// DECISION RULE (fixed before the run): use the embedding classifier only if its accuracy is >= the keyword list's; otherwise keep the keyword list.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const { isLiveStateText, createLiveStateClassifier } = await import(pathToFileURL(path.join(root, 'apps/web/evidence.ts')).href);
const { getEmbedder } = await import(pathToFileURL(path.join(root, 'apps/web/think-token-embed.ts')).href);
const { items } = JSON.parse(fs.readFileSync(path.join(root, 'apps/web/tests/fixtures/live-state-labeled.json'), 'utf8'));
const embedder = await getEmbedder();
if (!embedder) throw new Error('embedder unavailable');
const classify = await createLiveStateClassifier(embedder);
const emb = await classify(items.map((i) => i.text));
const rows = items.map((i, n) => ({ text: i.text, live: i.live, keyword: isLiveStateText(i.text), embedding: emb[n] }));
const acc = (k) => rows.filter((r) => r[k] === r.live).length;
const report = { keyword_correct: acc('keyword'), embedding_correct: acc('embedding'), total: rows.length, rows };
fs.writeFileSync(process.argv[2], `${JSON.stringify(report, null, 2)}\n`);
console.log(`keyword ${report.keyword_correct}/${rows.length} | embedding ${report.embedding_correct}/${rows.length}`);
for (const r of rows) if (r.keyword !== r.live || r.embedding !== r.live) console.log(r.live ? 'LIVE  ' : 'STATIC', `kw=${r.keyword} emb=${r.embedding}`, r.text.slice(0, 70));
