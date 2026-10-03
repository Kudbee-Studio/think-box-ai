// Which goals a local chat model can honestly answer (Layer 1, foundation: pure, no I/O).
//
// A local Ollama model runs as a plain chat with no tools (server.ts). It answers "2 plus 2" fine, but "what PR are we on" got a confident,
// made-up essay about machine learning, because it cannot look anything up. needsToolsOrLiveData() says when a goal depends on something
// outside the model's head, so the server can send it to the worker agent instead. It is conservative: a false positive costs a Mercury call,
// a false negative is a confident wrong answer, but plain knowledge questions must stay local.

// Heuristics: length, keywords, tool complexity. Shared by the CLI's auto-routing (simple -> local, complex -> Mercury-2).
export const COMPLEX_PATTERNS: RegExp[] = [
  /\b(code|write|generate|create|build|implement|design|refactor)\b/i,
  /\b(research|analyze|investigate|compare|debug|trace|profile)\b/i,
  /\b(multiple|several|many)\b.*\b(files|tasks|steps|goals|functions)\b/i,
  /\{.*\}/, // JSON structure in goal
  /```/, // Code blocks
  /\b(algorithm|architecture|design pattern|optimize|complex)\b/i,
];

const NEEDS: Array<{ reason: string; pattern: RegExp }> = [
  { reason: 'it asks about this repository or its pull requests, issues, branches, commits or CI', pattern: /\b(prs?|pull[- ]requests?|issues?|branch(es)?|commits?|merge[sd]?|repo(sitory)?|ci|build status|pipeline|workflow|deploy(ed|ment)?)\b/i },
  { reason: 'it asks about live state (what is running, open, failing, available or up)', pattern: /\b(is (it )?(up|down|running|working|open|failing|passing)|status of|currently|right now|uptime|port \d+|server (is|was)|balance)\b/i },
  { reason: 'it asks about the current date, time or recent events', pattern: /\b(today|tonight|now|latest|newest|recent(ly)?|current(ly)?|this (week|month|year)|news|weather|forecast|stock|price of|exchange rate|score)\b/i },
  { reason: 'it refers to a file, folder, workspace, URL or website', pattern: /(https?:\/\/|\bwww\.|\b[\w-]+\.(com|org|net|io|dev|ai)\b|\b[\w./-]+\.(md|txt|json|ts|js|mjs|py|csv|html|ya?ml|xml|log|pdf|png|jpe?g)\b|\b(files?|folders?|directory|directories|workspace|disk|path)\b)/i },
  { reason: 'it asks to take an action (read, open, list, search, fetch, download, run, install, clone, delete, save or send something)', pattern: /\b(read|open|list|search|look ?up|fetch|download|upload|run|execute|install|clone|delete|save|send|email|scrape|browse)\b/i },
  { reason: 'it asks for an image', pattern: /\b(image|picture|photo|drawing|logo|screenshot)s?\b/i },
  { reason: 'it asks about this system, its memory, tokens, runs or tasks', pattern: /\b(think ?tokens?|tt-\d+|memory|memories|my (runs?|tasks?|files?)|agent os|kudbee|dashboard)\b/i },
];

/** A reason sentence fragment when the goal depends on tools or live data, otherwise null. */
export function needsToolsOrLiveData(goal: string): string | null {
  const text = String(goal ?? '');
  for (const { reason, pattern } of NEEDS) if (pattern.test(text)) return reason;
  return null;
}

/** The CLI's rule: a goal is complex (worker agent) when it matches a complexity pattern, is long, or needs tools or live data. */
export function isComplexGoal(goal: string): boolean {
  return COMPLEX_PATTERNS.some((p) => p.test(goal)) || goal.length > 150 || needsToolsOrLiveData(goal) !== null;
}

/** Confidence (0-100) that a local model can handle this goal reliably. For P3.20 routing. */
export function localConfidence(goal: string): number {
  const text = String(goal ?? '');

  // Anything needing tools or live data: low confidence unless it's a known recipe
  if (needsToolsOrLiveData(text)) {
    const recipes = /\b(what pr|list files|list workspace|read.*\.md|read.*\.json|read.*\.ts|open pr|pull requests|current pr)\b/i;
    if (recipes.test(text)) return 75; // Known recipes have decent confidence
    return 25; // Unknown live-data goals: risky
  }

  // Plain knowledge questions: high confidence
  if (/\b(what is|define|explain|tell me|translate|how to|write|say|count|calculate|2\s?plus|capital of)\b/i.test(text)) {
    return 90;
  }

  // Complex code/analysis: low confidence
  if (isComplexGoal(text)) return 30;

  // Default: medium-high (most things will work at some level)
  return 70;
}

/** Ground an answer in evidence: check that it cites a fact from the tool result. Used for P3.20 grounding. */
export function groundAnswer(answer: string, evidence: string[]): { ok: boolean; why?: string } {
  const answerLower = answer.toLowerCase();
  // If answer contains a key fact from evidence, it's grounded
  for (const fact of evidence) {
    if (answerLower.includes(fact.toLowerCase())) return { ok: true };
  }
  // If no evidence was provided, we can't check grounding (will show data anyway)
  if (evidence.length === 0) return { ok: true };
  // Ungrounded
  return { ok: false, why: 'answer did not cite the supporting data' };
}
