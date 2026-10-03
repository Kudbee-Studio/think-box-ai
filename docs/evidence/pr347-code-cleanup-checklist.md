# PR #347: Code Cleanup Checklist & Execution Plan

**Date:** 2026-10-03  
**Agent Findings:** Code cleanup opportunities identified by Explore agent + manual review  
**Status:** EXECUTION PHASE

---

## HIGH PRIORITY FIXES

### [ ] Task H1: Replace 77+ `any` Types → Proper Types

**Files to refactor (by severity):**

1. **cli.ts** - Priority: CRITICAL
   - [ ] Line 52: `interface Msg { type: string; data?: any }`
   - [ ] Line 48-49: `type RouteTelemtry` with loose types
   - [ ] Lines 90+: Function return types with `any`
   - **Action:** Create specific message types (RunResult, ErrorInfo, etc.)
   - **Effort:** 3-4 hours
   - **Test:** npm test (all 576 must pass)

2. **types.ts** - Priority: HIGH
   - [ ] Line 13: `Record<string, any>` 
   - [ ] Create specific interfaces for state types
   - **Action:** Define PanelState, ViewState, etc.
   - **Effort:** 2 hours
   - **Test:** Verify all type usages pass typecheck

3. **Test files** - Priority: HIGH
   - [ ] `tests/server.test.ts`: `Promise<any>` callbacks
   - [ ] `tests/think-token-dashboard.test.ts`: `any` in addEventListener
   - [ ] `tests/think-token-p1-integration.test.ts`: Interface with `any` fields
   - **Action:** Create proper test interfaces
   - **Effort:** 3-4 hours
   - **Test:** npm test (full suite)

4. **Server files** - Priority: MEDIUM
   - [ ] `server.ts:344,584,1822`: Multiple `any` type casts
   - [ ] `governed-bridge.ts:35`: `any` in callback
   - [ ] `think-token-pipeline.ts:316`: `let parsed: any`
   - **Action:** Use `unknown` + type guards, or specific types
   - **Effort:** 4-5 hours
   - **Test:** Integration tests pass

**Total Effort:** 12-16 hours (roughly 2 days)
**Risk:** MEDIUM (refactoring complex types; test thoroughly)

**Validation:**
```bash
cd apps/web
npm run typecheck  # Must pass
npm test           # 576/576 must pass
grep -r "as any" . # Should be <10 after this task
```

---

### [ ] Task H2: Remove Silent Error Swallowing (20+ catch blocks)

**Files with silent catches:**

1. **git-repo-manager.ts** - Priority: CRITICAL (8 instances)
   - [ ] Line 106: `.catch()` silently
   - [ ] Line 120: Try-catch returns `{}`
   - [ ] Lines 173, 203, 224, 250, 303, 323: Similar patterns
   - **Pattern fix:**
   ```typescript
   // Before
   try { /* operation */ } catch { return {}; }
   
   // After
   try { /* operation */ } 
   catch (err) { 
     logger.error(`Operation failed: ${err instanceof Error ? err.message : String(err)}`);
     throw err; // Propagate
   }
   ```
   - **Effort:** 3-4 hours

2. **git-api-routes.ts** - Priority: HIGH (5+ instances)
   - [ ] Lines 34, 46, 69, 95, 124, 151, 169
   - **Effort:** 2-3 hours

3. **think-token-model.ts** - Priority: MEDIUM (3+ instances)
   - [ ] Lines 84, 119, 138
   - **Effort:** 1-2 hours

4. **memory.ts** - Priority: MEDIUM (4+ instances)
   - [ ] Lines 184, 274, 323, 339, 437
   - **Effort:** 1-2 hours

5. **services/plugins.ts** - Priority: LOW (2 instances)
   - [ ] Lines 27, 45
   - **Effort:** 30 min

**Total Effort:** 8-12 hours (roughly 1-2 days)
**Risk:** HIGH (error handling behavior changes; needs thorough testing)

**Implementation:**
```typescript
// Create error helper
export function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

// Use consistently
catch (err) {
  logger.error(`Context: ${errorMessage(err)}`);
  throw err; // or handle gracefully
}
```

**Validation:**
- [ ] No silent catches remain: `grep -r "catch\s*(" apps/web/*.ts | grep -v "console"` should show logging
- [ ] All error paths tested
- [ ] 576 tests still pass

---

### [ ] Task H3: Remove console.log from Production (20+ instances)

**Files to clean:**

1. **server.ts** - Priority: CRITICAL (8+ instances)
   - [ ] Line 325, 1347, 2051, 2058, 2064, 2640-2649
   - **Action:** Move to debug logger or remove if not essential
   - **Effort:** 1-2 hours

2. **think-token-model.ts** - Priority: HIGH (3+ instances)
   - [ ] Lines 44
   - **Effort:** 30 min

3. **think-token-embed.ts** - Priority: MEDIUM (1 instance)
   - [ ] Line 61
   - **Effort:** 15 min

4. **learning-integration.ts** - Priority: MEDIUM (1 instance)
   - [ ] Line 64
   - **Effort:** 15 min

5. **git-repo-manager.ts** - Priority: MEDIUM (4+ instances)
   - [ ] Lines 121, 174, 304, 324
   - **Effort:** 30 min

6. **think-token-propagation.ts** - Priority: MEDIUM (3+ instances)
   - [ ] Lines 154, 207, 216
   - **Effort:** 30 min

