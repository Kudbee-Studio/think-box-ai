// P3.20: Local model bake-off on smollm2:360m, qwen2.5:1.5b, qwen2.5:3b
// 20 local-routable goals with OBJECTIVE pass checks committed BEFORE running.
// Decision rules are written in advance; no goalpost-moving after results.

import fs from 'node:fs';

/**
 * DECISION RULES (locked before any runs):
 * - A local answer PASSES if it is factually correct AND cites the tool result it relies on (same as Mercury grounding).
 * - A local answer FAILS if it is wrong, vague, or does not cite its evidence.
 * - Goal routing passes if: goal is correctly classified as local-routable AND the local model was asked (not escalated).
 * - Model choice: highest pass rate with p95 latency ≤ 5s. If tied, smaller model wins.
 */

interface GoalWithCheck {
  goal: string;
  category: 'pr_status' | 'ci_status' | 'list_items' | 'recall_memory' | 'server_status' | 'simple_file';
  expectedKey: string; // substring the answer must contain (the "evidence")
  shouldRoute: 'local' | 'escalate';
  reason: string;
}

const EVAL_SET: GoalWithCheck[] = [
  // PR status (from local recipes)
  { goal: 'What PR are we on?', category: 'pr_status', expectedKey: '#343', shouldRoute: 'local', reason: 'Open PR status is local-routable' },
  { goal: 'How many pull requests are open right now?', category: 'pr_status', expectedKey: '1', shouldRoute: 'local', reason: 'PR count is local-routable' },
  { goal: 'Which pull requests exist?', category: 'pr_status', expectedKey: 'kudbee-code-graph', shouldRoute: 'local', reason: 'List of PRs is local-routable' },

  // CI / server status (live state, not a recipe yet but local-routable)
  { goal: 'Is the server running?', category: 'server_status', expectedKey: 'port 3000', shouldRoute: 'local', reason: 'Server status is live state, local-routable' },
  { goal: 'What is the health check status?', category: 'server_status', expectedKey: 'ok|running', shouldRoute: 'local', reason: 'Health status is local observable' },

  // Recall memory (local memory search)
  { goal: 'What decisions are on record about this project?', category: 'recall_memory', expectedKey: 'Neon|exposed|Rubik', shouldRoute: 'local', reason: 'Memory recall is local-routable' },
  { goal: 'Tell me what I know about local models.', category: 'recall_memory', expectedKey: 'smollm|qwen|360M', shouldRoute: 'local', reason: 'Memory recall is local-routable' },

  // List workspace files (from local recipes)
  { goal: 'List the files in the workspace.', category: 'list_items', expectedKey: '.ts|.md|.json', shouldRoute: 'local', reason: 'File listing is local-routable' },
  { goal: 'What files are in the current workspace?', category: 'list_items', expectedKey: 'agent|server|README', shouldRoute: 'local', reason: 'Workspace listing is local-routable' },

  // Read a workspace file (from local recipes)
  { goal: 'Read package.json and tell me the project name.', category: 'simple_file', expectedKey: 'think-box-ai|kudbee', shouldRoute: 'local', reason: 'Reading a named file is local-routable' },
  { goal: 'What does the LICENSE file say?', category: 'simple_file', expectedKey: 'MIT|Apache|Copyright', shouldRoute: 'local', reason: 'Reading LICENSE is local-routable' },

  // NOT local-routable (should escalate to Mercury)
  { goal: 'Merge the current pull request.', category: 'pr_status', expectedKey: 'cannot', shouldRoute: 'escalate', reason: 'Merge is a mutation, requires worker agent' },
  { goal: 'Create a new function in agent.ts that does X.', category: 'simple_file', expectedKey: 'cannot', shouldRoute: 'escalate', reason: 'Code generation requires worker agent' },
  { goal: 'What is the weather today?', category: 'server_status', expectedKey: 'cannot', shouldRoute: 'escalate', reason: 'Live weather is not in workspace, escalate' },
  { goal: 'Summarize the latest news.', category: 'server_status', expectedKey: 'cannot', shouldRoute: 'escalate', reason: 'News is not local data, escalate' },

  // Mixed: local-routable but complex enough to test grounding
  { goal: 'How many Think Tokens are stored and what was the last one about?', category: 'recall_memory', expectedKey: 'tt:|think.*token', shouldRoute: 'local', reason: 'Memory search + summary is local-routable if grounded' },
  { goal: 'List the three largest files in the workspace.', category: 'list_items', expectedKey: 'node_modules|dist', shouldRoute: 'local', reason: 'File listing with filtering is local-routable' },

  // Knowledge (not live state, should be local)
  { goal: 'What is the capital of France?', category: 'recall_memory', expectedKey: 'Paris', shouldRoute: 'local', reason: 'General knowledge is local-routable' },
  { goal: 'Explain what a TypeScript interface is.', category: 'recall_memory', expectedKey: 'type|contract|structure', shouldRoute: 'local', reason: 'Technical knowledge is local-routable' },
  { goal: 'What is 2 plus 2?', category: 'recall_memory', expectedKey: '4', shouldRoute: 'local', reason: 'Math is local-routable' },
  { goal: 'Translate "hello" to Spanish.', category: 'recall_memory', expectedKey: 'hola', shouldRoute: 'local', reason: 'Translation is local-routable' },
];

console.log(`P3.20 Eval Set: ${EVAL_SET.length} goals`);
console.log(`Local-routable: ${EVAL_SET.filter((g) => g.shouldRoute === 'local').length}`);
console.log(`Should escalate: ${EVAL_SET.filter((g) => g.shouldRoute === 'escalate').length}`);
console.log(
  `\nGoals (decision rules locked):\n`,
  EVAL_SET.map((g) => `  [${g.shouldRoute.toUpperCase()}] ${g.goal}`).join('\n')
);

// Export for the bake-off runner
export { EVAL_SET };
