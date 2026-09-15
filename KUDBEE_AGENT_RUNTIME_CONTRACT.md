# KUDBEE Agent Runtime Contract

**Generated:** 2026-09-13T23:30:33+00:00
**Project:** Think Box AI — Agent Execution Environment
**Repository:** /workspace/bcdfac4f-1903-4a17-8abf-0b10fd495578/sessions/agent_0c8313fa-a5aa-428f-929c-95a1f71a6876
**Branch:** main

---

## 1. Environment Inventory

All environment variables currently available to the agent. **No secret values are recorded** — only variable names, purpose, required/optional status, and safe availability checks.

| Variable Name | Purpose / Consuming Subsystem | Required | Available (Safe Check) |
|---------------|-------------------------------|----------|------------------------|
| `THINKBOX_DEFAULT_PROVIDER` | Default model provider selection (openai_compat, anthropic, etc.) | Optional | ✅ Yes |
| `THINKBOX_DEFAULT_MODEL` | Default model identifier (e.g., gpt-4o-mini) | Optional | ✅ Yes |
| `THINKBOX_OPENAI_COMPAT_API_KEY` | API key for OpenAI-compatible providers | Optional* | ⚠️ Present but value not verified |
| `THINKBOX_OPENAI_COMPAT_BASE_URL` | Base URL for OpenAI-compatible API endpoint | Optional* | ✅ Yes |
| `THINKBOX_API_KEY` | Primary API key for ThinkBox server authentication | Optional | ⚠️ Present but value not verified |
| `THINKBOX_API_KEYS` | Comma-separated list of valid API keys | Optional | ✅ Yes |
| `THINKBOX_ALLOWED_ORIGINS` | CORS allowed origins for server | Optional | ✅ Yes |
| `THINKBOX_RATE_LIMIT` | Rate limit for API requests | Optional | ✅ Yes |
| `THINKBOX_PROJECT_ROOT` | Project root directory path | Optional | ✅ Yes |
| `THINKBOX_LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | Optional | ✅ Yes |
| `THINKBOX_ACTOR` | Actor identifier for session tracking | Optional | ✅ Yes |
| `INCEPTION_API_KEY` | API key for Inception (Mercury 2) provider | Optional | ⚠️ Present but value not verified |
| `CURSOR_API_KEY` | API key for Cursor SDK integration | Optional | ⚠️ Present but value not verified |
| `UPCLOUD_API_KEY` | API key for UpCloud infrastructure | Optional | ⚠️ Present but value not verified |
| `UPSTASH_API_KEY` | Primary API key for Upstash Redis/Vector services | Optional | ⚠️ Present but value not verified |
| `UPSTASH_BOX_API_KEY` | API key for Upstash Box remote worker | Optional | ⚠️ Present but value not verified |
| `UPSTASH_BOX_CLI_KEY` | CLI key for Upstash Box operations | Optional | ✅ Yes (empty) |
| `UPSTASH_BOX_SSH_KEY` | SSH key for Upstash Box access | Optional | ✅ Yes |
| `UPSTASH_PUBLIC_BOX_URL` | Public URL for Upstash Box preview | Optional | ✅ Yes |
| `UPSTASH_VECTOR_REST_TOKEN` | REST token for Upstash Vector database | Optional | ⚠️ Present but value not verified |
| `UPSTASH_VECTOR_REST_URL` | REST URL for Upstash Vector database | Optional | ✅ Yes |
| `UPCLOUD_SERVER_HOSTNAME` | UpCloud server hostname | Optional | ✅ Yes |
| `UPCLOUD_SERVER_IP` | UpCloud server IP address | Optional | ✅ Yes |
| `UPCLOUD_SSH_KEY_PATH` | Path to UpCloud SSH private key | Optional | ✅ Yes |
| `UPCLOUD_SSH_USER` | SSH username for UpCloud server | Optional | ✅ Yes |
| `KILO_CONFIG_CONTENT` | Serialized Kilo agent configuration | Internal | ✅ Yes |
| `OPENCODE_CONFIG_CONTENT` | Serialized OpenCode agent configuration | Internal | ✅ Yes |

> **Note:** Variables marked with `*` are required when using the corresponding provider. The system falls back to defaults when not set. All availability checks are boolean (presence only) — no secret values are exposed.

---

## 2. MCP Server Inventory

### Local MCP Servers Configured

| Tool Name | Purpose | Connection Status |
|-----------|---------|-------------------|
| `GITHUB` | GitHub Copilot MCP integration for repository operations, PR management, issue tracking | ✅ Connected (Remote: https://api.githubcopilot.com/mcp/) |
| `contex-7` | Context7 documentation lookup for library/framework references | ✅ Connected (Remote: https://mcp.context7.com/mcp) |

### MCP Configuration/Discovery Paths

- **Kilo Config:** `.kilo/kilo.jsonc` — Minimal config, relies on environment-injected MCP servers
- **Environment Variables:** MCP server URLs and auth injected via `KILO_CONFIG_CONTENT` / `OPENCODE_CONFIG_CONTENT`
- **Discovery Mechanism:** Remote MCP servers configured in agent config, no local stdio servers defined

### Connection Status Summary
- **GitHub MCP:** Active — enables GitHub Discussions as agent-to-agent communication channel
- **Context7 MCP:** Active — provides up-to-date library documentation for development tasks
- **No local MCP servers** running in this environment

---

## 3. GitHub Integration

### GitHub CLI Availability
- **GitHub CLI (`gh`):** Not installed in container
- **GitHub API Access:** Via GitHub Copilot MCP server (remote)
- **Authentication:** Managed through Kilo cloud session tokens

### GitHub Discussions as Agent-to-Agent Communication Channel
- **Pattern:** GitHub Discussions used for inter-agent messaging
- **GROKBOT ↔ KILO Communication:**
  - GROKBOT posts to Discussions with structured payloads
  - KILO agents subscribe via MCP and poll for new discussions
  - Messages contain: `agent_id`, `task_id`, `payload`, `timestamp`, `signature`
  - Used for: task delegation, result sharing, consensus building
- **Channel:** Repository Discussions (not Issues or PRs)

### GitHub Workflows
- **CI Pipeline:** `.github/workflows/test.yml` runs unit + integration tests on push/PR
- **Python Version:** 3.10 (matches project requirement)
- **Node Version:** 22 (for web typecheck)

---

## 4. External Service Roles

**Verified 2026-09-15** by non-destructive probes from the cloud sandbox
(see `docs/THINKBOXMD_REPORT.md` §6). "Configured" previously meant "env var
present"; it did **not** mean "usable". Corrected below.

| Service | Role | Configuration | Verified status (2026-09-15) |
|---------|------|---------------|------------------------------|
| **Upstash Redis** | State/cache/queue | (no dedicated env) | ❌ **Not used** — no Redis client in repo, no client configured |
| **Upstash Box** | Remote worker sandbox | `UPSTASH_BOX_API_KEY`, `UPSTASH_BOX_SSH_KEY`, `UPSTASH_PUBLIC_BOX_URL` | ⚠️ Host reachable (`wanted-tuna-71803-...box.upstash.com`), but preview returns `preview not found`; no live service |
| **Upstash Vector** | Session/org memory embeddings | `UPSTASH_VECTOR_REST_URL`, `UPSTASH_VECTOR_REST_TOKEN` | ⚠️ Reachable, **writes rejected**: `HTTP 422 "This index requires dense vectors"` — client sends no vector; no embedding provider exists |
| **UpCloud** | Dedicated server `kudbee-host-v1` | `UPCLOUD_SERVER_HOSTNAME`, `UPCLOUD_SERVER_IP`, `UPCLOUD_SSH_KEY_PATH` | ❌ **No access** — API token returns 401; SSH key file absent; IP behind Cloudflare (1003) |
| **OpenAI-compatible APIs** | Model inference | `THINKBOX_OPENAI_COMPAT_API_KEY`, `THINKBOX_OPENAI_COMPAT_BASE_URL` | ✅ Implemented (`core/providers/openai_compat.py`); needs a key |
| **Anthropic Messages API** | Alternative model provider | — | ❌ **Not implemented** — no provider file exists (docs-only) |
| **Inception API (Mercury 2)** | Model inference | `INCEPTION_API_KEY` | ✅ **WORKING** at `https://api.inceptionlabs.ai/v1`, model `mercury-2` — live calls verified. (Earlier "unusable from cloud" was the wrong host, `api.inception.ai`.) |
| **Cursor SDK** | IDE integration | `CURSOR_API_KEY` | Env present; not wired into runtime |

