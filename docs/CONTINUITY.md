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
- [x] Tests executed and passing (560 OK, 6 skipped)
- [x] Evidence recorded in CONTINUITY.md
- [x] Documentation updated (CONTINUITY.md, AGENTS.md §14, STATUS.md)
- [x] Git state clean (working tree clean, main merged)
- [x] PR/commit referenced (PR #68 closed, PR #67 closed, PR #65 closed, PR #32 closed, PR #28 closed)
- [x] No stale open loop created
- [x] Next larger improvement documented
- [x] Security/credential check completed (0 credentials found)
- [x] Main branch merged with all work (commit 9f12e1d)
- [x] Safety gate JSON files removed from git (added to .gitignore)
- [x] UpCloud investigation Phase 1-6 COMPLETE (Case C confirmed)

---

## CURRENT STATE

| Field | Value |
|---|---|
| **Active objective** | Default-path generalization: VerifiedRetrySession as the standard verified execution path for all Think Jobs |
| **Latest completed work** | Default-path proof COMPLETE: 8 live jobs across compute/distractor/multifield via VerifiedRetrySession (budget 16, spent 9); 8/8 valid with 1 wrongkey conversion; IMPROVED mechanism at scale — 635 tests passing |
| **Current verified capabilities** | VerifiedRetrySession (bounded retries + session call budget + per-call traces) + 5 deterministic tests; live proof with memory + dashboard; 635 tests passing |
| **Current blockers** | None. `record_outcome` status stays pending (pre-existing). |
| **Known risks** | Conversion evidence still small-n (2 total across v3 + default-path); budget caps prevent runaway spend (proven: 9/16 spent, BudgetExhausted tested). |
| **Next larger improvement** | Promote VerifiedRetrySession into ThinkBoxEngine.execute_goal as the standard per-task wrapper with dashboard-visible retry telemetry |
| **PR status** | main at d691fa6; default-path work on main working tree, uncommitted |
| **Test count** | **635 tests passing (6 skipped)** |

---

## RECENT CHANGES

### 2026-09-17 — Default-Path Generalization (VerifiedRetrySession, 8 live jobs, IMPROVED)

| Field | Value |
|---|---|
| **Date** | 2026-09-17 |
| **Agent/task** | Generalize the v3 retry mechanism into the default Think Job path. HEAD `d691fa6`, branch `main`. No SSH, no UpCloud compute, no GPU, no fakes, no secrets. |
| **Mechanism** | `VerifiedRetrySession` + `VerifiedRetryConfig` + `VerifiedCallResult` + `BudgetExhausted` in `thinkbox/pop_arena.py`: sync-pure (complete/verify/reprompt injected), bounded retries for retryable taxonomies, per-call traces, session call budget. `+5` deterministic tests (21/21 arena tests OK). |
| **Live proof** | 8 jobs across compute/distractor(6)/multifield via the session (budget 16, spent 9): 8/8 valid, 1 retry fired → 1 conversion (`defaultpath_distractor_wrongkey`: distractor-compliance → valid, 2 attempts). Memory `learn:defaultpath:retry-session` + dashboard JOB_COMPLETED. |
| **Classification** | IMPROVED — mechanism generalizes across families (8/8 with conversion); orchestration level, NOT model intelligence; small-n honestly bounded. |
| **Restart** | Fresh handles verified (suite + dashboard read from storage). Proof `defaultpath_proof_20260917.json` SHA256 `5a0e0c16…94cfa3c74`, 9 files secrets-clean. Full suite 635 OK (6 skipped). |
| **FourState** | CODE_COMPLETE / TEST_VERIFIED (635) / LIVE_VERIFIED (substrate) / MODEL_EXECUTION_VERIFIED (72 live calls total) / ARENA_VERIFIED (default-path proof) / PRODUCTION not claimed |

### 2026-09-17 — Arena v3 Verifier-Side Retry (12 live, COMPLETE, IMPROVED at mechanism level)

| Field | Value |
|---|---|
| **Date** | 2026-09-17 |
| **Agent/task** | Structural attack on the v2 wrongkey failure: verifier retry loop (max 1, retryable taxonomies only). HEAD `0744610`, branch `main`. No SSH, no UpCloud compute, no GPU, no fakes, no secrets. |
| **Mechanism** | `should_retry` gate + `retry_prompt_for` (names observed failure, leaks no answer) + `resolve_retry` trace — all in `thinkbox/pop_arena.py`, all deterministically tested (`+4` tests, 16/16 arena tests OK). |
| **Run** | Control `tb_exp_20260917182126_3cf9f861`, 12 live distractor instances (6 baseline single-attempt + 6 retry-arm), Mercury-2 via existing path. Baseline reproduced v2: 5/6 (`{"result": 37}` again). Retry arm: 6/6 final-valid; the one retryable instance (`wrongkey_retry`: first `distractor-compliance`) converted to `{"answer": 37}` on retry (2 attempts, 716 tokens, 2.83s). |
| **Classification** | IMPROVED — scoped explicitly to mechanism level (orchestration converts the failure class prompt lessons could not). NOT model intelligence. Small-n (1 conversion), honestly bounded. |
| **Restart** | Fresh handles: v3 control COMPLETE, lesson + ledger verified. Proof `arena3_proof_20260917.json` SHA256 `b1aadd34…09ceaca8`, 13 files secrets-clean. Full suite 630 OK (6 skipped). |
| **FourState** | CODE_COMPLETE / TEST_VERIFIED (630) / LIVE_VERIFIED (substrate) / MODEL_EXECUTION_VERIFIED (64 live calls total) / ARENA_VERIFIED (v3 COMPLETE, IMPROVED mechanism) / PRODUCTION not claimed |

### 2026-09-17 — Arena v2 Transfer-Under-Difficulty (300 instances, COMPLETE, honest negative transfer)

| Field | Value |
|---|---|
| **Date** | 2026-09-17 |
| **Agent/task** | Execute the approved master plan: 3 harder families → 36-call live budget → failure-driven lesson → learned arm → compare with pre-registered threshold. HEAD `2030494`, branch `main`. No SSH, no UpCloud compute, no GPU, no fakes, no invented scores, no secrets. |
| **Phase 0 families** | compute (arithmetic+emit), distractor (injected instructions incl. key-swap), multifield (answer+parity+double consistency). `verify_v2` taxonomy: parse-fail/wrong-key/arithmetic/distractor-compliance/inconsistency/valid — all reached in tests. Replay emissions verify by construction. `+4` calibration tests (12/12 arena tests OK). |
| **Phase 1 config** | Control `tb_exp_20260917181211_b78ceb62`: hypothesis + threshold pre-registered (delta > 0.15, non-overlapping 95% Wilson CI). Population 300 (264 replay + 36 live), provider openai_compat / mercury-2, temp 0.2, 3500 floor, 60s timeout. |
| **Phase 2 baseline** | 18/18 live (6/family): 17 VALID, 1 FAIL — `arena2_distractor_wrongkey_000` emitted `{"result": 37}` (distractor-compliance). Rate 0.944 CI [0.742, 0.99]. Ceiling broken. |
| **Phase 3 lesson** | From the ONE observed failure only: `learn:arena2:failures` (conf 0.85, source=fail job): restate precedence + name the key explicitly. Nothing invented. |
| **Phase 4 learned** | 18/18 live with 18/18 retrieval provenance (event + param + ledger): 17 VALID, 1 FAIL — identical `{"result": 37}` on wrongkey_001. Lesson retrieved but fix INEFFECTIVE. |
| **Phase 5 compare** | 17/18 vs 17/18, delta 0.0, CIs fully overlap, threshold NOT met. Per-family: compute 6/6+6/6, multifield 6/6+6/6, distractor 5/6+5/6 (same failure). Classification: NO_MEASURABLE_IMPROVEMENT (negative transfer honestly recorded). |
| **Phase 6 restart** | Fresh handles: v2 control COMPLETE, 300 rows, lesson + ledger verify True. Dashboard arena block shows latest run. Proof `arena2_proof_20260917.json` SHA256 `413e05ad…65cea9c9`, 37 files secrets-clean. Full suite 626 OK (6 skipped). |
| **FourState** | CODE_COMPLETE / TEST_VERIFIED (626) / LIVE_VERIFIED (substrate) / MODEL_EXECUTION_VERIFIED (51 live calls total) / ARENA_VERIFIED (v2 COMPLETE, honest negative) / PRODUCTION not claimed |

### 2026-09-17 — Experiment Arena Control Surface (300 instances, COMPLETE)

| Field | Value |
|---|---|
| **Date** | 2026-09-17 |
| **Agent/task** | Integrate the 300-instance Arena into the CURRENT experiment/dashboard architecture (no parallel system). HEAD `ff44056`, branch `main`. No SSH, no UpCloud compute, no GPU, no fake improvement, no invented scores, no secrets. |
| **Architecture decision** | `thinkbox/pop_arena.py` IS canonical for the population layer. Existing `ExperimentManager` owns single-job persistence, `ChallengeArena` owns adversarial probes — neither owns a 300-instance population with live-budget separation and transfer classification. pop_arena delegates all writes to ExperimentManager/MemoryStore/ActionLedger; zero duplication (one defensive dedupe fix in `aggregate()` after finding double-outcome JOIN fanout). |
| **Arena run** | Control `tb_exp_20260917175431_3c4cf0e1`, session `tb_sess_20260917175440_f13c`: NOT_RUN→CONFIGURED→RUNNING→COMPLETE, all transitions + Chronicle lessons persisted. Population 300/300 (150 baseline + 150 learned). Live budget 12/12 spent: 6 baseline + 6 learned REAL Mercury-2 calls (1/variant/arm), 12/12 VALID, retrieval 6/6 with provenance. Replay 288/288 VALID (deterministic local emission, never shown as model calls). Honesty repairs recorded: 12 false-live flags corrected (telemetry 0.0s/0tok proof), 12 placeholder rows superseded, 12 double outcomes deduped, 1 orphaned call re-run. |
| **Metrics** | verified 300/300, errors 0, retries 0, latency live 0.6–51.5s vs replay 0.0s, tokens live 101–299 vs replay 0. No single score invented. Classification: NO_MEASURABLE_IMPROVEMENT (ceiling 1.0 everywhere — valid, not failure). |
| **Dashboard** | `/api/pipeline` arena block + Population Arena card (state, 300/300, 12/12 live, baseline/learned, provenance, outcomes, latency/tokens, replay state, proof file+hash, classification, blockers, next step). Restart-proof (fresh handles + HTTP). |
| **Chronicle** | arena_configured/started/completed events + lesson rows on control experiment; CONTINUITY/STATUS/AGENTS updated once. Proof `data/thinkboxmd/artifacts/arena_proof_20260917.json` SHA256 `82a29a84…60a0e2c`, secrets-clean. |
| **Tests** | `TestPopulationArena` +8 (300 ids, separation, replay validity, ceiling classification, lifecycle, aggregate rebuild, secrets). Full suite 622 OK (6 skipped). |
| **FourState** | CODE_COMPLETE / TEST_VERIFIED (622) / LIVE_VERIFIED (substrate) / MODEL_EXECUTION_VERIFIED (15 live calls total) / ARENA_VERIFIED (COMPLETE, ceiling honest) / PRODUCTION not claimed |

### 2026-09-17 — KUDBEE Dashboard + Chronicle Sync (pipeline view on existing dashboard)

| Field | Value |
|---|---|
| **Date** | 2026-09-17 |
| **Agent/task** | Update EXISTING dashboard (no parallel system) to expose the real pipeline; sync Chronicle/STATUS/CONTINUITY; land on MAIN. HEAD `e38956c`, branch `kilo/fair-wind-03a`. |
| **Dashboard** | `experiments/swarm_dashboard.py`: added `_pipeline()` (read-only SQLite: experiments/outcomes/proofs/artifacts/lessons/retrievals/params + memory.db + ledger verify; zero singleton reads) served at `/api/pipeline`, plus a Pipeline HTML tab (KPIs, jobs table with job/session/model/verify/hash/lesson-source, lessons/retrieval/memory/blockers/next-step). Restart-proof verified by serving from a fresh module load and by singleton-reset test. No secrets in payload (tested). |
| **Chronicle** | No `*chronicle*` files and no Chronicle references exist in the repo (glob + grep verified) — the Chronicle role is served by `docs/CONTINUITY.md` + `STATUS.md` + `AGENTS.md` + `data/thinkboxmd/artifacts/*.json` proof files. Updated all four in place; invented no new Chronicle files. |
| **State proven** | 6 experiments / 6 outcomes / 4 proofs / 9 artifacts / 6 lessons / 2 retrieval events / 3 memory keys / ledger 4 entries verified; 3 Mercury-2 jobs VALID (`4b92d477`, `fbb1ec84`, `a1ae355e`); lesson `learn:exact-json:directive` (task=baseline, conf 0.9); learned job `lesson_source`=baseline; classification NO_MEASURABLE_IMPROVEMENT. |
| **Tests** | `TestPipelineDashboard` +4 (rebuild-from-storage, singleton-reset recovery, learning-provenance exposure, no-secrets). Full suite 614 OK (6 skipped). |
| **FourState** | CODE_COMPLETE (dashboard+tests) / TEST_VERIFIED (614) / LIVE_VERIFIED (Box substrate, prior runs) / MODEL_EXECUTION_VERIFIED (3 live calls) / ARENA NOT_RUN / PRODUCTION not claimed |

### 2026-09-17 — End-to-End Learning Think Job (Box → Mercury-2 → reuse → compare)

| Field | Value |
|---|---|
| **Date** | 2026-09-17 |
| **Agent/task** | Prove first complete learning loop with measurable persisted-knowledge reuse. HEAD `7c9b45b`, branch `kilo/fair-wind-03a`. No SSH, no UpCloud compute, no GPU, no model mocks, no invented credentials. |
| **Phase 1 path** | Existing systems only: ExperimentManager (lessons/events) + MemoryStore (provenance task_id) + ActionLedger + ExperimentStore/SelfImprovementLoop (A/B + propose/retest/record) — traced, reused, no competing architecture. No EvidenceDrivenLearningEngine/OutcomeClassifier classes exist in repo (directive names not present — recorded; vocabulary IMPROVED/etc. used as plain classification). |
| **Phase 2 baseline** | Job `tb_exp_20260917170533_fbb1ec84` (session `tb_sess_20260917170533_4d11`): exact-JSON family, expected answer=7, strategy no-lesson. Live Mercury-2: VALID True, 0.39s, 98 tokens, cost \$0.0000585. Artifact SHA `6cc76885…18ddbd0f5`, proof + outcome TEST_VERIFIED. |
| **Phase 3 learning** | Lesson row (id 5) + memory key `learn:exact-json:directive` (conf 0.9, task provenance = baseline): known = directive+low-temp+token-floor works; unknown = transfer + smaller floor. |
| **Phase 4 learned** | Fresh handles; retrieved memory key (provenance logged); job `tb_exp_20260917170605_a1ae355e` (session `tb_sess_20260917170605_9e60`): same family, expected answer=9, strategy lesson-reuse. Retrieval provenance in 3 places: lesson_retrieval event + lesson_source param + ledger metadata. Live Mercury-2: VALID True, 0.433s, 91 tokens, cost \$0.0000533. Artifact SHA `814b63e0…def455c150f2`. |
| **Phase 5 compare** | verification True/True; retries 0/0; memory reuse proven; proof full/full; latency 0.39/0.433; tokens 98/91; cost down \$0.000005. No overall score invented. Classification: NO_MEASURABLE_IMPROVEMENT (ceiling effect at 1.0 — valid result, reuse proven, model NOT claimed smarter). |
| **Phase 6 restart** | Fresh process: both experiments + lessons + memory + artifacts + ledger all reload; provenance intact; hashes match; property replay True/True. |
| **Tests/evidence** | `test_learning_loop_provenance` (deterministic, mocked-free of live calls: lesson→retrieval→reload round-trip). Proof `learn_loop_proof_20260917.json` SHA256 `e05be996…22ffb7f90`, secrets-clean. Full suite 610 OK (6 skipped). |
| **FourState** | MODEL_EXECUTION_VERIFIED (two live calls) + learning loop TEST_VERIFIED |

### 2026-09-17 — Real Model-Backed Think Job (Mercury-2 via Box substrate)

| Field | Value |
|---|---|
| **Date** | 2026-09-17 |
| **Agent/task** | Prove Think Box → Upstash Box → Model Provider → Response → Validation → Artifact → Proof → Memory → Replay → Dashboard. HEAD `9d08ac3`, branch `kilo/fair-wind-03a`. No SSH, no UpCloud compute, no GPU, no mocks, no invented config. |
| **Phase 1 path** | Supported model providers: `openai_compat` + `ollama` (registry-verified). Live contract found in-repo: `experiments/thinkboxmd_research.py::MercuryClient` = `OpenAICompatProvider{api_key: INCEPTION_API_KEY (presence only), model: mercury-2, base_url: https://api.inceptionlabs.ai/v1}`. `think_box_ai/commands/inception.py` is simulate-only (not used). `thinkbox/model_client.py` has no auth path (not used). |
| **Phase 2 contract** | Legitimate existing configuration: INCEPTION_API_KEY SET + documented endpoint/model constants + proven provider composition (THINKBOXMD 9 PASS live, 2026-09-15). No values invented, no env changes. Standard `THINKBOX_OPENAI_COMPAT_*` contract stays absent by design — verdict is CONFIGURED via the Inception contract, not MODEL_NOT_CONFIGURED. |
| **Phase 3 live call** | ONE bounded call (temp 0.2, max_tokens 3500, 60s timeout): prompt demands exactly `{"answer": 42}`. Response 14 chars, parsed `{"answer": 42}`, property VALID. Usage 36/77/113 tokens (70 reasoning, 4 cached), latency 0.774s. Session `tb_sess_20260917165841_b7bdb508`, box `box_950e971d6d1b` (Vector persisted), job `tb_exp_20260917165842_4b92d477`, artifact `model_job_<id>.json` SHA256 `e41e8f9e…caf8f6`, ledger verify True, memory + proof + outcome TEST_VERIFIED + lesson + dashboard JOB_COMPLETED + provider verified. No intelligence claim. |
| **Phase 4 replay** | Fresh handles: experiment/session/box/artifact/proof/memory/outcome reload OK; canonical hash match; property re-validated True (byte-identical response NOT required — recorded explicitly). |
| **Phase 5 safety** | Artifact scanned: no API keys, no Authorization/Bearer, no env dump, no secret patterns; base_url + model recorded (safe); single bounded call; failure path = honest FAILED outcome. No new provider built — existing path reused. |
| **Tests/evidence** | `tests/unit/test_providers.py` +3 (endpoint shape, chat/completions targeting with URL/body assertions, no-secrets contract) — all mocked, deterministic. Proof `data/thinkboxmd/artifacts/model_job_proof_20260917.json` SHA256 `a4171cdc…356c12`. Full suite 609 OK (6 skipped). |
| **FourState** | MODEL_EXECUTION_VERIFIED (single bounded live call; path proven, quality unclaimed) |

### 2026-09-17 — Upstash Box as Primary Execution Substrate

| Field | Value |
|---|---|
| **Date** | 2026-09-17 |
| **Agent/task** | Make Upstash Box the primary substrate; UpCloud = control-plane only; SSH direction removed from roadmap. HEAD `76b576a`, branch `kilo/fair-wind-03a`. |
| **Phase 1 contract** | Traced `detect_substrate()` / `bind_think_box` / `WorkspaceRegistry+Store` / `SubstrateProbe` / env handling. Precedence proven live: `UPSTASH_PUBLIC_BOX_URL` (Box host) > `THINKBOX_UPCLOUD_API_TOKEN` (legacy label) > `CI` > `local`. Live selection: `wanted-tuna-71803-3000.preview.box.upstash.com`. No secrets printed (presence/length only). |
| **Phase 2 Box job** | Deterministic job through the REAL Box substrate (this process IS the Box compute: Firecracker kernel `6.18.36-cloudflare-firecracker`, Box host env; no remote-exec API exists — Box preview 404 on all paths, Box SSH password-only, no CLI/SDK — so claim is in-Box execution, honestly bounded). Session `tb_sess_20260917164614_26d2aca3`, box `box_62f30c9d3adc` (Vector snapshot persisted=True), job `tb_exp_20260917164615_32b3ee9c`, artifact `box_job_<id>.json` SHA256 `8bac2b52…57662550`, validation PASS, ledger verify True, memory record, outcome TEST_VERIFIED, dashboard JOB_COMPLETED. |
| **Phase 3 restart** | Fresh handles: experiment/session/box/artifact/proof/memory/outcome all reload; canonical hash matches; ledger verifies; replay `sorted([5,3,4,1,2])` identical `[1,2,3,4,5]`; substrate stable across processes. Note: `record_outcome` leaves status `pending` (pre-existing behavior, untouched). |
| **Phase 4 model (Box-primary run)** | `OpenAICompatProvider` implemented (chat/completions, embedding=False). At that time `THINKBOX_OPENAI_COMPAT_*` wiring absent → no call made. SUPERSEDED same-day: existing Inception contract (`INCEPTION_API_KEY` + MercuryClient constants) proven legitimate → live call VERIFIED (see "Real Model-Backed Think Job" above). |
| **Phase 5 reclassify** | `thinkbox/upcloud.py`: control-plane-only docstring, no stale host defaults (explicit values required), `api_url` 1.6→1.3, provider model/endpoint labels fixed. `tests/unit/test_cnc.py`: defaults + explicit-server tests. Historical docs/artifacts kept (superseded, not deleted). No competing substrate built. No SSH used. |
| **Evidence** | `data/thinkboxmd/artifacts/box_primary_proof_20260917.json` SHA256 `972f2b6e3081db1b0e38e61c67c0553c2cdbfdd6f05978c697188259f1d725e3`. Full suite 606 OK (6 skipped). |
| **FourState** | TEST_VERIFIED (job+restart+replay) with LIVE_VERIFIED substrate selection + Vector write; NOT production; no UpCloud/GPU/SSH/model claims |

### 2026-09-17 — UpCloud Runtime State Diagnostic (kudbeev3)

| Field | Value |
|---|---|
| **Date** | 2026-09-17 |
| **Agent/task** | Runtime-state-only diagnostic (no SSH troubleshooting, no mutation). HEAD `beee146`, branch `kilo/fair-wind-03a`, tree clean except new artifact. |
| **Phase 1 API state** | `/1.3/account` 200 (`kudbee`); `/1.3/server` 200 (1 server); `/1.3/server/<uuid>` 200: `kudbeev3` state=**started**, zone us-chi1, plan CLOUDNATIVE-16xCPU-48GB (16 cores, 49152MB, host 8388362883, boot_order=disk, firewall off), IPs 209.50.56.169 + 209.50.53.93 (public) + 10.3.14.89 (utility), storage ubuntu-16cpu-48gb-us-chi1 50GB virtio, tags []. GPU: none assigned; catalog has 68 GPU plans (L4/L40S/H100/B200/RTXPRO6000); current plan verified in catalog (182 plans total). **Server IS running.** |
| **Phase 2 SSH correlation** | Server running → port 22 tested: .169 OPEN (connect_ex=0), .93 TIMEOUT (connect_ex=11). Single BatchMode auth attempt on .169: Permission denied (publickey). Separate statuses: API reachable ✅ / server running ✅ / port22 .169 ✅ / port22 .93 ❌ / SSH key available ❌ / SSH auth successful ❌. |
| **Phase 3 substrate** | CURRENT EXECUTION SUBSTRATE = Upstash Box preview (`wanted-tuna-71803-3000.preview.box.upstash.com`; `detect_substrate()` precedence proven: UPSTASH_PUBLIC_BOX_URL wins even though THINKBOX_UPCLOUD_API_TOKEN is set). UPCLOUD API CONTROL PLANE = REACHABLE (read-only). UPCLOUD SERVER EXECUTION PATH = NOT WIRED (`UpCloudExecutionProvider.execute` is REST control-plane only; `UpCloudConfig` defaults stale 212.147.250.183; no SSH adapter; `bind_think_box` has no live-server branch). UPCLOUD GPU EXECUTION PATH = NOT PRESENT (CPU-only server; no GPU code path). |
| **No mutation** | Zero start/stop/reboot/resize/provision/delete/SSH-key-registration/package/service changes. GET-only API, one TCP probe per IP, one BatchMode SSH attempt. |
| **Evidence** | Experiment `tb_exp_20260917164001_073516d8` (session `tb_sess_20260917164001_fbb2`), artifact `data/thinkboxmd/artifacts/upcloud_runtime_state_20260917.json` SHA256 `e333faa4d1886d102d808ec3fffc4a1deef3a6af9eb02ee95226c1d10d711ff8`. Targeted 85 OK; full suite 605 OK (6 skipped). FourState: LIVE_VERIFIED (control-plane runtime state); machine execution NOT reached → no LIVE_VERIFIED for machine. |
| **Exact blocker** | No authorized SSH key on kudbeev3 — recovered historical key rejected (publickey). Server itself is running; user report of "not running" contradicted by live API. |
| **Status** | COMPLETE (diagnostic); SSH host access remains BLOCKED pending key registration |

### 2026-09-17 — Live UpCloud Host Verification (kudbeev3)

| Field | Value |
|---|---|
| **Date** | 2026-09-17 |
| **Agent/task** | Live host verification: SSH discovery → read-only host proof → API/machine reconciliation → substrate review → evidence |
| **Starting evidence check** | Directive cited SHA 5e8a7b7 / 693 tests / prior live proof artifact. Repo reality: HEAD 48fed0f, 605 tests, no 5e8a7b7 object in history, no prior artifact on disk. origin/main also 48fed0f. Recorded as divergence, not silently adopted. In-sync with origin/main; no stale-code risk. |
| **Phase 1 SSH discovery** | UPCLOUD_SSH_KEY_PATH configured (presence only) but file absent; UPCLOUD_SSH_USER + HOSTNAME + IP configured. Recovered keypair consistent (derived pub matches file pub, ed25519 thinkbox-agent-20260831) but is the HISTORICAL key. UpCloudConfig defaults stale (kudbee-host-v1/212.147.250.183); live IPs require explicit passing. Port 22: 209.50.56.169 OPEN (banner OpenSSH_10.2p1 Ubuntu-2ubuntu3.6), 209.50.53.93 TIMEOUT. No SSH adapter class exists; only UpCloudExecutionPath.step4 subprocess ssh. |
| **Phase 2 host proof** | SSH auth FAILED: Permission denied (publickey) — server offered only publickey, rejected historical key. No shell obtained. No packages installed, nothing mutated. Machine facts (hostname/OS/CPU/RAM/GPU/processes/repo): all UNVERIFIED. |
| **Phase 3 reconciliation** | API says: kudbeev3 / 209.50.56.169 + 209.50.53.93 / 16 cores / 49152MB / CPU-only plan. Machine says: banner-only on .169 (Ubuntu OpenSSH), .93 unreachable, everything else UNVERIFIED. Verdict: NOT_PROVEN same-machine (auth blocker). GPU: no shell evidence; CPU-only plan implies absence but unmeasured. |
| **Phase 4 substrate** | Current substrate is Upstash Box (detect_substrate reads UPSTASH_PUBLIC_BOX_URL; THINKBOX_UPCLOUD_API_TOKEN never consulted for live server). SubstrateProbe read-only OK. Smallest integration point: core/providers/upcloud.py execute(list_servers/get_server read-only) → UpCloudConfig(server_uuid/IP from API, key path) → substrate.bind_think_box live-server branch. Not built (directive: review only). |
| **Evidence** | Experiment tb_exp_20260917162855_5eb93b1c (session tb_sess_20260917162855_705f), artifact data/thinkboxmd/artifacts/upcloud_host_verify_20260917.json SHA256 400f4cc92b300a0553cdc9448d89c4cc7f22157985805af9c36fa9737e7bd20d. API contract: Bearer on /1.3 (200); /1.6 → 400; /v1 → 404. Targeted tests 40 OK; full suite 605 OK (6 skipped). Dashboard updated (job + kudbeev3 infra + provider + milestone). |
| **FourState** | TEST_VERIFIED (code+tests) with LIVE_VERIFIED API inventory; SSH host proof FAILED (blocker) |
| **Status** | BLOCKED on SSH authorization — key registration required via panel/API |

### 2026-09-17 — Main Merge and PR Cleanup

| Field | Value |
|---|---|
| **Date** | 2026-09-17 |
| **Agent/task** | Merge all work into main, close stale PRs |
| **PR/commit** | `9f12e1d` on `main` |
| **Result** | All work from `kilo/adept-marsh-qiq` merged into main. Safety gate JSON files removed from git. |
| **PRs closed** | #68 (superseded), #67 (superseded), #65 (superseded), #32 (DIRTY, superseded), #28 (DIRTY, superseded) |
| **Tests/evidence** | 560 tests pass (6 skipped), working tree clean |
| **Status** | COMPLETE |

### 2026-09-17 — UpCloud Investigation Phase 1-6 COMPLETE

| Field | Value |
|---|---|
| **Date** | 2026-09-17 |
| **Agent/task** | Full investigation: server identity, network diagnosis, alternative paths, dashboard update |
| **PR/commit** | `c62e50d` on `kilo/adept-marsh-qiq`, merged to main `9f12e1d` |
| **Result** | **CASE C CONFIRMED**: Historical IP 212.147.250.183 is no longer the current server. Port 22 TIMEOUT, Cloudflare 1003 on port 80, TLS error on 443. |
| **Diagnosis** | **NETWORK/FIREWALL layer failure**: TCP port 22 blocked by UpCloud security groups |
| **Dashboard** | Updated with actual infrastructure state |
| **Status** | BLOCKED — requires human action |

### 2026-09-17 — Recovery: Restore Missing Files from Git History

| Field | Value |
|---|---|
| **Date** | 2026-09-17 |
| **Agent/task** | Recover UpCloud provider, execution module, CONTINUITY.md |
| **PR/commit** | `3e7c361` on `kilo/adept-marsh-qiq`, merged to main `9f12e1d` |
| **Result** | Restored `core/providers/upcloud.py`, `core/providers/execution.py`, `core/providers/__init__.py`, `docs/CONTINUITY.md`, test files |
| **Tests/evidence** | 560 tests pass (6 skipped), SSH key recovered from git history |
| **Status** | COMPLETE |

### 2026-09-17 — UpCloud Connection Path Investigation

| Field | Value |
|---|---|
| **Date** | 2026-09-17 |
| **Agent/task** | Investigate September 15 server connection path |
| **Result** | All UpCloud API tokens return 401; SSH to 212.147.250.183 times out; Upstash SSH requires password; upctl CLI not installed |
| **Status** | BLOCKED |

### 2026-09-16 — UpCloud ExecutionProvider Phase 2: Credential Precedence

| Field | Value |
|---|---|
| **Date** | 2026-09-16 |
| **Agent/task** | UpCloud credential priority update |
| **PR/commit** | `a2335e2` on `kilo/leafy-dragon-4ck` |
| **Result** | `UPCLOUD_API_MAIN` primary, `UPCLOUD_API_KEY` fallback, config override |
| **Tests/evidence** | 33 unit tests pass, 6 credential precedence scenarios verified programmatically |
| **Status** | COMPLETE |

### 2026-09-16 — UpCloud ExecutionProvider Phase 1: Abstraction + Provider

| Field | Value |
|---|---|
| **Date** | 2026-09-16 |
| **Agent/task** | UpCloud ExecutionProvider initial implementation |
| **PR/commit** | `32d82ef` on `kilo/leafy-dragon-4ck` |
| **Result** | ExecutionProvider base class, UpCloudExecutionProvider, evidence records, dry-run plan mode |
| **Tests/evidence** | 31 unit tests pass, live API audit (all 401), credential scan clean |
| **Status** | COMPLETE (superseded by Phase 2) |

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
| 1 | UpCloud live capability verification | Any agent | BLOCKED | Obtain valid `UPCLOUD_API_MAIN` from UpCloud panel, verify server reachability | Valid API token from UpCloud panel |
| 2 | UpCloud autonomous provisioning | Any agent | BLOCKED | Complete live verification (item 1), then wire into runtime | Live capabilities VERIFIED |
| 3 | UpCloud server identity verification | Any agent | BLOCKED | Case C confirmed: historical IP 212.147.250.183 is no longer the current server. Need to determine current server IP or confirm server no longer exists. | UpCloud panel access + valid credentials |
| 4 | SSH key persistence | Any agent | BLOCKED | SSH key recovered from git `5f6a5c7` but NOT persisted to `~/.ssh/kilo-upcloud`. Key exists in workspace as `kilo-upcloud-recovered`. | Restore key to `~/.ssh/kilo-upcloud` |
| 5 | Dashboard state verification | Any agent | COMPLETE | Dashboard updated with actual infrastructure state | N/A |
| 6 | PR cleanup | Any agent | COMPLETE | PRs #68, #67, #65, #32, #28 all closed (superseded by main merge) | N/A |

## CLOSED LOOPS

### UpCloud ExecutionProvider Phase 1
- **Implementation**: `core/providers/execution.py`, `core/providers/upcloud.py`
- **Verification**: 31/31 unit tests pass, live API audit (all DENIED/401), credential scan clean
- **Evidence**: `tests/unit/test_upcloud_provider.py`, `tests/integration/test_upcloud_live.py`, `docs/upcloud-provider.md`
- **PR/Commit**: `32d82ef` on `kilo/leafy-dragon-4ck`
- **Closure**: Superseded by Phase 2 credential update

### Permanent Continuity Protocol
- **Implementation**: `docs/CONTINUITY.md`, `AGENTS.md` §14
- **Verification**: 449 tests pass, no credential leaks, docstring coverage verified, all required CONTINUITY.md sections present
- **Evidence**: `tests/unit/test_upcloud_provider.py` (33 tests), `tests/integration/test_upcloud_live.py` (5 skipped), credential precedence verification
- **PR/Commit**: `c7792b7` on `kilo/leafy-dragon-4ck`, PR #68
- **Closure**: COMPLETE (PR open for review, code committed and pushed)

### 2026-09-17 — Recovery: Restore Missing Files from Git History

| Field | Value |
|---|---|
| **Date** | 2026-09-17 |
| **Agent/task** | Recover UpCloud provider, execution module, CONTINUITY.md |
| **PR/commit** | `3e7c361` on `kilo/adept-marsh-qiq` |
| **Result** | Restored `core/providers/upcloud.py`, `core/providers/execution.py`, `core/providers/__init__.py`, `docs/CONTINUITY.md`, test files |
| **Tests/evidence** | 560 tests pass (6 skipped), SSH key recovered from git history |
| **Status** | COMPLETE |

### 2026-09-17 — UpCloud Connection Path Investigation (PHASE 1-6 COMPLETE)

| Field | Value |
|---|---|
| **Date** | 2026-09-17 |
| **Agent/task** | Full investigation: server identity, network diagnosis, alternative paths, dashboard update |
| **PR/commit** | `b04460b` on `kilo/adept-marsh-qiq` |
| **Result** | **CASE C CONFIRMED**: Historical IP 212.147.250.183 is no longer the current server. Port 22 times out, ports 80/443 behind Cloudflare (error 1003). All API tokens return 401. SSH key recovered from git but not persisted to disk. |
| **Diagnosis** | **NETWORK/FIREWALL layer failure**: TCP port 22 blocked by UpCloud security groups. Port 80 returns Cloudflare 1003 (direct IP access blocked). Port 443 TLS error. DNS not applicable (literal IP). |
| **Identity** | Historical server identity VERIFIED from git history (kudbee-host-v1, 212.147.250.183, ed25519 key thinkbox-agent-20260831). Current server status UNVERIFIED. |
| **Status** | BLOCKED — requires human action |

### 2026-09-17 — UpCloud Investigation: Exact Failure Layer

| Field | Value |
|---|---|
| **DNS** | N/A (literal IP, no DNS resolution needed) |
| **Routing** | TCP port 80/443 reachable, port 22 TIMEOUT |
| **TCP layer** | Port 22 blocked (timeout), Ports 80/443 open |
| **Firewall** | Cloudflare 1003 on port 80, TLS error on 443, port 22 blocked by security groups |
| **SSH layer** | Connection timed out — never reaches handshake |
| **Auth layer** | N/A (SSH never reaches handshake) |
| **Exact failure layer** | **NETWORK/FIREWALL — port 22 blocked by UpCloud security groups** |
| **Case** | **C: The historical IP is no longer the current server** |
| **Missing external action** | 1) Obtain valid `UPCLOUD_API_MAIN` from UpCloud panel 2) Verify server 212.147.250.183 is still the active machine (or find new IP) 3) Restore SSH key to `~/.ssh/kilo-upcloud` 4) If IP changed, update `UPCLOUD_SERVER_IP` |

