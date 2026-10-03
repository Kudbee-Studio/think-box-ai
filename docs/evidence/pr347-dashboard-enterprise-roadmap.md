# PR #347: Enterprise Dashboard Roadmap & Code Cleanup

**Date:** 2026-10-03  
**Phase:** P3.22 (Enterprise dashboard + codebase cleanup)  
**Status:** PLANNING PHASE

---

## Executive Summary

**Objective:** Build professional enterprise-grade dashboard with plugin architecture, while cleaning up codebase (77+ `any` types, 20+ silent catch blocks, orphaned docs).

**Scope:**
- ✅ Dashboard: 5+ enterprise features + plugin system
- ✅ Code: Fix TypeScript compliance, remove 77+ `any` instances
- ✅ Docs: Delete 40+ orphaned files, consolidate duplicates, update AGENTS.md

**Timeline:** 2-3 week sprint
**Risk:** Medium (refactoring + new features; requires careful testing)

---

## Part 1: Enterprise Dashboard Roadmap

### Current State (Baseline)
```
Dashboard has:
✅ Dark theme (pro-level design tokens)
✅ Basic enterprise polish (14 CSS categories)
✅ Think Token visualization
✅ Terminal for agent interactions
✅ File explorer
✅ Git integration panel

Needs:
❌ Plugin system
❌ User preferences/settings
❌ Custom themes
❌ Advanced analytics
❌ Workflow templates
❌ Real-time collaboration features
❌ Mobile responsiveness (tablet)
```

### Phase 1: Foundation (Week 1)

**1.1 Plugin Architecture Framework**
- Create plugin protocol in `apps/web/types/plugin.ts`
- Plugin manifest schema (name, version, capabilities)
- Plugin registry system (load, discover, enable/disable)
- Plugin storage (localStorage persistence)
- Example plugin template
- Tests for plugin lifecycle

**Files to create:**
- `apps/web/types/plugin.ts` (plugin protocol)
- `apps/web/services/plugin-manager.ts` (registry + lifecycle)
- `apps/web/plugins/example-plugin/` (template)
- `apps/web/tests/plugin-system.test.ts` (unit tests)

**Effort:** 1-2 days
**Risk:** LOW (isolated feature, no breaking changes)

---

**1.2 User Settings Panel**
- Settings page with tabs (appearance, behavior, data)
- Theme selector (dark/light + custom palettes)
- Keyboard shortcuts editor
- Run history retention slider
- Export/import settings JSON
- Reset to defaults

**Files to modify:**
- `apps/web/public/index.html` (add settings panel)
- `apps/web/public/js/app.js` (settings logic)
- `apps/web/public/css/main-pro.css` (settings styling)
- Create: `apps/web/services/user-preferences.ts`

**Effort:** 1-2 days
**Risk:** LOW (self-contained UI feature)

---

**1.3 Enterprise Color Themes**
- 3+ professional themes (dark, light, high-contrast)
- Theme switcher in settings
- CSS variable override system
- Local storage persistence
- Keyboard shortcut (Cmd/Ctrl+Shift+T)

**Files:**
- Create: `apps/web/themes/` directory with theme JSON files
- Update: `apps/web/public/css/main-pro.css` (theme vars)
- Create: `apps/web/services/theme-manager.ts`

**Effort:** 1 day
**Risk:** LOW

---

### Phase 2: Analytics & Observability (Week 2)

**2.1 Run Analytics Dashboard**
- KPI cards: total runs, success rate, avg latency, tokens saved
- Time-series graphs (runs per hour, latency trends, token efficiency)
- Run distribution by model (pie chart)
- Failure rate by category (bar chart)
- Historical comparison (this week vs. last week)

**Files:**
- Create: `apps/web/panels/analytics.ts` (panel component)
- Create: `apps/web/services/analytics.ts` (data aggregation)
- Create: `apps/web/public/css/analytics.css` (styling)
- Tests: `apps/web/tests/analytics.test.ts`

**Effort:** 2-3 days
**Risk:** MEDIUM (requires real-time data aggregation)

---

**2.2 Workflow Execution Timeline**
- Gantt-like timeline of tool execution within a run
- Step duration visualization
- Tool approval wait times
- Error/warning highlights
- Step-by-step review mode

