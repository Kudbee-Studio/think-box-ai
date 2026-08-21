# Organizational Memory — Verified Facts

> Appended 2026-08-21 from a separate cloud session (cross-session observation).
> Facts below are verified against the repository's visible issue/PR list.

## VERIFIED-001: GitHub shared issue/PR numbering explains high PR numbers

**Fact:** In a GitHub repo, issues and pull requests share ONE incrementing
number sequence. Creating issues advances the same counter that PRs use.

**Evidence (this repo):**
- PRs opened by us: #1 (scaffold), #3 (Phase 0 foundation, merged), #5 (review
  fixes, merged), #6 (session branch, closed/DO-NOT-MERGE), #7 (Stage 1
  AgentLoop, open), #22 (Issue #9 PostgreSQL migration, open).
- Issues we filed for the Phase 2–4 roadmap consumed #2, #4, #8–#21 (14 issue
  tickets: memory consolidation, PostgreSQL, voice, benchmarks, multi-agent,
  canvases, Next.js, sandbox, CLI, ESP32, security advisory, milestones).
- Therefore PR #22 is high ONLY because 14 issues (#8–#21) advanced the shared
  counter. No other contributor touched the repo ("no one else is working on
  it but me" is correct).

**Implication for future sessions:** Do NOT treat a high PR number as evidence
of external contributors or a forked history. Check `Issues` vs `Pull
requests` tabs separately. The human operator is the only contributor.

**Source:** Operator-reported, confirmed by issue/PR number gaps observed in
repo. Confidence: high (structural GitHub behavior + visible list).
