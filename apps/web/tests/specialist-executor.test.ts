import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { startMockInception, say, call } from './helpers/mock-inception.ts';
import {
  SPECIALISTS,
  independentlyValidate,
} from '../specialist-contracts.ts';
import {
  allocateSpecialistJobs,
  assembleSpecialistProof,
  executeSpecialistWave,
  evidenceFromSpecialistExecutions,
  replaySpecialistEvents,
  createRunToolAgentExecutor,
  completeSpecialistJob,
  validateSpecialistEvidence,
  planSpecialistWaves,
  executeSpecialistPlan,
} from '../specialist-executor.ts';

const modelEvent = (step: number, content: string) => ({
  kind: 'model' as const,
  step,
  latency_ms: 5,
  prompt_tokens: 3,
  completion_tokens: 2,
  cost_usd: 0.0001,
  tool_calls: [],
  content,
});

const toolEvent = (step: number, name: string, ok: boolean, output: string, args: Record<string, unknown> = {}) => ({
  kind: 'tool' as const,
  step,
  name,
  args,
  ok,
  latency_ms: 2,
  output,
  error: ok ? undefined : output,
});

describe('specialist execution adapter', () => {
  it('allocates one independently attributable Think Box job per selected contract', () => {
    const ids = ['box-a', 'box-b'];
    const jobs = allocateSpecialistJobs({
      jobId: 'job-1',
      intent: 'Build and test a report',
      specialists: [SPECIALISTS.builder, SPECIALISTS.tester],
      jobContext: { researcher_findings: 'source result', secret: 'not allowed' },
    }, () => ids.shift()!);

    assert.deepEqual(jobs.map((job) => job.thinkBoxId), ['box-a', 'box-b']);
    assert.deepEqual(jobs.map((job) => job.specialistId), ['builder', 'tester']);
    assert.equal(jobs[0].input.goal, 'Build and test a report');
    assert.equal(jobs[0].input.researcher_findings, 'source result');
    assert.equal('secret' in jobs[0].input, false);
  });

  it('executes independent boxes concurrently and preserves each run identity', async () => {
    const jobs = allocateSpecialistJobs({
      jobId: 'job-2',
      intent: 'Review a change',
      specialists: [SPECIALISTS.security, SPECIALISTS.tester],
      jobContext: {},
    }, (() => { let id = 0; return () => `box-${++id}`; })());
    let active = 0;
    let maxActive = 0;
    const result = await executeSpecialistWave(jobs, async (job) => {
      active++;
      maxActive = Math.max(maxActive, active);
      await new Promise((resolve) => setImmediate(resolve));
      active--;
      return {
        runId: `run-${job.specialistId}`,
        success: true,
        output: `${job.specialistId} reviewed`,
        events: [modelEvent(1, `${job.specialistId} model result`)],
        resourceUsage: { tokens: 5, costUsd: 0.0001, durationMs: 5 },
      };
    }, { now: () => 100 });

    assert.equal(maxActive, 2);
    assert.equal(new Set(result.executions.map((run) => run.thinkBoxId)).size, 2);
    assert.deepEqual(result.executions.map((run) => run.runId), ['run-security', 'run-tester']);
  });

  it('plans contract handoffs into dependent waves and runs independent reviewers concurrently', async () => {
    const contracts = [SPECIALISTS.builder, SPECIALISTS.security, SPECIALISTS.tester, SPECIALISTS.validator];
    const allocations = allocateSpecialistJobs({ jobId: 'job-waves', intent: 'Build and validate a report', specialists: contracts, jobContext: {} },
      (() => { let id = 0; return () => `box-wave-${++id}`; })());
    const waves = planSpecialistWaves(allocations);
    assert.deepEqual(waves.map((wave) => wave.map((item) => item.specialistId)), [
      ['builder'], ['security', 'tester'], ['validator'],
    ]);
    let active = 0;
    let maxActive = 0;
    const output = await executeSpecialistPlan(allocations, async (allocation) => {
      active++;
      maxActive = Math.max(maxActive, active);
      await new Promise((resolve) => setImmediate(resolve));
      active--;
      const isBuilder = allocation.specialistId === 'builder';
      return {
        runId: `run-${allocation.specialistId}`,
        success: true,
        output: isBuilder ? 'Created report.md' : 'Reviewed report.md',
        events: isBuilder
          ? [toolEvent(1, 'write_file', true, 'report.md', { path: 'report.md' })]
          : [toolEvent(1, allocation.specialistId === 'tester' ? 'exec' : 'read_file', true, 'report content')],
      };
    });

    assert.equal(maxActive, 2);
    assert.deepEqual(output.executions.map((run) => run.specialistId), ['builder', 'security', 'tester', 'validator']);
    assert.equal(allocations.find((item) => item.specialistId === 'security')?.input.artifact_path, 'report.md');
    assert.ok(Array.isArray(allocations.find((item) => item.specialistId === 'validator')?.input.claims_with_evidence));
  });

  it('runs separate specialist allocations through concurrent real runToolAgent loops', async () => {
    const previousKey = process.env.INCEPTION_API_KEY;
    const mocks = [await startMockInception(), await startMockInception()];
    const workspaces = [0, 1].map(() => fs.mkdtempSync(path.join(os.tmpdir(), 'specialist-box-')));
    process.env.INCEPTION_API_KEY = 'hermetic-test-key';
    const contracts = [SPECIALISTS.researcher, SPECIALISTS.validator];
    const allocations = allocateSpecialistJobs({
      jobId: 'job-runtime',
      intent: 'Research and validate a report',
      specialists: contracts,
      jobContext: {},
    }, (() => { let id = 0; return () => `box-runtime-${++id}`; })());
    mocks[0].script([{ ...say('Research result from the model.'), delayMs: 40 }]);
    mocks[1].script([{ ...say('Validator reviewed the supplied evidence.'), delayMs: 40 }]);
    const endpointByBox = new Map(allocations.map((allocation, index) => [allocation.thinkBoxId, mocks[index].baseUrl]));
    const workspaceByBox = new Map(allocations.map((allocation, index) => [allocation.thinkBoxId, workspaces[index]]));
    const execute = createRunToolAgentExecutor({
      model: 'mercury-2',
      maxIterations: 2,
      temperature: 0,
      createRunId: (() => { let id = 0; return () => `runtime-run-${++id}`; })(),
      createHooks: (allocation) => ({
        apiBaseUrl: endpointByBox.get(allocation.thinkBoxId)!,
        workspace: workspaceByBox.get(allocation.thinkBoxId)!,
        resolvePath: (relativePath) => path.join(workspaceByBox.get(allocation.thinkBoxId)!, relativePath),
        onThought: () => {},
        onEvent: () => {},
        onFilesChanged: () => {},
        signal: new AbortController().signal,
        checkBudget: () => null,
        approvedDomains: new Set<string>(),
        requestApproval: async () => false,
        remember: async () => ({ ok: false }),
        recall: async () => ({ results: [] }),
        rssFeed: async () => ({ items: [] }),
      }),
    });

    try {
      const result = await executeSpecialistWave(allocations, execute);
      assert.deepEqual(result.executions.map((run) => run.status), ['completed', 'completed']);
      assert.deepEqual(result.executions.map((run) => run.runId), ['runtime-run-1', 'runtime-run-2']);
      assert.notEqual(result.executions[0].thinkBoxId, result.executions[1].thinkBoxId);
      assert.equal(mocks[0].requests.length, 1);
      assert.equal(mocks[1].requests.length, 1);
      assert.match(String(mocks[0].requests[0].messages[0].content), /Researcher specialist/);
      assert.match(String(mocks[1].requests[0].messages[0].content), /Validator specialist/);
      assert.notEqual(workspaces[0], workspaces[1]);
    } finally {
      if (previousKey === undefined) delete process.env.INCEPTION_API_KEY;
      else process.env.INCEPTION_API_KEY = previousKey;
      await Promise.all(mocks.map((mock) => mock.close()));
      for (const workspace of workspaces) fs.rmSync(workspace, { recursive: true, force: true });
    }
  });

  it('real runtime failure experiment preserves A evidence, records B failure, and C independently reads A artifact', async () => {
    const previousKey = process.env.INCEPTION_API_KEY;
    const builderMock = await startMockInception();
    const validatorMock = await startMockInception();
    const contracts = [SPECIALISTS.builder, SPECIALISTS.tester, SPECIALISTS.validator];
    const allocations = allocateSpecialistJobs({
      jobId: 'job-controlled-failure',
      intent: 'Build a report and run its tests',
      specialists: contracts,
      jobContext: {},
    }, (() => { let id = 0; return () => `box-failure-${++id}`; })());
    const workspaces = allocations.map(() => fs.mkdtempSync(path.join(os.tmpdir(), 'specialist-failure-box-')));
    const endpointByBox = new Map([
      [allocations[0].thinkBoxId, builderMock.baseUrl],
      [allocations[2].thinkBoxId, validatorMock.baseUrl],
    ]);
    const workspaceByBox = new Map(allocations.map((allocation, index) => [allocation.thinkBoxId, workspaces[index]]));
    process.env.INCEPTION_API_KEY = 'hermetic-test-key';
    builderMock.script([
      call('write_file', { path: 'artifact.txt', content: 'artifact from specialist A' }),
      say('Created artifact.txt'),
    ]);
    validatorMock.script([
      call('read_file', { path: 'artifact.txt' }),
      say('The artifact content matches the expected report.'),
    ]);
    const execute = createRunToolAgentExecutor({
      model: 'mercury-2',
      maxIterations: 3,
      temperature: 0,
      createRunId: (() => { let id = 0; return () => `failure-run-${++id}`; })(),
      createHooks: (allocation) => ({
        apiBaseUrl: endpointByBox.get(allocation.thinkBoxId),
        workspace: workspaceByBox.get(allocation.thinkBoxId)!,
        resolvePath: (relativePath) => path.join(workspaceByBox.get(allocation.thinkBoxId)!, relativePath),
        onThought: () => {},
        onEvent: () => {},
        onFilesChanged: () => {},
        signal: new AbortController().signal,
        checkBudget: () => null,
        approvedDomains: new Set<string>(),
        requestApproval: async () => false,
        remember: async () => ({ ok: false }),
        recall: async () => ({ results: [] }),
        rssFeed: async () => ({ items: [] }),
      }),
    });

    try {
      const result = await executeSpecialistPlan(allocations, execute, {
        prepareWave: async (wave, completed) => {
          if (!wave.some((allocation) => allocation.specialistId === 'validator')) return;
          const builder = completed.find((execution) => execution.specialistId === 'builder');
          assert.ok(builder, 'Validator must wait for Builder');
          fs.mkdirSync(workspaces[2], { recursive: true });
          fs.copyFileSync(path.join(workspaces[0], 'artifact.txt'), path.join(workspaces[2], 'artifact.txt'));
        },
      });
      const executions = result.executions;
      const builderExecution = executions.find((execution) => execution.specialistId === 'builder')!;
      const testerExecution = executions.find((execution) => execution.specialistId === 'tester')!;
      const validatorExecution = executions.find((execution) => execution.specialistId === 'validator')!;
      assert.equal(builderExecution.status, 'completed');
      assert.equal(testerExecution.status, 'failed');
      assert.match(testerExecution.failure ?? '', /exec/);
      const evidence = evidenceFromSpecialistExecutions(executions).filter((item) => item.specialistId !== 'validator');
      const validation = validateSpecialistEvidence(evidence, executions);
      const tokenAttempts: Record<string, unknown>[] = [];
      const completion = completeSpecialistJob({
        jobId: 'job-controlled-failure',
        claim: 'A created the artifact and C independently read it; B could not run tests.',
        executions,
      }, (artifact) => tokenAttempts.push(artifact));

      assert.equal(validation.valid, true);
      assert.ok(validatorExecution.events.some((event) => event.kind === 'tool' && event.name === 'read_file' && event.ok));
      assert.ok(evidence.length > 0 && evidence.every((item) => item.specialistId === 'builder'));
      assert.equal(validateSpecialistEvidence([...evidence, ...validatorExecution.evidence], executions).valid, false,
        'Validator evidence must be rejected as self-evidence');
      assert.equal(completion.proof.ok, false, 'Proof Keeper must reject a job with failed selected specialist B');
      assert.equal(tokenAttempts.length, 0, 'no operational token callback before proof acceptance');
      assert.deepEqual(replaySpecialistEvents(result.events), executions);
      assert.equal(builderMock.requests.length, 2);
      assert.equal(validatorMock.requests.length, 2);
    } finally {
      if (previousKey === undefined) delete process.env.INCEPTION_API_KEY;
      else process.env.INCEPTION_API_KEY = previousKey;
      await Promise.all([builderMock.close(), validatorMock.close()]);
      for (const workspace of workspaces) fs.rmSync(workspace, { recursive: true, force: true });
    }
  });

  it('derives evidence from actual model/tool events, not success status or free-text output', async () => {
    const [job] = allocateSpecialistJobs({
      jobId: 'job-3',
      intent: 'Build a report',
      specialists: [SPECIALISTS.builder],
      jobContext: {},
    }, () => 'box-builder');
    const result = await executeSpecialistWave([job], async () => ({
      runId: 'run-builder',
      success: true,
      output: 'I succeeded',
      events: [
        modelEvent(1, 'Creating the report'),
        toolEvent(2, 'write_file', true, '{"ok":true,"path":"report.md"}'),
        toolEvent(3, 'write_file', false, 'disk full'),
      ],
      resourceUsage: { tokens: 10, costUsd: 0.001, durationMs: 20 },
    }), { now: () => 200 });
    const evidence = evidenceFromSpecialistExecutions(result.executions);

    assert.equal(evidence.length, 2);
    assert.ok(evidence.some((item) => item.reference === 'run-builder:model:1'));
    assert.ok(evidence.some((item) => item.reference === 'run-builder:tool:2:write_file'));
    assert.ok(evidence.every((item) => item.specialistId === 'builder'));
    assert.ok(evidence.every((item) => !item.reference.includes(':3:')));
  });

  it('preserves successful evidence when another specialist fails, and replays identical state', async () => {
    const jobs = allocateSpecialistJobs({
      jobId: 'job-failure',
      intent: 'Build and test a report',
      specialists: [SPECIALISTS.builder, SPECIALISTS.tester],
      jobContext: {},
    }, (() => { let id = 0; return () => `box-${++id}`; })());
    const result = await executeSpecialistWave(jobs, async (job) => {
      if (job.specialistId === 'tester') throw new Error('test command unavailable');
      return {
        runId: 'run-builder',
        success: true,
        output: 'created report.md',
        events: [toolEvent(1, 'write_file', true, '{"ok":true,"path":"report.md"}')],
        resourceUsage: { tokens: 4, costUsd: 0.0001, durationMs: 8 },
      };
    }, { now: () => 300 });
    const evidence = evidenceFromSpecialistExecutions(result.executions);
    const replayed = replaySpecialistEvents(result.events);

    assert.equal(result.executions.find((run) => run.specialistId === 'builder')?.status, 'completed');
    assert.equal(result.executions.find((run) => run.specialistId === 'tester')?.status, 'failed');
    assert.equal(evidence.length, 1);
    assert.equal(evidence[0].specialistId, 'builder');
    assert.deepEqual(replayed, result.executions);
  });

  it('uses independentValidate and rejects Validator self-evidence', () => {
    const jobs = allocateSpecialistJobs({
      jobId: 'job-4',
      intent: 'Validate a result',
      specialists: [SPECIALISTS.validator],
      jobContext: {},
    }, () => 'box-validator');
    assert.equal(jobs[0].specialistId, 'validator');
    assert.equal(independentlyValidate([{
      specialistId: 'validator', claim: 'self-check', reference: 'run-validator:model:1',
    }]).valid, false);
  });

  it('Proof Keeper refuses proof when any selected specialist failed, even if A evidence validates', async () => {
    const jobs = allocateSpecialistJobs({
      jobId: 'job-failure-proof',
      intent: 'Build and test a report',
      specialists: [SPECIALISTS.builder, SPECIALISTS.tester],
      jobContext: {},
    }, (() => { let id = 0; return () => `box-${++id}`; })());
    const result = await executeSpecialistWave(jobs, async (job) => job.specialistId === 'builder'
      ? { runId: 'run-builder', success: true, output: 'built', events: [toolEvent(1, 'write_file', true, 'report.md')], resourceUsage: { tokens: 1, costUsd: 0, durationMs: 1 } }
      : Promise.reject(new Error('controlled failure')), { now: () => 400 });
    const evidence = evidenceFromSpecialistExecutions(result.executions);
    const validation = independentlyValidate(evidence);
    const proof = assembleSpecialistProof({
      jobId: 'job-failure-proof',
      claim: 'report built and tested',
      executions: result.executions,
      evidence,
      validation,
    });

    assert.equal(validation.valid, true);
    assert.equal(proof.ok, false);
    if (!proof.ok) assert.match(proof.reason, /tester.*failed/i);
  });
});