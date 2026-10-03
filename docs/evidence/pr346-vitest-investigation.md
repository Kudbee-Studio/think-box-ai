# PR #346: VITEST Migration Investigation

**Date:** 2026-10-03  
**Phase:** P3.21 (testing infrastructure improvement)  
**Status:** INVESTIGATION PHASE — Evaluating VITEST as test runner replacement

---

## Executive Summary

**Current State:** Using tsgo/Node.js native test runner  
**Proposal:** Evaluate VITEST for better performance, DX, and features  
**Goal:** Determine if migration is worthwhile and create implementation plan

**Questions to Answer:**
1. ✅ Performance: Is VITEST faster than current setup?
2. ✅ Compatibility: Do existing tests run with zero changes?
3. ✅ Features: What new capabilities does VITEST unlock?
4. ✅ Effort: What's the migration cost (time, risk)?
5. ✅ Verdict: Should we migrate, and when?

---

## Current Test Setup

**Runner:** Node.js native `node:test` (via tsgo)  
**Test Count:** 576 tests, 52 suites  
**Duration:** ~22 seconds local  
**Framework:** Node.js built-in (no external test framework)

**Characteristics:**
- ✅ Zero external dependencies
- ✅ Native ES modules support
- ⚠️ Limited parallelization options
- ⚠️ No test filtering/tagging
- ⚠️ Basic output formatting
- ⚠️ No watch mode built-in

---

## VITEST Overview

**What it is:** Blazing fast unit test framework built on Vite  
**Key Features:**
- ⚡ ~10x faster (smart module pre-bundling + parallel execution)
- 🎯 Test filtering (by name, tag, regex)
- 👀 Watch mode with hot reload
- 🔄 Instant re-runs on file change
- 📊 Rich output formatting + UI
- 🧵 Built-in parallelization
- 📦 Works with existing Jest/Mocha suites
- 🌐 Browser-like environment (jsdom, happy-dom, edge options)

**Trade-offs:**
- Adds dependency (though small: ~40MB install)
- Configuration required (vitest.config.ts)
- Test syntax compatible but config differs

---

## Investigation Workload

### Phase 1: Proof of Concept (This PR)

**Task 1.1: Set Up VITEST Alongside Current Tests**

```bash
# Install VITEST
npm install --save-dev vitest @vitest/ui

# Create config
cat > vitest.config.ts << 'EOF'
import { defineConfig } from 'vitest/config'
import path from 'path'

export default defineConfig({
  test: {
    globals: true,
    environment: 'node',
    include: ['tests/**/*.test.ts'],
    exclude: ['node_modules'],
    reporter: ['verbose'],
    threads: true,
    maxThreads: 4,
    minThreads: 1,
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
})
EOF

# Run tests with VITEST
npx vitest run --reporter=verbose
```

**Deliverable:** Working VITEST setup running existing tests  
**Success Criteria:** All 576 tests pass with VITEST

---

**Task 1.2: Measure Performance**

```bash
# Baseline (current setup)
time npm test
# Expected: ~22 seconds

# VITEST single-threaded
time npx vitest run --no-coverage
# Expected: ? seconds (measure)

# VITEST multi-threaded (default 4)
time npx vitest run --threads --reporter=verbose
# Expected: ? seconds (measure)

# VITEST UI (interactive)
npx vitest --ui
# Open http://localhost:51204 to see interactive runner
```

**Deliverable:** Performance comparison table  
**Success Criteria:** Measure speedup (or confirm current is better)

---

**Task 1.3: Feature Evaluation**

Test VITEST capabilities we don't have now:

```bash
# Test filtering
npx vitest run --grep "memory"  # Run only tests matching /memory/
npx vitest run --grep "!integration"  # Exclude matching tests

# Watch mode
npx vitest watch  # Auto-reruns on file change

# UI mode
npx vitest --ui  # Visual test runner

# Debug mode
npx vitest --inspect-brk  # Node inspector integration
```

**Deliverable:** Feature matrix + screenshots  
**Success Criteria:** Document 3–5 new capabilities we'd gain

---

**Task 1.4: Compatibility Check**

Run full test suite with minimal changes:

```typescript
// Check 1: Can existing tests run as-is?
npx vitest run --reporter=verbose 2>&1 | tee vitest-run.log

// Check 2: API compatibility
// VITEST uses same APIs as Node.js test:
test('example', () => { assert.equal(2 + 2, 4) })
describe('suite', () => { ... })
beforeEach(() => { ... })
afterEach(() => { ... })
```

**Deliverable:** 
- Compatibility report (list any required changes)
- VITEST run log showing pass/fail counts
- Side-by-side test syntax comparison

**Success Criteria:** 
- 576/576 tests pass with VITEST
- 0 syntax changes required
- 0 breaking API incompatibilities

