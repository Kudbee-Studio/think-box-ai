// kudbEE specialist agent layer — capability contracts over the existing #288 execution path.
//
// This does NOT create a second agent runtime. Every specialist here is data: a contract plus
// pure validation functions, meant to compose with the existing `AgentProfile` (agent.ts) the
// same way `hermes`/`asclepius` already do — allowedTools restricts a real runToolAgent() call,
// roleContext becomes its system prompt. Director selection below is a pure, deterministic
// function (no LLM call), kept that way specifically so it costs nothing and is fully testable.
//
// HONEST ARCHITECTURE BOUNDARY (read before assuming more than this provides):
// #288 is one agent per session — there is no mechanism anywhere in this codebase to run several
// Think Boxes concurrently on one job. So "SWARM" below means Director selects which specialist
// CONTRACTS apply and in what order; it does not mean parallel execution. Claiming otherwise
// would repeat exactly the kind of unproven claim the Think Token audit (docs/enterprise/
// think-token-audit.md) found and corrected. See tests/specialist-contracts.test.ts for what is
// actually proven here versus explicitly marked UNPROVEN/BLOCKED.

export type PermissionBoundary = 'read_only' | 'read_write' | 'none';

export interface SpecialistContract {
  id: string;
  name: string;
  capability: string;
  /** What this specialist is allowed to receive as input. */
  allowedInputs: string[];
  /** What this specialist must produce. */
  expectedOutputs: string[];
  /** What must exist before a claim from this specialist can be believed. */
  evidenceRequirements: string[];
  successCriteria: string;
  failureBehavior: string;
  /** Real tool names from agent.ts's TOOLS list, or [] for a specialist that does no tool use. */
  toolsRequired: string[];
  modelRequirements: string;
  permissionsBoundary: PermissionBoundary;
  handoffContract: {
    /** Specialist ids this one may receive handoffs from. */
    acceptsFrom: string[];
    /** Specialist ids this one may hand off to. */
    handsOffTo: string[];
  };
  /** Specialist ids this one must never be collapsed into the same acting identity as. */
  mustBeIndependentOf: string[];
}

