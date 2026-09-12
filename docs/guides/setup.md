# Local Development Setup Guide

**Last updated:** 2026-08-28

This guide walks through setting up THINK BOX AI for local development. All commands are copy-paste ready.

---

## Prerequisites

| Requirement | Version | Required | Notes |
|-------------|---------|----------|-------|
| Python | 3.10+ | Yes | Core runtime |
| Node.js | 18+ | No | Only for deprecated web frontend |
| Ollama | latest | No | Optional, for local model providers |

Verify your Python version:

```bash
python3 --version
```

---

## Installation

Clone the repository and install with development dependencies:

```bash
git clone <repository-url>
cd thinkbox-ai
pip install -e ".[dev]"
```

This installs the package in editable mode along with `pytest` and `pytest-asyncio` for testing.

---

## Running Tests

Run unit tests (fast, no I/O):

```bash
python -m pytest tests/unit/
```

Run integration tests (requires SQLite):

```bash
python -m pytest tests/integration/
```

Run all tests:

```bash
python -m pytest tests/unit/ tests/integration/
```

Run with verbose output:

```bash
python -m pytest tests/unit/ tests/integration/ -v
```

---

## Configuring Providers

Providers are configured via `THINKBOX_*` environment variables. Configuration is hierarchical:

```
System defaults (in code)
    ↓
Project config (pyproject.toml [tool.thinkbox])
    ↓
Environment vars (THINKBOX_*)
    ↓
Runtime overrides (CLI flags)
```

### Available Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `THINKBOX_DEFAULT_PROVIDER` | `openai_compat` | Provider name (see `pyproject.toml`) |
| `THINKBOX_DEFAULT_MODEL` | `gpt-4o-mini` | Model identifier |
| `THINKBOX_MAX_THINK_BOX_DEPTH` | `2` | Maximum Think Box nesting depth |
| `THINKBOX_AUDIT_LOG_RETENTION_DAYS` | `90` | Days to retain audit log entries |

### Provider-Specific Variables

For OpenAI-compatible providers:

```bash
export THINKBOX_DEFAULT_PROVIDER=openai_compat
export THINKBOX_DEFAULT_MODEL=gpt-4o-mini
export OPENAI_API_KEY=sk-your-key-here
export OPENAI_BASE_URL=https://api.openai.com/v1
```

For Ollama (local models):

```bash
export THINKBOX_DEFAULT_PROVIDER=openai_compat
export THINKBOX_DEFAULT_MODEL=llama3
export OPENAI_BASE_URL=http://localhost:11434/v1
export OPENAI_API_KEY=ollama
```

For Anthropic:

```bash
export THINKBOX_DEFAULT_PROVIDER=anthropic
export THINKBOX_DEFAULT_MODEL=claude-3-sonnet-20240229
export ANTHROPIC_API_KEY=sk-ant-your-key-here
```

---

## Running the FastAPI Backend

Install backend dependencies:

```bash
pip install -r backend/requirements.txt
```

Start the development server:

```bash
uvicorn backend.main:app --reload
```

The API will be available at `http://localhost:8000`.

---

## Running the CLI

Display system information:

```bash
python -m think_box_ai --info
```

The CLI entry point is configured in `pyproject.toml` as `think-box-ai`.

---

## Running the Web Frontend (Deprecated)

The Node.js web frontend is deprecated. It is retained for reference but not actively maintained.

Install dependencies and start:

```bash
npm --prefix apps/web install
npm --prefix apps/web dev
```

---

## Running the Python Runtime Bridge

The runtime bridge executes a goal directly through the Python runtime without the API layer:

```bash
python apps/web/runtime_bridge.py '<goal>'
```

Example:

```bash
python apps/web/runtime_bridge.py 'Create a summary of the project structure'
```

---

## Project Structure Overview

```
thinkbox-ai/
├── apps/
│   ├── cli/                    # CLI interface
│   └── web/                    # Web interface (deprecated)
├── core/
│   ├── runtime/                # Agent Runtime (agent, thinkbox, planner, actor, observer)
│   ├── memory/                 # Memory Subsystem (session, task, org)
│   ├── providers/              # Provider Abstraction (OpenAI-compatible, Anthropic)
│   ├── tools/                  # Tool Registry (file, shell, http, memory tools)
│   └── governance/             # Governance (audit, permissions, approval)
├── agents/                     # Agent Implementations
├── backend/                    # FastAPI backend
├── benchmarks/                 # Benchmark Suite
├── docs/
│   ├── architecture-v1.md      # System architecture
│   ├── project-foundation.md   # Project foundation
│   ├── improvements.md         # Improvement proposals
│   ├── roadmap.md              # Development roadmap
│   ├── guides/
│   │   └── setup.md            # This file
│   └── decisions/              # Architecture Decision Records
├── tests/
│   ├── unit/                   # Unit tests
│   ├── integration/            # Integration tests
│   └── e2e/                    # End-to-end tests
├── pyproject.toml              # Project configuration
├── AGENTS.md                   # Development rules
└── README.md
```

---

## Troubleshooting

### Python version errors

Ensure Python 3.10+ is installed. On Ubuntu/Debian:

```bash
sudo apt update
sudo apt install python3.10 python3.10-venv python3.10-dev
```

### Import errors after installation

Verify the package is installed in editable mode:

```bash
pip show think-box-ai
```

### Provider connection errors

Check that environment variables are set correctly and the provider endpoint is reachable:

```bash
echo $THINKBOX_DEFAULT_PROVIDER
echo $OPENAI_BASE_URL
```

### Test failures

Ensure dev dependencies are installed:

```bash
pip install -e ".[dev]"
```

---

## See Also

- [Architecture v1](../architecture-v1.md) — System structure and design
- [Project Foundation](../project-foundation.md) — Project goals and principles
- [AGENTS.md](../../AGENTS.md) — Development rules and conventions
- [Improvements](../improvements.md) — Proposed improvements and changes
- [Roadmap](../roadmap.md) — Development roadmap and status
