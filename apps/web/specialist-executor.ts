import { randomUUID } from 'node:crypto';
import { runToolAgent, TOOLS, type AgentEvent, type AgentHooks } from './agent.ts';
import {
  SPECIALISTS,
  assembleProof,
  independentlyValidate,
  selectSpecialists,
  type Evidence,
  type ProofArtifactInput,
  type SelectionResult,
  type SpecialistContract,
  type ValidationResult,
} from './specialist-contracts.ts';

export interface SpecialistJobInput {
  jobId: string;
  intent: string;
  specialists: SpecialistContract[];
  jobContext: Record<string, unknown>;
}

export interface SpecialistAllocation {
  jobId: string;
  intent: string;
  specialistId: string;
  contract: SpecialistContract;
  thinkBoxId: string;
  input: Record<string, unknown>;
}

export interface SpecialistResourceUsage {
  tokens: number;
  costUsd: number;
  durationMs: number;
}

export interface SpecialistRunOutput {
  runId: string;
  success: boolean;
  output?: string;
  events: AgentEvent[];
  resourceUsage?: SpecialistResourceUsage;
  failure?: string;
  thoughts?: Array<{ id: string; timestamp: number; type: string; content: string; status: string; plugin?: string }>;
}

export interface SpecialistExecution extends SpecialistAllocation {
  status: 'completed' | 'failed';
  runId?: string;
  inputStartedAt: number;
  startedAt: number;
  endedAt: number;
  output?: string;
  evidence: Evidence[];
  events: AgentEvent[];
  resourceUsage?: SpecialistResourceUsage;
  failure?: string;
  thoughts: NonNullable<SpecialistRunOutput['thoughts']>;
}

export interface SpecialistExecutionEvent {
  sequence: number;
  type: 'started' | 'completed' | 'failed';
  jobId: string;
  specialistId: string;
  thinkBoxId: string;
  timestamp: number;
  execution?: SpecialistExecution;
}

export interface SpecialistJobEvent {
  sequence: number;
  phase: string;
  [key: string]: unknown;
}

export interface SpecialistJobReplay {
  events: SpecialistJobEvent[];
  executions: SpecialistExecution[];
  evidence: Evidence[];
  validation?: ValidationResult;
  proof?: unknown;
  thinkTokens: unknown[];
  handoffs: SpecialistJobEvent[];
  cubeFinalState?: unknown;
}

export interface ExecuteWaveOptions {
  now?: () => number;
  onEvent?: (event: SpecialistExecutionEvent) => void;
  prepareWave?: (wave: SpecialistAllocation[], completed: SpecialistExecution[]) => void | Promise<void>;
}

export interface SpecialistWaveResult {
  executions: SpecialistExecution[];
  events: SpecialistExecutionEvent[];
}

export interface RunToolAgentExecutorOptions {
  model: string;
  maxIterations: number;
  temperature: number;
  createHooks: (allocation: SpecialistAllocation, runId: string) => AgentHooks;
  createRunId?: () => string;
}

export interface SelectedSpecialistExecution extends SpecialistWaveResult {
  jobId?: string;
  selection: SelectionResult;
}

function specialistInput(intent: string, contract: SpecialistContract, context: Record<string, unknown>): Record<string, unknown> {
  const input: Record<string, unknown> = { intent };
  if (contract.allowedInputs.includes('goal')) input.goal = intent;
  for (const key of contract.allowedInputs) {
    if (key in context) input[key] = context[key];
  }
  return input;
}