**Files:**
- Create: `apps/web/panels/timeline.ts`
- Create: `apps/web/services/timeline.ts`
- Create: `apps/web/public/css/timeline.css`

**Effort:** 2 days
**Risk:** MEDIUM

---

### Phase 3: Collaboration & Sharing (Week 3)

**3.1 Run Sharing**
- Generate shareable run snapshot (JSON + formatted HTML)
- One-time or expiring links (via backend API)
- Anonymous view mode (no sensitive data)
- Copy-to-clipboard formatting
- Export options (JSON, Markdown, HTML)

**Files:**
- Create: `apps/web/services/run-sharing.ts`
- Create: `apps/web/panels/share-run.ts`
- Backend: `apps/web/server.ts` update for `/api/runs/:id/share`

**Effort:** 2 days
**Risk:** MEDIUM (API integration needed)

---

**3.2 Workflow Templates**
- Save/load run templates (tool sequence without data)
- Template library (built-in + user-created)
- Template preview before execution
- One-click run from template
- Share templates with team (localStorage or backend)

**Files:**
- Create: `apps/web/services/template-manager.ts`
- Create: `apps/web/panels/templates.ts`
- Create: `apps/web/public/css/templates.css`

**Effort:** 1-2 days
**Risk:** MEDIUM

---

### Phase 4: Mobile & Accessibility (Future)

**4.1 Tablet-Optimized UI**
- Responsive layout for 768px+ screens
- Touch-friendly button sizes (44px minimum)
- Stacked layout for small screens
- Swipe gestures for panel navigation

**Effort:** 2-3 days
**Risk:** MEDIUM

---

**4.2 Accessibility Audit & Fixes**
- WCAG 2.1 Level AAA compliance
- Screen reader testing
- Keyboard-only navigation
- Color-blind color palette option
- Font size adjustment

**Effort:** 1-2 days
**Risk:** LOW

---

## Part 2: Code Cleanup

### Section A: TypeScript Compliance (77+ issues)

**A.1 Replace `any` Types (HIGH PRIORITY)**

**Issue:** 77+ instances of `as any` throughout codebase

**Files affected:**
- cli.ts (interface Msg)
- Multiple test files (Promise<any>, callback: any)
- types.ts (Record<string, any>)

**Approach:**
1. Define proper types for each module
2. Create type interfaces for common patterns (Msg, ApiResponse, etc.)
3. Use `unknown` only where absolutely necessary
4. Add type guards for unknown data

**Example fix:**
```typescript
// Before
interface Msg { type: string; data?: any }

// After
type MessageData = RunResult | ErrorInfo | SuccessStatus;
interface Msg { type: 'run_result' | 'error' | 'success'; data: MessageData }
```

**Effort:** 2-3 days
**Risk:** MEDIUM (refactoring risk; comprehensive testing needed)
**Tests:** Ensure all 576 tests pass after each file

---

**A.2 Remove Silent Error Swallowing (HIGH PRIORITY)**

**Issue:** 20+ catch blocks that swallow errors

**Example:**
```typescript
// Before: git-repo-manager.ts:250-251
try {
  await syncRepo();
} catch {
  return {}; // Silent failure!
}

// After
try {
  await syncRepo();
} catch (err) {
  console.error(`Failed to sync repo: ${err instanceof Error ? err.message : String(err)}`);
  throw err; // Propagate or handle explicitly
}
```

**Files affected:**
- git-repo-manager.ts (8+ instances)
- git-api-routes.ts (5+ instances)
- think-token-model.ts (3+ instances)
- memory.ts (4+ instances)

**Approach:**
1. Add error logging to every catch block
2. Propagate errors up the stack
3. Create error handling helper function
4. Add telemetry/observability

**Effort:** 1-2 days
**Risk:** HIGH (changing error handling behavior)
**Tests:** Add tests for error scenarios

---

**A.3 Remove Console.log from Production (HIGH PRIORITY)**

**Issue:** 20+ console statements in production code

**Files affected:**
- server.ts (8+ instances)
- think-token-model.ts (3+ instances)
- git-repo-manager.ts (4+ instances)
- think-token-propagation.ts (3+ instances)

**Approach:**
1. Create debug logging infrastructure (if not exists)
2. Move console.log to debug-only logger
3. Keep error logging in place
4. Add env-based verbosity control