export const SPECIALISTS: Readonly<Record<string, SpecialistContract>> = Object.freeze({
  director: {
    id: 'director', name: 'Director',
    capability: 'Reads an intent/opportunity and selects which specialists a job needs; does not execute work itself.',
    allowedInputs: ['intent', 'opportunity'],
    expectedOutputs: ['selected_specialist_ids', 'selection_rationale'],
    evidenceRequirements: [], // selection itself produces no evidence claim to verify
    successCriteria: 'Selected specialists collectively cover every required capability for the intent, with no unnecessary inclusion.',
    failureBehavior: 'If no specialist covers a required capability, the job is reported BLOCKED, not silently run short-handed.',
    toolsRequired: [],
    modelRequirements: 'none (deterministic selection, no model call)',
    permissionsBoundary: 'none',
    handoffContract: { acceptsFrom: [], handsOffTo: ['researcher', 'builder', 'debugger', 'security', 'tester', 'disruptor'] },
    mustBeIndependentOf: [],
  },
  researcher: {
    id: 'researcher', name: 'Researcher',
    capability: 'Gathers information from memory and the public web before work starts.',
    allowedInputs: ['goal', 'prior_memory'],
    expectedOutputs: ['findings', 'sources'],
    evidenceRequirements: ['at least one fetch_url/read_rss/recall result backing every finding'],
    successCriteria: 'Every finding cites a source that was actually fetched or recalled in this run.',
    failureBehavior: 'Reports "no evidence found" rather than asserting an unsourced finding.',
    toolsRequired: ['fetch_url', 'read_rss', 'recall'],
    modelRequirements: 'mercury-2 (existing #288 worker path) or ollama local',
    permissionsBoundary: 'read_only',
    handoffContract: { acceptsFrom: ['director'], handsOffTo: ['builder', 'synthesizer'] },
    mustBeIndependentOf: [],
  },
  builder: {
    id: 'builder', name: 'Builder',
    capability: 'Produces or modifies a concrete artifact (file, code, document) in the session workspace.',
    allowedInputs: ['goal', 'researcher_findings'],
    expectedOutputs: ['artifact_path', 'artifact_diff_or_content'],
    evidenceRequirements: ['the write_file/exec tool_result that actually created or changed the artifact'],
    successCriteria: 'The claimed artifact exists on disk with the claimed content, independently checkable by Validator.',
    failureBehavior: 'A failed write_file/exec leaves the task visibly failed; Builder never reports success for a tool call that returned an error.',
    toolsRequired: ['write_file', 'read_file'],
    modelRequirements: 'mercury-2 (existing #288 worker path) or ollama local',
    permissionsBoundary: 'read_write',
    handoffContract: { acceptsFrom: ['director', 'researcher'], handsOffTo: ['tester', 'debugger', 'disruptor', 'validator'] },
    mustBeIndependentOf: ['disruptor'],
  },
  debugger: {
    id: 'debugger', name: 'Debugger',
    capability: 'Diagnoses why a prior tool_result/execution failed and proposes a concrete fix, without claiming the fix works until re-tested.',
    allowedInputs: ['failed_tool_result', 'error_message'],
    expectedOutputs: ['diagnosis', 'proposed_fix'],
    evidenceRequirements: ['the exact failing tool_result it is diagnosing'],
    successCriteria: 'The proposed fix is re-run and produces a successful tool_result; a diagnosis alone is not success.',
    failureBehavior: 'If the fix also fails, that failure is recorded, not hidden behind the diagnosis text.',
    toolsRequired: ['read_file', 'write_file'],
    modelRequirements: 'mercury-2 (existing #288 worker path) or ollama local',
    permissionsBoundary: 'read_write',
    handoffContract: { acceptsFrom: ['builder', 'disruptor'], handsOffTo: ['builder', 'tester'] },
    mustBeIndependentOf: [],
  },
  security: {
    id: 'security', name: 'Security',
    capability: 'Reviews an artifact or plan for secrets, destructive commands, or scope beyond the stated goal before it ships.',
    allowedInputs: ['artifact_path', 'planned_tool_calls'],
    expectedOutputs: ['findings', 'block_or_pass'],
    evidenceRequirements: ['the actual artifact content or tool-call list reviewed, quoted or referenced, not summarized from memory'],
    successCriteria: 'A pass decision only follows an actual read of the artifact/plan in this run.',
    failureBehavior: 'When unsure, blocks rather than passes; a block always states what would resolve it.',
    toolsRequired: ['read_file'],
    modelRequirements: 'mercury-2 (existing #288 worker path) or ollama local',
    permissionsBoundary: 'read_only',
    handoffContract: { acceptsFrom: ['builder', 'director'], handsOffTo: ['validator', 'proof_keeper'] },
    mustBeIndependentOf: ['builder'],
  },
  tester: {
    id: 'tester', name: 'Tester',
    capability: 'Runs the existing test suite (or a targeted subset) against Builder\'s change and reports the real result.',
    allowedInputs: ['artifact_path', 'test_command'],
    expectedOutputs: ['pass_fail', 'raw_test_output'],
    evidenceRequirements: ['the actual command exit code and stdout/stderr'],
    successCriteria: 'Reported pass/fail matches the real exit code; never a bare "tests pass" without the output that proves it.',
    failureBehavior: 'A failing test is reported with its real output and handed to Debugger, not retried silently until green.',
    toolsRequired: ['exec'],
    modelRequirements: 'mercury-2 (existing #288 worker path) or ollama local',
    permissionsBoundary: 'read_only',
    handoffContract: { acceptsFrom: ['builder'], handsOffTo: ['debugger', 'validator'] },
    mustBeIndependentOf: ['builder'],
  },
  disruptor: {
    id: 'disruptor', name: 'Disruptor',
    capability: 'Deliberately attempts to break Builder\'s artifact or claim (edge cases, adversarial input), independent of Builder.',
    allowedInputs: ['artifact_path', 'builder_claim'],
    expectedOutputs: ['vulnerabilities_found', 'repro_steps'],
    evidenceRequirements: ['a reproducible tool_result demonstrating each claimed vulnerability'],
    successCriteria: 'Every reported vulnerability includes a step that actually reproduces it in this session.',
    failureBehavior: 'Finding nothing is reported as "no vulnerability found in this pass", never as "verified secure".',
    toolsRequired: ['read_file', 'exec'],
    modelRequirements: 'mercury-2 (existing #288 worker path) or ollama local',
    permissionsBoundary: 'read_only',
    handoffContract: { acceptsFrom: ['builder', 'security'], handsOffTo: ['debugger', 'validator'] },
    mustBeIndependentOf: ['builder'],
  },
  validator: {
    id: 'validator', name: 'Validator',
    capability: 'Independently re-checks evidence other specialists submitted; never trusts a self-report.',
    allowedInputs: ['claims_with_evidence'],
    expectedOutputs: ['validation_result'],
    evidenceRequirements: ['Validator\'s own independent re-check of the underlying evidence, not a re-statement of the original claim'],
    successCriteria: 'Validation result is reproducible by re-running the same check against the same evidence.',
    failureBehavior: 'An unverifiable claim is marked INVALID, not passed through on trust.',
    toolsRequired: ['read_file'],
    modelRequirements: 'mercury-2 (existing #288 worker path) or ollama local',
    permissionsBoundary: 'read_only',
    handoffContract: { acceptsFrom: ['builder', 'tester', 'disruptor', 'security', 'researcher'], handsOffTo: ['proof_keeper'] },
    mustBeIndependentOf: ['builder'],
  },
  memory_curator: {
    id: 'memory_curator', name: 'Memory Curator',
    capability: 'Writes evidence-backed findings into org-layer memory; never promotes anything to the verified layer.',
    allowedInputs: ['validated_findings'],
    expectedOutputs: ['memory_item_id'],
    evidenceRequirements: ['the Validator result backing the item being saved'],
    successCriteria: 'Every write goes to the org layer via remember/POST /api/memory; the verified layer is never touched by this specialist.',
    failureBehavior: 'A finding without a Validator result is not saved at all, rather than saved unverified.',
    toolsRequired: ['remember', 'recall'],
    modelRequirements: 'mercury-2 (existing #288 worker path) or ollama local',
    permissionsBoundary: 'read_write',
    handoffContract: { acceptsFrom: ['validator'], handsOffTo: ['synthesizer'] },
    mustBeIndependentOf: [],
  },
  synthesizer: {
    id: 'synthesizer', name: 'Synthesizer',
    capability: 'Combines validated findings and the artifact into one coherent final answer for the job.',
    allowedInputs: ['validated_findings', 'artifact_path'],
    expectedOutputs: ['final_summary'],
    evidenceRequirements: ['every claim in the summary traces to a validated finding or the artifact itself'],
    successCriteria: 'No sentence in the summary is unsupported by something upstream produced with evidence.',
    failureBehavior: 'Gaps are stated as gaps ("X was not verified"), not smoothed over.',
    toolsRequired: ['read_file'],
    modelRequirements: 'mercury-2 (existing #288 worker path) or ollama local',
    permissionsBoundary: 'read_only',
    handoffContract: { acceptsFrom: ['memory_curator', 'validator'], handsOffTo: ['proof_keeper'] },
    mustBeIndependentOf: [],
  },
  resource_manager: {
    id: 'resource_manager', name: 'Resource Manager',
    capability: 'Records the real resource usage (tokens, cost, duration, tool calls) a job actually consumed.',
    allowedInputs: ['run_record'],
    expectedOutputs: ['resource_usage_report'],
    evidenceRequirements: ['the real RunRecord fields (prompt_tokens, completion_tokens, cost_usd, duration_ms, tool_calls) from runs.ts, not an estimate'],
    successCriteria: 'Reported numbers equal the real run_metadata persisted by persistence.ts for this run.',
    failureBehavior: 'Never estimates; if the real record is unavailable, reports UNPROVEN rather than a guess.',
    toolsRequired: [],
    modelRequirements: 'none (reads existing telemetry, no model call)',
    permissionsBoundary: 'read_only',
    handoffContract: { acceptsFrom: ['director'], handsOffTo: ['proof_keeper'] },
    mustBeIndependentOf: [],
  },
  proof_keeper: {
    id: 'proof_keeper', name: 'Proof Keeper',
    capability: 'Assembles the final proof artifact from evidence already produced; cannot create or alter evidence.',
    allowedInputs: ['validator_results', 'resource_usage_report', 'synthesizer_summary'],
    expectedOutputs: ['proof_artifact'],
    evidenceRequirements: ['every field in the proof artifact must reference an upstream specialist\'s output; a field with no such reference is not permitted'],
    successCriteria: 'A proof artifact only exists when Validator has already returned a non-empty, passing result for the claim it proves.',
    failureBehavior: 'If Validator has not run or found the evidence insufficient, Proof Keeper refuses to produce a proof artifact at all — it does not fabricate one.',
    toolsRequired: [],
    modelRequirements: 'none (pure assembly from upstream outputs, no model call)',
    permissionsBoundary: 'read_only',
    handoffContract: { acceptsFrom: ['validator', 'resource_manager', 'synthesizer'], handsOffTo: [] },
    mustBeIndependentOf: ['builder'],
  },
});

