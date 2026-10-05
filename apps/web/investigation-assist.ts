// When a small model answers an investigation goal with nothing (an empty reply, or an answer with no tool call), the engine can run the FIRST read-only
// tool itself for the goal shapes it recognises, then hand the evidence back and ask the model only for a grounded finding. The engine never decides the
// finding and never invents a path: every path it uses is written in the goal, and a tool that fails (path not found) simply yields no evidence.
import type { RepoEvidence } from './repo-tools.ts';

export type GoalShape = 'untested-function' | 'defines-constant' | 'named-function';
export type AssistCall = (tool: 'repo_search' | 'repo_read', args: Record<string, unknown>) => Promise<RepoEvidence | null>;

const UNTESTED = /\b(?:no|without|lacks?|lacking)\s+(?:a\s+|any\s+)?tests?\b|\buntested\b|\b(?:never|not)\s+covered\b|\bnot\s+tested\b/i;
const FILE_IN_GOAL = /\b((?:src|lib|app|server|packages)\/[\w./-]+\.[A-Za-z]{1,5})\b/;
const CONSTANT = /\bdefines?\s+([A-Z][A-Z0-9_]{2,})\b/;
const NAMED = /\bfunction\s+named\s+([A-Za-z_$][\w$]{1,79})\b/i;
const EXPORTED = /export\s+(?:async\s+)?(?:function\*?|class)\s+([A-Za-z_$][\w$]*)/;
const MAX_SYMBOLS = 6;

/** Which known goal shape this is, and what the goal itself names. Pure. */
export function goalShape(goal: string): { shape: GoalShape; file?: string; name?: string } | null {
  const file = goal.match(FILE_IN_GOAL)?.[1];
  if (UNTESTED.test(goal) && file) return { shape: 'untested-function', file };
  const c = goal.match(CONSTANT); if (c) return { shape: 'defines-constant', name: c[1]! };
  const n = goal.match(NAMED); if (n) return { shape: 'named-function', name: n[1]! };
  return null;
}

/** Run the first tool(s) for the goal. Returns how many tool calls the engine made (0 = the shape is unknown or nothing ran). */
export async function runRepoAssist(goal: string, call: AssistCall): Promise<number> {
  const shape = goalShape(goal);
  if (!shape) return 0;
  let calls = 0;
  const run = async (tool: 'repo_search' | 'repo_read', args: Record<string, unknown>): Promise<RepoEvidence | null> => { calls += 1; return call(tool, args); };
  if (shape.shape === 'untested-function') {
    const read = await run('repo_read', { path: shape.file!, start: 1, end: 200 });
    if (!read || read.tool !== 'repo_read') return calls;
    const names = [...new Set(read.lines.map((l) => l.text.match(EXPORTED)?.[1]).filter((x): x is string => Boolean(x)))].slice(0, MAX_SYMBOLS);
    for (const name of names) {
      // look for the function in the tests folder; when the repo has no such folder the search is over the whole repository
      const inTests = await run('repo_search', { query: name, path: 'tests' });
      if (!inTests) await run('repo_search', { query: name, path: '' });
    }
    return calls;
  }
  await run('repo_search', { query: shape.name!, path: '' });
  return calls;
}