export function allocateSpecialistJobs(
  input: SpecialistJobInput,
  createId: () => string = randomUUID,
): SpecialistAllocation[] {
  if (!input.jobId.trim()) throw new Error('jobId is required');
  if (!input.intent.trim()) throw new Error('intent is required');
  if (!input.specialists.length) throw new Error('At least one specialist contract is required');

  const ids = new Set<string>();
  const boxIds = new Set<string>();
  return input.specialists.map((contract) => {
    if (SPECIALISTS[contract.id] !== contract) throw new Error(`Unknown or unregistered specialist contract: ${contract.id}`);
    if (ids.has(contract.id)) throw new Error(`Duplicate specialist allocation: ${contract.id}`);
    ids.add(contract.id);
    const thinkBoxId = createId();
    if (!thinkBoxId || boxIds.has(thinkBoxId)) throw new Error(`Think Box IDs must be unique; duplicate: ${thinkBoxId}`);
    boxIds.add(thinkBoxId);
    return {
      jobId: input.jobId,
      intent: input.intent,
      specialistId: contract.id,
      contract,
      thinkBoxId,
      input: specialistInput(input.intent, contract, input.jobContext),
    };
  });
}

export function createRunToolAgentExecutor(options: RunToolAgentExecutorOptions): (allocation: SpecialistAllocation) => Promise<SpecialistRunOutput> {
  const availableTools = new Set(TOOLS.map((tool) => tool.function.name));
  const createRunId = options.createRunId ?? randomUUID;
  return async (allocation) => {
    const runId = createRunId();
    const hooks = options.createHooks(allocation, runId);
    const unsupported = allocation.contract.toolsRequired.filter((tool) => !availableTools.has(tool));
    if (unsupported.length) {
      return {
        runId,
        success: false,
        events: [],
        thoughts: [],
        failure: `Required runtime tool(s) unavailable: ${unsupported.join(', ')}`,
        resourceUsage: { tokens: 0, costUsd: 0, durationMs: 0 },
      };
    }

    const events: AgentEvent[] = [];
    const thoughts: SpecialistRunOutput['thoughts'] = [];
    const onEvent = hooks.onEvent;
    const onThought = hooks.onThought;
    const startedAt = Date.now();
    const roleContext = [
      `You are the ${allocation.contract.name} specialist for job ${allocation.jobId}.`,
      `Capability: ${allocation.contract.capability}`,
      `Required outputs: ${allocation.contract.expectedOutputs.join('; ')}`,
      `Evidence requirements: ${allocation.contract.evidenceRequirements.join('; ') || 'none'}`,
      `Success criteria: ${allocation.contract.successCriteria}`,
      `Failure behavior: ${allocation.contract.failureBehavior}`,
      'Report only work supported by actual model or tool events. Do not claim a tool ran unless its result is in this run.',
    ].join('\n');
    const result = await runToolAgent(
      `${allocation.intent}\n\nSpecialist input:\n${JSON.stringify(allocation.input)}`,
      options.model,
      options.maxIterations,
      options.temperature,
      [],
      {
        ...hooks,
        allowedTools: [...allocation.contract.toolsRequired],
        roleContext,
          onThought: (thought) => {
            thoughts.push({
              id: randomUUID(),
              timestamp: Date.now(),
              type: String(thought.type ?? 'reasoning'),
              content: String(thought.content ?? ''),
              status: String(thought.status ?? 'info'),
              plugin: typeof thought.plugin === 'string' ? thought.plugin : undefined,
            });
            onThought(thought);
          },
        onEvent: (event) => {
          events.push(event);
          onEvent(event);
        },
      },
    );
    return {
      runId,
      success: result.success,
      output: result.result,
      events,
      thoughts,
      failure: result.error,
      resourceUsage: {
        tokens: result.tokens,
        costUsd: result.cost_usd,
        durationMs: Date.now() - startedAt,
      },
    };
  };
}

export async function executeSelectedSpecialists(
  jobId: string,
  intent: string,
  jobContext: Record<string, unknown>,
  execute: (allocation: SpecialistAllocation) => Promise<SpecialistRunOutput>,
  opportunity?: string,
  options: ExecuteWaveOptions = {},
): Promise<SelectedSpecialistExecution> {
  const selection = selectSpecialists(intent, opportunity);
  if (selection.blocked) return { selection, executions: [], events: [] };
  const allocations = allocateSpecialistJobs({
    jobId,
    intent,
    specialists: selection.selected.map((id) => SPECIALISTS[id]),
    jobContext,
  });
  return { selection, ...await executeSpecialistWave(allocations, execute, options) };
}