export const SPECIALIST_IDS = Object.freeze(Object.keys(SPECIALISTS));

// ─── Director selection ─────────────────────────────────────────
// Deterministic, no model call: keyword/capability matching against intent + opportunity text.
// Kept simple and total specifically so it's free to run and exhaustively testable.

const KEYWORD_TO_SPECIALIST: ReadonlyArray<{ pattern: RegExp; id: string }> = [
  { pattern: /\b(research|find out|look up|investigate)\b/i, id: 'researcher' },
  { pattern: /\b(build|create|implement|write|fix|add)\b/i, id: 'builder' },
  { pattern: /\b(debug|diagnose|error|broken|failing)\b/i, id: 'debugger' },
  { pattern: /\b(secur|vulnerab|secret|credential)\b/i, id: 'security' },
  { pattern: /\b(test|verify tests|run.*suite)\b/i, id: 'tester' },
  { pattern: /\b(adversarial|break it|disrupt|attack|stress)\b/i, id: 'disruptor' },
  { pattern: /\b(validate|verify|double.?check)\b/i, id: 'validator' },
  { pattern: /\b(remember|save.*memory|note this)\b/i, id: 'memory_curator' },
  { pattern: /\b(summariz|synthesi)/i, id: 'synthesizer' },
  { pattern: /\b(cost|budget|resource usage|token usage)\b/i, id: 'resource_manager' },
  { pattern: /\b(prove|proof|evidence artifact)\b/i, id: 'proof_keeper' },
];

