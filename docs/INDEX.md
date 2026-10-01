# Documentation index

Every tracked Markdown file in this repository, by area (231 files). **Generated** by `python3 scripts/generate_docs_index.py`; do not edit by hand. A test fails when this page is stale, so run the script whenever you add, move or rename a `.md` file.

## Where Markdown lives, and why

- **Repository root keeps four files on purpose:** `README.md` (GitHub renders it), `CLAUDE.md` and `AGENTS.md` (Claude Code and other agents load them by path; AGENTS.md section 4.3 names the rules), and `STATUS.md` (named in AGENTS.md section 4.3 and section 13.1; `docs/STATUS.md` also exists, so it cannot move there). A test fails if any other `.md` file appears at the root.
- **Everything else lives in a folder.** Most documents are under `docs/`.
- **Left where they are because code or tooling reads them there:** `agents/` and `.agents/` (agent definitions), `data/` (evidence and proof documents that gates and docs cite), `tests/` and `examples/` (fixtures).
- **Not listed:** copies under `.kilo/worktrees/` (working-tree duplicates).

## Moved files

These files used to sit at the repository root. Older notes and chronicle entries may still mention the old path; the file names did not change.

| Old path | New path |
|---|---|
| `CI_TEST.md` | [`docs/archive/CI_TEST.md`](archive/CI_TEST.md) |
| `CONTRIBUTING.md` | [`docs/CONTRIBUTING.md`](CONTRIBUTING.md) |
| `DEPLOYMENT.md` | [`docs/deployment/DEPLOYMENT.md`](deployment/DEPLOYMENT.md) |
| `FEATURE1_PHASE2_INTEGRATION.md` | [`docs/plans/FEATURE1_PHASE2_INTEGRATION.md`](plans/FEATURE1_PHASE2_INTEGRATION.md) |
| `FORCE_PUSH_READY.md` | [`docs/incidents/FORCE_PUSH_READY.md`](incidents/FORCE_PUSH_READY.md) |
| `INCIDENT_RESPONSE_2026-09-28.md` | [`docs/incidents/INCIDENT_RESPONSE_2026-09-28.md`](incidents/INCIDENT_RESPONSE_2026-09-28.md) |
| `KUDBEE_AGENT_RUNTIME_CONTRACT.md` | [`docs/architecture/KUDBEE_AGENT_RUNTIME_CONTRACT.md`](architecture/KUDBEE_AGENT_RUNTIME_CONTRACT.md) |
| `PHASE9_INDEX.md` | [`docs/archive/PHASE9_INDEX.md`](archive/PHASE9_INDEX.md) |
| `RESEARCH.md` | [`docs/research/RESEARCH.md`](research/RESEARCH.md) |
| `ROADMAP.md` | [`docs/roadmaps/ROADMAP.md`](roadmaps/ROADMAP.md) |
| `SECURITY.md` | [`docs/SECURITY.md`](SECURITY.md) |
| `TEST_SYNC.md` | [`docs/archive/TEST_SYNC.md`](archive/TEST_SYNC.md) |
| `THINK_TOKEN_STRATEGY.md` | [`docs/strategy/THINK_TOKEN_STRATEGY.md`](strategy/THINK_TOKEN_STRATEGY.md) |

## Contents

