# Think Box AI

**Governed agent execution for the enterprise** — goals decompose into tasks, tools run behind permission checks, outcomes land in layered memory and tamper-evident ledgers, and every claim carries an evidence label. The [KUDBEE control fabric](docs/kudbee-control-fabric.md) (admission gates, Think Boxes, ActionLedger) keeps **draft/simulate** the default until a valid governance token is present.

| | |
|---|---|
| **Repository** | [Kudbee-Studio/think-box-ai](https://github.com/Kudbee-Studio/think-box-ai) |
| **Agent rules** | [AGENTS.md](AGENTS.md) |
| **Live chronicle** | [docs/CONTINUITY.md](docs/CONTINUITY.md) |
| **Architecture** | [docs/architecture-v1.md](docs/architecture-v1.md) |
| **Enterprise editing** | [docs/guides/kilo_enterprise_editing.md](docs/guides/kilo_enterprise_editing.md) |

---

## Documentation hub

### Platform & governance

| Resource | Description |
|----------|-------------|
| [Architecture v1](docs/architecture-v1.md) | Layered runtime, provider independence, memory model |
| [Project foundation](docs/project-foundation.md) | Phase boundaries, dependency policy |
| [KUDBEE control fabric](docs/kudbee-control-fabric.md) | Admission, workspaces, occupancy mesh, ledger |
| [KILO Live-proof readiness](docs/runbooks/kilo-live-proof-readiness.md) | Hermetic spine, operator runbooks, honesty gates |
| [Enterprise editing guide](docs/guides/kilo_enterprise_editing.md) | Chronicle, audit passes, single-theme PR discipline |
| [Post-#170 PR roadmap](docs/roadmaps/kilo-post-170-pr-roadmap.md) | Sequenced implementation slots |
| [Audit index](docs/audit/README.md) | Checklists and pass JSON under `docs/audit/passes/` |
| [Known defects](docs/known-defects.md) | Tracked gaps with evidence |
| [Docker enterprise](docs/guides/docker_enterprise.md) | API image, compose profiles, hermetic spine container |
| [Deployment](docs/guides/deployment.md) | Production TLS, reverse proxy, compose quick start |

### Operator surfaces

| Surface | Quickstart |
|---------|------------|
| **KUDBEECLI** (inspect, persist, REPL) | Phase 1 on `main`; Phase 2 [#178](https://github.com/Kudbee-Studio/think-box-ai/pull/178) · Phase 3 [#180](https://github.com/Kudbee-Studio/think-box-ai/pull/180) — [CLI Phase 2 guide](docs/guides/kudbee_cli_phase2_quickstart.md) · [Phase 3 guide](docs/guides/kudbee_cli_phase3_quickstart.md) |
| **Kudbee SDK** (Python + web) | App [#177](https://github.com/Kudbee-Studio/think-box-ai/pull/177) · Follow-up [#179](https://github.com/Kudbee-Studio/think-box-ai/pull/179) · Wave 2 [#181](https://github.com/Kudbee-Studio/think-box-ai/pull/181) (draft) — [SDK guide](docs/guides/kudbee_sdk_quickstart.md) · [Follow-up W2 guide](docs/guides/kudbee_sdk_followup_w2_quickstart.md) |
| **Control plane UI** | [Think Job status](docs/guides/think_job_status_stream.md) · [Control plane API](docs/guides/kilo_control_plane_api.md) · static assets in `public/control-plane/` |
| **Swarm & experiments** | [Swarm scale guide](docs/guides/kilo_swarm_scale.md) · `experiments/` proofs · [THINK burst protocol](docs/think-burst-protocol.md) |

### Agents & manufacturing

| Resource | Description |
|----------|-------------|
| [agents/README.md](agents/README.md) | KILO cloud agent framework (protocol-first) |
| [CNC ROI report](docs/cnc-roi-report.md) | Manufacturing intelligence platform evidence |
| [ADR 001 — CNC](docs/decisions/001-cnc-manufacturing.md) | Human-in-the-loop execution policy |

---

## Enterprise pillars

```text
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│   GOVERNANCE    │   │    EVIDENCE     │   │   OPERATIONS    │
│ AdmissionGate   │   │ Four-state caps │   │ Spine + gates   │
│ ActionLedger    │   │ Audit JSON      │   │ Hermetic CI     │
│ Permissions     │   │ Proof artifacts │   │ Secret scan     │
└────────┬────────┘   └────────┬────────┘   └────────┬────────┘
         │                     │                     │
         └─────────────────────┴─────────────────────┘
                    Think Box + Memory layers
```

1. **Governance by default** — Side effects pass admission; audit logs are append-only. Tools without an explicit permission level are `RESTRICTED`. See [AGENTS.md §1.4](AGENTS.md).
2. **Evidence over assumptions** — Capability claims use labels: *simulated*, *inferred*, *verified*, *physically_measured*. Hermetic repo work caps at **CODE COMPLETE / TEST VERIFIED** unless founder-run Live proof artifacts exist (`live_verified: false` on spine audits until then).
3. **Operational repeatability** — Fast spine verify, scoped lint execute, unittest discovery, and doc secret scan run on every meaningful change. Nested control-plane e2e is **opt-in** (`verify_kilo_spine.py --e2e`), not default PR CI.

---

## Release train (KILO post-#170)

| Milestone | PR | State | Entry point |
|-----------|-----|--------|-------------|
| Beyond-KILO lint readiness | [#170](https://github.com/Kudbee-Studio/think-box-ai/pull/170) | Merged | `scripts/verify_kilo_beyond_kilo_lint.py` |
| Implementation roadmap | [#171](https://github.com/Kudbee-Studio/think-box-ai/pull/171) | Merged | [roadmap](docs/roadmaps/kilo-post-170-pr-roadmap.md) |
| CI spine-trust | [#172](https://github.com/Kudbee-Studio/think-box-ai/pull/172) | Merged | [runbook H31](docs/runbooks/kilo-live-proof-readiness.md) |
| Chronicle honesty | [#173](https://github.com/Kudbee-Studio/think-box-ai/pull/173)–[#176](https://github.com/Kudbee-Studio/think-box-ai/pull/176) | Merged | README + spine Markdown |
| Lint scope waves 1–2 | [#174](https://github.com/Kudbee-Studio/think-box-ai/pull/174)–[#175](https://github.com/Kudbee-Studio/think-box-ai/pull/175) | Merged | [enterprise editing](docs/guides/kilo_enterprise_editing.md) |
| Kudbee SDK app | [#177](https://github.com/Kudbee-Studio/think-box-ai/pull/177) | Merged | `thinkbox/kudbee_sdk/` · [guide](docs/guides/kudbee_sdk_quickstart.md) |
| KUDBEECLI Phase 2 | [#178](https://github.com/Kudbee-Studio/think-box-ai/pull/178) | Merged | `thinkbox/cli_phase2/` · [guide](docs/guides/kudbee_cli_phase2_quickstart.md) |
| Kudbee SDK follow-up | [#179](https://github.com/Kudbee-Studio/think-box-ai/pull/179) | Merged | `thinkbox/kudbee_sdk_followup/` · `apps/web/sdk/followup.ts` |
| KUDBEECLI Phase 3 | [#180](https://github.com/Kudbee-Studio/think-box-ai/pull/180) | Merged | `thinkbox/cli_phase3/` · [guide](docs/guides/kudbee_cli_phase3_quickstart.md) |
| Kudbee SDK follow-up wave 2 | [#181](https://github.com/Kudbee-Studio/think-box-ai/pull/181) | **Draft** | `thinkbox/kudbee_sdk_followup_w2/` · [W2 guide](docs/guides/kudbee_sdk_followup_w2_quickstart.md) |

**How we ship:** One **single-theme** implementation PR at a time. No combined post-#N umbrella lanes by default. Authoritative counts and blockers: [docs/CONTINUITY.md](docs/CONTINUITY.md) · [docs/STATUS.md](docs/STATUS.md).

---

## Quick start

### Prerequisites

- Python ≥ 3.10
- [pip](https://pip.pypa.io/)

### Clone & install

```bash
git clone https://github.com/Kudbee-Studio/think-box-ai.git
cd think-box-ai
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### Operator verification (hermetic)

```bash
python3 -m unittest discover -s tests -t .
PYTHONUNBUFFERED=1 python3 -u scripts/verify_kilo_spine.py
pip install -e ".[lint]"
KILO_BEYOND_KILO_LINT_EXECUTE=1 python3 scripts/verify_kilo_beyond_kilo_lint.py
python3 scripts/verify_kilo_pr177_kudbee_sdk_app.py
python3 scripts/verify_kilo_pr178_kudbee_cli_phase2.py
python3 scripts/verify_kilo_pr179_kudbee_sdk_followup.py
python3 scripts/verify_kilo_pr180_kudbee_cli_phase3.py
python3 scripts/verify_kilo_pr181_kudbee_sdk_followup_w2.py
python3 scripts/verify_kilo_pr182_receipt_chain_deepen.py
python3 scripts/verify_kilo_pr183_think_job_hermetic_e2e.py
python3 scripts/verify_kilo_pr184_think_job_post_run_deepen.py
python3 scripts/scan_doc_secrets.py
```

### KUDBEECLI (inspection)

```bash
python3 -m thinkbox swarm status
python3 -m thinkbox ledger verify
python3 -m thinkbox env status
python3 -m thinkbox cli health    # Phase 2+ deepen
```

### Kudbee SDK (hermetic demo)

```bash
python3 examples/kudbee_sdk_followup_quickstart.py
python3 examples/kudbee_sdk_followup_w2_quickstart.py
python3 examples/receipt_chain_deepen_quickstart.py
python3 examples/think_job_hermetic_e2e_quickstart.py   # when #183 branch present
```

### Control fabric demo

```bash
python3 examples/control_fabric_demo.py
```

### Docker (API + optional UI)

Full guide: [docs/guides/docker_enterprise.md](docs/guides/docker_enterprise.md).

```bash
export THINKBOX_API_KEY="$(python3 -c "import secrets; print('tb_' + secrets.token_urlsafe(24))")"
make docker-contract    # hermetic file contract (no daemon)
make docker-build       # requires Docker engine
make docker-up          # API on http://127.0.0.1:8000/health
make docker-hermetic      # spine verify inside container
```

---

## Architecture (summary)

Layered stack — details in [architecture v1](docs/architecture-v1.md):

```text
Layer 5: Agent implementations (KILO agent era, CNC, marketplace)
Layer 4: Runtime (engine, decomposer, swarm, scheduler)
Layer 3: Governance & tools (permissions, audit, admission)
Layer 2: Memory (session, task, organizational, verified knowledge)
Layer 1: Providers (OpenAI-compatible, Anthropic protocol, local — config swap)
Layer 0: Foundation (config, schemas, logging, structured errors)
```

**Execution substrate (2026-09-17):** [Upstash Box](docs/CONTINUITY.md) as primary execution path from env (`UPSTASH_PUBLIC_BOX_URL`); UpCloud remains **control-plane read-only** (no SSH execution path). Deep execution milestones, swarm proofs, and DAG verified runs are recorded in [CONTINUITY](docs/CONTINUITY.md) with artifact hashes — not repeated here.

**Phase 9 modules** (`coalition`, `consensus`, `economy`, `intelligence`, `benchmark`, `session`) — index: [PHASE9_INDEX.md](PHASE9_INDEX.md).

---

## Repository layout

```text
think-box-ai/
├── thinkbox/           # Engine, KILO gates, SDK, CLI phases, scheduler, CNC
├── core/               # Foundation, providers, memory, runtime, governance
├── backend/            # FastAPI control plane + API v1 routes
├── apps/web/           # TypeScript 7 web shell + Kudbee SDK TS packages
├── public/control-plane/   # Hermetic operator HTML/JS
├── scripts/            # verify_kilo_* spine and PR gates
├── tests/              # unit · integration · e2e (e2e opt-in on spine)
├── docs/               # Architecture, runbooks, guides, audit passes
├── experiments/        # Swarm, research, and live proof harnesses
└── data/               # Manifests, fixtures, thinkboxmd artifacts
```

---

## Testing & quality

| Check | Command |
|-------|---------|
| Full suite | `python3 -m unittest discover -s tests -t .` |
| KILO spine (fast) | `python3 -u scripts/verify_kilo_spine.py` |
| Spine + nested e2e | `python3 -u scripts/verify_kilo_spine.py --e2e` |
| Scoped lint execute | `KILO_BEYOND_KILO_LINT_EXECUTE=1 python3 scripts/verify_kilo_beyond_kilo_lint.py` |
| Doc secrets | `python3 scripts/scan_doc_secrets.py` |

Do not treat README test counts as authoritative if they drift from [CONTINUITY](docs/CONTINUITY.md).

---

## Web runtime (TypeScript 7)

```bash
cd apps/web
npm install
npm run typecheck      # tsgo --noEmit
npm start              # Node 22+ with type stripping
```

SDK exports: [`apps/web/sdk/index.ts`](apps/web/sdk/index.ts) (base client, follow-up, follow-up W2).

---

## Demos

| Demo | Script / doc |
|------|----------------|
| Control plane dry-run (hermetic) | [PR111 doc](docs/PR111_CONTROL_PLANE_DRY_RUN.md) · `scripts/demo_in_10_control_plane_dry_run.sh` |
| Burst / mock vLLM smoke | `scripts/demo_in_10_control_plane.sh` |
| THINKBOXMD research workflow | `experiments/thinkboxmd_research.py` · [report](docs/THINKBOXMD_REPORT.md) |

---

## Honest capability notes

- **Live model provider:** Inception **Mercury 2** (`api.inceptionlabs.ai/v1`) is used in bounded experiments; providers are swappable via config. See [CONTINUITY](docs/CONTINUITY.md) for current blockers (Box token, concurrency characterization).
- **Simulated economics:** `thinkbox/economy.py` is in-process accounting — not on-chain settlement.
- **Upstash Vector:** historical dense-index defect documented in `data/findings/thinkboxmd_upstash_vector_defect.md` (fix tracked in chronicle).
- **Four-state ladder:** CODE_COMPLETE → TEST_VERIFIED → LIVE_VERIFIED → PRODUCTION_READY — hermetic CI never advances the last two without founder artifacts.

---

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md). Use conventional commits (`type(scope): description`), one logical PR per theme, target `main`, and paste the PR URL in your handoff.

---

## License

[MIT License](LICENSE).