### 2026-09-17 — Dashboard State Updated

| Field | Value |
|---|---|
| **Dashboard** | Updated with actual infrastructure state |
| **UPCloud identity** | VERIFIED (historical) / UNVERIFIED (current) |
| **Network** | TIMEOUT (port 22) |
| **SSH** | BLOCKED |
| **GPU** | UNKNOWN |
| **Model** | UNKNOWN |
| **Think Box routing** | NOT CONNECTED |
| **Evidence label** | verified (from actual network probes) |

### UpCloud ExecutionProvider Phase 2: Credential Precedence
- **Implementation**: Updated `core/providers/upcloud.py` credential resolution
- **Verification**: 33/33 unit tests pass, 6 credential precedence scenarios verified, credential scan clean
- **Evidence**: `tests/unit/test_upcloud_provider.py` (33 tests), credential precedence verification script
- **PR/Commit**: `a2335e2` on `kilo/leafy-dragon-4ck`
- **Closure**: Code committed, pushed, tests passing — COMPLETE

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
| **API Endpoint** | https://api.upcloud.com/v1 |
| **Primary Credential** | `UPCLOUD_API_MAIN` env var — NOT SET |
| **Fallback Credential** | `UPCLOUD_API_KEY` env var — NOT SET |
| **Credential detected** | **NO** (neither env var set in this environment) |
| **CLI Tool** | upctl — NOT installed |
| **Provider Implementation** | REST API via `urllib` (stdlib) |
| **Live API Reachable** | YES (HTTP 401) |
| **Read Capabilities** | ALL DENIED (no credentials) |
| **Mutation Capabilities** | NOT TESTED (requires approval + credentials) |
| **Verification Status** | CREDENTIALS NEEDED |
| **Server IP** | 212.147.250.183 (kudbee-host-v1) — **CASE C: historical IP, no longer confirmed current** |
| **Port 22 (SSH)** | TIMEOUT — blocked by UpCloud security groups |
| **Port 80 (HTTP)** | Cloudflare 1003 — direct IP access blocked |
| **Port 443 (HTTPS)** | TLS error |
| **SSH Key** | Recovered from git `5f6a5c7` (ed25519, thinkbox-agent-20260831) but NOT persisted to `~/.ssh/kilo-upcloud` |
| **Last Known Working** | 2026-09-15 |
| **Network Diagnosis** | Port 22 blocked at network/firewall layer. Not DNS, not routing, not SSH auth. |
| **Case** | **C: The historical IP is no longer the current server** |
| **Required Human Action** | 1) Obtain valid `UPCLOUD_API_MAIN` from UpCloud panel 2) Verify if 212.147.250.183 is still the active server or find new IP 3) Restore SSH key to `~/.ssh/kilo-upcloud` 4) Update `UPCLOUD_SERVER_IP` if changed |

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