export interface SelectionResult {
  selected: string[];
  rationale: Record<string, string>;
  blocked: boolean;
  blockedReason?: string;
}

/**
 * Director's selection function. Pure and deterministic: same intent (+opportunity) text always
 * selects the same specialists. Builder, if selected, always pulls in Validator (nothing may
 * claim success without independent verification) — this is a hard rule, not a suggestion.
 */
export function selectSpecialists(intent: string, opportunity?: string): SelectionResult {
  const text = `${intent} ${opportunity ?? ''}`;
  const selected = new Set<string>();
  const rationale: Record<string, string> = {};

  for (const { pattern, id } of KEYWORD_TO_SPECIALIST) {
    if (pattern.test(text)) {
      selected.add(id);
      rationale[id] = `matched /${pattern.source}/i in intent/opportunity text`;
    }
  }

  if (selected.has('builder') && !selected.has('validator')) {
    selected.add('validator');
    rationale.validator = (rationale.validator ?? '') + ' auto-added: Builder is selected, and no specialist may claim success without independent verification';
  }
  if (selected.has('builder') && !selected.has('security')) {
    // Not forced the way Validator is (Disruptor is a stronger, opt-in adversarial pass), but
    // Security always accompanies Builder for a baseline review (including when Disruptor is selected).
    selected.add('security');
    rationale.security = (rationale.security ?? '') + ' auto-added: Builder is selected, baseline review required';
  }

  if (selected.size === 0) {
    return { selected: [], rationale: {}, blocked: true, blockedReason: 'No specialist capability matched this intent/opportunity text.' };
  }

  return { selected: [...selected].sort(), rationale, blocked: false };
}

