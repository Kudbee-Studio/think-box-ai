# ADR 001: Compute Fabric and Secrets Abstraction

**Date:** 2026-08-28
**Status:** Accepted

## Context

The runtime is a skeleton: `Planner`, `Actor`, `Agent`, and `Observer` exist but
are not wired to a real provider. The `ModelProvider` protocol and
`ProviderRegistry` are defined in `core/providers/base.py`, and an
OpenAI-compatible provider exists in `core/providers/openai_compat.py`, but no
provider is instantiated or passed into the agent loop. Meanwhile, the backend
layer has a working Ollama client (`backend/models/ollama_client.py`) with
streaming, completion, and model listing — but it lives outside the provider
abstraction and cannot be selected at runtime.

Two problems must be solved:

1. **Compute fabric**: The runtime needs a real provider to drive planning and
   observation. The provider must be swappable without code changes (AGENTS.md
   §1.2 Provider Independence).
2. **Secrets**: API keys, tokens, and other secrets are currently absent from
   the configuration system. A secrets strategy is needed that does not
   introduce new infrastructure or violate the layer discipline.

## Options Considered

### Option A: Introduce a dedicated secrets manager

Create a new `core/foundation/secrets.py` module with a `SecretResolver` class
that reads from environment variables, a vault, or a `.env` file. Add a new
layer or service object that providers depend on.

**Pros:**
- Explicit secrets surface, easy to audit.

**Cons:**
- Adds a new concept (secrets manager) that does not yet exist in the codebase.
- Providers would need a new dependency, increasing coupling.
- Premature: the only secrets in use are API keys passed via config dicts.

### Option B: Extend ThinkBoxConfig + leverage existing env-var pattern (CHOSEN)

Secrets are resolved by `ThinkBoxConfig` from `THINKBOX_*` environment
variables (the existing pattern in `core/foundation/config.py:69-80`). Provider
API keys are passed via the `provider_configs` dict already present on
`ThinkBoxConfig`. No new secrets infrastructure is introduced.

**Pros:**
- Reuses the existing configuration hierarchy (defaults → pyproject → env → CLI).
- No new modules, no new dependencies, no layer violations.
- Backward compatible: all existing code continues to work.

**Cons:**
- Secrets in environment variables are less isolated than a dedicated vault.
  Acceptable for Phase 1; a vault can be added later without changing the
  provider interface.

## Decision

We chose **Option B**. Secrets are resolved through the existing
`ThinkBoxConfig` environment-variable override mechanism. The
`provider_configs` field (already a `dict[str, dict[str, Any]]`) carries
provider-specific secrets (API keys, base URLs) from configuration. No new
secrets manager is introduced.

## Compute Fabric Pattern

The compute fabric is the execution loop that connects a provider to the
runtime. It follows the layer dependency graph defined in
`docs/architecture-v1.md`:

```
Provider → Planner → Actor → Tools → Memory → Observer
```

1. **Provider** (`core/providers/base.py:ModelProvider`): Declares capabilities
   and exposes `complete()`, `stream()`, `embed()`. Selected by name from
   `ProviderRegistry`. The runtime never imports a provider SDK directly.
2. **Planner** (`core/runtime/planner.py`): When a provider is available, uses
   it to decompose a `Goal` into meaningful `Step` objects. Falls back to
   placeholder planning when `provider=None` (backward compatible).
3. **Actor** (`core/runtime/actor.py`): Executes one step. Looks up the tool
   in the `ToolRegistry`, checks permissions via the `ApprovalGate`, executes
   the handler, and records the result in the audit log.
4. **Tools** (`core/tools/`): Stateless async functions registered by name.
   Permission-checked before execution.
5. **Memory** (`core/memory/`): Session and task memory adapters over SQLite.
   The Observer reads from and writes to memory but does not own it.
6. **Observer** (`core/runtime/observer.py`): Validates step results against
   `expected_output`. Signals the Planner to replan on failure.

### Provider Independence

Swapping providers is a configuration change, not a code change:

```python
provider = ProviderRegistry.get(config.default_provider)
```

The runtime queries `provider.capabilities` at startup and adjusts behavior
(streaming vs. non-streaming, system prompt handling) accordingly. No runtime
code path is gated by provider name.

### Adding AWS Bedrock, UpCloud, or Local Providers

New providers implement the `ModelProvider` protocol and register with
`@ProviderRegistry.register("name")`. No runtime code changes are required.
Provider-specific configuration (region, endpoint, credentials) flows through
`ThinkBoxConfig.provider_configs[name]` and is resolved from `THINKBOX_*`
environment variables.

Example for a future AWS Bedrock provider:

```python
@ProviderRegistry.register("aws_bedrock")
class AWSBedrockProvider:
    def __init__(self, config: dict[str, Any]) -> None:
        self._region = config.get("region", "us-east-1")
        # credentials from THINKBOX_AWS_ACCESS_KEY_ID, etc.
```

The runtime does not import `AWSBedrockProvider`. It resolves `"aws_bedrock"`
from the registry at startup.

## Bridging core/providers/ and backend/models/ollama_client.py

The backend has a working Ollama client with `stream_chat()`, `chat_completion()`,
and `list_models()`. To make Ollama available as a first-class provider in the
`core/providers/` abstraction:

1. Create `core/providers/ollama.py` implementing `ModelProvider` for Ollama.
2. Bridge the logic from `backend/models/ollama_client.py` without modifying
   that file (it remains in use by the backend layer).
3. Configure via `THINKBOX_OLLAMA_BASE_URL` (default `http://localhost:11434`)
   and `THINKBOX_OLLAMA_MODEL`.
4. Register as `"ollama"` in the `ProviderRegistry`.

This enables local-first compute: the runtime can use Ollama as its provider
without any code changes to the backend layer, and the provider can be swapped
to OpenAI-compatible or AWS Bedrock by changing `THINKBOX_DEFAULT_PROVIDER`.

## Security Note

`docs/project-foundation.md` §6 identifies a GitHub personal access token
embedded in the `origin` remote URL. This is a credential leak risk. It must be
removed from `.git/config` and rotated on GitHub. No secrets belong in the
repository — not in code, config files, or documentation. All secrets are
injected at runtime via `THINKBOX_*` environment variables.

## Consequences

- **Positive**: The compute fabric is fully provider-independent. Adding a new
  provider is a single file in `core/providers/` plus a config change.
- **Positive**: No new infrastructure. Secrets flow through the existing config
  hierarchy.
- **Positive**: Backward compatible. The runtime works with `provider=None`.
- **Negative**: Environment variables are the only secrets mechanism in Phase 1.
  A dedicated vault (HashiCorp Vault, AWS Secrets Manager) is deferred.
- **Negative**: The Ollama bridge duplicates some logic from
  `backend/models/ollama_client.py`. This is intentional — the backend layer
  must not depend on `core/providers/` (layer discipline).

## Related

- `docs/architecture-v1.md` — system layers and dependency rules
- `docs/project-foundation.md` — security concerns, dependencies
- `docs/roadmap.md` — Phase 1 boundaries
- `core/providers/base.py` — `ModelProvider` protocol, `ProviderRegistry`
- `core/foundation/config.py` — `ThinkBoxConfig`, env-var override mechanism
- `backend/models/ollama_client.py` — existing Ollama client to be bridged
