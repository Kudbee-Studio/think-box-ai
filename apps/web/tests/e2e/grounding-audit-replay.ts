// Replays every stored audit row through the CURRENT validator (the stored evidence is the full tool evidence) and prints old vs new verdicts.
// Run: npm run test:live-grounding-audit-replay [-- path/to/runs.jsonl]
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { validateGrounding } from '../../grounding.ts';

const here = path.dirname(fileURLToPath(import.meta.url));
const file = process.argv[2] ?? path.resolve(here, '../../../../docs/evidence/p3.30-grounding-audit/runs.jsonl');
const rows = fs.readFileSync(file, 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l));
let changed = 0;
for (const r of rows) {
  if (!r.answer || !r.evidence?.length) { console.log(`${r.model.padEnd(11)} ${r.goal.slice(0, 44).padEnd(44)} (no answer or evidence: ${String(r.failure ?? 'none').slice(0, 50)})`); continue; }
  const g = validateGrounding(r.answer, r.evidence, { goal: r.goal });
  const was = r.grounding?.status === 'GROUNDED' ? 'ok  ' : 'FAIL'; const now = g.status === 'GROUNDED' ? 'ok  ' : 'FAIL';
  if (was !== now) changed += 1;
  console.log(`${r.model.padEnd(11)} ${r.goal.slice(0, 44).padEnd(44)} stored ${was} -> now ${now}  ${g.unsupported.map((u) => `${u.kind}:${u.claim}`).join('; ').slice(0, 100)}`);
}
console.log(`${rows.length} rows, ${changed} verdict(s) differ from the stored one`);