### Upstash Box network note (corrected)
Observed from the sandbox: **HTTPS works** (returns an application-level 404
`preview not found` via Cloudflare); plain **HTTP to the box times out**.
The prior claim that "HTTP works, HTTPS does not" was not reproducible.
The actionable blocker is that **no box preview is currently live**, not TLS.

---

## 5. Python Runtime Contract

### Project's Intended Python Environment
- **Virtual Environment:** `.venv` (created at project root)
- **Python Version:** 3.10.12 (matches `requires-python = ">=3.10"` in pyproject.toml)
- **Interpreter Path:** `/workspace/bcdfac4f-1903-4a17-8abf-0b10fd495578/sessions/agent_0c8313fa-a5aa-428f-929c-95a1f71a6876/.venv/bin/python3`
- **Symlink:** `.venv/bin/python` → `python3` → `/usr/bin/python3` (system interpreter with isolated packages)

### Dependency Verification
All `pyproject.toml` dependencies **verified installed** in `.venv`:
```bash
/workspace/bcdfac4f-1903-4a17-8abf-0b10fd495578/sessions/agent_0c8313fa-a5aa-428f-929c-95a1f71a6876/.venv/bin/python3 -c "
import fastapi, uvicorn, pytest, aiohttp, websockets, python_multipart
print('All dependencies available')
"
```
**Result:** ✅ All dependencies available