function evidenceForRun(specialistId: string, runId: string, events: AgentEvent[]): Evidence[] {
  const evidence: Evidence[] = [];
  for (const event of events) {
    if (event.kind === 'model' && event.content.trim()) {
      evidence.push({
        specialistId,
        claim: `Recorded model output: ${event.content}`,
        reference: `${runId}:model:${event.step}`,
      });
    } else if (event.kind === 'tool' && event.ok) {
      evidence.push({
        specialistId,
        claim: `Tool ${event.name} returned: ${event.output}`,
        reference: `${runId}:tool:${event.step}:${event.name}`,
      });
    }
  }
  return evidence;
}

export async function executeSpecialistWave(
  allocations: SpecialistAllocation[],
  execute: (allocation: SpecialistAllocation) => Promise<SpecialistRunOutput>,
  options: ExecuteWaveOptions = {},
): Promise<SpecialistWaveResult> {
  const now = options.now ?? Date.now;
  const events: SpecialistExecutionEvent[] = [];
  let sequence = 0;
  const emit = (event: Omit<SpecialistExecutionEvent, 'sequence'>): void => {
    const sequenced = { ...event, sequence: ++sequence };
    events.push(sequenced);
    options.onEvent?.(sequenced);
  };

  const executions = await Promise.all(allocations.map(async (allocation): Promise<SpecialistExecution> => {
    const startedAt = now();
    emit({
      type: 'started',
      jobId: allocation.jobId,
      specialistId: allocation.specialistId,
      thinkBoxId: allocation.thinkBoxId,
      timestamp: startedAt,
    });
    try {
      const run = await execute(allocation);
      const endedAt = now();
      const failed = !run.success;
      const execution: SpecialistExecution = {
        ...allocation,
        status: failed ? 'failed' : 'completed',
        runId: run.runId,
        inputStartedAt: startedAt,
        startedAt,
        endedAt,
        output: run.output,
        events: run.events,
        thoughts: run.thoughts ?? [],
        evidence: evidenceForRun(allocation.specialistId, run.runId, run.events),
        resourceUsage: run.resourceUsage,
        failure: failed ? run.failure || 'Specialist run reported failure' : undefined,
      };
      emit({
        type: failed ? 'failed' : 'completed',
        jobId: allocation.jobId,
        specialistId: allocation.specialistId,
        thinkBoxId: allocation.thinkBoxId,
        timestamp: endedAt,
        execution,
      });
      return execution;
    } catch (err) {
      const endedAt = now();
      const execution: SpecialistExecution = {
        ...allocation,
        status: 'failed',
        inputStartedAt: startedAt,
        startedAt,
        endedAt,
        events: [],
        thoughts: [],
        evidence: [],
        failure: err instanceof Error ? err.message : String(err),
      };
      emit({
        type: 'failed',
        jobId: allocation.jobId,
        specialistId: allocation.specialistId,
        thinkBoxId: allocation.thinkBoxId,
        timestamp: endedAt,
        execution,
      });
      return execution;
    }
  }));

  return { executions, events };
}

export function planSpecialistWaves(allocations: SpecialistAllocation[]): SpecialistAllocation[][] {
  const byId = new Map(allocations.map((allocation) => [allocation.specialistId, allocation]));
  const dependencies = new Map(allocations.map((allocation) => [allocation.specialistId, new Set<string>()]));
  for (const source of allocations) {
    for (const target of allocations) {
      if (target.contract.handoffContract.acceptsFrom.includes(source.specialistId)) {
        dependencies.get(target.specialistId)!.add(source.specialistId);
      }
    }
  }

  const completed = new Set<string>();
  const pending = new Set(allocations.map((allocation) => allocation.specialistId));
  const waves: SpecialistAllocation[][] = [];
  while (pending.size) {
    const ready = allocations.filter((allocation) => pending.has(allocation.specialistId)
      && [...dependencies.get(allocation.specialistId)!].every((id) => completed.has(id)));
    if (!ready.length) {
      throw new Error(`Specialist handoff dependency cycle: ${[...pending].join(', ')}`);
    }
    waves.push(ready);
    for (const allocation of ready) {
      pending.delete(allocation.specialistId);
      completed.add(allocation.specialistId);
    }
  }
  return waves;
}

