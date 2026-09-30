# Enterprise Agent OS — Baseline (four-state)

**As of:** `main` @ `71027021` (2026-09-30). **Status:** Proposed, part of the enterprise plan in [`README.md`](README.md).

This is an honest accounting of what exists today. It uses the repo's four-state convention
(AGENTS.md): **CODE COMPLETE** (implemented) / **TEST VERIFIED** (automated tests pass) /
**LIVE VERIFIED** (proven against a real browser, server or host) / **PRODUCTION READY** (deployable
and signed off). Cells are `yes`, `partial`, `no`, `UNPROVEN` (no evidence found either way) or `n/a`.
Nothing here is a claim of "COMPLETE" without a state. Every row cites its evidence below the table.

## Summary

| # | Component | CODE | TEST | LIVE | PROD |
|---|---|---|---|---|---|
| 1 | Dashboard (`apps/web`) | yes | partial | yes (loopback only) | no |
| 2 | Identity and authentication | partial | UNPROVEN | partial | no |
| 3 | Governed backend (FastAPI `/api/v1/run`) | yes | yes (CI UNPROVEN) | yes (loopback) | no |
| 4 | Admission gate, governance tokens, identity ledger | yes | yes | yes (dashboard to worker path) | no |
| 5 | `remote_exec_policy` | yes | yes | yes | no |
| 6 | `upcloud-ssh` substrate / worker-02 | yes | yes | yes (2026-09-29) | no |
| 7 | Receipts and action ledger | yes | yes | yes (worker-02 run) | no |
| 8 | Audit logging | partial | UNPROVEN | no | no |
| 9 | Memory (Markdown + index, SQLite stores) | yes | yes | partial | no |
| 10 | Model routing | yes | yes | partial | no |
| 11 | MCP registry / skills | partial | yes | partial (fallback only) | no |
| 12 | Git panel (#289) | yes | yes (real server) | no | no |
| 13 | Think Token (#288) | partial (unwired) | partial | no (simulated) | no |
| 14 | CI | yes (workflows exist) | n/a | partial | no |
| 15 | Upstash Box substrate | yes (adapter) | yes (hermetic gate) | no (NOT_CONFIGURED) | no |
| 16 | Secrets and key hygiene | n/a | n/a | no (private key exposed in public history) | no |
| 17 | Deployment, HTTPS, backups | partial (config files) | no | no | no |

## Measurements taken for this baseline (2026-09-30)

| Check | Command | Result |
|---|---|---|
| Web suite on `main` | `cd apps/web && node --experimental-strip-types --no-warnings --test --test-timeout=30000 --test-reporter=spec "tests/*.test.ts"` | 173 tests, 172 pass, 1 cancelled (the `update_config` test hangs), 35.7 s. Plain `npm test` never finishes on `main` because of that hang. PR #302 fixes it (178/178). |
| Web typecheck | `cd apps/web && npm run typecheck` | 12 errors in 5 files, all pre-existing. PR #300 fixes them. |
| Hermetic proof | `python3 scripts/prove_think_box_local.py --provider mock` | 6/6 PASS (model reachable, governed answer, no-token denied, forged token denied, ledger verified, tamper detected). Local artifact sha256 `8ed45978a9d3163b6d0464b88bf563b6fbc9a51982a387a98cd9deb3ef6d9e25`; `data/proofs/` is gitignored, so it is not committed. |
| Upstash Box access | `python3 scripts/upstash_box_access_probe.py` | `ENV_NOT_CONFIGURED` (classification A): the required `UPSTASH_PUBLIC_BOX_URL` and `UPSTASH_PUBLIC_BOX_TOKEN` are absent. No network call was made. |
| CI on open PRs | `gh pr checks <n>` | CodeQL and Bugbot pass; `web-typecheck` fails on the 12 errors above; the Python `unit-and-integration` job runs for hours and was never observed finishing. |

No UpCloud host, Upstash service or model provider was contacted for this baseline. Anything that
would have needed that is marked UNPROVEN rather than assumed.

## Evidence by component

### 1. Dashboard (`apps/web`)
- **CODE yes:** Express + WebSocket server (`server.ts`), ten header panels, terminal, tasks, memory, files, metrics.
- **TEST partial:** 172 of 173 pass on `main` (see measurements); the failure is a real bug, not flakiness (`update_config` never called `sanitizeConfigPatch`). Open fixes: #302 (validation + bounded runtime), #298 (terminal did not scroll), #300 (12 type errors).
- **LIVE yes, loopback only:** headless Chrome at 1440, 1024 and 390 px with 0 console errors (AGENTS.md, dashboard polish entry; `STATUS.md`). Re-checked 2026-09-30; that pass found the terminal-scroll bug fixed in #298.
- **PROD no:** local-only by design (the server refuses a non-loopback bind and non-loopback `Host`/`Origin`), no login, no HTTPS, sessions held in memory in one process. Unvalidated input remains on `state_save` (client `panelState`/`viewState` persisted as-is) and `run_goal` (client `model` and `routeTelemetry` passed through).

### 2. Identity and authentication
- **CODE partial:** there are no users, roles or sessions. The dashboard login was built in #286 and **removed in #289** (`82165813` deleted `apps/web/auth.ts`, `scripts/hash-password.ts`, `tests/auth.test.ts`) because the dashboard was declared a local-only operator console. The backend authenticates with shared secrets only: `THINKBOX_API_KEY`/`THINKBOX_API_KEYS` (a set of keys with no per-key identity, `backend/security.py`) and one shared bearer for the control plane (`THINKBOX_CONTROL_PLANE_TOKEN`; fail-closed 503 when unset, dev token only with an explicit opt-in; compared with `!=`, not constant time).
- **TEST UNPROVEN:** not audited for this baseline; the governed-bridge tests cover the API-key hop.
- **LIVE partial:** the shared API-key hop web to backend was live in #284.
- **PROD no:** a single fixed governance identity (`web-dashboard-agent`) stands in for every human.

### 3. Governed backend (FastAPI)
- **CODE yes:** `POST /api/v1/run`, job status, resume/reclaim, receipts, admission-token endpoint (`backend/api/v1/`).
- **TEST yes, CI UNPROVEN:** a local broad Python regression of 104 modules passed 1861 tests (1 skipped, 3 expected failures) on 2026-09-29 (`docs/CONTINUITY.md`). The CI `unit-and-integration` job has not been seen to finish.
- **LIVE yes (loopback):** run/resume/reclaim through the real backend over HTTP to the real worker (`STATUS.md`).
- **PROD no:** SQLite only, in-memory governance state (row 4), no deploy target.

### 4. Admission gate, governance tokens, identity ledger
- **CODE yes:** `AdmissionGate` requires the capability in both the token and the identity (`token_capability_not_granted`, #286).
- **TEST yes:** hermetic proof 6/6 (no token and forged token denied).
- **LIVE yes:** dashboard to worker path (#284, #286).
- **PROD no:** `GovernanceTokenService` keeps tokens in a process-memory dict and `IdentityLedger` keeps identities in a process-memory dict, so both are lost on restart. `verify()` is a dict lookup; the embedded HMAC signature is never re-checked, so it is decorative. The signing key falls back to a hardcoded default when `THINKBOX_GOVERNANCE_SIGNING_KEY` is unset (`backend/api/v1/run_governed.py`, `get_api_run_governance`). TTL for web tokens is 300 s.

### 5. `remote_exec_policy`
- **CODE/TEST/LIVE yes:** policy `upcloud-ssh-readonly` v1 (`thinkbox/remote_exec_policy.py`): the capability `shell:upcloud-ssh:readonly` authorizes only the `upcloud-ssh` substrate, and only the exact commands `hostname`, `uname -a`, `uptime`, `whoami`, `df -h /`, `free -m`. Enforced again in run, resume and reclaim. Live against worker-02.
- **PROD no:** the policy is a code constant with no versioned store or change control; there is exactly one policy.

### 6. `upcloud-ssh` substrate / worker-02
- **CODE/TEST/LIVE yes:** governed `hostname` executed on worker-02 (`209.50.51.174`), exit 0, receipt and artifact hash recorded (AGENTS.md and `docs/CONTINUITY.md`, 2026-09-29).
- **PROD no:** SSH user defaults to `root` (`UPCLOUD_SSH_USER`), host keys use `StrictHostKeyChecking=accept-new` (trust on first use, not pinned; `thinkbox/cloud_execution/providers/ssh_remote.py`), no SSH-only firewall (open founder decision), an orphan duplicate server exists and worker-01 (account `kudbee`) has no key. Not contacted for this baseline; last live check 2026-09-29.

### 7. Receipts and action ledger
- **CODE yes:** `ActionLedger` is a SQLite hash chain (`prev_hash`/`entry_hash`, sha256 truncated to 32 hex chars) with `verify()`; HTTP-run receipts persist to `data/thinkboxmd/db/http_run_experiments.db` plus an artifacts directory.
- **TEST yes:** proof shows a tamper is detected.
- **LIVE yes:** receipt for a real worker-02 run.
- **PROD no:** the chain is **not signed** (anyone with write access to the database can recompute it), there is no external anchor and no export format, and the ledger defaults to `:memory:` unless a path is configured.

### 8. Audit logging
- **CODE partial:** the dashboard's "audit log" (`Enterprise.auditLog` in `public/js/enterprise.js`) is browser `localStorage` and can be cleared from the UI, so it is **not an audit trail**. The Python backend has `backend/audit_storage.py` (SQLite, `data/audit.db`, gitignored). The web server records no audit events.
- **TEST UNPROVEN / LIVE no / PROD no.**

### 9. Memory
- **CODE yes:** web memory is Markdown files in task/org/verified layers with an Upstash sparse-vector index or an in-process BM25 fallback (`apps/web/memory.ts`); SQLite backs dashboard state and token stats (`persistence.ts`); run history is a single JSON file (AGENTS.md open items). Python memory layers are separate (`thinkbox/memory_layers.py`).
- **TEST yes:** `memory.test.ts` and `memory-restart-e2e.test.ts` pass.
- **LIVE partial:** the Upstash index was live in a 2026-09-27 run, but the dashboard showed "Vector offline" on 2026-09-30, so current Upstash reachability is UNPROVEN.
- **PROD no:** lexical search only, global (not tenant-scoped), single process.

### 10. Model routing
- **CODE yes:** Mercury-2 through Inception and local Ollama; token-aware routing is decided **client-side** (`selectModelForGoal` in `cli.ts`), and the server records the client's `routeTelemetry` (`route_reason`, `tokens_saved_est`) unvalidated.
- **TEST yes:** `token-routing.test.ts`, `token-stats-integration.test.ts`.
- **LIVE partial:** a real Mercury-2 run completed on 2026-09-27; the local route needs `ollama pull qwen2.5:1.5b` and is UNPROVEN now.
- **PROD no:** savings figures are client-asserted; no per-tenant budget (there is a global `KUDBEE_DAILY_BUDGET_USD`).

### 11. MCP registry / skills
- **CODE partial:** `apps/web/mcp-registry.ts` fetches `anthropics/mcp-servers` from the GitHub API, which returns 404, so it falls back to six hardcoded servers (AGENTS.md, 2026-09-28). The Neon skills bundle was removed in #301 (ADR 026); the repo has no runtime skills system.
- **TEST yes:** `mcp-registry.test.ts`. **LIVE partial:** fallback path only. **PROD no.**

### 12. Git panel (#289)
- **CODE yes, TEST yes (real server), LIVE no (not browser-tested), PROD no** (`STATUS.md`). Clones public https repos only; input is validated; operator clone/write actions need approval.

### 13. Think Token (#288)
- **CODE partial:** the classes, store, factory, propagator and panel exist, but **nothing in `server.ts` or `agent.ts` imports them**; `ServerLearningIntegration` and the `create*` factories have no callers. AGENTS.md section 1.3a describes integration points (constructor, `runGoal()`, dashboard) that are not wired. Also, `new LearningStore()` creates `apps/web/learning.db` as a side effect and that path is not gitignored.
- **TEST partial:** #300 adds 3 tests for one path; 12 type errors sit in this code on `main` until #300 merges.
- **LIVE no:** the Learning panel **simulates** events ("Emit mock events for demo", `think-token-dashboard.js`); evidence label `simulated`. **PROD no.**

### 14. CI
- **CODE yes:** `.github/workflows/test.yml` with `unit-and-integration` (Python, about 29 sequential steps, no `timeout-minutes` so GitHub's 360-minute default applies) and `web-typecheck` (typecheck, then `npm test`); CodeQL; Cursor Bugbot.
- **LIVE partial:** the billing lock lifted on 2026-09-30 and jobs now run; only CodeQL and Bugbot are green. `web-typecheck` is red on 12 type errors and, once typecheck passes, would hang in `npm test` (the `update_config` test) with no timeout. No required check can go green today.
- **PROD no.**

### 15. Upstash Box substrate
- **CODE/TEST yes:** adapter plus hermetic gate #201. **LIVE no:** `ENV_NOT_CONFIGURED` (measured above); AGENTS.md records #201 as "not LIVE VERIFIED". **PROD no.**

### 16. Secrets and key hygiene
- **LIVE no, PROD no. A private key is exposed in public history right now.**
  - **What the record says.** `INCIDENT_RESPONSE_2026-09-28.md` (repo root) states the history purge was **completed**: `git filter-branch` over 2,135 commits, force-pushed to `origin/main` on 2026-09-28 04:48 UTC, `.env` fixed to mode 600. It lists key rotation as **pending**: the boxes for `INCEPTION_API_KEY`, `UPSTASH_VECTOR_REST_TOKEN` and `CURSOR_API_KEY` are unchecked, and no revocation of the UpCloud key is recorded as done. `FORCE_PUSH_READY.md` is the earlier "ready to push" note and is stale.
  - **What the repository shows (2026-09-30).** Commit `c62e50d1` (2026-09-17, "docs: add Phase 1-6 UpCloud investigation results") adds two files, `kilo-upcloud-recovered` and `kilo-upcloud-recovered.pub`. It **is an ancestor of `origin/main`** (2,237 commits, not the rewritten history the incident record describes) and is reachable from **171 refs**. Checked without printing contents: the first file is 419 bytes and contains `PRIVATE KEY` header lines; the second is one ED25519 public-key line, fingerprint `SHA256:makvGnTYVYSackBcxfGD/QGCV/rLvryYpWy39HK/1GQ`. The repository visibility is **PUBLIC**. The path is absent from the current tree (`HEAD`), which is why the incident record's `git ls-tree -r HEAD` check passes.
  - **Reading.** Either the purge was later overwritten or it never covered what is on `origin/main` today. A history rewrite cannot un-publish a key that may already be cloned, so the key must be treated as compromised regardless. Whether it was revoked on UpCloud and removed from every server's `authorized_keys` is **UNPROVEN**. The fingerprint above lets you check (`ssh-keygen -lf` on each `authorized_keys`). No UpCloud host was contacted.
  - **Also open here:** API-key rotation (above), 39 Dependabot alerts on the default branch (19 high, 19 moderate, 1 low), and `docs/known-defects.md` is stale (dated 2026-09-19). Local `.env` is mode 600.

### 17. Deployment, HTTPS, backups
- **CODE partial:** `deploy/nginx.conf` has a TLS 1.2/1.3 server and an 80-to-443 redirect; `deploy/Caddyfile` has `auto_https off`; `docs/guides/deployment.md` and `docker_enterprise.md` exist. **TEST no, LIVE no, PROD no:** nothing is deployed (`STATUS.md`) and no backup procedure was found.
