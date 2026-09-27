# Auditable Governance Layer for Autonomous Decisions

**An accountability infrastructure for recorded governance signals, not an alignment solution.**

This system records what governance rules were applied to each autonomous decision, enabling independent verification—without claiming those decisions are ethically correct.

---

## The Distinction

### What This System Does NOT Claim

❌ "This proves decisions are ethical"
❌ "This proves alignment"
❌ "This solves AI safety"
❌ "This guarantees good outcomes"

### What This System DOES Provide

✅ **Recorded governance signals** — Human preferences, policies, governance decisions with full provenance
✅ **Explicit conflict detection** — Identifies when policies contradict
✅ **Decision gates** — Evaluates proposed actions against declared constraints
✅ **Tamper-evident proofs** — Cryptographic evidence that rules were applied
✅ **Complete audit trails** — WHO decided → WHAT they decided → WHAT evidence applied → WHETHER human reviewed
✅ **Independent verification** — Anyone can verify governance artifacts

---

## The Six Governance Primitives

### 1. Value Signal Ledger

Records every input to governance decisions with full provenance:

```python
# Human preference
signal = await ledger.record_signal(
    signal_type=GovernanceSignalType.HUMAN_PREFERENCE,
    provenance="human_alice_20260926",
    content="Prioritize human safety over cost"
)

# Policy constraint
signal = await ledger.record_signal(
    signal_type=GovernanceSignalType.POLICY_CONSTRAINT,
    provenance="policy_v2_healthcare",
    content="deny: any decision with <0.95 harm prevention confidence",
    versioning="policy_v2"
)

# Governance decision
signal = await ledger.record_signal(
    signal_type=GovernanceSignalType.GOVERNANCE_DECISION,
    provenance="governance_board_20260926",
    content="Escalate all high-risk decisions",
    human_id="board_member_1"
)
```

Every signal is:
- **Sourced** — WHO supplied it (auditable)
- **Versioned** — WHICH version of policy (policy_v1 vs policy_v2)
- **Timestamped** — WHEN it was recorded
- **Hashed** — SHA256 for tamper detection

### 2. Governance Consensus Engine

Detects conflicts, applies explicit resolution rules, escalates when necessary:

```python
# Evaluate against recorded signals
decision = await ledger.evaluate_against_constraints(
    action_description="Execute autonomous decision",
    applicable_signal_ids=[signal1.signal_id, signal2.signal_id]
)

# Decision is one of three states
if decision.decision == DecisionGatingDecision.ALLOW:
    # All applicable signals permit this action
    pass
elif decision.decision == DecisionGatingDecision.DENY:
    # At least one signal prohibits this action
    pass
elif decision.decision == DecisionGatingDecision.ESCALATE:
    # Signals conflict (some allow, some deny)
    # → Human review required
    pass

# Resolution rule is explicit
print(decision.resolution_rule)
# "Conflicting governance signals; human escalation required"
```

**No fabricated consensus.** If signals contradict, the system escalates rather than guessing.

### 3. Alignment Drift Monitor

Records detected deviations from baseline behavior:

```python
drift_signal = await ledger.record_signal(
    signal_type=GovernanceSignalType.DRIFT_ALERT,
    provenance="drift_detector_system",
    content="Detected deviation: decision pattern differs 0.3 from baseline"
)
```

Drift is **detected and recorded**, not used to automatically deny decisions.

### 4. Decision Governance Gate

Evaluates constraints before execution, records evidence, fails safely:

```python
decision = await ledger.evaluate_against_constraints(
    action_description="Proposed autonomous action",
    applicable_signal_ids=[policy_signals]
)

# Evidence is recorded
print(decision.evidence)
# {
#     "allow_signals": 2,
#     "deny_signals": 1,
#     "total_signals": 3,
# }

# Decision is explicit
print(decision.decision.value)  # "escalate"
```

Gate produces deterministic output for the same signals + action.

### 5. Proof Layer

Produces cryptographic evidence that governance was applied:

```python
proof = await ledger.generate_proof(decision.decision_id)

# Contains:
print(proof.decision_hash)      # SHA256 of the decision
print(proof.signal_hashes)      # SHA256 of each governing signal
print(proof.previous_proof_hash) # Links to prior decision (chain)

# Verify the chain is intact
is_valid = await ledger.verify_proof_chain()
# True = no tampering detected
# False = chain broken (evidence of modification)
```

Proofs are **verifiable by independent auditor**—they can recompute the hashes and confirm governance artifacts haven't been modified.

### 6. Human Audit Trail

Complete record for human review and governance verification:

```python
trail = ledger.get_audit_trail(decision_id)

# Shows:
{
    "decision_id": "decision_abc123",
    "action_description": "Execute autonomous decision",
    "decision": "escalate",
    
    # WHO supplied governance signals
    "governing_signals": {
        "signal_1": {
            "type": "human_preference",
            "provenance": "human_alice_20260926",
            "content": "Prioritize safety"
        },
        "signal_2": {
            "type": "policy_constraint",
            "provenance": "policy_v2_healthcare",
            "content": "deny: <0.95 safety confidence"
        }
    },
    
    # WHAT evidence was available
    "evidence": {
        "allow_signals": 1,
        "deny_signals": 1,
        "total_signals": 2
    },
    
    # Conflict resolution
    "conflict_detected": True,
    "resolution_rule": "Conflicting signals; human escalation required",
    
    # Whether human intervened
    "human_intervened": True,
    "intervention_note": "Human Alice approved after inspection",
    
    # Everything is verifiable
    "can_verify": True
}
```

This trail answers:
- ✅ WHO supplied governance signals?
- ✅ WHAT decision was made?
- ✅ WHAT evidence was available?
- ✅ WHICH policies applied?
- ✅ Was there conflict?
- ✅ Did a human intervene?
- ✅ Is the chain tamper-evident?

---

## What This Enables

### For Auditors

Auditors can independently verify that:
1. Governance signals were recorded from specified sources
2. Decision gates evaluated proposed actions against those signals
3. Rules were applied consistently
4. Cryptographic proofs haven't been tampered with

### For Governance Teams

Teams can:
1. Record policies and constraints
2. See how those rules applied to each decision
3. Identify conflicts automatically
4. Track human interventions and outcomes
5. Iterate on governance rules based on results

### For Regulators

Regulators can:
1. Audit every decision's governance chain
2. Verify that declared policies were actually applied
3. Identify systematic deviations from declared rules
4. Check for human review where required
5. Understand decision provenance without black boxes

---

## Implementation Example

```python
async def autonomous_decision_with_governance(
    action_description: str,
    autonomous_system_output: dict
) -> DecisionGatingDecision:
    """Execute autonomous decision with recorded governance."""
    
    # 1. Get applicable governance signals
    signals = await governance_db.get_applicable_signals(action_description)
    signal_ids = [s.signal_id for s in signals]
    
    # 2. Evaluate against recorded constraints
    gov_decision = await ledger.evaluate_against_constraints(
        action_description=action_description,
        applicable_signal_ids=signal_ids
    )
    
    # 3. Generate cryptographic proof
    proof = await ledger.generate_proof(gov_decision.decision_id)
    
    # 4. If escalation required, involve human
    if gov_decision.decision == DecisionGatingDecision.ESCALATE:
        human_decision = await human_review_queue.wait_for_decision(
            decision_id=gov_decision.decision_id
        )
        await ledger.record_human_intervention(
            decision_id=gov_decision.decision_id,
            intervention_note=f"Human {human_decision.human_id}: {human_decision.note}"
        )
    
    # 5. Execute or deny based on governance gate
    if gov_decision.decision == DecisionGatingDecision.DENY:
        await log_event("GOVERNANCE_DENIED", {"action": action_description})
        return DecisionGatingDecision.DENY
    
    # Execute the autonomous system's decision
    await log_event("GOVERNANCE_APPROVED", {"action": action_description})
    return gov_decision.decision
```

---

## Testing & Verification

**17 Unit Tests, All Passing**