- [Start here (repository root)](#start-here-repository-root) (4)
- [Decisions (ADRs)](#decisions-adrs) (35)
- [Enterprise Agent OS plan](#enterprise-agent-os-plan) (5)
- [Guides](#guides) (63)
- [Runbooks](#runbooks) (4)
- [Roadmaps, status and continuity](#roadmaps-status-and-continuity) (7)
- [Security and incidents](#security-and-incidents) (5)
- [Project policies](#project-policies) (1)
- [Architecture, plans and deployment](#architecture-plans-and-deployment) (5)
- [Audits and reviews](#audits-and-reviews) (32)
- [Research and strategy](#research-and-strategy) (4)
- [Archive](#archive) (3)
- [Other documents in docs/](#other-documents-in-docs) (28)
- [Agent definitions](#agent-definitions) (17)
- [Evidence and data documents](#evidence-and-data-documents) (16)
- [Tests and examples](#tests-and-examples) (2)

## Start here (repository root)

| File | Title | About |
|---|---|---|
| [AGENTS.md](../AGENTS.md) | AGENTS.md — THINK BOX AI | Purpose: This file defines the rules that every agent (human or AI) working |
| [CLAUDE.md](../CLAUDE.md) | CLAUDE.md — kudbEE Agent OS Project Guidelines | Purpose: This file tells AI (Claude, other agents) how to contribute to this project effectively. |
| [README.md](../README.md) | Think Box AI | Governed agent execution for the enterprise — goals decompose into tasks, tools run behind permission checks,... |
| [STATUS.md](../STATUS.md) | STATUS.md | - CODE COMPLETE / TEST VERIFIED / LIVE VERIFIED (real Mercury 2 runs on the real server, real browser): permanent... |

## Decisions (ADRs)

| File | Title | About |
|---|---|---|
| [docs/decisions/001-cnc-manufacturing.md](decisions/001-cnc-manufacturing.md) | ADR 001: CNC Manufacturing Intelligence Platform | Think Box AI needed to extend beyond agent reasoning and scheduling into |
| [docs/decisions/002-cloud-execution-substrate.md](decisions/002-cloud-execution-substrate.md) | ADR 002: Cloud execution substrate (Phase 1) | Think Box needs a provider-neutral execution substrate for cloud agent jobs (intent → admission → workspace → worker... |
| [docs/decisions/002-kilo-env-matrix.md](decisions/002-kilo-env-matrix.md) | ADR 002: KILO env-matrix hermetic contract (PR #142) | The #141–#150 Live-proof readiness arc needs a fail-closed description of which |
| [docs/decisions/003-cloud-execution-durable-queue.md](decisions/003-cloud-execution-durable-queue.md) | ADR 003: Cloud execution durable queue (Phase 2) | PR #197 introduced a provider-neutral in-memory execution substrate. Phase 2 requires durable queued jobs, worker... |
| [docs/decisions/003-kilo-substrate-checklist.md](decisions/003-kilo-substrate-checklist.md) | ADR 003: KILO substrate-checklist Box readiness (PR #143) | PR #142 closed env-matrix with generic substrate env contracts. Live-proof prep |
| [docs/decisions/003-think-repository-stage-1.md](decisions/003-think-repository-stage-1.md) | ADR 003: Think Repository Stage 1 — Git worktree metadata layer | KUDBEE's primary object is the Think Workspace / Think Box, not the Git |
| [docs/decisions/004-cloud-execution-worker-orchestrator.md](decisions/004-cloud-execution-worker-orchestrator.md) | ADR 004: Cloud execution worker orchestrator (Phase 3) | PR #198 added a durable SQLite queue with claims, leases, and restart recovery. Phase 3 needs a governed,... |
| [docs/decisions/004-kilo-governance-evidence.md](decisions/004-kilo-governance-evidence.md) | ADR 004: KILO governance-evidence gate (PR #145) | The #141–#150 Live-proof readiness arc needs a hermetic contract for admission tokens and |
| [docs/decisions/004-upstash-box-auth-contract.md](decisions/004-upstash-box-auth-contract.md) | ADR 004: Upstash Box Authentication Contract | The think-box-ai repository implements a remote execution adapter for Upstash Box in thinkbox/executionadapter.py.... |
| [docs/decisions/005-environmental-variables.md](decisions/005-environmental-variables.md) | ADR 005: Environmental variables pack (PR #200) | THINK BOX / KUDBEE reads dozens of environment variables across substrate, governance, providers, cloud execution,... |
| [docs/decisions/005-kilo-mercury-hermetic.md](decisions/005-kilo-mercury-hermetic.md) | ADR 005: KILO mercury-hermetic gate (PR #146) | The #141–#150 Live-proof readiness arc needs bounded Mercury mock completions and |
| [docs/decisions/006-kilo-swarm-instrumentation.md](decisions/006-kilo-swarm-instrumentation.md) | ADR 006: KILO swarm-instrumentation gate (PR #147) | Live-proof readiness arc PR #147 must close gate swarm-instrumentation so operators can |
| [docs/decisions/007-kilo-proof-schema.md](decisions/007-kilo-proof-schema.md) | ADR 007: KILO proof-schema gate (PR #148) | Live-proof readiness arc PR #148 must close gate proof-schema so KILO proof and ledger |
| [docs/decisions/008-kilo-dashboard-slots.md](decisions/008-kilo-dashboard-slots.md) | ADR 008: KILO dashboard-slots hermetic gate | PR #139–#140 established receipt-keyed watch and jobs-digest multiplex panel helpers. PR #148 |
| [docs/decisions/009-kilo-live-proof-exec.md](decisions/009-kilo-live-proof-exec.md) | ADR 009: KILO live-proof-exec (PR #150 season close) | Arc #141–#150 prepared hermetic gates for an honest KILO Live proof. PR #150 must close |
| [docs/decisions/010-kilo-post-season-harden.md](decisions/010-kilo-post-season-harden.md) | ADR 010: Post-season harden (PR #151) | Arc #141–#150 closed with PR #150 live-proof-exec (hermetic season marker only). |
| [docs/decisions/011-kilo-live-smoke-evidence.md](decisions/011-kilo-live-smoke-evidence.md) | ADR 011: Bounded live smoke evidence binder (PR #152) | PR #150 shipped the live-proof-exec plan; PR #151 hardened CI and branch hygiene. |
| [docs/decisions/012-kilo-live-smoke-operator.md](decisions/012-kilo-live-smoke-operator.md) | ADR 012: Live-smoke operator path (PR #153) | PR #152 introduced the bounded live smoke evidence schema, validators, and |
| [docs/decisions/013-kilo-control-plane-api.md](decisions/013-kilo-control-plane-api.md) | ADR 013: Control-plane API surface upgrade (PR #154) | Post-arc maintenance (#151–#153) added smoke evidence and operator paths. The FastAPI |
| [docs/decisions/014-kilo-receipt-chain-etag.md](decisions/014-kilo-receipt-chain-etag.md) | ADR 014: Receipt-chain and ETag deepen (PR #155) | PR #154 mounted control-plane HTTP routes with a basic /receipts/chain conditional GET. |
| [docs/decisions/015-kilo-dashboard-receipt-chain-bind.md](decisions/015-kilo-dashboard-receipt-chain-bind.md) | ADR 015: Dashboard bind for receipt-chain / END LINK | PR #155 deepened receipt-chain reads and conditional HTTP. Operators need a hermetic dashboard surface to exercise... |
| [docs/decisions/016-kilo-api-ops-harden.md](decisions/016-kilo-api-ops-harden.md) | ADR 016: KILO API / ops harden after dashboard bind | PR #154–#156 shipped control-plane HTTP, receipt-chain ETag deepen, and dashboard ENDLINK bind. |
| [docs/decisions/017-kilo-end-link-deepen.md](decisions/017-kilo-end-link-deepen.md) | ADR 017: KILO END LINK / control-plane deepen (PR #158) | PR #154–#157 shipped control-plane HTTP, receipt-chain ETag, dashboard ENDLINK bind, and API ops harden. Operators... |
| [docs/decisions/018-kilo-end-link-operator-ux.md](decisions/018-kilo-end-link-operator-ux.md) | ADR 018: KILO END LINK operator UX deepen (PR #159) | PR #158 shipped hermetic ENDLINK deepen: batch validate API, link integrity fields, chain filters on the server, and... |
| [docs/decisions/019-kilo-receipt-chain-end-link-docs-audit.md](decisions/019-kilo-receipt-chain-end-link-docs-audit.md) | ADR 019: Receipt-chain / ENDLINK docs + audit pack (PR #160) | PR #155–#159 shipped receipt-chain/ETag deepen, dashboard bind, API/ops harden, ENDLINK deepen, and operator UX.... |
| [docs/decisions/020-kilo-end-link-api-ops-harden.md](decisions/020-kilo-end-link-api-ops-harden.md) | ADR 020: END LINK API / ops harden (PR #161) | PR #158–#160 delivered END LINK deepen, operator UX, and docs/audit. Operators still |
| [docs/decisions/021-kilo-receipt-chain-end-link-era-close.md](decisions/021-kilo-receipt-chain-end-link-era-close.md) | ADR 021: Receipt-chain / ENDLINK era audit close (PR #162) | PR #154–#161 shipped the control-plane receipt-chain and ENDLINK stack. PR #160 |
| [docs/decisions/022-kilo-control-plane-e2e-deepen.md](decisions/022-kilo-control-plane-e2e-deepen.md) | ADR 022: KILO control-plane E2E deepen (PR #162) | PR #154–#161 shipped control-plane receipt-chain / ENDLINK HTTP routes and ops harden |
| [docs/decisions/023-kilo-governance-evidence-live-proof-readiness.md](decisions/023-kilo-governance-evidence-live-proof-readiness.md) | ADR 023: KILO governance-evidence Live-proof readiness gate (PR #164) | After PR #163 merged control-plane E2E deepen, the governance-evidence path (#145) still |
| [docs/decisions/024-upstash-box-access-verification.md](decisions/024-upstash-box-access-verification.md) | ADR 024: Upstash Box access verification (PR #201) | PR #200 shipped a typed environmental-variables pack, including substrate keys UPSTASHPUBLICBOXURL and... |
| [docs/decisions/025-trait-lab-autonomous-worker-executor.md](decisions/025-trait-lab-autonomous-worker-executor.md) | ADR 025: Trait Lab Autonomous Worker Executor — Governance Layer | The Trait Lab autonomous chain (PRs #203–#229) has built a complete CI/CD pipeline for autonomous applications: |
| [docs/decisions/026-neon-serverless-postgres.md](decisions/026-neon-serverless-postgres.md) | ADR 026: Neon serverless Postgres setup (PR #257) — revert | On 2026-09-01, issue #9 ("Phase 2: PostgreSQL 19 + pgvector Migration") proposed |
| [docs/decisions/027-enterprise-agent-os-architecture.md](decisions/027-enterprise-agent-os-architecture.md) | ADR 027: Enterprise Agent OS architecture | The Agent OS is a local-only operator console today: one implicit user, no login, one fixed governance identity,... |
| [docs/decisions/028-think-token-persistence.md](decisions/028-think-token-persistence.md) | ADR 028: Where Think Token state lives (SQLite now; Neon only if a reopen criterion is met) | On 2026-09-30 the founder asked for a Neon database to track Think Tokens. That request arrives hours after ADR 026 |
| [docs/decisions/029-think-token-intelligence-object.md](decisions/029-think-token-intelligence-object.md) | ADR 029: The Think Token as a reconfigurable intelligence object | Supersedes nothing. Builds on ADR 026 (Accepted: the unused Neon setup was reverted, so SQLite stays), ADR 027... |

## Enterprise Agent OS plan

| File | Title | About |
|---|---|---|
| [docs/enterprise/baseline.md](enterprise/baseline.md) | Enterprise Agent OS — Baseline (four-state) | This is an honest accounting of what exists today. It uses the repo's four-state convention |
| [docs/enterprise/gap-analysis.md](enterprise/gap-analysis.md) | Enterprise Agent OS — Gap analysis | Each gap points at the evidence in baseline.md (row numbers in brackets) and at the phase in |
| [docs/enterprise/README.md](enterprise/README.md) | Enterprise KUDBEE Agent OS — plan | E0 starts when the founder approves the plan. No code, infrastructure, UpCloud host, Neon resource or external... |
| [docs/enterprise/roadmap.md](enterprise/roadmap.md) | Enterprise Agent OS — Roadmap (E0 to E6) | E0 begins only after the founder approves this plan. |
| [docs/enterprise/think-token-audit.md](enterprise/think-token-audit.md) | Think Token / THNK / DTHINK audit | Status: evidence-only audit, 2026-09-30. Nothing was changed, minted, provisioned or contacted to produce it. Every |

## Guides

| File | Title | About |
|---|---|---|
| [docs/guides/agent-pr-instructions.md](guides/agent-pr-instructions.md) | Agent PR Instructions — copy/paste task-kickoff template | Purpose: a ready-to-fill prompt for starting a scoped PR. It assembles the |
| [docs/guides/agent_os.md](guides/agent_os.md) | kudbEE Agent OS | The interactive web runtime lives in apps/web and serves the Agent OS at |
| [docs/guides/auditable-governance-layer.md](guides/auditable-governance-layer.md) | Auditable Governance Layer for Autonomous Decisions | An accountability infrastructure for recorded governance signals, not an alignment solution. |
| [docs/guides/autonomous-swarm-integration.md](guides/autonomous-swarm-integration.md) | Autonomous Swarm Integration — Production Workflows | Bind autonomous workflow loops to the enterprise swarm pool for concurrent execution with production-grade... |
| [docs/guides/autonomous_loop_actions.md](guides/autonomous_loop_actions.md) | Autonomous Loop Actions Documentation | The autonomous decision loop now tracks user‑initiated actions (start, stop, run, reset) via an audit trail. Each... |
| [docs/guides/deployment.md](guides/deployment.md) | Production Deployment Guide | See the dedicated Docker enterprise guide for profiles, hermetic spine images, and security notes. |
| [docs/guides/docker_enterprise.md](guides/docker_enterprise.md) | Docker — enterprise operator guide | Hermetic containers for the Think Box AI API and optional control-plane static assets. |
| [docs/guides/environment-variables.md](guides/environment-variables.md) | Environment Variables — Model Execution | Think Box AI supports multiple model providers through environment variables. This guide documents the correct setup... |
| [docs/guides/environmental_variables_matrix.md](guides/environmental_variables_matrix.md) | Environmental variables matrix (PR #200) | Hermetic reference for how THINK BOX loads and validates environment variables. No live credentials — use... |
| [docs/guides/flight-readiness.md](guides/flight-readiness.md) | Flight Readiness | Ten verification practices from flight-software engineering (NASA/JPL), mapped |
| [docs/guides/github_webhook.md](guides/github_webhook.md) | GitHub Webhook — Signed PR Lifecycle Receiver | This guide covers the governed GitHub webhook that drives PRLifecycleEventCoordinator |
| [docs/guides/governed-autonomous-execution.md](guides/governed-autonomous-execution.md) | Governed Autonomous Execution Integration | Proof that governance gates actually work in real autonomous task execution. |
| [docs/guides/governed_run_http.md](guides/governed_run_http.md) | Governed POST /api/v1/run (hermetic) | Branch contract for PR #132–#134. Not LIVE VERIFIED. Not PRODUCTION READY. |
| [docs/guides/kilo_api_ops_harden.md](guides/kilo_api_ops_harden.md) | KILO API / ops harden (PR #157) | Hermetic hardening for control-plane HTTP, receipt-chain pagination integrity, |
| [docs/guides/kilo_beyond_kilo_lint_operator.md](guides/kilo_beyond_kilo_lint_operator.md) | Beyond-KILO lint operator guide (PR #170, merged on main) | Hermetic readiness lane for ruff, mypy, and bandit on a scoped path set |
| [docs/guides/kilo_control_plane_api.md](guides/kilo_control_plane_api.md) | KILO control-plane API (PR #154) | Hermetic HTTP surface upgrade for /api/v1/control-plane/. CODE COMPLETE / |
| [docs/guides/kilo_control_plane_e2e_deepen.md](guides/kilo_control_plane_e2e_deepen.md) | KILO control-plane E2E deepen (PR #162) | Hermetic end-to-end (HTTP TestClient) coverage for receipt-chain / ENDLINK control-plane |
| [docs/guides/kilo_dashboard_receipt_chain_bind.md](guides/kilo_dashboard_receipt_chain_bind.md) | KILO dashboard receipt-chain / END LINK bind (PR #156) | Hermetic gate id: dashboard-receipt-chain-bind (layers on receipt-chain-etag). |
| [docs/guides/kilo_dashboard_slots.md](guides/kilo_dashboard_slots.md) | KILO dashboard-slots (PR #149) | Hermetic slot registry for control-plane Live-proof bindings. Not a live dashboard HTTP surface. |
| [docs/guides/kilo_end_link_api_ops_harden.md](guides/kilo_end_link_api_ops_harden.md) | KILO END LINK API / ops harden (PR #161) | Hermetic hardening for control-plane END LINK routes after PR #159–#160: |
| [docs/guides/kilo_end_link_deepen.md](guides/kilo_end_link_deepen.md) | KILO END LINK deepen (PR #158) | Gate id: end-link-deepen |
| [docs/guides/kilo_end_link_operator_ux.md](guides/kilo_end_link_operator_ux.md) | KILO END LINK operator UX (PR #159) | Gate id: end-link-operator-ux |
| [docs/guides/kilo_enterprise_editing.md](guides/kilo_enterprise_editing.md) | KILO enterprise editing | Enterprise editing is how this repository treats changes to canonical narrative and |
| [docs/guides/kilo_governance_evidence_live_proof_readiness.md](guides/kilo_governance_evidence_live_proof_readiness.md) | KILO governance-evidence Live-proof readiness (PR #164) | Hermetic gate: governance-evidence-live-proof-readiness. Four-state on this branch: |
| [docs/guides/kilo_live_proof_exec.md](guides/kilo_live_proof_exec.md) | KILO live-proof-exec guide (PR #150) | Gate ID: live-proof-exec. Hermetic execution-plan contract for a future bounded |
| [docs/guides/kilo_live_proof_readiness.md](guides/kilo_live_proof_readiness.md) | KILO Live-proof readiness (PR #141 spine) | Canonical runbook: docs/runbooks/kilo-live-proof-readiness.md |
| [docs/guides/kilo_live_smoke_evidence.md](guides/kilo_live_smoke_evidence.md) | KILO bounded live smoke evidence (PR #152) | Gate id: live-smoke-evidence |
| [docs/guides/kilo_live_smoke_operator.md](guides/kilo_live_smoke_operator.md) | KILO live-smoke operator path (PR #153) | Gate id: live-smoke-operator |
| [docs/guides/kilo_post_season_harden.md](guides/kilo_post_season_harden.md) | KILO post-season harden (PR #151) | Hermetic ops gate post-season-harden — not part of arc #141–#150. |
| [docs/guides/kilo_proof_schema.md](guides/kilo_proof_schema.md) | KILO proof-schema guide (PR #148) | Hermetic JSON contract for KILO live-proof and ledger artifacts. Gate id: proof-schema. |
| [docs/guides/kilo_receipt_chain_end_link_era_close.md](guides/kilo_receipt_chain_end_link_era_close.md) | KILO receipt-chain / ENDLINK era audit close (PR #162) | Hermetic consolidated audit index for control-plane work #154–#161. |
| [docs/guides/kilo_receipt_chain_end_link_operator.md](guides/kilo_receipt_chain_end_link_operator.md) | KILO receipt-chain + ENDLINK operator surface (#155–#159) | Hermetic operator/founder reference for the control-plane receipt chain and ENDLINK validate paths shipped in PR... |
| [docs/guides/kilo_receipt_chain_etag.md](guides/kilo_receipt_chain_etag.md) | KILO receipt-chain / ETag deepen (PR #155) | Hermetic gate id: receipt-chain-etag (layers on control-plane-api). |
| [docs/guides/kilo_swarm_scale.md](guides/kilo_swarm_scale.md) | KILO Swarm Scale Guide | Operational notes for experiments/bigswarm.py at 256+ live calls (Mercury-2 / Inception). |
| [docs/guides/kudbee_cli_enterprise_upgrade_quickstart.md](guides/kudbee_cli_enterprise_upgrade_quickstart.md) | KUDBEECLI enterprise upgrade (PR #196) | After merged #195 enterprise SDK lanes. |
| [docs/guides/kudbee_cli_phase2_quickstart.md](guides/kudbee_cli_phase2_quickstart.md) | KUDBEECLI Phase 2 quickstart (PR #178) | Hermetic deepen layer for the thinkbox CLI. Caps at CODE COMPLETE / TEST VERIFIED — not LIVE VERIFIED. |
| [docs/guides/kudbee_cli_phase3_quickstart.md](guides/kudbee_cli_phase3_quickstart.md) | KUDBEECLI Phase 3 quickstart (PR #180) | Hermetic deepen layer for the thinkbox CLI after merged #178 Phase 2. Caps at CODE COMPLETE / TEST VERIFIED — not... |
| [docs/guides/kudbee_sdk_enterprise_lr_energy_quickstart.md](guides/kudbee_sdk_enterprise_lr_energy_quickstart.md) | Kudbee SDK enterprise long-range energy quickstart (PR #195) | Twenty-five enterprise lanes on merged #193–#194 (lr-energy SDK + major fixes). |
| [docs/guides/kudbee_sdk_followup_w2_quickstart.md](guides/kudbee_sdk_followup_w2_quickstart.md) | Kudbee SDK follow-up wave 2 quickstart (PR #181) | Hermetic toolkit under thinkbox/kudbeesdkfollowupw2/ deepening merged #177 and #179. |
| [docs/guides/kudbee_sdk_followup_w3_major_fixes_quickstart.md](guides/kudbee_sdk_followup_w3_major_fixes_quickstart.md) | Kudbee SDK follow-up wave 3 major fixes (PR #192) | Hermetic major-fix pack for thinkbox/kudbeesdkfollowupw3majorfixes/ after merged #191. |
| [docs/guides/kudbee_sdk_followup_w3_quickstart.md](guides/kudbee_sdk_followup_w3_quickstart.md) | Kudbee SDK follow-up wave 3 quickstart (PR #191) | Hermetic toolkit under thinkbox/kudbeesdkfollowupw3/ deepening merged #177, #179, and #181 (wave 2). |
| [docs/guides/kudbee_sdk_longrange_energy_major_fixes_quickstart.md](guides/kudbee_sdk_longrange_energy_major_fixes_quickstart.md) | Kudbee SDK long-range energy major fixes quickstart (PR #194) | Twenty-five hermetic fixes on merged #193 (thinkbox/kudbeesdklongrangeenergy/). |
| [docs/guides/kudbee_sdk_longrange_energy_quickstart.md](guides/kudbee_sdk_longrange_energy_quickstart.md) | Kudbee SDK long-range + energy loops quickstart (PR #193) | Hermetic toolkit under thinkbox/kudbeesdklongrangeenergy/ deepening merged #191 and #192 (wave 3 + major fixes /... |
| [docs/guides/kudbee_sdk_quickstart.md](guides/kudbee_sdk_quickstart.md) | Kudbee SDK quickstart (PR #177) | Primary surface: Python package thinkbox/kudbeesdk/ and TypeScript apps/web/sdk/ for the kudbEE web app (apps/web). |
| [docs/guides/local-development.md](guides/local-development.md) | Local Development — Autonomous Workflow | Clone the repo and run the proof: |
| [docs/guides/local_think_box.md](guides/local_think_box.md) | Run a real Think Box on your laptop | This guide gets thinkbox run calling a real model, through governance, with a |
| [docs/guides/memory-layers.md](guides/memory-layers.md) | Memory Layers — Four-Layer Design | Think Box AI uses four memory layers instead of chat history. Each layer has distinct scope, lifetime, and write policy. |
| [docs/guides/model-examples.md](guides/model-examples.md) | Model Execution Examples | Real-world examples for executing models through Think Box AI. All examples assume environment variables are... |
| [docs/guides/multi-box-swarm-orchestration.md](guides/multi-box-swarm-orchestration.md) | Multi-Box Swarm Orchestration with Persistent Knowledge Fabric | PR #263 — The Information Outlives the Box |
| [docs/guides/multi-model-orchestrator.md](guides/multi-model-orchestrator.md) | Enterprise Multi-Model LLM Orchestrator | Intelligent routing across multiple LLM providers with real-time cost optimization, latency management, and... |
| [docs/guides/receipt_chain_deepen_quickstart.md](guides/receipt_chain_deepen_quickstart.md) | Receipt-chain deepen quickstart (PR #182) | Hermetic toolkit under thinkbox/receiptchaindeepen/ deepening receipt-chain, |
| [docs/guides/swarm-enterprise.md](guides/swarm-enterprise.md) | Enterprise-Grade Swarm Orchestration | Production-ready concurrent task execution with resilience, observability, and adaptive performance tuning. |
| [docs/guides/synthesis-calibration-arena.md](guides/synthesis-calibration-arena.md) | Synthesis Calibration Arena — Pre-Registered Research Result | A test of the PR #263 SynthesisEngine, not a demo of it. |
| [docs/guides/think_job_control_plane_ui.md](guides/think_job_control_plane_ui.md) | Think Job control-plane UI (PR #138, #139, #140) | Hermetic dashboard page for watching Think Job status via SSE (#137) with poll fallback. |
| [docs/guides/think_job_governed_run_major_fixes_quickstart.md](guides/think_job_governed_run_major_fixes_quickstart.md) | Think Job governed run major fixes (PR #188) | Hermetic 25-fix pack on rungoverned / F132 spine. Not LIVE VERIFIED — no Mercury calls in gate paths. |
| [docs/guides/think_job_hermetic_e2e_quickstart.md](guides/think_job_hermetic_e2e_quickstart.md) | Think Job hermetic e2e quickstart (PR #183) | Hermetic toolkit under thinkbox/thinkjobe2edeepen/ deepening Think Job |
| [docs/guides/think_job_lifecycle_fixes_quickstart.md](guides/think_job_lifecycle_fixes_quickstart.md) | Think Job lifecycle fix pack (PR #185) | Hermetic integration fixes under thinkbox/thinkjoblifecyclefixes/ bridging #183 e2e deepen, |
| [docs/guides/think_job_lifecycle_major_fixes_quickstart.md](guides/think_job_lifecycle_major_fixes_quickstart.md) | Think Job lifecycle major fixes (PR #189) | Hermetic 25-fix pack on F023 Think Job lifecycle + control-plane status handoff. Not LIVE VERIFIED. |
| [docs/guides/think_job_post_run_deepen_quickstart.md](guides/think_job_post_run_deepen_quickstart.md) | Think Job POST /run contract deepen quickstart (PR #184) | Hermetic toolkit under thinkbox/thinkjobpostrundeepen/ deepening POST /api/v1/run |
| [docs/guides/think_job_post_run_major_fixes_quickstart.md](guides/think_job_post_run_major_fixes_quickstart.md) | Think Job POST /run major fixes (PR #190) | Hermetic 25-fix pack on F131 POST /run contract after #184 deepen. Not LIVE VERIFIED. |
| [docs/guides/think_job_run_receipt_deepen_quickstart.md](guides/think_job_run_receipt_deepen_quickstart.md) | Think Job governed run receipt deepen (PR #186) | Hermetic toolkit under thinkbox/thinkjobrunreceiptdeepen/ for F133 HTTP run receipts |
| [docs/guides/think_job_status_stream.md](guides/think_job_status_stream.md) | Think Job status stream (hermetic SSE) | PR #137 adds Server-Sent Events (SSE) for Think Job status deltas so clients can |
| [docs/guides/upstash_box_access_verification.md](guides/upstash_box_access_verification.md) | Upstash Box access verification (PR #201) | Hermetic / operator path for proving whether this runtime can reach the existing Upstash Box. No new infrastructure.... |

## Runbooks

| File | Title | About |
|---|---|---|
| [docs/runbooks/branch-hygiene.md](runbooks/branch-hygiene.md) | Branch hygiene runbook (post-season #151) | Purpose: Safely list and delete merged remote agent branches (cursor/, optional convoy/) without touching protected... |
| [docs/runbooks/kilo-live-proof-readiness.md](runbooks/kilo-live-proof-readiness.md) | KILO Live-proof readiness runbook | Four-state: CODE COMPLETE / TEST VERIFIED on branch only. |
| [docs/runbooks/README.md](runbooks/README.md) | Runbooks | Operator and agent runbooks for Think Box AI / KILO. Hermetic checklists live here; |
| [docs/runbooks/think-job-pr185-local-environment.md](runbooks/think-job-pr185-local-environment.md) | Think Job PR #185 — local environment | Run the lifecycle fix pack on a developer machine. Hermetic only — no live Mercury or Box HTTP. |

## Roadmaps, status and continuity

| File | Title | About |
|---|---|---|
| [docs/CONTINUITY.md](CONTINUITY.md) | CONTINUITY — Canonical Agent State Artifact | Purpose: Every agent MUST read this before making changes. |
| [docs/known-defects.md](known-defects.md) | Known Defects | Auto-generated by test suite run. Honest accounting of failures that block green CI but are NOT caused by current work. |
| [docs/PREP.md](PREP.md) | PREP — Handoff & Readiness Brief | Architecture: apps/web/specialist-executor.ts consumes unchanged contracts/Director selection and runs each... |
| [docs/roadmap.md](roadmap.md) | KUdBEE — Implementation Roadmap | Architecture: Python backend (FastAPI + WebSocket + SSE) + React/Vite frontend + Ollama/OpenAI models |
| [docs/roadmaps/kilo-post-170-pr-roadmap.md](roadmaps/kilo-post-170-pr-roadmap.md) | KILO post-#170 PR roadmap (implementation slots) | GitHub #171 (merged) was the planning PR for this table. Implementation slots map to GitHub PR numbers from #172 onward. |
| [docs/roadmaps/ROADMAP.md](roadmaps/ROADMAP.md) | kudbEE Agent OS Dashboard — Development Roadmap | kudbEE Agent OS now features a professional-grade dashboard with enterprise-level features for managing, monitoring,... |
| [docs/STATUS.md](STATUS.md) | STATUS — Think Box AI | - CODE COMPLETE: Director selection now allocates contract-backed jobs to unique AgentSession IDs and confined... |

## Security and incidents

| File | Title | About |
|---|---|---|
| [docs/incidents/FORCE_PUSH_READY.md](incidents/FORCE_PUSH_READY.md) | FORCE-PUSH READY — SSH Key Purged | - Ran git filter-branch on 2,135 commits |
| [docs/incidents/INCIDENT_RESPONSE_2026-09-28.md](incidents/INCIDENT_RESPONSE_2026-09-28.md) | INCIDENT RESPONSE REPORT — 2026-09-28 | Severity: CRITICAL (REMEDIATED) |
| [docs/SECURITY.md](SECURITY.md) | Security Policy | If you discover a security vulnerability in Think Box AI, please report it by emailing |
| [docs/SECURITY_CHECKLIST.md](SECURITY_CHECKLIST.md) | SECURITY CHECKLIST — kudbEE Agent OS | Purpose: Every agent session MUST run this checklist before committing code or accessing production systems. |
| [docs/SECURITY_HARDENING_PR271.md](SECURITY_HARDENING_PR271.md) | PR 271 — Security Hardening & Incident Remediation | Severity: CRITICAL + HIGH |

## Project policies

| File | Title | About |
|---|---|---|
| [docs/CONTRIBUTING.md](CONTRIBUTING.md) | Contributing to Think Box AI | Thank you for your interest in contributing! Think Box AI is an enterprise-grade AI reasoning engine, and we... |

## Architecture, plans and deployment

| File | Title | About |
|---|---|---|
| [docs/architecture-v1.md](architecture-v1.md) | THINK BOX AI — Architecture v1 | Supersedes: None (first architecture document) |
| [docs/architecture/KUDBEE_AGENT_RUNTIME_CONTRACT.md](architecture/KUDBEE_AGENT_RUNTIME_CONTRACT.md) | KUDBEE Agent Runtime Contract | All environment variables currently available to the agent. No secret values are recorded — only variable names,... |
| [docs/deployment/DEPLOYMENT.md](deployment/DEPLOYMENT.md) | DEPLOYMENT.md — Running Think Box AI | git clone https://github.com/Kudbee-Studio/think-box-ai.git |
| [docs/plans/FEATURE1_PHASE2_INTEGRATION.md](plans/FEATURE1_PHASE2_INTEGRATION.md) | Feature 1 Phase 2: Server Integration Plan | import PersistenceLayer from './persistence.ts'; |
| [docs/project-foundation.md](project-foundation.md) | THINK BOX AI — Project Foundation | Repository: Kudbee-Studio/think-box-ai |

## Audits and reviews

| File | Title | About |
|---|---|---|
| [docs/audit/checklists/deploy-vercel.md](audit/checklists/deploy-vercel.md) | Vercel / preview deploy checklist | 1. No vercel.json in repository — routing/build not defined. |
| [docs/audit/checklists/kilo-api-ops-harden-pr157.md](audit/checklists/kilo-api-ops-harden-pr157.md) | Audit checklist — PR #157 api-ops-harden | - [ ] liveverified: false in checklist and audit pass |
| [docs/audit/checklists/kilo-control-plane-api-pr154.md](audit/checklists/kilo-control-plane-api-pr154.md) | PR #154 control-plane-api checklist | - [ ] thinkbox/kilocontrolplaneapi.py gate id control-plane-api |
| [docs/audit/checklists/kilo-control-plane-e2e-deepen-pr162.md](audit/checklists/kilo-control-plane-e2e-deepen-pr162.md) | KILO control-plane E2E deepen — PR #162 checklist | - [ ] Hermetic only — no Box/Mercury HTTP |
| [docs/audit/checklists/kilo-dashboard-receipt-chain-bind-pr156.md](audit/checklists/kilo-dashboard-receipt-chain-bind-pr156.md) | Audit checklist — PR #156 dashboard receipt-chain bind | - [ ] Gate id dashboard-receipt-chain-bind |
| [docs/audit/checklists/kilo-dashboard-slots-pr149.md](audit/checklists/kilo-dashboard-slots-pr149.md) | PR #149 dashboard-slots checklist | - [ ] thinkbox/kilodashboardslots.py gate module (dashboard-slots) |
| [docs/audit/checklists/kilo-end-link-api-ops-harden-pr161.md](audit/checklists/kilo-end-link-api-ops-harden-pr161.md) | Audit checklist — PR #161 end-link-api-ops-harden | - [ ] liveverified: false on audit pass and gate checklist |
| [docs/audit/checklists/kilo-end-link-deepen-pr158.md](audit/checklists/kilo-end-link-deepen-pr158.md) | PR #158 audit checklist — END LINK deepen | - [ ] liveverified: false in checklist and audit pass JSON |
| [docs/audit/checklists/kilo-end-link-operator-ux-pr159.md](audit/checklists/kilo-end-link-operator-ux-pr159.md) | Audit checklist — PR #159 end-link-operator-ux | - [ ] verifykiloendlinkoperatorux.py exit 0 in CI |
| [docs/audit/checklists/kilo-env-matrix-pr142.md](audit/checklists/kilo-env-matrix-pr142.md) | Checklist — KILO env-matrix gate (PR #142) | - [ ] thinkbox/kiloenvmatrix.py contract module present |
| [docs/audit/checklists/kilo-governance-evidence-live-proof-readiness-pr164.md](audit/checklists/kilo-governance-evidence-live-proof-readiness-pr164.md) | Audit checklist — PR #164 governance-evidence Live-proof readiness | - [ ] gateid: governance-evidence-live-proof-readiness |
| [docs/audit/checklists/kilo-governance-evidence-pr145.md](audit/checklists/kilo-governance-evidence-pr145.md) | Checklist — KILO governance-evidence gate (PR #145) | - [ ] thinkbox/kilogovernanceevidence.py contract module present |
| [docs/audit/checklists/kilo-live-proof-exec-pr150.md](audit/checklists/kilo-live-proof-exec-pr150.md) | Audit checklist — KILO live-proof-exec (PR #150) | - [ ] thinkbox/kiloliveproofexec.py present |
| [docs/audit/checklists/kilo-live-smoke-evidence-pr152.md](audit/checklists/kilo-live-smoke-evidence-pr152.md) | Audit checklist — PR #152 live-smoke-evidence (merged) | Operator write path continues in PR #153 (live-smoke-operator). |
| [docs/audit/checklists/kilo-live-smoke-operator-pr153.md](audit/checklists/kilo-live-smoke-operator-pr153.md) | Audit checklist — PR #153 live-smoke-operator | - [ ] thinkbox/kilolivesmokeoperator.py gate id live-smoke-operator |
| [docs/audit/checklists/kilo-mercury-hermetic-pr146.md](audit/checklists/kilo-mercury-hermetic-pr146.md) | Checklist — KILO mercury-hermetic gate (PR #146) | - [ ] thinkbox/kilomercuryhermetic.py contract module present |
| [docs/audit/checklists/kilo-post-season-harden-pr151.md](audit/checklists/kilo-post-season-harden-pr151.md) | Audit checklist — post-season harden (PR #151) | - [ ] thinkbox/kilopostseasonharden.py layers on live-proof-exec |
| [docs/audit/checklists/kilo-proof-schema-pr148.md](audit/checklists/kilo-proof-schema-pr148.md) | Checklist — KILO proof-schema gate (PR #148) | - [ ] thinkbox/kiloproofschema.py gate module (proof-schema) |
| [docs/audit/checklists/kilo-receipt-chain-end-link-docs-pr160.md](audit/checklists/kilo-receipt-chain-end-link-docs-pr160.md) | Audit checklist — PR #160 receipt-chain-end-link-docs | Hermetic docs + audit pack after #159. No live HTTP. |
| [docs/audit/checklists/kilo-receipt-chain-end-link-era-close-pr162.md](audit/checklists/kilo-receipt-chain-end-link-era-close-pr162.md) | Audit checklist — PR #162 receipt-chain-end-link-era-close | - [ ] liveverified: false on era pack, checklist, and pr162 pass |
| [docs/audit/checklists/kilo-receipt-chain-etag-pr155.md](audit/checklists/kilo-receipt-chain-etag-pr155.md) | PR #155 audit checklist — receipt-chain-etag | - [ ] liveverified: false on checklist + audit pass |
| [docs/audit/checklists/kilo-spine-pr141.md](audit/checklists/kilo-spine-pr141.md) | Checklist — KILO Live-proof readiness spine (PR #141) | - [ ] docs/runbooks/kilo-live-proof-readiness.md headings complete |
| [docs/audit/checklists/kilo-substrate-checklist-pr143.md](audit/checklists/kilo-substrate-checklist-pr143.md) | Checklist — KILO substrate-checklist gate (PR #143) | - [ ] thinkbox/kilosubstratechecklist.py contract module present |
| [docs/audit/checklists/kilo-swarm-instrumentation-pr147.md](audit/checklists/kilo-swarm-instrumentation-pr147.md) | Checklist — KILO swarm-instrumentation gate (PR #147) | - [ ] thinkbox/kiloswarminstrumentation.py gate module (swarm-instrumentation) |
| [docs/audit/checklists/repo-wide.md](audit/checklists/repo-wide.md) | Repo-wide audit checklist (PR #125) | - [ ] Layer imports respect AGENTS.md §1.1 (no cross-layer runtime imports) |
| [docs/audit/README.md](audit/README.md) | Repository audit ledger (PR #125) | Persistent, git-tracked audit state for Kudbee Studio / Think Box AI. Conversations and CI runs are ephemeral; this... |
| [docs/audits/upm-package-manager-integration-audit.md](audits/upm-package-manager-integration-audit.md) | UPM Package-Manager Integration Audit | Research Question: Can UPM (the lightweight TypeScript package manager) become an optional Think Box primitive for... |
| [docs/RED/agents.md](RED/agents.md) | RED: Agent Coordination |  |
| [docs/RED/architecture.md](RED/architecture.md) | RED: Core Architecture |  |
| [docs/RED/index.md](RED/index.md) | RED: Master Index | New agent starting work: |
| [docs/RED/README.md](RED/README.md) | RED: RED File System Index | RED is a structured orientation format for agents entering the project. |
| [docs/RED/scheduler.md](RED/scheduler.md) | RED: Scheduler Module |  |

## Research and strategy

| File | Title | About |
|---|---|---|
| [docs/research/2026-10-01-think-box-findings.md](research/2026-10-01-think-box-findings.md) | Think Box findings — 2026-10-01 | Source document for ADR 029. Each row has two parts, kept apart on purpose: |
| [docs/research/277-vinext-software-factory-experiment.md](research/277-vinext-software-factory-experiment.md) | Research #277: Vinext-Style Software-Factory Experiment | Experiment: Can Think Box reproduce autonomous software-factory workflows described in Cloudflare's Vinext announcement? |
| [docs/research/RESEARCH.md](research/RESEARCH.md) | RESEARCH.md — Doginals Indexer-Split Thesis | Different Doginals/DRC-20 indexers disagree on which deployment transaction is |
| [docs/strategy/THINK_TOKEN_STRATEGY.md](strategy/THINK_TOKEN_STRATEGY.md) | THINK Token & Training Strategy | This file is about the THNK economic token (staking, rewards, votes, paying for compute) and a plan to fine-tune a |

## Archive

| File | Title | About |
|---|---|---|
| [docs/archive/CI_TEST.md](archive/CI_TEST.md) | CI Test |  |
| [docs/archive/PHASE9_INDEX.md](archive/PHASE9_INDEX.md) | ThinkBox Phase 9: The Archival Index — 55 Innovations | Strategy: Equal-opportunity collaborative agent architecture |
| [docs/archive/TEST_SYNC.md](archive/TEST_SYNC.md) | Local sync test - Mon Sep 28 15:51:57 UTC 2026 |  |

## Other documents in docs/

| File | Title | About |
|---|---|---|
| [docs/ASCLEPIUS_MEDICATION.md](ASCLEPIUS_MEDICATION.md) | ASCLEPIUS — Medication Label Research Agent | ASCLEPIUS is a named, tool-scoped agent lane (apps/web/agent.ts, AGENTPROFILES.asclepius), |
| [docs/cnc-integration-proof.md](cnc-integration-proof.md) | THINK CNC AI — Integration + Enterprise Proof Report | Branch: kilo/adept-marsh-qiq (ahead of origin by 2 commits) |
| [docs/cnc-roi-report.md](cnc-roi-report.md) | CNC ROI & Evidence Report | Module: thinkbox/cnc/ |
| [docs/DASHBOARD_BUILDOUT.md](DASHBOARD_BUILDOUT.md) | Dashboard → Middleware → Backend — Build-Out List | servers, no framework, no daemon fleet. Everything below is stdlib or a single |
| [docs/dependencies/UPGRADE-2026-10-01.md](dependencies/UPGRADE-2026-10-01.md) | Dependency upgrade — 2026-10-01 | Branch chore/deps-upgrade, one PR. Scope: apps/web npm dependencies, Python version floors and dev |
| [docs/disruptor-evaluation.md](disruptor-evaluation.md) | Disruptor + Verifier Evaluation Harness | Companion to: KUDBEE white paper §11 (Evaluation agenda) and |
| [docs/evidence/adr-029-p1.md](evidence/adr-029-p1.md) | ADR 029 P1 + P2 — evidence | Date: 2026-10-01. Scope: Think Token lifecycle with permanent TT- ids, a real extractor and challenge, a score... |
| [docs/evidence/docs-sync-2026-10-01.md](evidence/docs-sync-2026-10-01.md) | Docs sync — 2026-10-01 | Rides along with the ADR-029 P1/P2 PR (no separate PR, one push). No code behavior changes come from this part. |
| [docs/gcode-checklist.md](gcode-checklist.md) | G-Code "Read This Block" Checklist — One-Page Safety Check | Read this before running ANY G-code program. |
| [docs/gcode-mastery.md](gcode-mastery.md) | G-Code Mastery Curriculum — 2-Week Daily Drills | For: Dominick (CNC beginner → solid) |
| [docs/harvest-replay.md](harvest-replay.md) | Harvest & Replay | Harvest once on the GPU; re-score forever offline. This closes the loop |
| [docs/HERMES_ALGORAND.md](HERMES_ALGORAND.md) | HERMES — Algorand Read-Only Research Agent | HERMES is a named, tool-scoped agent lane inside kudbEE Agent OS (apps/web/agent.ts, |
| [docs/kilo-live-proof-arc.md](kilo-live-proof-arc.md) | KILO → Live proof readiness arc (#141–#150) | Owner: Founder-directed arc (2026-09-23) |
| [docs/kudbee-control-fabric.md](kudbee-control-fabric.md) | KUDBEE Control Fabric — Implementation Reference | Companion to: the KUDBEE white paper (working draft) |
| [docs/PHASE3_OPTIMIZATION_RESILIENCE.md](PHASE3_OPTIMIZATION_RESILIENCE.md) | PHASE 3: Optimization & Resilience | Timestamp: 2026-09-27 |
| [docs/PR101_BYOC_THINK_STASH.md](PR101_BYOC_THINK_STASH.md) | PR #101 — BYOC Mercury-2 + Upstash THINK Stash × Proof Bind (×10) | Branch: feat/byoc-think-stash-mercury-upstash-x10 |
| [docs/PR102_BOX_MERCURY_LIVE.md](PR102_BOX_MERCURY_LIVE.md) | PR #102 — Upstash Box + Inception Mercury-2 Live Experiment | Branch: feat/byoc-box-mercury-live |
| [docs/PR103_BOX_MERCURY_PERSISTENT.md](PR103_BOX_MERCURY_PERSISTENT.md) | PR #103 — Live Box + Mercury-2 Experiment: Persistent Results & Comparison | Branch: feat/byoc-box-mercury-live-v2 |
| [docs/PR111_CONTROL_PLANE_DRY_RUN.md](PR111_CONTROL_PLANE_DRY_RUN.md) | PR #111 — Demo-in-10 Control Plane Dry Run | GitHub PR: #111 (draft) |
| [docs/PR272_DASHBOARD_REDESIGN.md](PR272_DASHBOARD_REDESIGN.md) | PR 272 — Dashboard CSS & Layout Redesign | Focus: Premium UI aesthetics, improved metrics hierarchy, better info scannability |
| [docs/PR273_PERSISTENT_MEMORY_PHP.md](PR273_PERSISTENT_MEMORY_PHP.md) | PR 273 — Persistent Memory via PHP | Currently, the kudbEE Agent OS dashboard loses all state when: |
| [docs/PR274_STREAMING_UI_TOKENS.md](PR274_STREAMING_UI_TOKENS.md) | PR 274 — Token-by-Token Streaming UI | Currently, agent thoughts appear as complete blocks after generation completes. This creates: |
| [docs/PR275_MCP_INTEGRATION.md](PR275_MCP_INTEGRATION.md) | PR 275 — MCP Server Integration: Interactive Plugin Discovery & Selection | 🎯 /skills → Browse 100+ MCP skills (pop-up menu) |
| [docs/PR289_GIT_INTEGRATION.md](PR289_GIT_INTEGRATION.md) | PR #289 — Git Repository Integration | The Git integration works in three layers: |
| [docs/savanna-solana-plan.md](savanna-solana-plan.md) | SAVANNAH — Solana Wallet & Token Ecosystem Plan | Build a production-grade Solana wallet and token ecosystem into Think Box AI. The wallet (codename Savannah)... |
| [docs/stress_test_framework.md](stress_test_framework.md) | Concurrency Stress Testing Framework | The thinkbox.concurrentgoals module now includes a comprehensive stress testing framework for evaluating concurrent... |
| [docs/think-burst-protocol.md](think-burst-protocol.md) | THINK Burst Protocol | Goal: maximize THINK-token quality per GPU-dollar via short, bounded |
| [docs/THINKBOXMD_REPORT.md](THINKBOXMD_REPORT.md) | THINKBOXMD-RESEARCH — End-to-End Research Workflow Test | Runner: KILO (cloud agent sandbox) |

## Agent definitions

| File | Title | About |
|---|---|---|
| [.agents/snapshots/AGENTS.md.20260927-2230.md](../.agents/snapshots/AGENTS.md.20260927-2230.md) | AGENTS.md — THINK BOX AI | Purpose: This file defines the rules that every agent (human or AI) working |
| [agents/chronological/000-pre-agent-architecture.md](../agents/chronological/000-pre-agent-architecture.md) | Pre-Agent Architecture Baseline — KILO Platform Before PR88 | Purpose: Documents the state of the KILO platform immediately before PR88 (Agent Framework initialization). This... |
| [agents/chronological/001-pr88-initialization.md](../agents/chronological/001-pr88-initialization.md) | PR88: KILO Cloud Agent Framework Initialization | Branch: kilo/bubbly-eagle-hg7 |
| [agents/chronological/002-pr89-autonomous-core.md](../agents/chronological/002-pr89-autonomous-core.md) | PR89: Autonomous Agent Core — Implementation Plan | Branch: feat/kilo-agent-core-pr89 |
| [agents/chronological/003-pr90-multi-agent-clustering.md](../agents/chronological/003-pr90-multi-agent-clustering.md) | PR90: Multi-Agent Clustering — Implementation Plan | Branch: feat/kilo-agent-clustering-pr90 |
| [agents/chronological/004-pr91-distributed-governance.md](../agents/chronological/004-pr91-distributed-governance.md) | PR91: Distributed Governance — Implementation Plan | Branch: pushed to main as d803cd2 (no dedicated branch) |
| [agents/chronological/005-pr92-agent-marketplace.md](../agents/chronological/005-pr92-agent-marketplace.md) | PR92: Agent Marketplace — Implementation Plan | Branch: pushed to main as c4c326c (no dedicated branch) |
| [agents/core/agent-categories.md](../agents/core/agent-categories.md) | KILO Cloud Agent Categories — Taxonomy & Classification | Purpose: Defines the canonical taxonomy for KILO Cloud Agents. Every agent MUST declare its category at... |
| [agents/core/agent-kernel.md](../agents/core/agent-kernel.md) | KILO Cloud Agent Kernel — Core Definition | Purpose: Defines the agent kernel — the foundational abstraction that all KILO Cloud Agents implement. This is the... |
| [agents/core/agent-lifecycle.md](../agents/core/agent-lifecycle.md) | KILO Cloud Agent Lifecycle — State Machine & Transitions | Purpose: Defines the complete lifecycle of a KILO Cloud Agent from spawn to termination, including all valid state... |
| [agents/core/cloud-interaction-model.md](../agents/core/cloud-interaction-model.md) | KILO Cloud Agent Cloud Interaction Model — Environment & Platform Integration | Purpose: Defines how KILO Cloud Agents interact with cloud environments — provisioning, networking, storage,... |
| [agents/core/execution-boundaries.md](../agents/core/execution-boundaries.md) | KILO Cloud Agent Execution Boundaries — Sandbox & Resource Isolation | Purpose: Defines the execution boundaries, sandboxing model, and resource isolation guarantees for KILO Cloud... |
| [agents/governance/approval-gates.md](../agents/governance/approval-gates.md) | KILO Cloud Agent Approval Gates — Specifications | Purpose: Defines the approval gate system for KILO Cloud Agents. Approval gates enforce human-in-the-loop and... |
| [agents/governance/audit-logging.md](../agents/governance/audit-logging.md) | KILO Cloud Agent Audit Logging — Format & Verification | Purpose: Defines the audit logging format, storage, verification, and retention requirements for KILO Cloud Agents.... |
| [agents/governance/compliance-model.md](../agents/governance/compliance-model.md) | KILO Cloud Agent Compliance Model — Expectations & Audit | Purpose: Defines the compliance expectations for KILO Cloud Agents and the audit framework that validates adherence.... |
| [agents/governance/governance-hooks.md](../agents/governance/governance-hooks.md) | KILO Cloud Agent Governance Hooks — Integration Points | Purpose: Defines the governance integration points that all KILO Cloud Agents must implement. These hooks connect... |
| [agents/README.md](../agents/README.md) | KILO Cloud Agent Framework — Documentation Index | Purpose: This directory contains the complete documentation suite for the KILO Cloud Agent Framework, introduced in... |

## Evidence and data documents

| File | Title | About |
|---|---|---|
| [data/evals/disruptor_eval_20260912_201005.md](../data/evals/disruptor_eval_20260912_201005.md) | Disruptor Evaluation Report — kudbee-disruptor-eval | Timestamp: 2026-09-12T20:10:05.978469+00:00 |
| [data/evals/disruptor_eval_20260912_230127.md](../data/evals/disruptor_eval_20260912_230127.md) | Disruptor Evaluation Report — kudbee-disruptor-eval | Timestamp: 2026-09-12T23:01:27.696940+00:00 |
| [data/evals/harvest_report.md](../data/evals/harvest_report.md) | Harvest Replay Report | Timestamp: 2026-09-12T20:30:37.364557+00:00 |
| [data/findings/dogi_indexer_split.md](../data/findings/dogi_indexer_split.md) | DOGI Indexer Split | Verdict: Cannot verify via public APIs alone |
| [data/findings/job_compare_dogi_dbit.md](../data/findings/job_compare_dogi_dbit.md) | DOGI vs DBIT Compare | Verdict: Cannot verify via public APIs alone |
| [data/findings/swarm_proof_artifacts_invalid.md](../data/findings/swarm_proof_artifacts_invalid.md) | Finding: 14 of 38 committed swarm proof artifacts fail the repo's own validator | Discovered by: repo audit (thinkbox.cliinspect.validateproofdocument) |
| [data/findings/thinkboxmd_upstash_vector_defect.md](../data/findings/thinkboxmd_upstash_vector_defect.md) | Finding: Upstash Vector sync is incompatible with the configured dense index | Discovered by: experiments/thinkboxmdresearch.py (THINKBOXMD-RESEARCH run) |
| [data/findings/wallet_DDCkpBDN.md](../data/findings/wallet_DDCkpBDN.md) | Wallet DDCkpBDN | Verdict: Cannot scan wallet |
| [data/kilo_dashboard_slots/fixtures/README.md](../data/kilo_dashboard_slots/fixtures/README.md) | KILO dashboard-slots hermetic fixtures (PR #149) | - valid.json must pass validateslotregistrydocument. |
| [data/kilo_live_proof_exec/fixtures/README.md](../data/kilo_live_proof_exec/fixtures/README.md) | KILO live-proof-exec fixtures (PR #150) | Hermetic execution-plan JSON for validateexecutionplandocument. |
| [data/kilo_live_smoke_evidence/fixtures/README.md](../data/kilo_live_smoke_evidence/fixtures/README.md) | KILO live smoke evidence fixtures (PR #152) | Hermetic JSON fixtures for thinkbox.kilolivesmokeevidence.validatesmokeevidencedocument. |
| [data/kilo_live_smoke_operator/fixtures/README.md](../data/kilo_live_smoke_operator/fixtures/README.md) | KILO live-smoke operator fixtures (PR #153) | Hermetic operator-path fixtures for thinkbox.kilolivesmokeoperator.runoperatorfixturesuite. |
| [data/kilo_post_season_harden/README.md](../data/kilo_post_season_harden/README.md) | Post-season harden checklist (PR #151) | Frozen operator checklist consumed by \thinkbox/kilopostseasonharden.py\. |
| [data/kilo_proof_schema/fixtures/README.md](../data/kilo_proof_schema/fixtures/README.md) | KILO proof-schema hermetic fixtures (PR #148) | JSON fixtures for validateproofdocument and runfixturesuite. |
| [data/thinkboxmd/PRODUCTIZATION_AUDIT.md](../data/thinkboxmd/PRODUCTIZATION_AUDIT.md) | Think Box AI — Productization Audit | Auditor: Claude Haiku 4.5 |
| [data/thinkboxmd/thinkboxmd_20260915_231732.md](../data/thinkboxmd/thinkboxmd_20260915_231732.md) | THINKBOXMD-RESEARCH — thinkboxmd20260915231732 | Synthetic only: True \| Not clinical: True |

## Tests and examples

| File | Title | About |
|---|---|---|
| [examples/gcode/README.md](../examples/gcode/README.md) | G-Code Examples — Dry-Run Guide | NEVER run unproven G-code on metal. |
| [tests/e2e/README.md](../tests/e2e/README.md) | End-to-end tests (Phase 1 — hermetic) | Phase 1 mock-provider coverage lives here. No network, no Upstash/Mercury credentials, no live substrate. |
