# PR #345: Founder Gate Runbook & Decision Templates

**Date:** 2026-10-03  
**Purpose:** Exact next steps for founder decisions and execution

---

## Gate (a): Think Token Architectural Decision

### Background

**What exists:** PR #288 proposes the learning library (persistent lessons with evidence gates, semantic recall, prompt injection gating). ADRs 028 and 029 document three options: wire into `AgentSession`, decouple as optional library, or drop entirely.

**Current state:** CODE COMPLETE / TEST VERIFIED (all memory layers working, CLI `kudbee tokens` commands, dashboard Think Tokens view). **Not wired into agent lifecycle yet** — tokens are created, stored, retrieved, but not automatically surfaced to agent prompts.

**Blocker:** Design decision is required. The roadmap does not choose.

---

### Option 1: Wire (Recommended by P1 Evidence)

**What:** Integrate token retrieval into agent goal/task processing. Agent prompts surface relevant lessons ahead of tool calls.

**Implementation scope:**
- Modify `apps/web/agent.ts` to call token retrieval on goal entry
- Build retrieval ranking (BM25 + semantic; P3.8 cosine currently best, 0.02 tiebreak)
- Add token text to agent system prompt or tool descriptions
- Risk: Prompt token overhead (528–560 tokens per run per learned lesson)
- Opportunity: Live learning loop closes; agent improves over time

**Evidence file:** `docs/evidence/adr-029-p1.md` §Performance (tokens per run)

**Next step if chosen:** Create PR for integration; target phase P3.11

---

### Option 2: Decouple

**What:** Keep the library standalone. Operators manually query lessons via `/tokens` CLI or dashboard. No automatic agent integration.

**Implementation scope:**
- Minimal: Finalize CLI commands (`kudbee tokens list|show|search`)
- Document best-practices guide for when to apply lessons
- Mark learning library API stable (no breaking changes)
- Risk: Requires operator discipline; lessons may not be applied
- Opportunity: Low cognitive load, no prompt bloat, explicit control

**Evidence file:** Current code already supports this (CLI works)

**Next step if chosen:** Document operator guide; no new code PR needed

---

### Option 3: Drop

**What:** Retire the learning library. Delete memory layers 2–4 (task, org, verified knowledge). Keep session layer for telemetry only.

**Implementation scope:**
- Remove code: `thinkbox/think_token_*.py`, memory layers, challenge/scoring
- Remove dashboard: Think Tokens view, memory graph explorer
- Keep: Session telemetry (token usage, latency, cost)
- Risk: Loss of institutional memory and learning loops
- Opportunity: Simpler codebase, lower maintenance

**Evidence file:** Code to be deleted tracked in `thinkbox/__init__.py` exports

**Next step if chosen:** Create PR; delete and document rationale in AGENTS.md

---

### Founder Decision Format

**Requested format for decision:**

```
I choose: [ ] Wire [ ] Decouple [ ] Drop

Rationale: [one sentence]
Timeline: [do it now / after item 3/4 / after Phase 4]
```

**When decided:** Comment in PR #345 with the choice. We create the implementation PR immediately.

---

## Gate (b): Real Worker-02 Live Evidence

### Background

**What needs proving:** Items 3 (SSH hardening) and 4 (live-proof bundle) are CODE/TEST VERIFIED but need one real execution on worker-02 to move to LIVE VERIFIED.