---

**Task 1.5: Risk Assessment**

Identify migration blockers:

| Risk | Status | Mitigation |
|------|--------|-----------|
| Node version incompatibility | CHECK | VITEST requires Node 14+; we have 22 ✅ |
| Test syntax changes | CHECK | No breaking changes expected |
| Coverage tool changes | CHECK | VITEST has c8 integration |
| CI/CD changes | CHECK | GitHub Actions will need vitest command |
| IDE integration | CHECK | VS Code, JetBrains support built-in |
| Performance regression | CHECK | Measure; should be faster |

**Deliverable:** Risk matrix with mitigations  
**Success Criteria:** Identify top 3 risks + solutions

---

### Phase 2: Implementation Plan (PR #347+)

If PoC succeeds:

1. **Commit VITEST setup** to PR #346
2. **Migrate npm scripts** (package.json test command)
3. **Update CI** (.github/workflows/test.yml to use vitest)
4. **Remove old runner** config (tsgo if not used elsewhere)
5. **Add npm audit** check (VITEST security)
6. **Document** in README and AGENTS.md

**Estimated effort:** 1 day  
**Risk level:** LOW (test runner swap, non-blocking)

---

## Success Criteria for PR #346

| Criterion | Status | Evidence |
|-----------|--------|----------|
| VITEST runs 576 tests | ⏳ TBD | vitest run output |
| All tests pass | ⏳ TBD | 576/576 PASS |
| Performance measured | ⏳ TBD | Time comparison log |
| Features documented | ⏳ TBD | Feature matrix |
| Compatibility verified | ⏳ TBD | Syntax check report |
| Risks identified | ⏳ TBD | Risk matrix |
| No breaking changes | ⏳ TBD | Test syntax unchanged |
| Config committed | ⏳ TBD | vitest.config.ts in repo |

---

## Decision Tree

**If PoC Passes:**
```
✅ All 576 tests pass with VITEST
  ├─ Performance > 2x faster? → Migrate immediately (PR #347)
  ├─ Performance similar? → Migrate for UX (watch mode, UI) (PR #347)
  └─ Performance slower? → Keep current (document why)
```

**If PoC Fails:**
```
❌ Tests don't pass with VITEST
  ├─ Minor syntax changes? → Fix and re-evaluate
  ├─ Major incompatibilities? → Defer migration
  └─ Blockers? → Document and close
```

---

## Workload Breakdown (Detailed Tasks)

### To Do

- [ ] **Task 1.1:** Install VITEST + write config
  - Command: `npm install --save-dev vitest @vitest/ui`
  - Deliverable: `vitest.config.ts`
  - Est. time: 30 min

- [ ] **Task 1.2:** Performance benchmark
  - Commands: time npm test, time npx vitest run
  - Deliverable: benchmark table (3 runs: current, vitest-single, vitest-multi)
  - Est. time: 20 min

- [ ] **Task 1.3:** Feature walkthrough
  - Test: filtering, watch mode, UI mode, debug mode
  - Deliverable: feature matrix + 3 screenshots
  - Est. time: 30 min

- [ ] **Task 1.4:** Compatibility verification
  - Run full suite, check for errors
  - Deliverable: vitest-run.log + compatibility report
  - Est. time: 15 min

- [ ] **Task 1.5:** Risk assessment
  - Create matrix: 5–7 risks, mitigation for each
  - Deliverable: risk matrix table
  - Est. time: 20 min

- [ ] **Commit & document**
  - Add vitest.config.ts and findings to PR #346
  - Est. time: 15 min

**Total Estimated Time:** 2.5–3 hours

---

## Decision Gate

**This PR #346 should end with a clear recommendation:**

✅ **RECOMMEND MIGRATION IF:**
- All 576 tests pass
- Performance >= 1.5x faster OR watch mode saves >30 min/day
- Zero code changes required
- CI changes are straightforward

❌ **DEFER IF:**
- Tests fail with incompatibilities
- Performance is slower
- Major refactoring needed

---

## References

- **VITEST docs:** https://vitest.dev/
- **Current runner:** Node.js test module docs
- **Config reference:** vitest.config.ts options
- **Test syntax:** Maintained in Node.js native test format

---

## Four-State Classification (Expected)

| State | Target |
|-------|--------|
| CODE COMPLETE | ✅ VITEST config + investigation complete |
| TEST VERIFIED | ✅ 576 tests run and pass with VITEST |
| LIVE VERIFIED | ⏳ TBD — depends on performance results |
| PRODUCTION READY | ⏳ TBD — depends on investigation outcome |

---

Generated by Claude Haiku 4.5 — VITEST Migration Investigation Workload for PR #346