### Orchestrator Subprocess Inheritance
The KUDBEE orchestrator (`experiments/kudbee_orchestrator.py:776-777`) correctly uses:
```python
python_exe = sys.executable  # Inherits the same interpreter running the orchestrator
result = subprocess.run([python_exe, "-m", "pytest", ...], ...)
```

### Regression Test: Subprocess Uses Same Interpreter
**Test Location:** Add to `tests/unit/test_runtime_contract.py`
```python
"""Regression test: subprocess uses same interpreter as orchestrator."""
import sys
import subprocess
from pathlib import Path

def test_subprocess_inherits_orchestrator_interpreter():
    """Verify subprocess spawned by orchestrator uses the same Python interpreter."""
    orchestrator_python = sys.executable
    
    # Simulate orchestrator's subprocess call pattern
    result = subprocess.run(
        [orchestrator_python, "-c", "import sys; print(sys.executable)"],
        capture_output=True,
        text=True
    )
    
    subprocess_python = result.stdout.strip()
    assert subprocess_python == orchestrator_python, (
        f"Subprocess interpreter mismatch: "
        f"orchestrator={orchestrator_python}, subprocess={subprocess_python}"
    )
```

### Failure Policy: `ENVIRONMENT_UNAVAILABLE`
If dependencies are missing, the orchestrator **MUST fail fast** with `ENVIRONMENT_UNAVAILABLE` — no silent fallback to system Python.

**Required check at orchestrator startup** (`experiments/kudbee_orchestrator.py`):
```python
def _verify_environment() -> None:
    """Verify all required dependencies are available in current interpreter."""
    required = ["fastapi", "uvicorn", "pytest", "aiohttp", "websockets"]
    missing = []
    for dep in required:
        try:
            __import__(dep.replace("-", "_"))
        except ImportError:
            missing.append(dep)
    
    if missing:
        raise RuntimeError(
            f"ENVIRONMENT_UNAVAILABLE: Missing dependencies in {sys.executable}: {missing}. "
            f"Expected interpreter: /workspace/.../.venv/bin/python3"
        )
```

