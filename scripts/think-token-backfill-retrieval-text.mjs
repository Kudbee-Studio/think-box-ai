// Copy a seed database and write `when_to_use` retrieval text for every accepted lesson that lacks it, with the real extraction model
// (Mercury 2, key from the repo .env, never printed). The model sees only the lesson, never a goal. Usage:
//   node --experimental-strip-types scripts/think-token-backfill-retrieval-text.mjs <in.db> <out.db>
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
for (const f of [path.join(root, '.env'), path.join(root, 'apps/web/.env')]) { try { process.loadEnvFile(f); } catch { /* optional */ } }
const [inFile, outFile] = process.argv.slice(2);
if (!inFile || !outFile) throw new Error('usage: think-token-backfill-retrieval-text.mjs <in.db> <out.db>');
const { SqliteTokenStore } = await import(pathToFileURL(path.join(root, 'apps/web/think-token-store.ts')).href);
const { backfillRetrievalText } = await import(pathToFileURL(path.join(root, 'apps/web/think-token-pipeline.ts')).href);
const { createTokenModels } = await import(pathToFileURL(path.join(root, 'apps/web/think-token-model.ts')).href);

fs.copyFileSync(inFile, outFile);
const store = new SqliteTokenStore(outFile);
const n = await backfillRetrievalText({ store, models: createTokenModels(), env: { ...process.env, THINKBOX_TOKEN_MODEL_CALLS_PER_RUN: '100' } }, 'backfill-retrieval-text', 100);
const rows = store.list({ status: 'accepted', limit: 100 }).map((t) => ({ slug: t.evidence_ref, when_to_use: store.retrievalTextFor(t.id) }));
store.close();
console.log(JSON.stringify({ written: n, accepted: rows.length, without: rows.filter((r) => !r.when_to_use).length }));
fs.writeFileSync(outFile.replace(/\.db$/, '.when-to-use.json'), `${JSON.stringify(rows, null, 2)}\n`);
