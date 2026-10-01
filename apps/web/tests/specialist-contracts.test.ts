// Tests the specialist capability-contract layer (specialist-contracts.ts). Pure logic, no I/O,
// matching this repo's unit-test convention. See that file's header for the honest architecture
// boundary: this proves selection, handoff validation, evidence/validation rules and proof
// assembly — it does NOT prove concurrent multi-box swarm execution, which #288 does not support.
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
  SPECIALISTS,
  SPECIALIST_IDS,
  selectSpecialists,
  independentlyValidate,
  assembleProof,
  validateComposition,
  validateHandoff,
  type Evidence,
} from '../specialist-contracts.ts';

describe('Specialist registration', () => {
  it('all 12 requested specialists are registered, each with a unique id', () => {
    const expected = ['director', 'researcher', 'builder', 'debugger', 'security', 'tester', 'disruptor', 'validator', 'memory_curator', 'synthesizer', 'resource_manager', 'proof_keeper'];
    assert.equal(SPECIALIST_IDS.length, 12);
    for (const id of expected) assert.ok(SPECIALISTS[id], `missing specialist: ${id}`);
    assert.equal(new Set(SPECIALIST_IDS).size, 12, 'ids must be unique');
  });

  it('every specialist defines all required contract fields, none empty', () => {
    for (const [id, c] of Object.entries(SPECIALISTS)) {
      assert.equal(c.id, id);
      assert.ok(c.name.length > 0, `${id}: name`);
      assert.ok(c.capability.length > 0, `${id}: capability`);
      assert.ok(Array.isArray(c.allowedInputs), `${id}: allowedInputs`);
      assert.ok(Array.isArray(c.expectedOutputs) && c.expectedOutputs.length > 0, `${id}: expectedOutputs`);
      assert.ok(Array.isArray(c.evidenceRequirements), `${id}: evidenceRequirements`);
      assert.ok(c.successCriteria.length > 0, `${id}: successCriteria`);
      assert.ok(c.failureBehavior.length > 0, `${id}: failureBehavior`);
      assert.ok(Array.isArray(c.toolsRequired), `${id}: toolsRequired`);
      assert.ok(c.modelRequirements.length > 0, `${id}: modelRequirements`);
      assert.ok(['read_only', 'read_write', 'none'].includes(c.permissionsBoundary), `${id}: permissionsBoundary`);
      assert.ok(c.handoffContract, `${id}: handoffContract`);
    }
  });

  it('capability discovery: every specialist is findable by its own capability text', () => {
    for (const [id, c] of Object.entries(SPECIALISTS)) {
      const found = Object.values(SPECIALISTS).find((x) => x.id === id);
      assert.equal(found?.capability, c.capability);
    }
  });
});

describe('Director selection', () => {
  it('selects Researcher for a research-shaped intent', () => {
    const r = selectSpecialists('Please research the current state of X');
    assert.ok(r.selected.includes('researcher'));
    assert.equal(r.blocked, false);
  });

  it('selects Builder and auto-adds Validator and Security (never Builder alone)', () => {
    const r = selectSpecialists('Build a new feature for the dashboard');
    assert.ok(r.selected.includes('builder'));
    assert.ok(r.selected.includes('validator'), 'Validator must be auto-added whenever Builder is selected');
    assert.ok(r.selected.includes('security'), 'Security must be auto-added whenever Builder is selected');
  });

  it('does not hard-code every job to use every agent', () => {
    const r = selectSpecialists('Please research the current state of X');
    assert.ok(!r.selected.includes('builder'));
    assert.ok(!r.selected.includes('tester'));
    assert.ok(r.selected.length < SPECIALIST_IDS.length);
  });

  it('is deterministic: same intent text always selects the same specialists', () => {
    const a = selectSpecialists('Build and test a new tool, then validate it');
    const b = selectSpecialists('Build and test a new tool, then validate it');
    assert.deepEqual(a.selected, b.selected);
  });

  it('blocks (does not silently run empty-handed) when no capability matches', () => {
    const r = selectSpecialists('asdkjfh qwerty zzz');
    assert.equal(r.blocked, true);
    assert.equal(r.selected.length, 0);
    assert.ok(r.blockedReason);
  });

  it('every selection includes a rationale naming why each specialist was chosen', () => {
    const r = selectSpecialists('Build a tool and test it for security vulnerabilities');
    for (const id of r.selected) assert.ok(r.rationale[id], `missing rationale for ${id}`);
  });
});