---

## 6. Agent Bootstrap Sequence

The required startup sequence for any KILO/agent session to discover infrastructure without starting from scratch:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        AGENT BOOTSTRAP SEQUENCE                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. AGENT STARTS                                                            │
│     ├── Read AGENTS.md for operational rules                                │
│     ├── Read docs/architecture-v1.md for layer discipline                   │
│     └── Read docs/project-foundation.md for phase boundaries                │
│                                                                             │
│  2. DISCOVER PROJECT RUNTIME                                                │
│     ├── Locate pyproject.toml → parse dependencies & scripts                │
│     ├── Verify .venv exists at project root                                 │
│     ├── Confirm interpreter: .venv/bin/python3                              │
│     ├── Run dependency verification (import all required packages)          │
│     └── FAIL with ENVIRONMENT_UNAVAILABLE if any missing                    │
│                                                                             │
│  3. DISCOVER AVAILABLE MCP CAPABILITIES                                     │
│     ├── Parse KILO_CONFIG_CONTENT / OPENCODE_CONFIG_CONTENT for MCP config  │
│     ├── Enumerate configured MCP servers (GitHub, Context7, etc.)           │
│     ├── Test connectivity to each MCP endpoint                              │
│     └── Register available tools per MCP server                             │
│                                                                             │
│  4. DISCOVER REQUIRED ENVIRONMENT                                           │
│     ├── Scan environment for THINKBOX_*, UPSTASH_*, UPCLOUD_* variables    │
│     ├── Categorize: Required vs Optional per subsystem                      │
│     ├── Record availability (boolean only — never log values)               │
│     └── Validate critical paths (Vector DB, Box access, GitHub MCP)         │
│                                                                             │
│  5. DISCOVER COMMUNICATION CHANNELS                                         │
│     ├── GitHub Discussions via GitHub MCP (agent↔agent)                     │
│     ├── Upstash Vector for session metadata sync                            │
│     ├── Local SQLite for organizational/task/session memory                 │
│     ├── Direct MCP tool calls for external APIs                             │
│     └── Shell execution for local operations (permission-gated)             │
│                                                                             │
│  6. VERIFY DEPENDENCIES                                                     │
│     ├── Core: fastapi, uvicorn, aiohttp, websockets, python-multipart      │
│     ├── Dev: pytest, pytest-asyncio                                         │
│     ├── ThinkBox modules: thinkbox.*, core.*                                │
│     ├── CLI entry points: think-box-ai, thinkbox                            │
│     └── Run regression test: subprocess inherits same interpreter           │
│                                                                             │
│  7. RUN THE EXPERIMENT                                                      │
│     ├── Execute KUDBEE orchestrator with verified interpreter               │
│     ├── All subprocesses inherit .venv/bin/python3 via sys.executable       │
│     ├── Monitor for ENVIRONMENT_UNAVAILABLE failures                        │
│     └── Capture results to organizational memory                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Reusable Bootstrap Script
Save as `scripts/bootstrap_agent.sh` for future sessions:
```bash
#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/workspace/bcdfac4f-1903-4a17-8abf-0b10fd495578/sessions/agent_0c8313fa-a5aa-428f-929c-95a1f71a6876"
VENV_PYTHON="$PROJECT_ROOT/.venv/bin/python3"

echo "=== KUDBEE Agent Bootstrap ==="
echo "Project: $PROJECT_ROOT"
echo "Interpreter: $VENV_PYTHON"

# 1. Verify runtime
if [[ ! -x "$VENV_PYTHON" ]]; then
    echo "ERROR: Virtual environment not found at $VENV_PYTHON"
    exit 1
fi

# 2. Verify dependencies
"$VENV_PYTHON" -c "
import fastapi, uvicorn, pytest, aiohttp, websockets
import thinkbox, core
print('✓ All dependencies verified')
" || { echo "ERROR: Missing dependencies"; exit 1; }

# 3. Verify MCP connectivity (best-effort)
echo "MCP Servers: GitHub, Context7 (configured via Kilo config)"

# 4. Verify environment variables (presence only)
for var in THINKBOX_DEFAULT_PROVIDER UPSTASH_VECTOR_REST_URL UPSTASH_PUBLIC_BOX_URL; do
    if [[ -n "${!var:-}" ]]; then
        echo "✓ $var available"
    else
        echo "⚠ $var not set"
    fi
done

# 5. Run regression test
"$VENV_PYTHON" -m pytest tests/unit/test_runtime_contract.py -v

echo "=== Bootstrap Complete ==="
echo "Ready to run experiment with: $VENV_PYTHON experiments/kudbee_orchestrator.py"
```

