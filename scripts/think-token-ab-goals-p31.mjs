// P3.1 goals: each hits a real quirk of the worker's tools (apps/web/agent.ts executeTool) that a correct lesson states.
// `check(files, answer)` is an objective test on what the run left in its workspace and what it answered.
const lines = (t) => (t ?? '').split('\n').map((l) => l.trim()).filter(Boolean);
export const GOALS = [
  { id: 'bytes-not-chars', related: true, goal: 'Write utf8.txt containing exactly the text: héllo wörld ✓ . Then tell me how many bytes write_file reported for it.', check: (f, a) => (f['utf8.txt'] ?? '').trim() === 'héllo wörld ✓' && /\b17\b/.test(a ?? '') },
  { id: 'append', related: true, goal: 'Create log.md containing the line "start". Then add a second line "done" at the END of log.md without losing "start".', check: (f) => JSON.stringify(lines(f['log.md'])) === JSON.stringify(['start', 'done']) },
  { id: 'list-subdir', related: true, goal: 'Write docs/a.md and docs/b.md, each containing "x", then list only the files inside the docs folder and answer with their names.', check: (f, a) => 'docs/a.md' in f && 'docs/b.md' in f && /a\.md/.test(a ?? '') && /b\.md/.test(a ?? '') },
  { id: 'missing-then-create', related: true, goal: 'Read settings.json (it may not exist). If it does not exist, create it containing {"theme":"dark"}, then read it back and tell me the theme.', check: (f, a) => /dark/.test(f['settings.json'] ?? '') && /dark/i.test(a ?? '') },
  { id: 'dotdot-path', related: true, goal: 'Save the text "shared note" to the path ../shared/note.txt.', check: (f) => Object.entries(f).some(([k, v]) => k.endsWith('note.txt') && /shared note/.test(v)) },
  { id: 'counter', related: true, goal: 'Create counter.txt containing 1. Then increment it three times, reading it before each write, so that it ends containing 4.', check: (f) => (f['counter.txt'] ?? '').trim() === '4' },
  { id: 'three-files', related: true, goal: 'Create one.md, two.md and three.md, each containing its own file name. Then read two.md, report its content, and list the workspace.', check: (f, a) => ['one.md', 'two.md', 'three.md'].every((n) => (f[n] ?? '').includes(n.replace('.md', ''))) && /two/.test(a ?? '') },
  { id: 'missing-no-invent', related: true, goal: 'Read missing-report.md and summarize it in two sentences.', check: (_f, a) => /not (exist|found)|missing|no such|ENOENT|does not|couldn|cannot|can.t|unable/i.test(a ?? '') },
];
