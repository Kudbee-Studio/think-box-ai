# Research #277: Vinext-Style Software-Factory Experiment

**Date:** 2026-09-29  
**Status:** RESEARCH IN PROGRESS  
**Experiment:** Can Think Box reproduce autonomous software-factory workflows described in Cloudflare's Vinext announcement?

---

## Executive Summary

This experiment investigates whether Think Box's existing autonomous primitives (decision loop, receipt chains, governance, memory layers) can support the Vinext-style software-factory workflow:

```
Upstream Change → Detect Impact → Reproduce Case → Execute Work 
    → Collect Evidence → Classify Result → Identify Action → Human Escalation
```

**Hypothesis:** Think Box can reproduce this workflow using existing primitives without new core abstractions.

---

## Research Questions

1. **Primitive Mapping:** Which existing Think Box primitives correspond to each Vinext stage?
2. **Missing Binding:** What (if anything) is missing to wire them together?
3. **Autonomy Boundary:** Where does the current system require human intervention?
4. **Evidence Standard:** What qualifies as "test verified" vs "live verified"?
5. **Scale:** Can this work with one upstream change? Multiple changes? Concurrent workflows?

---

## Repository Ground Truth

### Current Autonomous Capabilities (Verified in CONTINUITY.md)

**LIVE VERIFIED (as of 2026-09-26):**
- ✅ Mercury-2 model execution via Inception API
- ✅ Upstash Redis persistence
- ✅ Autonomous decision loop (Sense → Decide → Act → Learn)
- ✅ Dashboard state tracking