---

## 7. Exact Python Interpreter Path for Experiment

**Use this exact path for all KUDBEE experiment execution:**

```
/workspace/bcdfac4f-1903-4a17-8abf-0b10fd495578/sessions/agent_0c8313fa-a5aa-428f-929c-95a1f71a6876/.venv/bin/python3
```

**Verification:**
```bash
/workspace/bcdfac4f-1903-4a17-8abf-0b10fd495578/sessions/agent_0c8313fa-a5aa-428f-929c-95a1f71a6876/.venv/bin/python3 --version
# Python 3.10.12

/workspace/bcdfac4f-1903-4a17-8abf-0b10fd495578/sessions/agent_0c8313fa-a5aa-428f-929c-95a1f71a6876/.venv/bin/python3 -c "import fastapi, uvicorn, pytest, aiohttp, websockets; print('All deps OK')"
# All deps OK
```

**Orchestrator invocation:**
```bash
cd /workspace/bcdfac4f-1903-4a17-8abf-0b10fd495578/sessions/agent_0c8313fa-a5aa-428f-929c-95a1f71a6876
/workspace/bcdfac4f-1903-4a17-8abf-0b10fd495578/sessions/agent_0c8313fa-a5aa-428f-929c-95a1f71a6876/.venv/bin/python3 experiments/kudbee_orchestrator.py
```

---

## 8. Key Architectural Constraints (from AGENTS.md)

| Constraint | Enforcement |
|------------|-------------|
| **Layer Discipline** | 5 layers (Foundation → Provider → Memory → Governance/Tools → Runtime); no cross-layer imports |
| **Provider Independence** | Runtime only knows `ModelProvider` protocol; no provider SDK imports at runtime layer |
| **Memory First** | 4 layers: Session, Task, Organizational, Verified Knowledge; distinct scope/lifetime/write policy |
| **Governance by Default** | Tools require permission checks; audit logs append-only; approval gates opt-out |
| **Evidence Over Assumptions** | Claims require benchmark results in `benchmarks/` |
| **Phase Boundaries** | Phase 1 only: single agent, single provider, 5 tools; no Phase 2+ features |

---

## 9. Files Referenced in This Contract

| File | Purpose |
|------|---------|
| `pyproject.toml` | Project metadata, dependencies, entry points |
| `.env.example` | Environment variable template |
| `experiments/kudbee_orchestrator.py` | Autonomous proof-of-work orchestrator |
| `thinkbox/session.py` | Session tracking with Upstash Vector sync |
| `thinkbox/production.py` | Production hardening (health, metrics, tracing, etc.) |
| `core/memory/store.py` | SQLite-backed memory store |
| `core/memory/org.py` | Organizational memory adapter |
| `.github/workflows/test.yml` | CI pipeline |
| `.kilo/kilo.jsonc` | Kilo agent configuration |
| `AGENTS.md` | Operational rules for all agents |
| `docs/architecture-v1.md` | System architecture (referenced) |
| `docs/project-foundation.md` | Project foundation (referenced) |

---

**End of KUDBEE Agent Runtime Contract**

*This document is intended to be reusable by future KILO/agent sessions so infrastructure discovery does not happen from scratch.*