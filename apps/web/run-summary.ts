// After a run: one plain card. What happened, what changed, what it cost, and what to do next. Built from the saved run record only; it never invents a number.
import type { RunRecord } from './runs.ts';

export interface RunSummary { headline: string; lines: string[]; next: string[] }
type Summarizable = Pick<RunRecord, 'status' | 'files' | 'approvals' | 'tool_calls'> & Partial<Pick<RunRecord, 'duration_ms' | 'cost_usd' | 'steps' | 'error' | 'evidence_conflicts'>>;

const plural = (n: number, word: string): string => `${n} ${word}${n === 1 ? '' : 's'}`;

export function summarizeRun(run: Summarizable): RunSummary {
  const secs = typeof run.duration_ms === 'number' ? `${(run.duration_ms / 1000).toFixed(1)}s` : null;
  const headline = run.status === 'failed' ? `Failed: ${run.error || 'the run did not finish'}` : run.status === 'stopped' ? 'Stopped before it finished' : run.status === 'running' ? 'Still running' : `Done${secs ? ` in ${secs}` : ''}`;
  const lines: string[] = [];
  const files = run.files ?? [];
  if (files.length) lines.push(`Changed ${plural(files.length, 'file')}: ${files.slice(0, 5).join(', ')}${files.length > 5 ? ` and ${files.length - 5} more` : ''}`);
  else lines.push('No files changed');
  const facts = [typeof run.cost_usd === 'number' ? `$${run.cost_usd.toFixed(4)}` : null, Array.isArray(run.steps) ? plural(run.steps.length, 'step') : null, typeof run.tool_calls === 'number' ? plural(run.tool_calls, 'tool call') : null].filter(Boolean);
  if (facts.length) lines.push(facts.join(' · '));
  const a = run.approvals;
  if (a && (a.approved || a.denied)) lines.push(`Approvals: ${a.approved} approved, ${a.denied} denied`);
  for (const c of run.evidence_conflicts ?? []) lines.push(`The answer disagreed with what a tool returned: ${c}`);
  const next: string[] = [];
  if (files.length) next.push('Review the changes in the Files panel (Changes); undo any you do not want.');
  if (run.status === 'failed') next.push('Open the Execution timeline to see the step that failed.');
  return { headline, lines, next };
}