**CODE COMPLETE / TEST VERIFIED (not yet LIVE VERIFIED):**
- Autonomous workflow primitives (A01–A25, PRs #217–#223)
- Receipt chain + control plane (PRs #244–#245)
- Autonomous swarm pool + multi-model orchestrator (PRs #259–#260)
- Auditable governance layer (PR #261)
- Governed execution integration (PR #262)
- Multi-box orchestration (PR #263)
- Orchestrator strategy fix + synthesis calibration v2 (PR #264)

### Existing Primitive Inventory

| Primitive | Location | Status | Notes |
|-----------|----------|--------|-------|
| **Decision Loop** | `thinkbox/autonomous_workflow.py` | CODE COMPLETE | Hermetic; plan/sign/verify chain |
| **Receipt Chain** | `thinkbox/receipt_chain_query.py` | CODE COMPLETE | Deep-link, ETag, end-to-end query |
| **Governance** | `thinkbox/governs_execution_lifecycle.py` | CODE COMPLETE | Phases: ADMISSION → QUEUED → RUNNING → COMPLETED/FAILED |
| **Memory Layers** | `thinkbox/memory_layers.py` | CODE COMPLETE | 4 layers: Session, Task, Org, Verified |
| **Actions** | `thinkbox/operator_session.py` | CODE COMPLETE | Session prep, dry-run, receipt |
| **Evidence** | `thinkbox/kilo_live_smoke_evidence.py` | CODE COMPLETE | Proof schema, validation |
| **Classification** | `thinkbox/multi_model_orchestrator.py` | CODE COMPLETE | Consensus, strategy, synthesis |

---

## Experiment: Minimal Software-Factory Loop

### Goal
Build the SMALLEST possible harness that demonstrates:
1. External trigger (simulated upstream change)
2. Impact detection (test compatibility)
3. Case reproduction (create minimal test)
4. Work execution (run the test)
5. Evidence collection (persist result)
6. Classification (pass/fail/requires-attention)
7. Action recommendation (next step)
8. Human escalation (when judgment needed)

### Constraints
- Use ONLY existing primitives
- No new database, no new execution substrate
- Keep experimental code isolated and reversible
- Mark all as provisional/research

### Implementation Plan

#### Phase 1: Upstream Change Simulation (Trivial)
Mock an upstream change: a requirement update that *might* break something.

```python
# Simulated upstream event
upstream_event = {
    "type": "dependency_update",
    "package": "think-box-core",
    "old_version": "0.1.0",
    "new_version": "0.2.0",
    "breaking_changes": ["API.think_job_status: removed `local_result`, use `global_result`"]
}
```

#### Phase 2: Impact Detection
Query existing code to find all usages of the breaking API.

```python
# Use grep/ast to find all references
# Store findings in Org memory layer
```

#### Phase 3: Reproduce Case
Create a minimal test that exercises the breaking change.

```python
# Write a new test file that imports the old API
# This test should FAIL with the new version
```

#### Phase 4: Execute Work
Run the test against both old and new versions.

```python
# Run test with old version → should PASS
# Run test with new version → should FAIL
# Store both results
```

#### Phase 5: Collect Evidence
Use existing Evidence schema to persist results.

```python
# Use think_box_ai.kilo_live_smoke_evidence
# Create evidence document with both runs
```

#### Phase 6: Classify Result
Use existing Classification primitives.

```python
# Use multi_model_orchestrator.py or simpler heuristic
# Classification: "INCOMPATIBLE" if test fails on new version
```

#### Phase 7: Identify Action
Use memory + decision loop to recommend next step.

```python
# Classify → recommend_action()
# "INCOMPATIBLE" → "Requires code change (migration guide needed)"
```

#### Phase 8: Escalation Gate
Determine what needs human review.

```python
# High-confidence findings → automated fix
# Ambiguous findings → human escalation
```

---

## Current Placeholder (Tests)

### Test File: `tests/research/test_277_vinext_software_factory.py`

```python
def test_277_upstream_event_detection():
    """Simulate upstream change detection."""
    # 1. Create mock upstream event
    # 2. Parse breaking changes
    # 3. Find affected code via grep + AST
    # 4. Assert findings match known breakpoints
    pass

def test_277_case_reproduction():
    """Create minimal test for breaking change."""
    # 1. Generate test file
    # 2. Run against old version → PASS
    # 3. Run against new version → FAIL
    # 4. Assert failure mode is the breaking change
    pass

def test_277_evidence_collection():
    """Persist test results as Evidence."""
    # 1. Create evidence document
    # 2. Store both run results
    # 3. Validate against kilo_live_smoke_evidence schema
    # 4. Assert hash/etag correct
    pass

def test_277_classification_and_action():
    """Classify result and recommend action."""
    # 1. Load evidence
    # 2. Classify: INCOMPATIBLE / COMPATIBLE / MANUAL_REVIEW
    # 3. Recommend action
    # 4. Assert action is one of: FIX / ESCALATE / MONITOR
    pass

def test_277_memory_integration():
    """Wire to memory layers."""
    # 1. Store upstream event in Org memory
    # 2. Store case reproduction in Task memory
    # 3. Store evidence in Verified memory (with live_verified: false)
    # 4. Query all three layers, assert retrieval works
    pass

def test_277_autonomy_boundary():
    """Identify where human escalation is required."""
    # 1. Create ambiguous case (unclear if breaking)
    # 2. Run classification
    # 3. Assert result is "REQUIRES_HUMAN"
    # 4. Assert evidence includes rationale
    pass
```

---

## Success Criteria

**This experiment is TEST VERIFIED if:**

1. ✅ Upstream event can be created and parsed
2. ✅ Breaking API references can be found in code
3. ✅ Test case can be generated and run
4. ✅ Evidence can be persisted using existing schema
5. ✅ Classification produces a decision
6. ✅ Action recommendation is unambiguous
7. ✅ Memory integration works (all 4 layers)
8. ✅ Human escalation gate works

**This experiment reaches LIVE VERIFIED if:**

(Out of scope for #277 — requires actual upstream change + real test execution)

---

## What Remains Out of Scope

❌ Actual upstream changes (use mocks)  
❌ Network calls to real repositories  
❌ Real model inference (use stubs/mocks)  
❌ Production-grade parsing (AST is sufficient)  
❌ Concurrent workflow orchestration  
❌ Automatic code fixes (classification only)

---

## Evidence Collection Plan

### Files to Create
- `docs/research/277-vinext-software-factory-experiment.md` (this file)
- `tests/research/test_277_vinext_software_factory.py` (test harness)
- `thinkbox/research_277_vinext_factory.py` (experiment primitives)
- `data/research/277-upstream-event-sample.json` (mock upstream event)
- `data/research/277-test-evidence-sample.json` (sample evidence output)

### Evidence Output
- Test results: `tests/research/test_277_*.py` all pass
- Primitive validation: Existing memory layers accept research data
- Classification output: Decision tree produces expected actions
- Integration output: All 8 phases execute in sequence

---

## Next Larger Improvement

If successful:
- PR #278: Bind upstream change detection to real GitHub webhooks (LIVE VERIFIED)
- PR #279: Automatic migration guide generation (CODE COMPLETE / TEST VERIFIED)
- PR #280: Concurrent multi-package workflow orchestration (CODE COMPLETE)

If unsuccessful:
- Identify missing primitive (binding layer vs architecture gap)
- Propose new layer or ADR
- Document in CONTINUITY.md why hypothesis failed

---

## References

- Cloudflare Vinext: https://blog.cloudflare.com/vinext-nextjs-on-vite/
- CONTINUITY.md: Autonomous workflow core LIVE VERIFIED as of 2026-09-26
- AGENTS.md §1: Layer discipline, provider independence, evidence-over-assumptions
- Autonomous workflow: PRs #217–#223 (A01–A25 steps)
- Receipt chain: PRs #240–#245 (deep-link, control plane)
- Governance: PR #261 (ADMISSION→RUNNING→COMPLETED)

---

## Status

**2026-09-29:** Research PR created.  
**Next:** Run test harness to answer research questions.
