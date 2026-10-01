// kudbEE Think Token extractor (ADR 028). Deterministic: the same finished run always yields the same
// drafts. Only a successful run mints tokens (a failed or stopped run teaches nothing reliable), at most
// MAX_PER_RUN per run, and drafts hold run metadata (tool names, error summaries) rather than transcripts.
// Every draft is only a proposal; SqliteTokenStore.write() is the admission gate that redacts, caps and records it.
import type { AgentEvent } from './agent.ts';
import { LIMITS, keywords, redact, type TokenDraft } from './think-token-store.ts';

export const MAX_PER_RUN = 3;
const EVIDENCE_TOOLS = new Set(['fetch_url', 'read_rss', 'read_file']);

export interface FinishedRun {
  id: string;
  goal: string;
  success: boolean;
  steps: AgentEvent[];
}

function clip(text: string, max: number): string {
  const flat = text.replace(/\s+/g, ' ').trim();
  return flat.length > max ? `${flat.slice(0, max - 1)}…` : flat;
}

function goalTags(goal: string): string[] {
  return keywords(goal).slice(0, 5);
}

export function extractDrafts(run: FinishedRun): TokenDraft[] {
  if (!run.success) return [];
  const tools = run.steps.filter((s): s is Extract<AgentEvent, { kind: 'tool' }> => s.kind === 'tool');
  const drafts: TokenDraft[] = [];
  const tags = goalTags(run.goal);
  const goal = clip(redact(run.goal), 80);
  const evidence = `run:${run.id}`;

  // A fix that worked: a tool failed, and a later call to the same tool succeeded.
  for (let i = 0; i < tools.length && drafts.length < MAX_PER_RUN; i++) {
    const failed = tools[i];
    if (failed.ok || !failed.error) continue;
    const recovered = tools.slice(i + 1).find((t) => t.ok && t.name === failed.name);
    if (!recovered) continue;
    drafts.push({
      source_run_id: run.id,
      kind: 'fix',
      title: `${failed.name} recovery for "${goal}"`.slice(0, LIMITS.title),
      content: `${failed.name} failed with "${clip(failed.error, 160)}"; a retry succeeded after changing its arguments (${Object.keys(recovered.args).slice(0, 6).join(', ') || 'none'}).`,
      tags: [failed.name, 'fix', ...tags],
      evidence_ref: evidence,
    });
  }

  // A tool pattern: two or more distinct successful tools in order.
  const okSeq = tools.filter((t) => t.ok).map((t) => t.name);
  const dedup = okSeq.filter((name, i) => name !== okSeq[i - 1]);
  if (dedup.length >= 2 && drafts.length < MAX_PER_RUN) {
    drafts.push({
      source_run_id: run.id,
      kind: 'tool_pattern',
      title: `Tool sequence for "${goal}"`.slice(0, LIMITS.title),
      content: `For goals like "${goal}", this tool sequence worked: ${dedup.slice(0, 8).join(' → ')}.`,
      tags: [...dedup.slice(0, 3), 'tool_pattern', ...tags],
      evidence_ref: evidence,
    });
  }

  // A lesson: the answer was grounded in observed evidence, not model memory.
  const grounded = [...new Set(tools.filter((t) => t.ok && EVIDENCE_TOOLS.has(t.name)).map((t) => t.name))];
  if (grounded.length && drafts.length < MAX_PER_RUN) {
    drafts.push({
      source_run_id: run.id,
      kind: 'lesson',
      title: `Ground "${goal}" in evidence`.slice(0, LIMITS.title),
      content: `Goals like "${goal}" were answered successfully using observed evidence from ${grounded.join(', ')}.`,
      tags: [...grounded, 'lesson', ...tags],
      evidence_ref: evidence,
    });
  }
  return drafts.slice(0, MAX_PER_RUN);
}

/** Optional cheap local-model pass. It may only reword title/content; everything else (kind, tags, evidence) is kept, and the store gate re-checks the result. */
export type Refiner = (draft: TokenDraft) => Promise<{ title: string; content: string } | null>;

export async function refineDrafts(drafts: TokenDraft[], refine?: Refiner): Promise<TokenDraft[]> {
  if (!refine) return drafts;
  const out: TokenDraft[] = [];
  for (const draft of drafts) {
    try {
      const better = await refine(draft);
      if (better && typeof better.title === 'string' && typeof better.content === 'string' && better.title.trim() && better.content.trim()) {
        out.push({ ...draft, title: better.title.slice(0, LIMITS.title), content: better.content.slice(0, LIMITS.content) });
        continue;
      }
    } catch {
      // A local model that is down or misbehaving falls back to the deterministic draft.
    }
    out.push(draft);
  }
  return out;
}
