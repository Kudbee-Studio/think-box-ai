// P3.3 held-out goals (not used to tune matchStrength). Each has expectedLesson slug matching [lesson:slug] in seed titles.
const lines = (t) => (t ?? '').split('\n').map((l) => l.trim()).filter(Boolean);

export const GOALS = [
  {
    id: 'deep-mkdir',
    related: true,
    expectedLesson: 'deep-mkdir',
    goal: 'Write the text "deep" to deep/nested/out.txt (nested folders). Then confirm the path exists via list_files.',
    check: (f) => (f['deep/nested/out.txt'] ?? '').trim() === 'deep',
  },
  {
    id: 'zero-byte',
    related: true,
    expectedLesson: 'zero-byte',
    goal: 'Create empty.file with no content at all (zero bytes). Then tell me the byte count write_file reported.',
    check: (f, a) => 'empty.file' in f && (f['empty.file'] ?? '') === '' && /\b0\b/.test(a ?? ''),
  },
  {
    id: 'path-normalize',
    related: true,
    expectedLesson: 'path-normalize',
    goal: 'Save the text "norm" to the path ./nested/./note.txt .',
    check: (f) => Object.entries(f).some(([k, v]) => k.endsWith('nested/note.txt') && v.trim() === 'norm'),
  },
  {
    id: 'recursive-list',
    related: true,
    expectedLesson: 'recursive-list',
    goal: 'Write a/b/c.txt containing "c". Then run list_files and answer whether a/b/c.txt appears.',
    check: (f, a) => (f['a/b/c.txt'] ?? '').trim() === 'c' && /a\/b\/c\.txt|c\.txt/.test(a ?? ''),
  },
  {
    id: 'size-match',
    related: true,
    expectedLesson: 'size-match',
    goal: 'Write payload.md whose entire content is exactly abcde (5 letters). Report how many bytes write_file returned.',
    check: (f, a) => (f['payload.md'] ?? '') === 'abcde' && /\b5\b/.test(a ?? ''),
  },
  {
    id: 'replace-not-append',
    related: true,
    expectedLesson: 'replace-not-append',
    goal: 'Create hello.txt containing only the letter A. Then replace the entire file so it contains only the letter B (not "AB").',
    check: (f) => (f['hello.txt'] ?? '').trim() === 'B',
  },
  {
    id: 'emoji-utf8',
    related: true,
    expectedLesson: 'emoji-utf8',
    goal: 'Write emoji.txt containing only the single emoji 🎯. Tell me the byte count write_file reported.',
    check: (f, a) => (f['emoji.txt'] ?? '') === '🎯' && /\b4\b/.test(a ?? ''),
  },
  {
    id: 'json-line',
    related: true,
    expectedLesson: 'json-line',
    goal: 'Write data.json whose entire content is exactly {"ok":true} on one line with no spaces.',
    check: (f) => (f['data.json'] ?? '').trim() === '{"ok":true}',
  },
];
