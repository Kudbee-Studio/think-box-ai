# THINK BOX AI

**Governed agent execution** for the [KUDBEE](https://www.kudbee.xyz) product line (this repository was formerly discussed as *thinkTokens*). Goals decompose into tasks, tools run behind permission checks, outcomes land in layered memory and tamper-evident ledgers, and capability claims carry explicit evidence labels.

| | |
|---|---|
| **GitHub** | [Kudbee-Studio/think-box-ai](https://github.com/Kudbee-Studio/think-box-ai) |
| **Agent & contributor rules** | [AGENTS.md](AGENTS.md) |
| **Architecture** | [docs/architecture-v1.md](docs/architecture-v1.md) |
| **Documentation index** | [docs/INDEX.md](docs/INDEX.md) (generated; run `python3 scripts/generate_docs_index.py` after moving `.md` files) |
| **Current status** | [STATUS.md](STATUS.md) · [docs/CONTINUITY.md](docs/CONTINUITY.md) |

---

## What this repository is

THINK BOX AI is an **agent OS**: a Python runtime (`thinkbox/`, `core/`) with governance (admission gates, append-only ledgers, tool permissions), a **FastAPI control plane** (`backend/`), and a **local-first operator dashboard** plus `kudbee` CLI (`apps/web/`). Models are **provider-swappable** (Ollama, OpenAI-compatible APIs, Inception Mercury-2 via env config)—no provider SDKs in the runtime layer.

**Think Tokens** (durable, reviewable lessons from finished runs) live in SQLite at `apps/web/data/think-tokens.db` by default; the dashboard **Think Tokens** view and `kudbee tokens list|show|links` read the same store ([AGENTS.md §0.6](AGENTS.md)).

Hermetic development and CI cap most repo work at **CODE COMPLETE / TEST VERIFIED** unless founder-run live proof artifacts exist; see [STATUS.md](STATUS.md) for the four-state ladder.

---

## Repository layout

```text
think-box-ai/
├── thinkbox/              # Engine, scheduler, KILO gates, CLI modules, CNC, cloud execution
├── core/                  # Foundation, providers, memory, governance primitives
├── think_box_ai/          # Packaged CLI entry (`thinkbox`, `think-box-ai`)
├── backend/               # FastAPI app (control plane, governed `/api/v1/*`)
├── apps/web/              # Agent OS: Express 5 + WebSocket dashboard, worker agent, Think Tokens
├── public/control-plane/  # Static operator HTML/JS (Think Job status, receipts, etc.)
├── scripts/               # `verify_kilo_*` spine gates, doc secret scan, demos
├── tests/                 # unit · integration · e2e (Python)
├── docs/                  # Architecture, ADRs, guides, runbooks, audit passes
├── experiments/           # Swarm and research harnesses (not required for a minimal local run)
└── data/                  # Fixtures, manifests, proof artifacts (git-tracked samples)
```

---

## Prerequisites

| Component | Requirement |
|-----------|-------------|
| **Python** | ≥ 3.10 |
| **Node.js** (dashboard / web tests only) | ≥ 22.6 ([`apps/web/package.json`](apps/web/package.json)) |
| **Optional** | [Ollama](https://ollama.com) for local models; Docker for [containerized API](docs/guides/docker_enterprise.md) |

---

## Install

```bash
git clone https://github.com/Kudbee-Studio/think-box-ai.git
cd think-box-ai
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Copy environment template (names only—never commit real secrets):

```bash
cp .env.example .env
# Edit .env with your keys; see "Configuration" below and docs/guides/environmental_variables_matrix.md
```

**Web shell** (separate from Python venv):

```bash
cd apps/web
npm install
```

> Some FastAPI tests use Starlette’s `TestClient` and need **`httpx`** installed in the Python environment if you run the full Python suite (see [docs/dependencies/UPGRADE-2026-10-01.md](docs/dependencies/UPGRADE-2026-10-01.md)).

---

## Run locally

### 1. Governed CLI (Python, real or mock provider)

See [docs/guides/local_think_box.md](docs/guides/local_think_box.md).

```bash
# After setting provider env vars (e.g. THINKBOX_DEFAULT_PROVIDER, INCEPTION_API_KEY, or Ollama)
python3 -m thinkbox.cli model check
python3 -m thinkbox.cli run --goal "What is 17 * 23? Reply with only the number."
python3 scripts/prove_think_box_local.py   # six governed-path checks; exit 0 = pass
```

Inspection commands (hermetic / read-only): `python3 -m thinkbox swarm status`, `ledger verify`, `env status` — see [AGENTS.md — KUDBEECLI](AGENTS.md).

### 2. FastAPI backend (control plane)

```bash
make serve
# or: python3 -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Health: `GET http://127.0.0.1:8000/health` (exact routes depend on auth configuration; see backend docs).

### 3. Agent OS dashboard + worker (`kudbee`)

Binds to **loopback by default** (`LISTEN_ADDR` / `127.0.0.1`; see [AGENTS.md](AGENTS.md) guardrails).

```bash
cd apps/web
npm start          # same as npm run dev — port 3000 unless PORT is set
```

Optional launcher from repo root: `apps/web/bin/kudbee` (symlink into `PATH` as documented in [AGENTS.md — kudbEE Agent OS](AGENTS.md)).

List Think Tokens without starting the server (reads SQLite):

```bash
cd apps/web && node --experimental-strip-types bin/kudbee tokens list
```

---

## Test

Commands below match scripts in the repo; run from the repository root unless noted.

| What | Command |
|------|---------|
| **Python unit** (subset) | `make test` |
| **Python full suite** | `python3 -m unittest discover -s tests -t .` |
| **KILO spine (fast)** | `python3 -u scripts/verify_kilo_spine.py` |
| **Doc secret scan** | `python3 scripts/scan_doc_secrets.py` |
| **Web typecheck** | `cd apps/web && npm run typecheck` |
| **Web tests** (mocked model, hermetic) | `cd apps/web && npm test` |
| **Lint (optional)** | `make lint` · scoped KILO lint: `pip install -e ".[lint]"` then `KILO_BEYOND_KILO_LINT_EXECUTE=1 python3 scripts/verify_kilo_beyond_kilo_lint.py` |

Authoritative test counts and blockers: [STATUS.md](STATUS.md) and [docs/CONTINUITY.md](docs/CONTINUITY.md)—do not treat static numbers in this README as canonical if they drift.

### Continuous integration

GitHub Actions workflow [`.github/workflows/test.yml`](.github/workflows/test.yml) on `push` / `pull_request` to `main`, `feat/**`, `session/**`, and `cursor/**`:

1. `npm install` in `apps/web`
2. `npm run typecheck` (TypeScript 7 / `tsgo`)
3. `npm test` (hermetic Agent OS tests)

---

## Configuration

**Source of truth for names:** [`.env.example`](.env.example) (copy to `.env` at repo root; `apps/web/server.ts` loads repo-root `.env` server-side).

**Grouped reference (no secret values):** [docs/guides/environmental_variables_matrix.md](docs/guides/environmental_variables_matrix.md).

| Area | Variables (set only in environment or `.env`) |
|------|-----------------------------------------------|
| **Python providers** | `THINKBOX_DEFAULT_PROVIDER`, `THINKBOX_DEFAULT_MODEL`, `THINKBOX_OPENAI_COMPAT_API_KEY`, `THINKBOX_OPENAI_COMPAT_BASE_URL`, `THINKBOX_OLLAMA_BASE_URL`, `INCEPTION_API_KEY`, `THINKBOX_EMBED_MODEL` |
| **API / security** | `THINKBOX_API_KEY`, `THINKBOX_API_KEYS`, `THINKBOX_ALLOWED_ORIGINS`, `THINKBOX_RATE_LIMIT`, `THINKBOX_PROJECT_ROOT`, `THINKBOX_LOG_LEVEL` |
| **Upstash Box / vector** | `UPSTASH_PUBLIC_BOX_URL`, `UPSTASH_PUBLIC_BOX_TOKEN`, `UPSTASH_VECTOR_REST_URL`, `UPSTASH_VECTOR_REST_TOKEN`, `KUDBEE_VECTOR_NAMESPACE` |
| **Agent OS web** | `PORT`, `LISTEN_ADDR`, `INCEPTION_API_KEY`, `INCEPTION_BASE_URL`, `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, `XAI_API_KEY`, `XAI_BASE_URL`, `KUDBEE_CLOUD_ROUTING` (`off` keeps registry order), `KUDBEE_CLOUD_FAILOVER` (`off` disables failover), `OLLAMA_BASE_URL`, `KUDBEE_DATA_DIR`, `KUDBEE_MEMORY_DIR`, `KUDBEE_WORKSPACE_DIR`, `KUDBEE_DAILY_BUDGET_USD`, `KUDBEE_THINK_TOKEN_DB`, `THINKBOX_BACKEND_URL`, `THINKBOX_API_KEY`, `THINKBOX_LOCAL_MODEL` (alias: `KUDBEE_LOCAL_MODEL`) |
| **UpCloud (governed SSH substrate)** | `UPCLOUD_SERVER_IP`, `UPCLOUD_SSH_USER`, `UPCLOUD_SSH_KEY_PATH`, `THINKBOX_UPCLOUD_API_TOKEN` — see [AGENTS.md §13.5](AGENTS.md) |
| **Algorand (read-only / optional testnet signing)** | `ALGORAND_ALGOD_URL_*`, `ALGORAND_INDEXER_URL_*`, `KUDBEE_ENABLE_ALGORAND_TESTNET_SIGNING`, `KUDBEE_ALGORAND_TESTNET_MNEMONIC` |

Never commit `.env`, `.db`, API keys, or mnemonics. Dashboard defaults to **localhost-only** binding and Host/Origin gates; do not expose the operator UI without authentication ([AGENTS.md](AGENTS.md)).

---

## Documentation map

| Topic | Location |
|-------|----------|
| **All Markdown files** | [docs/INDEX.md](docs/INDEX.md) |
| **Architecture & layers** | [docs/architecture-v1.md](docs/architecture-v1.md) · [docs/project-foundation.md](docs/project-foundation.md) |
| **Decision records (ADRs)** | [docs/decisions/](docs/decisions/) (35+ records; e.g. CNC, cloud execution, Think Token lifecycle) |
| **KUDBEE control fabric** | [docs/kudbee-control-fabric.md](docs/kudbee-control-fabric.md) |
| **Local Think Box / CLI** | [docs/guides/local_think_box.md](docs/guides/local_think_box.md) |
| **Docker / deployment** | [docs/guides/docker_enterprise.md](docs/guides/docker_enterprise.md) · [docs/guides/deployment.md](docs/guides/deployment.md) |
| **KILO live-proof spine** | [docs/runbooks/kilo-live-proof-readiness.md](docs/runbooks/kilo-live-proof-readiness.md) |
| **Contributing** | [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) |
| **KILO post-#170 PR roadmap** | [docs/roadmaps/kilo-post-170-pr-roadmap.md](docs/roadmaps/kilo-post-170-pr-roadmap.md) |

---

## Docker (optional)

```bash
export THINKBOX_API_KEY="$(python3 -c "import secrets; print('tb_' + secrets.token_urlsafe(24))")"
make docker-contract    # hermetic file contract (no daemon)
make docker-build       # requires Docker
make docker-up          # API on http://127.0.0.1:8000/health
```

Details: [docs/guides/docker_enterprise.md](docs/guides/docker_enterprise.md).

---

## Contributing

Read [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) and [AGENTS.md](AGENTS.md). Use conventional commits (`type(scope): description`), one focused PR per theme, target `main`. AI agents must follow the evidence and CI-cost rules in AGENTS.md §0.

---

## License

[MIT License](LICENSE).