function handoffInputs(allocation: SpecialistAllocation, completed: SpecialistExecution[]): void {
  const allEvidence = evidenceFromSpecialistExecutions(completed);
  const tools = completed.flatMap((execution) => execution.events.filter((event) => event.kind === 'tool'));
  const artifact = tools.find((event) => event.kind === 'tool' && event.ok && event.name === 'write_file' && typeof event.args.path === 'string');
  const failure = completed.find((execution) => execution.status === 'failed');
  const failedTool = tools.find((event) => event.kind === 'tool' && !event.ok);
  const values: Record<string, unknown> = {
    artifact_path: artifact?.kind === 'tool' ? artifact.args.path : undefined,
    researcher_findings: completed.find((execution) => execution.specialistId === 'researcher' && execution.status === 'completed')?.output,
    failed_tool_result: failedTool ? JSON.stringify(failedTool) : undefined,
    error_message: failure?.failure ?? (failedTool?.kind === 'tool' ? failedTool.error : undefined),
    builder_claim: completed.find((execution) => execution.specialistId === 'builder')?.output,
    planned_tool_calls: tools.map((event) => event.kind === 'tool' ? { name: event.name, args: event.args } : null).filter(Boolean),
    claims_with_evidence: allEvidence,
    validated_findings: completed.find((execution) => execution.specialistId === 'validator' && execution.status === 'completed')?.output,
    resource_usage: completed.reduce((total, execution) => ({
      tokens: total.tokens + (execution.resourceUsage?.tokens ?? 0),
      costUsd: total.costUsd + (execution.resourceUsage?.costUsd ?? 0),
      durationMs: total.durationMs + (execution.resourceUsage?.durationMs ?? 0),
    }), { tokens: 0, costUsd: 0, durationMs: 0 }),
    run_record: completed.map((execution) => ({ runId: execution.runId, specialistId: execution.specialistId, status: execution.status, resourceUsage: execution.resourceUsage })),
  };
  for (const key of allocation.contract.allowedInputs) {
    if (!(key in allocation.input) && values[key] !== undefined) allocation.input[key] = values[key];
  }
}

export async function executeSpecialistPlan(
  allocations: SpecialistAllocation[],
  execute: (allocation: SpecialistAllocation) => Promise<SpecialistRunOutput>,
  options: ExecuteWaveOptions = {},
): Promise<SpecialistWaveResult> {
  const plannedWaves = planSpecialistWaves(allocations);
  const executionsBySpecialist = new Map<string, SpecialistExecution>();
  const events: SpecialistExecutionEvent[] = [];
  let sequence = 0;
  for (const wave of plannedWaves) {
    const completed = allocations.map((allocation) => executionsBySpecialist.get(allocation.specialistId)).filter((run): run is SpecialistExecution => Boolean(run));
    for (const allocation of wave) handoffInputs(allocation, completed);
    await options.prepareWave?.(wave, completed);
    const result = await executeSpecialistWave(wave, execute, {
      now: options.now,
      onEvent: (event) => {
        const sequenced = { ...event, sequence: ++sequence };
        events.push(sequenced);
        options.onEvent?.(sequenced);
      },
    });
    for (const execution of result.executions) executionsBySpecialist.set(execution.specialistId, execution);
  }
  const startOrder = new Map(events.filter((event) => event.type === 'started').map((event) => [event.specialistId, event.sequence]));
  return {
    executions: [...executionsBySpecialist.values()].sort((a, b) => (startOrder.get(a.specialistId) ?? 0) - (startOrder.get(b.specialistId) ?? 0)),
    events,
  };
}

export function evidenceFromSpecialistExecutions(executions: SpecialistExecution[]): Evidence[] {
  return executions.flatMap((execution) => execution.evidence);
}