7. **cli.ts** - Priority: LOW (2 instances)
   - [ ] Lines 65, 73, 83 (these are CLI output, keep)
   - **Effort:** 0 (cli.ts is allowed to log)

**Total Effort:** 3-4 hours
**Risk:** LOW (simple removal/refactoring)

**Validation:**
```bash
grep -r "console\.\(log\|warn\|error\)" apps/web --include="*.ts" | grep -v "cli.ts" | grep -v "test"
# Should show 0 results after cleanup
```

---

## MEDIUM PRIORITY FIXES

### [ ] Task M1: Replace Record<string, any> with Specific Types (15+ instances)

**Pattern:**
```typescript
// Before
Record<string, any>

// After
interface PanelState { 
  visibilityState: 'visible' | 'hidden'; 
  position?: { x: number; y: number }; 
}
```

**Affected files:**
- types.ts (3 instances)
- persistence.ts (5+ instances)
- server.ts (3+ instances)
- cli.ts (1 instance)

**Effort:** 4-5 hours
**Risk:** MEDIUM

---

### [ ] Task M2: Extract Hardcoded Literals to Constants

**Pattern:**
```typescript
// Before
const PORT = process.env.PORT || 3000;
const batchSize = 100; // In memory.ts
const maxDepth = 10; // In git-repo-manager.ts

// After
// Create: apps/web/constants.ts
export const CONFIG = {
  DEFAULT_PORT: 3000,
  BATCH_SIZE: 100,
  MAX_GIT_DEPTH: 10,
  MAX_MODEL_INPUT_CHARS: 8000,
  CALL_TIMEOUT_MS: 30000,
};
```

**Effort:** 2-3 hours
**Risk:** LOW

---

### [ ] Task M3: Extract Repeated Validation Patterns

**Files:**
- specialist-executor.ts (jobId/intent/specialists validation)
- git-repo-manager.ts (URL/branch/depth validation)

**Create:** `apps/web/validators.ts`

**Effort:** 2 hours
**Risk:** LOW

---

## DOCUMENTATION CLEANUP

### [ ] Task D1: Delete 85+ Orphaned Files

**Safe to delete (no references):**
- `docs/guides/kilo_*.md` (40+ files)
- `docs/decisions/kilo_*.md` (20+ files)
- `docs/audit/checklists/kilo_*.md` (20+ files)
- `docs/RED/` (5 files)

**Action:**
```bash
# Verify no references first
grep -r "kilo_" docs/ --include="*.md" # Should show 0
rm docs/guides/kilo_*.md
rm docs/decisions/kilo_*.md
rm docs/audit/checklists/kilo_*.md
rm -rf docs/RED/
```

**Effort:** 1 hour (including verification)
**Risk:** LOW (git history preserved)

---

### [ ] Task D2: Consolidate Duplicate Guides

**Known duplicates:**
- 5+ SDK quickstart versions → Keep `kudbee_sdk_quickstart.md`, archive others
- 3+ environment variable docs → Merge into single `docs/guides/environment-variables.md`

**Effort:** 2 hours
**Risk:** MEDIUM (verify all references updated)

---

### [ ] Task D3: Update AGENTS.md with PR #347 Info

**Add sections:**
- [ ] PR #347 completion status
- [ ] Code cleanup checklist results
- [ ] Dashboard plugin architecture guide
- [ ] Enterprise feature roadmap link
- [ ] TypeScript compliance status (any count reduction)

**Effort:** 1 hour

---

## VALIDATION & TESTING

### Pre-Commit Checklist

- [ ] `npm run typecheck` passes (0 errors)
- [ ] `npm test` passes (576/576 tests passing)
- [ ] `npm run lint` passes (if available)
- [ ] No `grep -r "as any" apps/web` or <10 instances remain
- [ ] No `console.log` in production code (except cli.ts)
- [ ] No silent catch blocks remain
- [ ] 85+ files deleted successfully
- [ ] All documentation references updated

### Post-Merge Validation

- [ ] CI checks pass on GitHub
- [ ] No regressions in production behavior
- [ ] Dashboard still loads and functions correctly
- [ ] Agent still works (tests pass)

---

## Execution Order

**Recommended sequence (to minimize conflicts):**

1. Task H1 (Replace `any`) — 2 days
2. Task H2 (Fix error handling) — 1-2 days
3. Task H3 (Remove console) — 4 hours
4. Task M1 (Record<string, any>) — 5 hours
5. Task M2 (Extract constants) — 3 hours
6. Task M3 (Validation helpers) — 2 hours
7. Task D1 (Delete orphaned docs) — 1 hour
8. Task D2 (Consolidate duplicates) — 2 hours
9. Task D3 (Update AGENTS.md) — 1 hour

**Total Effort:** ~22-25 hours (roughly 3-4 days of focused work)

---

## Success Criteria

- [ ] ✅ `any` instances: 77+ → <10
- [ ] ✅ Silent catches: 20+ → 0
- [ ] ✅ Production console.log: 20+ → 0
- [ ] ✅ Record<string, any>: 15+ → 0
- [ ] ✅ Tests passing: 576/576
- [ ] ✅ TypeScript strict: all checks pass
- [ ] ✅ Orphaned docs: 85 files deleted
- [ ] ✅ AGENTS.md: updated with all changes

---

Generated by Claude Haiku 4.5 — Code Cleanup Execution Plan