**Current blocker:** SSH credentials missing from this worktree (purged in PR #271). The proof script expects `UPCLOUD_SSH_KEY_PATH` and `UPCLOUD_SERVER_IP` in the environment.

---

### Prerequisites

Founder must provide:
1. **SSH private key file** for the `kudbee` or `root` user on worker-02
   - Or: Temporary SSH access via Bastion
   - Or: AWS/UpCloud console admin action
2. **Worker-02 IP address or hostname**
   - Current dead: `212.147.250.183`
   - Expected live: `209.50.51.174` (from STATUS.md) or check UpCloud console
3. **Known-hosts entry** (if host-key pinning is enabled)
   - File: `~/.ssh/known_hosts` entry for worker-02
   - Or: Provide the expected host key so we add it

---

### Runbook (Founder Executes)

Once credentials are ready:

```bash
# 1. Set environment
export UPCLOUD_SSH_KEY_PATH=~/.ssh/kudbee-worker02  # or your key path
export UPCLOUD_SERVER_IP=209.50.51.174              # real IP
export UPCLOUD_SSH_HARDENED=true                    # enable pinning
export UPCLOUD_SSH_KNOWN_HOSTS=~/.ssh/known_hosts   # trusted hosts file

# 2. Test connectivity
ssh -i "$UPCLOUD_SSH_KEY_PATH" kudbee@"$UPCLOUD_SERVER_IP" hostname
# Expect: real output like "worker-02" or similar

# 3. Run the proof bundle builder
cd ~/projects/think-box-ai
python3 scripts/run_live_proof_bundle.py --command hostname

# 4. Commit evidence
git add docs/evidence/live-proof/
git commit -m "docs(evidence): real worker-02 live-proof bundle

Live evidence from worker-02:
- SSH hardening: host-key pinning + non-root user verified
- Live-proof bundle: redaction + bundle builder run successfully
- Command: hostname
- Host: worker-02 (UPCLOUD_SERVER_IP)

Items 3 & 4 now LIVE VERIFIED.

Co-Authored-By: [Founder Name] <founder-email>"

# 5. Push to PR #345
git push origin feat/pr345-p3-evidence-and-analysis
```

### What Success Looks Like

After the proof script runs:
- ✅ `docs/evidence/live-proof/` contains: bundle output, redacted artifact, hostname output
- ✅ No secrets in the output (redaction verified)
- ✅ Commit message includes proof details
- ✅ PR #345 updated with evidence links

**After merge:**
- Items 3 (SSH hardening) & 4 (live-proof bundle) move from UNPROVEN to LIVE VERIFIED
- Next phase work (enterprise E2) can begin

---

## Gate (c): Dashboard Auth Deferral Lift

### Background

**Current status:** Dashboard auth + HTTPS are deferred by founder decision (2026-09-30). Required before any remote or shared deployment.

**Why deferred:** Local-only operator console (loopback bind) needs authentication before exposed to network or multiple users.

**Current implementation status:** Deferred — not started.

---

### Prerequisites for Lift

Before starting auth implementation, founder must confirm:
1. **Deployment target:** Where will the dashboard run?
   - Same machine (loopback only)? → Defer auth indefinitely
   - Shared team machine? → Session-based auth needed
   - Remote cloud? → Full OAuth2 + HTTPS required
2. **User model:** How many users? Single operator or team?
3. **Compliance:** Any regulatory requirements (HIPAA, SOC2, etc.)?
4. **Timeline:** Does Phase 3 completion require this, or is Phase 4 acceptable?

---

### Architecture Options (if auth is needed)

#### Option A: Session-Based (Lighter weight)

```typescript
// apps/web/server.ts additions
- POST /api/auth/login (username + password)
- Session cookie (secure, httponly, sameSite=Strict)
- Middleware: require session for all API routes
- Logout: clear session
- Recovery: session file on disk (for restart)
```

**Scope:** ~150 lines of code  
**Security:** Good for single team machine; not for public internet  
**Deadline:** 1–2 day sprint

#### Option B: OAuth2 (Heavier, production-ready)

```typescript
// Integrate with GitHub OAuth or similar
- Redirect to provider on /login
- Exchange code for token
- Store token + user info in session
- HTTPS required (OAuth2 mandate)
```

**Scope:** ~300 lines + provider setup  
**Security:** Industry standard; multi-user safe  
**Deadline:** 3–5 day sprint

#### Option C: OIDC + Reverse Proxy

```
nginx/caddy in front of dashboard
- TLS termination
- OIDC middleware (e.g., dex)
- Dashboard: internal-only, no auth needed
```

**Scope:** Infrastructure (not application code)  
**Security:** Excellent; separates concerns  
**Deadline:** Depends on infrastructure team

---

### Founder Decision Format

**Requested format:**

```
Auth is needed for: [ ] Loopback only (defer forever) [ ] Team machine [ ] Remote cloud

Chosen approach: [ ] Session-based [ ] OAuth2 [ ] OIDC/Proxy [ ] Other

Timeline: [immediate / after Phase 3 items 1-4 / after Phase 4]

Constraints: [regulatory, user count, provider preferences]
```

**When decided:** Comment in PR #345. We create the implementation PR immediately.

---

## Summary: Founder Decision Checklist

| Gate | Decision | Format | Timeline |
|------|----------|--------|----------|
| (a) Think Token | Wire / Decouple / Drop | Comment + choice | Now or P3.11? |
| (b) Worker-02 Evidence | Provide SSH creds + IP | Email or comment + runbook | Now? |
| (c) Auth Deferral | Lift & choose auth type | Comment + option + constraints | Now? / After Phase 3? |

---

## Expected Outcomes per Gate

### After (a) — Think Token Decision

- 1 new implementation PR (if Wire is chosen)
- OR: 1 docs PR with operator guide (if Decouple)
- OR: 1 cleanup PR deleting library (if Drop)

### After (b) — Worker-02 Live Evidence

- Items 3 & 4 move to LIVE VERIFIED
- Proof artifacts committed to `docs/evidence/live-proof/`
- Phase 3 implementation lanes: 1, 2, 2b, 3, 4, 6 are LIVE VERIFIED (ready to ship)
- Item 5 still waiting on gate (a)
- Item 7 still waiting on gate (c)

### After (c) — Auth Lift + Decision

- 1 new implementation PR for auth (if lift is confirmed)
- Scope: 150–300 lines or infrastructure setup
- Timeline: 1–5 days depending on approach

---

Generated by Claude Haiku 4.5 — Founder Gate Runbook