export function validateSpecialistEvidence(
  evidence: Evidence[],
  executions: SpecialistExecution[] = [],
): ValidationResult {
  const shape = independentlyValidate(evidence);
  if (!shape.valid || executions.length === 0) return shape;

  const validator = executions.find((execution) => execution.specialistId === 'validator');
  if (!validator || validator.status !== 'completed' || !validator.runId) {
    return { valid: false, checkedEvidenceCount: 0, reason: 'A successful independent Validator execution is required.' };
  }
  const validatorChecks = validator.events.filter((event) => event.kind === 'tool' && event.ok);
  if (!validatorChecks.length) {
    return { valid: false, checkedEvidenceCount: 0, reason: 'Validator produced no successful independent check tool result.' };
  }
  const validatorReadPaths = new Set(validator.events
    .filter((event) => event.kind === 'tool' && event.ok && event.name === 'read_file' && typeof event.args.path === 'string')
    .map((event) => event.kind === 'tool' ? String(event.args.path) : ''));
  const requiredTools: Record<string, string[]> = {
    researcher: ['fetch_url', 'read_rss', 'recall'],
    builder: ['write_file'],
    security: ['read_file'],
    tester: ['exec'],
    disruptor: ['exec'],
    memory_curator: ['remember'],
  };
  for (const execution of executions) {
    if (execution.status !== 'completed') continue;
    const required = requiredTools[execution.specialistId];
    if (required && !execution.events.some((event) => event.kind === 'tool' && event.ok && required.includes(event.name))) {
      return { valid: false, checkedEvidenceCount: 0, reason: `${execution.specialistId} did not produce a required successful tool result (${required.join(', ')}).` };
    }
  }
  for (const item of evidence) {
    const source = executions.find((execution) => execution.runId && item.reference.startsWith(`${execution.runId}:`));
    if (!source || source.specialistId !== item.specialistId) {
      return { valid: false, checkedEvidenceCount: 0, reason: `Evidence reference is not present in a recorded run for ${item.specialistId}.` };
    }
    if (source.thinkBoxId === validator.thinkBoxId) {
      return { valid: false, checkedEvidenceCount: 0, reason: 'Validator must use a separate Think Box from the evidence producer.' };
    }
    const modelMatch = item.reference.match(/:model:(\d+)$/);
    const toolMatch = item.reference.match(/:tool:(\d+):(.+)$/);
    if (modelMatch && !source.events.some((event) => event.kind === 'model' && event.step === Number(modelMatch[1]) && Boolean(event.content.trim()))) {
      return { valid: false, checkedEvidenceCount: 0, reason: `Model evidence reference was not found in run ${source.runId}.` };
    }
    if (toolMatch && !source.events.some((event) => event.kind === 'tool' && event.step === Number(toolMatch[1]) && event.name === toolMatch[2] && event.ok)) {
      return { valid: false, checkedEvidenceCount: 0, reason: `Tool evidence reference was not found in run ${source.runId}.` };
    }
    if (!modelMatch && !toolMatch) {
      return { valid: false, checkedEvidenceCount: 0, reason: `Unsupported evidence reference format: ${item.reference}` };
    }
    const sourcePaths = source.events
      .filter((event) => event.kind === 'tool' && event.ok && ['write_file', 'read_file'].includes(event.name) && typeof event.args.path === 'string')
      .map((event) => event.kind === 'tool' ? String(event.args.path) : '');
    if (!sourcePaths.length) {
      return { valid: false, checkedEvidenceCount: 0, reason: `Evidence ${item.reference} has no independently checkable artifact path.` };
    }
    if (!sourcePaths.some((artifactPath) => validatorReadPaths.has(artifactPath))) {
      return { valid: false, checkedEvidenceCount: 0, reason: `Validator did not independently read an artifact supporting ${item.reference}.` };
    }
  }
  return shape;
}

