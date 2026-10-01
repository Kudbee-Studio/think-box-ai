// Child process for the concurrent-ID test: opens the same SQLite file as its siblings and writes N tokens.
import { SqliteTokenStore } from '../../think-token-store.ts';

const [dbPath, count, tag] = process.argv.slice(2);
const store = new SqliteTokenStore(dbPath);
const ids: string[] = [];
for (let i = 0; i < Number(count); i++) {
  const result = store.write({ source_run_id: `run-${tag}`, kind: 'lesson', title: `lesson ${tag} ${i}`, content: `unique lesson text ${tag} number ${i}`, evidence_ref: `run:${tag}` }, `proc:${tag}`);
  if (!result.ok) throw new Error(result.reason);
  ids.push(result.id);
}
store.close();
console.log(JSON.stringify(ids));
