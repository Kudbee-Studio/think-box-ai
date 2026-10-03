// P3.20 eval set. Pass checks are fixed HERE, before any model is run; nothing below changes after seeing results.
//
// Three kinds of goal, matching how the product uses the local model:
//   knowledge  - plain chat, objective expected answer (regex).
//   data       - code made the lookup (a fixed fixture stands in for it); the model words it. PASS = the sentence passes groundedAnswer
//                (every number/link is in the fixture) AND it contains at least one `must` fragment from the fixture.
//   escalate   - the ROUTER must refuse to send it local (localConfidence below LOCAL_THRESHOLD). No model is run.
// Default-model rule (fixed now): highest pass rate over knowledge+data goals with p95 latency <= 5000 ms; tie -> the smaller model.

export const LOCAL_THRESHOLD = 60;

export interface Goal {
  kind: 'knowledge' | 'data' | 'escalate';
  goal: string;
  expect?: RegExp;
  facts?: string;
  must?: RegExp;
}

const PRS = 'Open pull requests in Acme/widgets (live from GitHub just now): 2.\n- #331 "Add retry to the uploader" by sam, updated 2026-10-01T10:00:00Z https://github.com/Acme/widgets/pull/331\n- #330 "Fix flaky cache test" (draft) by lee, updated 2026-09-30T09:00:00Z https://github.com/Acme/widgets/pull/330';
const MERGED = 'Last merged pull request in Acme/widgets (live from GitHub just now):\n- #329 "Polish the dashboard" by sam, merged 2026-10-01T08:00:00Z https://github.com/Acme/widgets/pull/329';
const FILES = 'Workspace files (3):\n- notes.md (31 B)\n- data/out.csv (200 B)\n- src/main.ts (1200 B)';
const CI = 'Latest CI run on main in Acme/widgets (live from GitHub just now):\n- "tests" failure, finished 2026-10-01T11:00:00Z https://github.com/Acme/widgets/actions/runs/777';
const TOKENS = 'Think Tokens (3 accepted):\n- TT-000001 "Prefer list_files before read_file"\n- TT-000002 "Cite the fetched URL in answers"\n- TT-000003 "Stop after the file is written"';
const SERVER = 'Server health (live just now): status ok, uptime 3600 s, port 3000.';
const MEMORY = 'Recalled 2 memories:\n- "Decisions on record" (org): Neon rejected, test key rotated.\n- "Local model notes" (org): smollm2 is plain chat only.';
const FILE = 'File notes.md (first 40 characters):\nShip the uploader retry on Friday.';

export const EVAL_SET: Goal[] = [
  { kind: 'knowledge', goal: 'What is the capital of France?', expect: /paris/i },
  { kind: 'knowledge', goal: 'What is 2 plus 2?', expect: /\b4\b|four/i },
  { kind: 'knowledge', goal: 'Translate "hello" to Spanish.', expect: /hola/i },
  { kind: 'knowledge', goal: 'What is the chemical symbol for water?', expect: /H2O|H₂O/i },
  { kind: 'knowledge', goal: 'Name the largest planet in our solar system.', expect: /jupiter/i },
  { kind: 'knowledge', goal: 'What is 10 times 3?', expect: /\b30\b|thirty/i },
  { kind: 'data', goal: 'WHAT PR ARE WE ON', facts: PRS, must: /#331|#330/ },
  { kind: 'data', goal: 'which pull requests are open?', facts: PRS, must: /#331|#330/ },
  { kind: 'data', goal: 'what was the last merged PR?', facts: MERGED, must: /#329/ },
  { kind: 'data', goal: 'list my files', facts: FILES, must: /notes\.md|out\.csv|main\.ts/ },
  { kind: 'data', goal: 'did CI pass on main?', facts: CI, must: /fail/i },
  { kind: 'data', goal: 'list my Think Tokens', facts: TOKENS, must: /TT-00000[123]/ },
  { kind: 'data', goal: 'is the server up?', facts: SERVER, must: /\bok\b|up|3000/i },
  { kind: 'data', goal: 'what do you remember about local models?', facts: MEMORY, must: /smollm2|plain chat/i },
  { kind: 'data', goal: 'read notes.md and tell me what it says', facts: FILE, must: /uploader|Friday/i },
  { kind: 'escalate', goal: 'Merge the current pull request.' },
  { kind: 'escalate', goal: 'Create a new function in agent.ts that retries failed fetches.' },
  { kind: 'escalate', goal: 'What is the weather today?' },
  { kind: 'escalate', goal: 'Summarize the latest news about AI.' },
  { kind: 'escalate', goal: 'Refactor the memory module and write tests for it.' },
];