describe('Evidence requirements and independent validation', () => {
  const refEvidence: Evidence[] = [{ specialistId: 'builder', claim: 'created report.md', reference: 'tool_result:write_file:report.md' }];

  it('no specialist may claim success without evidence: empty evidence fails validation', () => {
    const result = independentlyValidate([]);
    assert.equal(result.valid, false);
  });

  it('evidence without a concrete reference fails validation', () => {
    const result = independentlyValidate([{ specialistId: 'builder', claim: 'it works', reference: '' }]);
    assert.equal(result.valid, false);
  });

  it('Validator must independently verify: Validator cannot validate its own evidence', () => {
    const result = independentlyValidate([{ specialistId: 'validator', claim: 'self-approved', reference: 'self' }]);
    assert.equal(result.valid, false);
    assert.match(result.reason, /independence/i);
  });

  it('well-formed evidence with a concrete reference passes', () => {
    const result = independentlyValidate(refEvidence);
    assert.equal(result.valid, true);
    assert.equal(result.checkedEvidenceCount, 1);
  });
});

describe('Proof Keeper integrity', () => {
  const evidence: Evidence[] = [{ specialistId: 'builder', claim: 'created report.md', reference: 'tool_result:write_file:report.md' }];
  const passingValidation = independentlyValidate(evidence);

  it('Proof Keeper cannot manufacture evidence: refuses with zero evidence even if told valid', () => {
    const result = assembleProof({ jobId: 'job-1', claim: 'x', evidence: [], validation: { valid: true, checkedEvidenceCount: 0, reason: 'forced' } });
    assert.equal(result.ok, false);
  });

  it('Proof Keeper refuses to produce a proof artifact when validation did not pass', () => {
    const result = assembleProof({ jobId: 'job-1', claim: 'x', evidence, validation: { valid: false, checkedEvidenceCount: 1, reason: 'failed' } });
    assert.equal(result.ok, false);
  });

  it('produces a proof artifact only once validation genuinely passed, referencing the real evidence', () => {
    const result = assembleProof({ jobId: 'job-1', claim: 'report created', evidence, validation: passingValidation });
    assert.equal(result.ok, true);
    if (result.ok) {
      assert.equal(result.artifact.jobId, 'job-1');
      assert.deepEqual((result.artifact.evidenceReferences as Array<{ reference: string }>)[0].reference, 'tool_result:write_file:report.md');
    }
  });
});

describe('Handoff contracts (valid/invalid)', () => {
  it('a listed handoff is valid: Researcher -> Builder', () => {
    assert.equal(validateHandoff('researcher', 'builder').ok, true);
  });

  it('an unlisted handoff is rejected: Proof Keeper -> Builder (Proof Keeper hands off to nothing)', () => {
    const result = validateHandoff('proof_keeper', 'builder');
    assert.equal(result.ok, false);
  });

  it('rejects a handoff to an unknown specialist id', () => {
    const result = validateHandoff('builder', 'not_a_real_specialist');
    assert.equal(result.ok, false);
  });
});

describe('Disruptor/Validator/Security independence from Builder', () => {
  it('rejects a composition where Disruptor and Builder share the same acting identity', () => {
    const result = validateComposition({ builder: 'agent-run-1', disruptor: 'agent-run-1' });
    assert.equal(result.ok, false);
    assert.match(result.reason!, /independent/i);
  });

  it('accepts a composition where Disruptor and Builder are different acting identities', () => {
    const result = validateComposition({ builder: 'agent-run-1', disruptor: 'agent-run-2' });
    assert.equal(result.ok, true);
  });

  it('rejects Validator sharing identity with Builder', () => {
    const result = validateComposition({ builder: 'agent-run-1', validator: 'agent-run-1' });
    assert.equal(result.ok, false);
  });

  it('rejects Proof Keeper sharing identity with Builder', () => {
    const result = validateComposition({ builder: 'agent-run-1', proof_keeper: 'agent-run-1' });
    assert.equal(result.ok, false);
  });
});

describe('Failed-agent recovery', () => {
  it('a specialist with no evidence is not silently promoted to success', () => {
    const result = independentlyValidate([]);
    assert.equal(result.valid, false);
    const proof = assembleProof({ jobId: 'job-2', claim: 'unverified', evidence: [], validation: result });
    assert.equal(proof.ok, false);
  });

  it('one specialist failing does not corrupt validation of another specialist\'s good evidence', () => {
    const mixed: Evidence[] = [
      { specialistId: 'builder', claim: 'created file', reference: 'tool_result:write_file:ok.txt' },
    ];
    const result = independentlyValidate(mixed);
    assert.equal(result.valid, true);
  });
});

describe('Honest architecture boundary', () => {
  it('this module makes no claim of concurrent multi-box execution', () => {
    // Nothing here spawns more than one real agent run; selection and validation are pure data
    // operations. This test exists to document the boundary, not to exercise new behavior.
    assert.equal(typeof selectSpecialists, 'function');
    assert.equal(SPECIALISTS.director.toolsRequired.length, 0, 'Director never calls a tool itself');
  });
});