// ─── Evidence and validation ────────────────────────────────────

export interface Evidence {
  specialistId: string;
  claim: string;
  /** A reference to something checkable: a tool_result, a file path, a run id — never free text alone. */
  reference: string;
}

export interface ValidationResult {
  valid: boolean;
  checkedEvidenceCount: number;
  reason: string;
}

/**
 * Validator's independent check: valid only if every piece of evidence has both a claim and a
 * concrete reference, and the submitting specialist is not Validator itself (independence).
 */
export function independentlyValidate(evidence: Evidence[]): ValidationResult {
  if (evidence.length === 0) {
    return { valid: false, checkedEvidenceCount: 0, reason: 'No evidence submitted; nothing to validate.' };
  }
  for (const e of evidence) {
    if (e.specialistId === 'validator') {
      return { valid: false, checkedEvidenceCount: 0, reason: 'Validator cannot validate its own evidence (independence violation).' };
    }
    if (!e.reference || !e.reference.trim()) {
      return { valid: false, checkedEvidenceCount: 0, reason: `Evidence for claim "${e.claim}" has no concrete reference.` };
    }
  }
  return { valid: true, checkedEvidenceCount: evidence.length, reason: 'Every claim has a concrete, checkable reference.' };
}

export interface ProofArtifactInput {
  jobId: string;
  claim: string;
  evidence: Evidence[];
  validation: ValidationResult;
  resourceUsage?: { tokens: number; costUsd: number; durationMs: number };
}

/**
 * Proof Keeper: refuses to produce an artifact unless validation already passed. This is the
 * code-level enforcement of "Proof Keeper cannot manufacture evidence" — there is no path here
 * that creates evidence or a passing validation; both must already exist, from upstream.
 */
export function assembleProof(input: ProofArtifactInput): { ok: true; artifact: Record<string, unknown> } | { ok: false; reason: string } {
  if (!input.validation.valid) {
    return { ok: false, reason: 'Validation did not pass; Proof Keeper will not produce a proof artifact for an unvalidated claim.' };
  }
  if (input.evidence.length === 0) {
    return { ok: false, reason: 'No evidence to reference; Proof Keeper has no mechanism to create evidence itself.' };
  }
  return {
    ok: true,
    artifact: {
      jobId: input.jobId,
      claim: input.claim,
      evidenceReferences: input.evidence.map((e) => ({ specialistId: e.specialistId, reference: e.reference })),
      validation: input.validation,
      resourceUsage: input.resourceUsage ?? null,
    },
  };
}

/**
 * Enforces "Disruptor must be independent of Builder" / "Validator must independently verify" /
 * "Security must be independent of Builder" / "Tester must be independent of Builder" structurally:
 * a composition is invalid if any specialist id appears in another's mustBeIndependentOf list
 * while both are also assigned to the SAME acting identity string (e.g. the same session/agent
 * instance pretending to be two roles at once).
 */
export function validateComposition(assignments: Record<string, string>): { ok: true } | { ok: false; reason: string } {
  for (const [idA, actorA] of Object.entries(assignments)) {
    const contractA = SPECIALISTS[idA];
    if (!contractA) return { ok: false, reason: `Unknown specialist id: ${idA}` };
    for (const idB of contractA.mustBeIndependentOf) {
      const actorB = assignments[idB];
      if (actorB && actorB === actorA) {
        return { ok: false, reason: `${contractA.name} and ${SPECIALISTS[idB]?.name ?? idB} must be independent but are assigned the same acting identity (${actorA}).` };
      }
    }
  }
  return { ok: true };
}

/** A handoff is only valid if the receiving contract explicitly accepts handoffs from the sender. */
export function validateHandoff(fromId: string, toId: string): { ok: true } | { ok: false; reason: string } {
  const to = SPECIALISTS[toId];
  if (!to) return { ok: false, reason: `Unknown specialist id: ${toId}` };
  if (!to.handoffContract.acceptsFrom.includes(fromId)) {
    return { ok: false, reason: `${SPECIALISTS[toId]?.name ?? toId} does not accept handoffs from ${SPECIALISTS[fromId]?.name ?? fromId}.` };
  }
  return { ok: true };
}