**Effort:** 1 day
**Risk:** LOW

---

### Section B: Documentation Cleanup

**B.1 Delete Orphaned Files (SAFE)**

**Files to DELETE:**
- `docs/guides/kilo_*.md` (40+ files) — KILO project archived
- `docs/decisions/kilo_*.md` (20+ files) — Project references
- `docs/audit/checklists/kilo_*.md` (20+ files) — Project checklists
- `docs/RED/` (5 files) — External project reference (unclear status)

**Total:** 85+ files
**Risk:** LOW (git history preserved; no active references)

**Action:** Create cleanup PR that deletes these in one commit

---

**B.2 Archive Historical Docs**

**Files to MOVE to docs/archive/:**
- `docs/archive/PHASE9_INDEX.md` (already in archive)
- `docs/archive/TEST_SYNC.md` (already in archive)
- Old SDK quickstart versions (keep latest only)
- Experimental/research docs >6 months old

**Risk:** LOW

---

**B.3 Consolidate Duplicates**

**Known duplicates:**
- SDK quickstart versions (5 files) → Keep latest, archive others
- Environment variable docs (3 versions) → Merge into single source

**Action:** Identify, consolidate, update references

---

**B.4 Update AGENTS.md**

**Add sections:**
1. PR #347 completion status
2. Dashboard plugin architecture guide
3. TypeScript compliance checklist
4. Code cleanup checklist
5. Enterprise feature roadmap

**Action:** Update after implementing each phase

---

## Part 3: Testing Strategy

### Test Coverage Requirements

**For new features:**
- Unit tests: 80%+ coverage for each plugin/component
- Integration tests: Full workflow from UI interaction to persistence
- E2E tests: User journey tests (if setup available)

**For cleanup work:**
- No test regressions (576 tests must still pass)
- New error handling paths tested
- Type changes verified

---

## Four-State Classification (Projected)

| State | PR #347 Projection |
|-------|-------------------|
| CODE COMPLETE | ✅ All features implemented; cleanup done |
| TEST VERIFIED | ✅ 576+ tests passing; new tests added |
| LIVE VERIFIED | ⏳ Depends on founder approval for enterprise features |
| PRODUCTION READY | ⏳ After review and acceptance testing |

---

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Type refactoring breaks code | HIGH | Run full test suite after each file |
| Error handling changes break flow | HIGH | Comprehensive error scenario testing |
| Documentation inconsistency | MEDIUM | Update AGENTS.md continuously |
| Plugin API too rigid | MEDIUM | Design API first; get feedback before impl |
| Cleanup deletes needed docs | LOW | Check git history; verify no references |

---

## Success Criteria

1. ✅ All 576 tests passing (no regressions)
2. ✅ TypeScript `any` count < 10 (down from 77+)
3. ✅ Zero silent error catches (all log + propagate)
4. ✅ 0 console.log in production code
5. ✅ 85+ orphaned docs deleted
6. ✅ Plugin system working + documented
7. ✅ At least 2 new enterprise features in dashboard
8. ✅ AGENTS.md updated with all changes

---

## Timeline Estimate

| Phase | Effort | Risk |
|-------|--------|------|
| Phase 1: Foundation | 2-3 days | LOW |
| Phase 2: Analytics | 4-5 days | MEDIUM |
| Phase 3: Collaboration | 3-4 days | MEDIUM |
| Cleanup & Testing | 3-4 days | HIGH |
| **Total** | **12-16 days** | **MEDIUM** |

**Recommended:** 2-3 week sprint with daily progress check-ins

---

## Related PRs & Dependencies

- Requires: PR #346 (dashboard polish) ✅ MERGED
- Related: AGENTS.md cleanup and documentation updates
- Future: PR #348 (mobile optimization, if approved)

---

## Questions for Founder/Team

1. **Plugin priorities:** Which enterprise features matter most?
2. **Data sharing:** Is backend API for run sharing needed, or localStorage only?
3. **Collaboration:** Real-time multi-user features or just sharing?
4. **Timeline:** Can afford 3-week sprint, or need to phase differently?
5. **TypeScript:** Willing to invest 2-3 days in type safety refactoring?

---

Generated by Claude Haiku 4.5 — Enterprise Dashboard Roadmap & Code Cleanup Plan
