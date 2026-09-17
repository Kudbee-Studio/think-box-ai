# CONTINUITY — Canonical Agent State Artifact

**Purpose:** Every agent MUST read this before making changes.
This is the repository's memory. Conversations are temporary; this is persistent.

**Location:** `docs/CONTINUITY.md` (this file)
**Inherited by:** All agents via AGENTS.md §14
**Last updated:** 2026-09-17

---

## AGENT EXIT CHECK

Before declaring completion, every agent MUST verify:

- [x] Existing continuity state read
- [x] Work classified ACTIVE/BLOCKED/PARKED/COMPLETE
- [x] 4-state classification assigned per AGENTS.md §14.7 for all work items
- [x] Tests executed and passing (449 OK, 6 skipped)
- [x] Evidence recorded in CONTINUITY.md
- [x] Documentation updated (CONTINUITY.md, AGENTS.md §14, STATUS.md)
- [x] Git state clean (working tree clean, 12 commits on kilo/leafy-dragon-4ck)
- [x] PR/commit referenced (PR #68 CLOSED without merge, commits 32d82ef → 8ea6552)
- [x] No stale open loop created
- [x] Next larger improvement documented
- [x] Security/credential check completed (0 credentials found)

---

## CURRENT STATE

| Field | Value |
|---|---|
| **Active objective** | Close continuity loop — integrate credential precedence into main |
| **Latest completed work** | UpCloud ExecutionProvider + credential precedence + continuity audit (commits `32d82ef` → `8ea6552`) on `kilo/leafy-dragon-4ck` |
| **Current verified capabilities** | ExecutionProvider abstraction (CODE COMPLETE ✅), UpCloud provider with credential precedence (CODE COMPLETE ✅), 33 unit tests (TEST VERIFIED ✅), credential precedence logic (TEST VERIFIED ✅), permanent agent protocol (CODE COMPLETE ✅ / TEST VERIFIED ✅) |
| **Current blockers** | No `UPCLOUD_API_MAIN` credential in environment; all API probes return 401; PR #68 CLOSED without merge — credential precedence exists only on `kilo/leafy-dragon-4ck`; main has older UpCloud provider without credential precedence |
| **Known risks** | UpCloud API unreachable with current credentials; PR #68 closed unmerged; main's UpCloud provider lacks credential precedence; server STOPPED; SSH keys absent |
| **Next larger improvement** | Cherry-pick `a2335e2` onto main (4 code files apply cleanly, 2 doc files need trivial resolution) → set valid `UPCLOUD_API_MAIN` env var → run live smoke tests |

---

## SERVER CONNECTION PATH RECOVERY (2026-09-16)

The September 15 server connection was traced from git history, docs, and infra config. It was **SSH-based**, not API-based. The current agent CANNOT reuse this path because: (a) SSH key was on Kudbee's laptop (not in repo), (b) server is unreachable from sandbox (port 22 times out), (c) server is in STOPPED state per infra config.

### September 15 Connection Mechanism

Evidence sources: SESSION.md (commit 5e91758), MEMORY.md (commit 5e91758), data/infra_upcloud.ini (commit 9097194), docs/guides/server-setup.md (commit 0752566).

| Layer | Mechanism | Evidence |
|-------|-----------|----------|
| **Origin** | Kudbee's laptop (NOT this cloud sandbox) | SESSION.md checklist |
| **Authentication** | SSH key on Kudbee's laptop (path unknown — explicitly NOT `~/.ssh/kilo-upcloud` per MEMORY.md) | MEMORY.md: "SSH key: unknown until laptop" |
| **Network** | SSH to floating IP `87.58.150.62` | SESSION.md checklist item 2 |
| **Server** | `gpu-ubuntu-20cpu-256gb-fi-hel2` (UUID `00d832ec`), zone `fi-hel2` | data/infra_upcloud.ini |
| **Plan** | GPU-SPOT-20xCPU-256GB-3xL40S (3x L40S GPUs) | data/infra_upcloud.ini |
| **Remote workspace** | `/opt/kudbee/repo` on Ubuntu 24.04 + NVIDIA/CUDA | docs/guides/server-setup.md |
| **Services** | Nginx:80 (dashboard), Ollama:11434, model runtime:1919 | docs/guides/server-setup.md |
| **Model runtime** | `ft serve --host 0.0.0.0 --port 1919 --model <path>` | SESSION.md checklist item 6 |
| **Think Box** | openai_compat → `http://87.58.150.62:1919/v1` | SESSION.md checklist item 7 |
| **Models** | gpt-oss:20b, gpt-oss:120b on attached data disks | MEMORY.md |

### Why Think Box Is Not Using It

1. **Server STOPPED** — `data/infra_upcloud.ini` records `state_expected = stopped`, `power = human_only` (requires human authorization to start)
2. **SSH key absent** — Was on Kudbee's laptop (per MEMORY.md: "not ~/.ssh/kilo-upcloud", "path unknown until laptop"), never in this environment
3. **Network unreachable** — SSH to `87.58.148.168` and `87.58.150.62` both time out from this sandbox; ping fails; THINKBOXMD_REPORT.md confirms "SSH port is filtered from this sandbox"
4. **API token invalid** — `THINKBOX_UPCLOUD_API_TOKEN` returns HTTP 401; `UPCLOUD_API_MAIN` not set
5. **Cloudflare block** — `212.147.250.183` (old host `kudbee-host-v1`) behind Cloudflare 1003

### Permanent Known-Good Server Access Path

```
Kudbee laptop → SSH key (path: unknown, on laptop) → root@87.58.150.62
  → /opt/kudbee/repo → services running → Ollama (gpt-oss:20b, gpt-oss:120b)
  → model runtime :1919 → Think Box (openai_compat → http://87.58.150.62:1919/v1)
```

**To restore (requires HUMAN action):**
1. Start server from UpCloud panel (Kudbee authorization — `power = human_only`)
2. Retrieve SSH private key from Kudbee's laptop (NOT available in this environment, NOT `~/.ssh/kilo-upcloud`)
3. Place key on the machine running Think Box
4. `chmod 600 <KEY_PATH>`
5. `ssh -i <KEY_PATH> root@87.58.150.62` (floating IP, not Cloudflare-blocked)
6. Verify: `nvidia-smi` (GPU), `curl http://87.58.148.168` (dashboard)
7. Configure Think Box: `THINKBOX_DEFAULT_PROVIDER=openai_compat`, `THINKBOX_OPENAI_COMPAT_BASE_URL=http://87.58.150.62:1919/v1`

### Recovery Verification

| Check | Result | Details |
|-------|--------|---------|
| Connection path identified | CODE COMPLETE ✅ | Traced from SESSION.md, MEMORY.md, infra config |
| Path still works | NOT VERIFIED ⚠️ | SSH timeouts from sandbox, no key, server stopped |
| Origin accessible | NOT VERIFIED ⚠️ | Was Kudbee laptop, not this sandbox |
| Server reachable | NOT VERIFIED ⚠️ | Port 22 timeout, ping fail |
| Key available | NOT VERIFIED ⚠️ | On Kudbee laptop, not in this environment |
| GPU discovered | NOT VERIFIED ⚠️ | 3x L40S per config (not probed live) |
| Runtime/model discovered | NOT VERIFIED ⚠️ | gpt-oss:20b/120b per docs (not probed live) |
| Dashboard state | NOT VERIFIED ⚠️ | http://87.58.148.168 (not probed live) |

---

## 4-STATE WORK CLASSIFICATION (MANDATORY)

All work items are classified per AGENTS.md §14.7. **"COMPLETE" alone is never sufficient** — every item must state which of the four states applies.

### UpCloud ExecutionProvider — Current State

| Work Item | State | Evidence | Blocked By |
|-----------|-------|----------|------------|
| UpCloud provider implementation | CODE COMPLETE ✅ | Committed `32d82ef` + `a2335e2` | — |
| Security handling | TEST VERIFIED ✅ | 11 security findings PASS, 0 credential leaks | — |
| Unit tests | TEST VERIFIED ✅ | 33/33 pass, credential precedence verified | — |
| Dry-run mode | TEST VERIFIED ✅ | Mocked execution tested, plan() dry_run | — |
| Provider abstraction | TEST VERIFIED ✅ | Base class + registry tested | — |
| Live UpCloud authentication | NOT VERIFIED ⚠️ | All API probes HTTP 401 | No `UPCLOUD_API_MAIN` |
| Real UpCloud execution | NOT VERIFIED ⚠️ | Cannot execute without auth | Live auth NOT VERIFIED |
| Autonomous provisioning | BLOCKED ⚠️ | Depends on live verification | Live auth NOT VERIFIED |
| PR #68 review | CLOSED — not merged ⚠️ | PR closed without merge; work on kilo/leafy-dragon-4ck only | Founder decision: merge or discard |
| PRODUCTION READY | NOT REACHED ⚠️ | Requires all four states | Missing LIVE VERIFIED + review |

---

## RECENT CHANGES

### 2026-09-16 — Permanent Continuity Protocol

| Field | Value |
|---|---|
| **Date** | 2026-09-16 |
| **Agent/task** | Permanent agent governance protocol |
| **PR/commit** | `c7792b7` on `kilo/leafy-dragon-4ck`, PR #68 (CLOSED without merge) |
| **Result** | CONTINUITY.md created, AGENTS.md §14 added with 4-state classification mandate |
| **Tests/evidence** | 449 tests pass, no credential leaks, docstring coverage verified |
| **State** | CODE COMPLETE ✅ / TEST VERIFIED ✅ (PR closed without merge; content remains on branch) |

### 2026-09-16 — UpCloud ExecutionProvider Phase 2: Credential Precedence

| Field | Value |
|---|---|
| **Date** | 2026-09-16 |
| **Agent/task** | UpCloud credential priority update |
| **PR/commit** | `a2335e2` on `kilo/leafy-dragon-4ck` |
| **Result** | `UPCLOUD_API_MAIN` primary, `UPCLOUD_API_KEY` fallback, config override |
| **Tests/evidence** | 33 unit tests pass, 6 credential precedence scenarios verified programmatically |
| **State** | CODE COMPLETE ✅ / TEST VERIFIED ✅ |

### 2026-09-16 — UpCloud ExecutionProvider Phase 1: Abstraction + Provider

| Field | Value |
|---|---|
| **Date** | 2026-09-16 |
| **Agent/task** | UpCloud ExecutionProvider initial implementation |
| **PR/commit** | `32d82ef` on `kilo/leafy-dragon-4ck` |
| **Result** | ExecutionProvider base class, UpCloudExecutionProvider, evidence records, dry-run plan mode |
| **Tests/evidence** | 31 unit tests pass, live API audit (all 401), credential scan clean |
| **State** | CODE COMPLETE ✅ / TEST VERIFIED ✅ (superseded by Phase 2) |

### Pre-2026-09-16 — Prior work (see STATUS.md for full history)

| Work | Status |
|---|---|
| Phase 9 innovations (55 features) | COMPLETE |
| Phase 12 KUDBEE Control Fabric | COMPLETE |
| Disruptor + Verifier evaluation | COMPLETE (12/12 STRONG) |
| THINK Burst Protocol | COMPLETE |
| Harvest & Replay | COMPLETE |

---

## DECISIONS

### ADR 001: UpCloud ExecutionProvider

**Record:** `docs/decisions/001-upcloud-execution-provider.md`

**Key decisions:**
1. **Provider-agnostic core**: ExecutionProvider base class in `core/providers/`, no provider-specific code in Think Box core
2. **Honest capability reporting**: VERIFIED/DENIED/NOT_TESTED/REQUIRES_ADMIN_APPROVAL — never fake success
3. **No secrets in code/tests/docs**: Credentials from env vars only, evidence excludes secrets
4. **Dry-run plan mode**: `plan()` always dry_run; `execute()` requires `approve=True` for destructive/billable
5. **Evidence records**: Every action produces auditable record (no secrets)
6. **REST API over CLI**: `urllib` stdlib, not `upctl` (not installed)
7. **Credential precedence**: `UPCLOUD_API_MAIN` → `UPCLOUD_API_KEY` → config → none (ADDED 2026-09-16 Phase 2)

### ADR 002: Permanent Continuity Protocol

**Record:** This file (`docs/CONTINUITY.md`)

**Key decisions:**
1. **Canonical artifact**: `docs/CONTINUITY.md` — single source of truth for agent state
2. **Protocol in AGENTS.md**: Section 14 defines mandatory agent workflow rules
3. **Stale-work prevention**: Every agent reads STATUS.md and CONTINUITY.md before changes, leaves records after
4. **GitHub discipline**: IMPLEMENT → TEST → DOCUMENT → PR/ISSUE → VERIFY → CLOSE

---

## OPEN LOOPS

| # | Item | Owner/Agent | State | Next Action | Blocking Dependency |
|---|---|---|---|---|---|
| 1 | UpCloud live capability verification | Any agent | CODE COMPLETE / LIVE VERIFIED NOT REACHED | Set `UPCLOUD_API_MAIN` env var, run `tests/integration/test_upcloud_live.py` | Valid API token from UpCloud panel |
| 2 | UpCloud autonomous provisioning | Any agent | BLOCKED | Complete live verification (item 1), then wire into runtime | Live capabilities LIVE VERIFIED |
| 3 | Merge credential precedence into main | Any agent | ACTIVE | Cherry-pick `a2335e2` onto origin/main (4 code files apply cleanly, 2 doc files need trivial `git add`) | Developer/Founder decision |
| 4 | UpCloud provider on main lacks credential precedence | Any agent | ACTIVE | Main's `core/providers/upcloud.py` uses only `UPCLOUD_API_KEY` — needs update from kilo/leafy-dragon-4ck | Item 3 |

## CLOSED LOOPS

### UpCloud ExecutionProvider Phase 1
- **Implementation**: `core/providers/execution.py`, `core/providers/upcloud.py`
- **State**: CODE COMPLETE ✅ / TEST VERIFIED ✅
- **Verification**: 33/33 unit tests pass, live API audit (all DENIED/401), credential scan clean
- **Evidence**: `tests/unit/test_upcloud_provider.py`, `tests/integration/test_upcloud_live.py`, `docs/upcloud-provider.md`
- **PR/Commit**: `32d82ef` on `kilo/leafy-dragon-4ck`
- **Closure**: Superseded by Phase 2 credential update; code NOT merged into main

### Permanent Continuity Protocol
- **Implementation**: `docs/CONTINUITY.md`, `AGENTS.md` §14
- **State**: CODE COMPLETE ✅ / TEST VERIFIED ✅
- **Verification**: 449 tests pass, no credential leaks, docstring coverage verified, all required CONTINUITY.md sections present, 4-state classification mandated
- **Evidence**: `tests/unit/test_upcloud_provider.py` (33 tests), `tests/integration/test_upcloud_live.py` (5 skipped), credential precedence verification
- **PR/Commit**: `c7792b7` on `kilo/leafy-dragon-4ck`, PR #68 (CLOSED without merge; content on branch)
- **Closure**: CODE COMPLETE ✅ / TEST VERIFIED ✅ (PR closed without merge; protocol content remains on kilo/leafy-dragon-4ck)

### UpCloud ExecutionProvider Phase 2: Credential Precedence
- **Implementation**: Updated `core/providers/upcloud.py` credential resolution
- **State**: CODE COMPLETE ✅ / TEST VERIFIED ✅
- **Verification**: 33/33 unit tests pass, 6 credential precedence scenarios verified, credential scan clean
- **Evidence**: `tests/unit/test_upcloud_provider.py` (33 tests), credential precedence verification script
- **PR/Commit**: `a2335e2` on `kilo/leafy-dragon-4ck` (HEAD is now `c35ea5b`)
- **Closure**: CODE COMPLETE ✅ / TEST VERIFIED ✅; NOT on main; main's version lacks credential precedence

### health_check() Attempt (REVERTED)
- **Attempt**: Added `health_check()` method to `core/providers/execution.py`
- **State**: REVERTED — never committed
- **Reason**: System reminder redirected to PR/documentation audit; no code change made
- **Evidence**: `git checkout -- core/providers/execution.py`; working tree clean

### Full Test Suite
- **Implementation**: N/A (regression)
- **Verification**: 449 tests pass, 6 skipped (pre-existing live tests requiring credentials)
- **Evidence**: `python3 -m unittest discover tests/` → OK
- **PR/Commit**: Included in `a2335e2`
- **Closure**: COMPLETE

---

## INFRASTRUCTURE

### UpCloud Infrastructure

| Field | Value |
|---|---|
| **Current server** | `gpu-ubuntu-20cpu-256gb-fi-hel2` (UUID `00d832ec-8565-447b-86ac-74bf9bd41e57`) |
| **Current server IP** | `87.58.148.168` (public_nic) / `87.58.150.62` (floating_ip) |
| **Previous server** | `kudbee-host-v1` at `212.147.250.183` (Cloudflare 1003 blocked) |
| **Plan** | GPU-SPOT-20xCPU-256GB-3xL40S (3x L40S GPUs) |
| **Zone** | fi-hel2 (Finland Helsinki) |
| **Template** | Ubuntu 24.04 + NVIDIA/CUDA |
| **SSH user** | `root` |
| **SSH key path** | `~/.ssh/kilo-upcloud` (ed25519, committed `5f6a5c7`, removed `09830a6`) |
| **SSH command** | `ssh -i ~/.ssh/kilo-upcloud root@87.58.148.168` |
| **Dashboard** | http://87.58.148.168 |
| **Cloudflare Tunnel** | `api.thinkboxai.xyz` (via `deploy/setup_tunnel.sh`) |
| **Server state** | STOPPED (requires human authorization — `power = human_only`) |
| **Primary credential** | `THINKBOX_UPCLOUD_API_TOKEN` (returns 401) |
| **Credential detected** | **NO** (neither `UPCLOUD_API_MAIN` nor `THINKBOX_UPCLOUD_API_TOKEN` set) |
| **SSH key available** | **NO** (file absent from all locations) |
| **CLI Tool** | upctl — NOT AVAILABLE (PyPI `upctl` v0.1.0 is a project stack detector, NOT UpCloud infrastructure CLI; package uninstalled). No Go runtime to build official binary. Resolution requires HUMAN action. |
| **Provider Implementation** | REST API via `urllib` (stdlib) — `core/providers/upcloud.py` |
| **Live API Reachable** | YES (HTTP 401) |
| **Read Capabilities** | ALL DENIED (no credentials) |
| **Mutation Capabilities** | NOT TESTED (requires approval + credentials) |
| **SSH from sandbox** | **BLOCKED** (port 22 timeout, ping fail, firewall filtered per THINKBOXMD_REPORT.md) |
| **UpCloud Provider State** | CODE COMPLETE ✅ / LIVE VERIFIED NOT REACHED ⚠️ |
| **Server Connection Recovery** | CODE COMPLETE ✅ / LIVE VERIFIED NOT REACHED ⚠️ |
| **Verification Status** | CREDENTIALS NEEDED — cannot upgrade to TEST VERIFIED/LIVE VERIFIED |

### Other Infrastructure

| Service | Status | Notes |
|---|---|---|
| Inception Mercury 2 | ✅ Live | `INCEPTION_API_KEY` set, `api.inceptionlabs.ai/v1` working |
| Upstash Vector | ⚠️ Partial | Reachable, writes rejected (dense index + no embedder) |
| Upstash Box | ❌ Dead | Preview `not found` |
| UpCloud | ❌ No access | No credentials, API 401 |
| OpenAI-compatible | ⚠️ Needs key | Implementation exists, needs key |
| Anthropic | ❌ Not implemented | No provider file |
| Ollama | ❌ Not installed | Local only |
| Groq | ⚠️ Needs key | Reachable |

### Active Branches

| Branch | Ahead of Origin | Status | Notes |
|---|---|---|---|
| `kilo/leafy-dragon-4ck` | 10 commits | ACTIVE | UpCloud provider + credential precedence; PR #68 CLOSED without merge; work NOT on main; main has older UpCloud provider |

### Stale/Parked Branches (require review before cleanup)

| Branch | Origin SHA | Local? | Merged to main? | Content | Recommendation |
|---|---|---|---|---|---|
| `session/agent_79e656bf-clean` | b99c58c | NO | NO | SESSION.md update only (15+/-2 lines) | LOW RISK — trivial doc change; safe to close after verifying content on main |
| `session/agent_79e656bf-37c6-46f2-833e-1eb027b99152` | ccd4ac9 | NO | NO | AGENTS.md update only (16+/-1 lines) | LOW RISK — trivial doc change; safe to close after verifying content on main |

### Other Observed Branches (not audited — exist on origin)

`session/agent_370e6239-*`, `session/agent_53455b5f-*`, `session/agent_5475066e-*`, `session/agent_7af7e70e-*`, `session/agent_926d99f0-*`, `session/agent_d8a04fb5-*`, plus numerous `convoy/*`, `cursor/*`, `kilo/*` branches. Not audited — requires separate investigation if needed.

No parked branches identified beyond the two session branches above.

---

## SECURITY

### Credential Policy

- **Primary**: `UPCLOUD_API_MAIN` — checked first
- **Fallback**: `UPCLOUD_API_KEY` — checked second (backwards compatible)
- **Config override**: `config["api_key"]` — checked third
- **None**: No credentials → read-only / no auth
- **Never**: Print, log, store, serialize, or commit credential values

### Security Findings (Current Session)

| Finding | Severity | Status |
|---|---|---|
| No tokens in source files | — | PASS |
| No tokens in test files | — | PASS |
| No tokens in documentation | — | PASS |
| Hardcoded `UPCLOUD_API_MAIN=` values | — | PASS |
| No hardcoded credential values in any file | — | PASS |
| Credential in evidence records | — | PASS (never stored) |
| Credential in logs | — | PASS (never logged) |
| Credential in plan output | — | PASS (never included) |
| Env var values exposed | — | PASS (only presence checked) |
| Cross-layer import violations in providers | — | PASS |
| Print statements leaking credentials | — | PASS (none found) |

---

## GITHUB DISCIPLINE

### PR Audit (2026-09-17)

All 5 audited PRs are CLOSED. None merged via GitHub.

| PR | Title | Author | Head Branch | State | Merged | Notes |
|---|---|---|---|---|---|---|
| #68 | chore(continuity): permanent agent protocol + CONTINUITY.md | app/kilo-code-bot | kilo/leafy-dragon-4ck (f132934) | CLOSED | NO | Head was 2 commits behind current HEAD (d961ba9); 2 more commits added after PR closed; continuity protocol content remains on branch |
| #67 | fix(upstash): embedder + vector upsert fail closed | app/kilo-code-bot | convoy/compute-fabric-foundation-secrets-abstra/74f72471/head | CLOSED | NO | mergeStateStatus=DIRTY; mergeCommit=null |
| #65 | docs(agents): AGENTS.md as single source of truth | Kudbee | cursor/agents-md-update-4de1 | CLOSED | NO | mergeCommit=null |
| #32 | fix(roadmap): correct Stage 0 accuracy issues | app/kilo-code-bot | convoy/10-improvements-roadmap-update/fb526512/gt/maple/3cf40fcd | CLOSED | NO | mergeStateStatus=DIRTY; 19+ days old; work may be superseded by convoy roadmap merge (PR #31) |
| #28 | fix(providers): rewrite OllamaProvider | app/kilo-code-bot | gt/maple/813b602a | CLOSED | NO | mergeStateStatus=DIRTY; work superseded by origin/gt/maple/813b602a which is already merged into main |

### PR Decision Log

- **#68**: CLOSED without merge. Continuity protocol content exists on `kilo/leafy-dragon-4ck`. Credential precedence update (`a2335e2`) NOT on main. Recommend: merge credential precedence update into main or reopen.
- **#67**: CLOSED without merge. Upstash embedder fail-closed work. Check if content exists in `feat/upstash-vector-embedder` (merged into main).
- **#65**: CLOSED without merge. AGENTS.md documentation update. Content may be subsumed by subsequent AGENTS.md edits.
- **#32**: CLOSED without merge (DIRTY). Roadmap accuracy fix. May be superseded by PR #31 (convoy roadmap merge into main). Verify before reopening.
- **#28**: CLOSED without merge (DIRTY). OllamaProvider rewrite. Check if content exists in `origin/gt/maple/813b602a` (which IS merged into main via the convoy post-review-feedback integration).

### PR Description Template (for meaningful work)

```
## WHAT CHANGED
<Describe the implementation changes>

## WHY
<Explain the problem being solved and the decision rationale>

## EVIDENCE
<Test results, API probes, audit findings>

## TESTS
<Test count, pass rate, coverage>

## LIMITATIONS
<Known constraints, dependencies, blockers>

## NEXT LARGER IMPROVEMENT
<What comes after this work>
```

---

## CONTINUITY PROTOCOL

### Permanent Agent Rules (see AGENTS.md §14)

1. **READ** the current continuity status artifact BEFORE making changes
2. **IDENTIFY** current active work, blocked work, recently completed work, next larger improvement
3. **BEFORE FINISHING**, leave a durable record of what was discovered or changed
4. **Every meaningful implementation** must be associated with a GitHub PR or documented issue/continuity record
5. **If work is complete**, MUST close the PR/issue when appropriate
6. **If work is incomplete**, MUST explicitly mark: ACTIVE / BLOCKED / PARKED / NEEDS HUMAN / COMPLETE
7. **NEVER** leave "in progress" work without a next action
8. **NEVER** create duplicate rediscovery work when an existing record documents state
9. **NEVER** claim something is verified unless evidence exists
10. **NEVER** use "COMPLETE" alone to mean verified — always pair with 4-state classification (see AGENTS.md §14.7)
11. **NEVER** silently discard a discovery, failed experiment, architectural decision, security finding, or important limitation

### Agent Session Checklist

```
Before making any change:
  ☐ Read STATUS.md
  ☐ Read docs/CONTINUITY.md
  ☐ Check git state (branch, working tree, last commits)
  ☐ Run tests to establish baseline

During work:
  ☐ Document decisions in docs/decisions/NNN-*.md
  ☐ Write tests before implementation (TDD)
  ☐ Update this CONTINUITY.md with recent changes

Before finishing:
  ☐ Run full test suite
  ☐ Verify no credential exposure
  ☐ Update STATUS.md or CONTINUITY.md
  ☐ Commit with conventional message
  ☐ Push and create/update PR
  ☐ Update this CONTINUITY.md with results

After finishing:
  ☐ Verify no stale open loops created
  ☐ Document next larger improvement
  ☐ Close PR/issue if work is complete
```

---

## HOW FUTURE AGENTS DISCOVER THIS

1. **AGENTS.md §14** mandates reading CONTINUITY.md before any work
2. **STATUS.md** provides current project state summary
3. **docs/CONTINUITY.md** provides the canonical, detailed state
4. **docs/decisions/** contains all architectural decision records
5. **Git log** provides commit history and authorship trace
6. **GitHub PRs** provide review history and approval state

**The repository is the memory. No agent may assume the next agent knows what it knows.**
