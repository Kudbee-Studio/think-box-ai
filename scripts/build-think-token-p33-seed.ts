// Hermetic seed for ADR-029 P3.3 held-out eval + A/B (no Mercury). Writes docs/evidence/adr-029-p3/p33-seed.db
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { SqliteTokenStore, type TokenDraft } from '../apps/web/think-token-store.ts';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const out = path.join(root, 'docs/evidence/adr-029-p3/p33-seed.db');
fs.mkdirSync(path.dirname(out), { recursive: true });
if (fs.existsSync(out)) fs.unlinkSync(out);

type SeedRow = { slug: string; title: string; content: string; tags: string[] };

const p31Lessons: SeedRow[] = [
  { slug: 'bytes-not-chars', title: '[lesson:bytes-not-chars] Report write_file UTF-8 bytes', content: 'For utf8.txt goals, read the bytes field from write_file (not string length). héllo wörld ✓ is 17 bytes.', tags: ['write_file', 'utf8'] },
  { slug: 'append', title: '[lesson:append] Append with read_file then write_file', content: 'To append to log.md, read_file the file, keep existing lines, then write_file the full content with the new line at the end.', tags: ['write_file', 'read_file'] },
  { slug: 'list-subdir', title: '[lesson:list-subdir] list_files is recursive', content: 'list_files walks subdirectories; after writing docs/a.md and docs/b.md, the listing includes those paths.', tags: ['list_files', 'write_file'] },
  { slug: 'missing-then-create', title: '[lesson:missing-then-create] Create missing JSON settings', content: 'If read_file fails for settings.json, write_file {"theme":"dark"} then read it back for the theme.', tags: ['read_file', 'write_file'] },
  { slug: 'dotdot-path', title: '[lesson:dotdot-path] Parent paths via write_file', content: 'write_file creates parent directories; ../shared/note.txt resolves inside the workspace.', tags: ['write_file'] },
  { slug: 'counter', title: '[lesson:counter] Increment via read/write loop', content: 'To reach 4 in counter.txt, read_file, parse integer, add one, write_file; repeat three times after seeding 1.', tags: ['read_file', 'write_file'] },
  { slug: 'three-files', title: '[lesson:three-files] Name files in content', content: 'For one.md two.md three.md, each file content should include its basename; read two.md before answering.', tags: ['write_file', 'read_file'] },
  { slug: 'missing-no-invent', title: '[lesson:missing-no-invent] Admit missing files', content: 'If read_file errors on a missing file, answer that it does not exist; do not invent a summary.', tags: ['read_file'] },
];

const p33Lessons: SeedRow[] = [
  { slug: 'deep-mkdir', title: '[lesson:deep-mkdir] Nested paths auto-create dirs', content: 'write_file to deep/nested/out.txt creates deep/nested/; no separate mkdir tool exists.', tags: ['write_file', 'nested'] },
  { slug: 'zero-byte', title: '[lesson:zero-byte] Empty file is zero bytes', content: 'write_file with an empty string creates a zero-byte file; write_file reports bytes: 0.', tags: ['write_file'] },
  { slug: 'path-normalize', title: '[lesson:path-normalize] Dots in paths', content: 'Paths like ./nested/./note.txt normalize; write_file still creates nested/note.txt under the workspace.', tags: ['write_file'] },
  { slug: 'recursive-list', title: '[lesson:recursive-list] list_files finds deep files', content: 'After writing a/b/c.txt, list_files returns a/b/c.txt in the files array (recursive walk).', tags: ['list_files', 'write_file'] },
  { slug: 'size-match', title: '[lesson:size-match] Five ASCII bytes', content: 'Content abcde is exactly 5 bytes; cite write_file bytes field in the answer.', tags: ['write_file'] },
  { slug: 'replace-not-append', title: '[lesson:replace-not-append] Overwrite replaces all', content: 'To change hello.txt from A to B, write_file B without concatenating the old content.', tags: ['write_file'] },
  { slug: 'emoji-utf8', title: '[lesson:emoji-utf8] Emoji byte length', content: 'A single 🎯 in UTF-8 is 4 bytes; use write_file bytes in the answer.', tags: ['write_file', 'utf8'] },
  { slug: 'json-line', title: '[lesson:json-line] Compact JSON line', content: 'Write data.json as one line {"ok":true} with no extra whitespace or trailing newline unless asked.', tags: ['write_file', 'json'] },
];

const noise: SeedRow[] = [
  { slug: 'noise-rss', title: 'HN rss digests need citations', content: 'When summarizing RSS, cite story titles from read_rss output.', tags: ['read_rss'] },
  { slug: 'noise-algo', title: 'Algorand asset decimals', content: 'Use algorand asset action and divide total supply by 10**decimals.', tags: ['algorand'] },
  { slug: 'noise-memory', title: 'remember needs evidence', content: 'remember is blocked until fetch_url or read_file of pre-existing files.', tags: ['remember'] },
  { slug: 'noise-arith', title: 'Mental math without tools', content: 'Simple arithmetic can be answered without tools when the goal forbids them.', tags: ['arithmetic'] },
  { slug: 'noise-approval', title: 'Approval for new domains', content: 'First fetch_url to a new host needs human approval in the dashboard.', tags: ['fetch_url'] },
];

const store = new SqliteTokenStore(out);
let n = 0;
for (const row of [...p31Lessons, ...p33Lessons, ...noise]) {
  const draft: TokenDraft = {
    source_run_id: `seed-p33-${row.slug}`,
    kind: 'lesson',
    title: row.title,
    content: row.content,
    tags: row.tags,
    evidence_ref: `seed:${row.slug}`,
    extractor: 'template',
  };
  const w = store.write(draft, 'seed-builder');
  if (!w.ok) throw new Error(`${row.slug}: ${w.reason}`);
  store.setStatus(w.id, 'accepted', 'seed-builder');
  n += 1;
}
store.close();
console.log(JSON.stringify({ out, tokens: n, p31: p31Lessons.length, p33: p33Lessons.length, noise: noise.length }));