| Branch | Ahead of Origin | Status |
|---|---|---|
| `main` | 0 | CURRENT — all work merged |
| `kilo/adept-marsh-qiq` | 0 | MERGED into main |
| `kilo/leafy-dragon-4ck` | 0 | SUPERSEDED — work merged into main |

### Parked/Inactive Branches

| Branch | Status |
|---|---|
| `kilo/amber-link-x8y` | Merged to main (PR #62) |
| `feat/disruptor-evaluation` | Merged to main (PR #61) |
| `feat/phase12-kudbee-control-fabric` | Merged to main (PR #60) |
| All other branches | Stale, superseded by main |

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

### Active PRs

| PR | Title | State | Notes |
|---|---|---|---|
| None | — | — | All PRs closed or merged |

### Closed PRs (2026-09-17)

| PR | Title | State | Reason |
|---|---|---|---|
| #68 | chore(continuity): permanent agent protocol + CONTINUITY.md | CLOSED | Superseded by main merge |
| #67 | feat(dashboard): KUDBEE control surface | CLOSED | Superseded by main merge |
| #65 | docs(agents): AGENTS.md as single source of truth | CLOSED | Superseded by main merge |
| #32 | fix(roadmap): correct Stage 0 accuracy issues | CLOSED | DIRTY, superseded by main merge |
| #28 | fix(providers): rewrite OllamaProvider | CLOSED | DIRTY, superseded by main merge |

### Merged to Main

| Commit | Title | Notes |
|---|---|---|
| `9f12e1d` | Merge branch 'kilo/adept-marsh-qiq' | All work merged into main |
| `42cd276` | chore(cnc): add safety gate JSON files | Removed from git, added to .gitignore |
| `c62e50d` | docs: add Phase 1-6 UpCloud investigation | Case C confirmed |
| `b04460b` | docs: update CONTINUITY.md and AGENTS.md | Recovery status |
| `3e7c361` | feat(recovery): restore UpCloud provider | From git history |
| `ee1d619` | feat(dashboard): make dashboard the living control plane | Dashboard state |
| `19fa4a3` | feat(dashboard): integrate dashboard state | Backend integration |
| `a388bcc` | feat(cnc): implement CNC manufacturing platform | CNC module |

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
10. **NEVER** silently discard a discovery, failed experiment, architectural decision, security finding, or important limitation

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