export function assembleSpecialistProof(
  input: Omit<ProofArtifactInput, 'validation'> & {
    executions: SpecialistExecution[];
    validation: ValidationResult;
  },
): { ok: true; artifact: Record<string, unknown> } | { ok: false; reason: string } {
  const failures = input.executions.filter((execution) => execution.status === 'failed');
  const validation = failures.length
    ? {
        ...input.validation,
        valid: false,
        reason: `Selected specialist execution failed: ${failures.map((execution) => `${execution.specialistId} failed (${execution.failure || 'unknown failure'})`).join(', ')}`,
      }
    : input.validation;
  const proof = assembleProof({
    jobId: input.jobId,
    claim: input.claim,
    evidence: input.evidence,
    validation,
    resourceUsage: input.resourceUsage,
  });
  if (!proof.ok && failures.length) return { ok: false, reason: validation.reason };
  return proof;
}

export function completeSpecialistJob(
  input: {
    jobId: string;
    claim: string;
    executions: SpecialistExecution[];
    resourceUsage?: SpecialistResourceUsage;
  },
  onProofAccepted?: (artifact: Record<string, unknown>) => void,
): {
  evidence: Evidence[];
  validation: ValidationResult;
  proof: ReturnType<typeof assembleSpecialistProof>;
} {
  const evidence = evidenceFromSpecialistExecutions(input.executions)
    .filter((item) => item.specialistId !== 'validator');
  const validation = validateSpecialistEvidence(evidence, input.executions);
  const proof = assembleSpecialistProof({
    jobId: input.jobId,
    claim: input.claim,
    executions: input.executions,
    evidence,
    validation,
    resourceUsage: input.resourceUsage,
  });
  if (proof.ok) onProofAccepted?.(proof.artifact);
  return { evidence, validation, proof };
}

export function replaySpecialistEvents(events: SpecialistExecutionEvent[]): SpecialistExecution[] {
  const completed = new Map<string, SpecialistExecution>();
  for (const event of [...events].sort((a, b) => a.sequence - b.sequence)) {
    if (event.execution) completed.set(event.specialistId, event.execution);
  }
  const startOrder = new Map<string, number>();
  for (const event of events) {
    if (event.type === 'started') startOrder.set(event.specialistId, event.sequence);
  }
  return [...completed.values()].sort((a, b) => (startOrder.get(a.specialistId) ?? 0) - (startOrder.get(b.specialistId) ?? 0));
}

export function replaySpecialistJobEvents(events: SpecialistJobEvent[]): SpecialistJobReplay {
  const ordered = [...events].sort((a, b) => a.sequence - b.sequence);
  ordered.forEach((event, index) => {
    if (event.sequence !== index + 1) throw new Error(`Specialist event sequence gap at ${index + 1}`);
  });
  const started = new Map<string, number>();
  const executions = new Map<string, SpecialistExecution>();
  const handoffs: SpecialistJobEvent[] = [];
  const thinkTokens: unknown[] = [];
  let validation: ValidationResult | undefined;
  let proof: unknown;
  let cubeFinalState: unknown;

  for (const entry of ordered) {
    if (entry.phase === 'run_started' && typeof entry.specialistId === 'string') {
      started.set(entry.specialistId, entry.sequence);
    } else if (entry.phase === 'specialist_event' && entry.event && typeof entry.event === 'object') {
      const specialistEvent = entry.event as SpecialistExecutionEvent;
      if (specialistEvent.execution) executions.set(specialistEvent.specialistId, specialistEvent.execution);
    } else if (entry.phase === 'artifact_handoff') {
      handoffs.push(entry);
    } else if (entry.phase === 'validation') {
      validation = entry.validation as ValidationResult;
    } else if (entry.phase === 'proof_accepted' || entry.phase === 'proof_refused') {
      proof = entry.proof;
    } else if (entry.phase === 'think_token') {
      thinkTokens.push(entry.token);
    } else if (entry.phase === 'cube_final_state') {
      cubeFinalState = entry.state;
    }
  }

  const replayedExecutions = [...executions.values()].sort((a, b) => (started.get(a.specialistId) ?? 0) - (started.get(b.specialistId) ?? 0));
  return {
    events: ordered,
    executions: replayedExecutions,
    evidence: evidenceFromSpecialistExecutions(replayedExecutions),
    validation,
    proof,
    thinkTokens,
    handoffs,
    cubeFinalState,
  };
}