Each primitive is tested for deterministic behavior:

| Primitive | Tests | Focus |
|-----------|-------|-------|
| Value Signal Ledger | 4 | Recording signals with provenance, hashing, versioning |
| Governance Consensus Engine | 3 | Allow/deny/escalate logic, conflict detection |
| Alignment Drift Monitor | 1 | Recording drift alerts |
| Decision Governance Gate | 2 | Evidence recording, decision hashing |
| Proof Layer | 3 | Proof generation, chaining, tamper detection |
| Human Audit Trail | 4 | Complete trail, intervention tracking, verifiability |

All tests are deterministic (no randomness) and verifiable (can be re-run and produce same results).

---

## Four-State Classification

| State | Status | What It Means |
|-------|--------|---|
| **CODE_COMPLETE** | ✅ | Governance primitives implemented and compilable |
| **TEST_VERIFIED** | ✅ (17/17 passing) | Deterministic tests demonstrate primitive behavior |
| **LIVE_VERIFIED** | ⏳ | Real autonomous workflow produces governance artifacts |
| **PRODUCTION_READY** | ⏳ | All three + human expert review + operational runbook |

### CODE_COMPLETE ✅
- `thinkbox/governance_ledger.py` (340 lines)
- `GovernanceLedger` class with six primitives
- Signal recording, gate evaluation, proof generation
- Compile check: ✅ Passes Python syntax validation

### TEST_VERIFIED ✅
- `tests/unit/test_governance_ledger.py` (17 tests)
- Each primitive has deterministic tests
- Tests verify behavior matches specification
- Result: All 17 pass, 0 failures

### LIVE_VERIFIED ⏳
- **Needed:** Real autonomous workflow produces governance artifacts
- **Next step:** Integrate with autonomous swarm (PR #259)
- **Verification method:** Extract governance artifacts from live runs, verify they match specification
- **Success criteria:** 100/100 governance artifacts produce valid proof chains

### PRODUCTION_READY ⏳
- **Needed:** All three states + human expert review
- **Who:** Security team, governance policy expert, audit specialist
- **Checklist:** Read architecture, review code, verify tests, approve audit readiness

---

## What NOT to Do

### ❌ Don't Claim This Proves Alignment

This is an **accountability layer**, not an alignment solution. It records what rules were applied—not whether those rules were good.

Correct: "This decision was evaluated against declared policy version 2, which prohibits <95% safety confidence. The evaluation escalated for human review."

Incorrect: "This decision was proven to be ethically aligned by our system."

### ❌ Don't Skip the Proof Chain Verification

Always run `verify_proof_chain()` before claiming artifacts are trustworthy.

```python
if not await ledger.verify_proof_chain():
    raise ValueError("Proof chain tampered; cannot trust governance artifacts")
```

### ❌ Don't Fabricate Human Intervention

If no human reviewed a decision, don't mark `human_intervened=True`. Record truth.

```python
# Correct
await ledger.record_human_intervention(
    decision_id=decision_id,
    intervention_note="Human Alice reviewed and approved"
)

# Incorrect
await ledger.record_human_intervention(
    decision_id=decision_id,
    intervention_note="Automated review approved"  # ❌ This is not human review
)
```

---

## See Also

- `thinkbox/governance_ledger.py` — Implementation
- `tests/unit/test_governance_ledger.py` — Test suite (17 tests)
- `docs/guides/autonomous-swarm-integration.md` — Workflow integration
- `docs/guides/multi-model-orchestrator.md` — Decision execution

---

## The Difference This Makes

**Before:** Autonomous decisions execute without recorded governance evidence. No audit trail. No tamper detection. No proof that rules were applied.

**After:** Every decision produces cryptographic proof of what governance was applied, enabling:
- ✅ Independent audit
- ✅ Regulatory compliance
- ✅ Tamper detection
- ✅ Governance iteration
- ✅ Human accountability

**This is not alignment. This is transparency.**

Alignment requires humans to decide what governance should be—this layer just faithfully records and verifies that those decisions were applied.
