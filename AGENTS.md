# AGENTS.md — THINK BOX AI

**Purpose:** This file defines the rules that every agent (human or AI) working
on this repository must follow. It is the operational layer of the architecture
defined in `docs/architecture-v1.md`.

---

## 1. Architecture Principles

These are non-negotiable. Violating them requires a decision record.

### 1.1 Layer Discipline

The system has five layers (Foundation, Provider, Memory, Governance/Tools,
Runtime). A layer may only import from layers beneath it. Cross-layer imports
are architectural errors.

**Check:** Before committing, verify imports with:
`python3 -c "import ast,sys; [print(f) for f in sys.argv[1:] if True]"` or manual
review.

### 1.2 Provider Independence

No model provider is hardcoded. The runtime must work identically with:
- OpenAI-compatible APIs (OpenAI, Groq, Together, vLLM, Ollama)
- Anthropic Messages API
- Local models (Phase 2+)

Swapping a provider is a configuration change, not a code change.

**Rule:** Never import a provider-specific SDK at the runtime layer. The
runtime only knows the `ModelProvider` protocol.

### 1.3 Memory First

Memory is not a chat history. It has four layers: Session, Task,
Organizational, Verified Knowledge. Each has a distinct scope, lifetime, and
write policy.

**Rule:** Never store transient UI state in memory. Never store speculative
claims in Organizational Memory.

### 1.4 Governance by Default

Tools do not execute without permission checks. Audit logs are append-only.
Approval gates are opt-out, not opt-in.

**Rule:** A tool without an explicit `permission` level is `RESTRICTED` and
requires approval.

### 1.5 Evidence Over Assumptions

Claims about model performance, tool reliability, or system behavior must be
backed by measurements stored in Organizational Memory.

**Rule:** Never commit a claim like "Model X is better" without a benchmark
result in `benchmarks/`.

---

## 2. Coding Rules

### 2.1 Language

- **Core:** Python 3.10+
- **CLI wrapper (future):** TypeScript/Node (deferred)
- **No other languages** without a decision record.

### 2.2 Dependencies

- Phase 0: Python standard library only.
- Every external dependency must have a documented trigger (see
  `docs/project-foundation.md` §4).
- No "maybe we'll need it" imports.

### 2.3 Style

- Follow PEP 8.
- Use type hints on all public functions and methods.
- Use `dataclasses` for data structures (Phase 1). Add `pydantic` when
  schemas stabilize.
- Docstrings on all public classes and functions.
- No comments that explain *what* the code does. Comments explain *why*.

### 2.4 Async

- The runtime is async (`asyncio`). All I/O-bound operations must be async.
- Blocking operations must be explicitly marked and isolated.

### 2.5 Error Handling

- Never swallow exceptions silently.
- All errors carry: `agent_id`, `task_id`, `think_box_id`, `timestamp`,
  `error_type`, `context`.
- The runtime raises structured errors. It does not log and continue.

### 2.6 Logging

- Use `logging` from stdlib.
- Log levels: `DEBUG` (internal state), `INFO` (significant events),
  `WARNING` (recoverable issues), `ERROR` (failures).
- Never log secrets, tokens, or PII.

---

## 3. Testing Requirements

### 3.1 Test Coverage

- Phase 1 target: 80% coverage for `core/` and `core/tools/`.
- Tests run in CI. No PR merges without passing tests.

### 3.2 Test Structure

```
tests/
  unit/           # Pure logic, no I/O, no network
  integration/    # Memory store, provider HTTP client, tool execution
  e2e/            # Full runtime loop with a mock provider
```

### 3.3 Test Requirements

- Every public function has at least one test.
- Every error path has a test.
- Tools have tests for: valid input, invalid input, permission denied,
  approval required.
- Memory has tests for: write, read, delete, conflict, retention.

### 3.4 Test Commands

```bash
python3 -m pytest tests/unit/          # Fast, no I/O
python3 -m pytest tests/integration/   # Requires SQLite
python3 -m pytest tests/                # All tests
```

### 3.5 Mocking

- Mock providers in unit tests. Do not make real HTTP calls.
- Use `unittest.mock` from stdlib. No external mocking libraries in Phase 1.

---

## 4. Documentation Requirements

### 4.1 What Must Be Documented

| Artifact | Location | Required |
|----------|----------|----------|
| Architecture | `docs/architecture-v1.md` | Yes |
| Project foundation | `docs/project-foundation.md` | Yes |
| Decision records | `docs/decisions/NNN-*.md` | Yes (for every ADR) |
| Module docstrings | In-code | Yes |
| Public API docstrings | In-code | Yes |
| Setup guide | `docs/guides/setup.md` | Phase 1 |
| Tool authoring guide | `docs/guides/tools.md` | Phase 1 |

### 4.2 Decision Records

Every significant decision gets a record:

```
docs/decisions/
  001-*.md   # First decision
  002-*.md   # Second decision
  ...
```

Format:

```markdown
# ADR NNN: Title

**Date:** YYYY-MM-DD
**Status:** Accepted | Rejected | Superseded

## Context
What problem are we solving?

## Options Considered
1. Option A
2. Option B

## Decision
We chose Option X because...

## Consequences
What changes as a result?
```

---

## 5. Decision Recording Process

1. **Draft:** Author writes the ADR before implementing the decision.
2. **Review:** At least one other contributor reviews.
3. **Accept:** ADR is marked `Accepted` and committed with the implementation.
4. **Supersede:** If a later decision invalidates an ADR, mark it
   `Superseded` and reference the new ADR.

ADRs are never deleted. They are historical records.

---

## 6. Branching and Commits

### 6.1 Branch Naming

```
feat/phase-N-description   # New feature or phase
fix/NNN-description        # Bug fix, references ADR if applicable
docs/description           # Documentation only
refactor/description       # Code restructuring, no behavior change
```

### 6.2 Commit Messages

Format: `type(scope): description`

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`

Examples:
```
feat(providers): add OpenAI-compatible provider
fix(memory): handle SQLite lock on concurrent write
docs(architecture): update Think Box lifecycle
refactor(runtime): extract Planner class from Agent
test(tools): add permission denied tests for shell_exec
```

No commit without a message. No "fix stuff" or "wip" messages in main branch
commits.

### 6.3 What to Commit

- Source code
- Tests
- Documentation
- Configuration files (`pyproject.toml`, etc.)

**Never commit:**
- Secrets, tokens, API keys
- `.env` files
- Model weights or large binaries (use Git LFS or external storage)
- `__pycache__`, `.pytest_cache`, `.mypy_cache`
- IDE config files (`.vscode/`, `.idea/`)

---

## 7. Git Hygiene

- Commit early, commit often.
- One logical change per commit.
- No merge commits in feature branches (rebase or squash).
- PRs target `main`. Do not push directly to `main`.
- Keep the branch up to date with `main` before opening a PR.

---

## 8. Code Review

- Every PR requires at least one review.
- Reviewers check: architecture compliance, test coverage, documentation,
  security.
- Reviewers do not approve PRs that violate layer discipline or introduce
  undocumented dependencies.

---

## 9. Security Rules

- No secrets in code, config files, or documentation.
- Secrets are injected via environment variables at runtime.
- Tool execution must be permission-checked before it runs.
- Audit logs are append-only and tamper-evident.
- External HTTP calls must have timeouts and retry limits.
- Shell execution must be explicitly approved by the user.

---

## 10. Phase Boundaries

| Phase | Goal | Phase 1 Boundary |
|-------|------|-----------------|
| Phase 0 | Foundation | This document |
| Phase 1 | Prove architecture with single agent, single provider, 5 tools | No multi-agent, no benchmarks, no UI |
| Phase 2 | Add pattern extraction, local models, benchmarks | — |
| Phase 3 | Multi-agent, UI, organizational memory scaling | — |

Do not implement Phase 2+ features in Phase 1. Do not implement Phase 1
features before the foundation is solid.

---

## 11. When in Doubt

1. Read `docs/architecture-v1.md`.
2. Read `docs/project-foundation.md`.
3. Check `docs/decisions/` for prior decisions on the topic.
4. If still uncertain, write an ADR before writing code.
5. Default to simplicity. The simplest solution that satisfies the
   architecture is correct.

---

## 12. Enforcement

These rules are enforced by:
- Code review
- CI checks (tests, lint, import ordering)
- Architectural review for cross-layer imports

Violations are bugs. Fix them before merging.

---

## 13. Think Box Infrastructure Access

This section documents how to access and operate on the Think Box v1 VM
(UpCloud managed Kubernetes node `kudbee-host-v1`).

### 13.1 Environment Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `THINKBOX_UPCLOUD_API_TOKEN` | UpCloud API token (Bearer auth) | `ucat_01M...` |
| `UPCLOUD_SERVER_HOSTNAME` | Target server hostname | `kudbee-host-v1` |
| `UPCLOUD_SERVER_IP` | Public IP | `212.147.250.183` |
| `UPCLOUD_SSH_USER` | SSH user | `root` |
| `UPCLOUD_SSH_KEY_PATH` | Path to SSH private key | `~/.ssh/kilo-upcloud` |

### 13.2 UpCloud API Authentication

This environment uses an UpCloud API token (format `ucat_...`). Authentication
uses the Bearer header:

```bash
curl -H "Authorization: Bearer $THINKBOX_UPCLOUD_API_TOKEN" \
  https://api.upcloud.com/1.3/server
```

The token also works with the UpCloud CLI (`upctl`) via the `UPCLOUD_TOKEN`
environment variable. Install `upctl` from
<https://github.com/UpCloudLtd/upcloud-cli/releases>.

### 13.3 Establishing SSH Access

The Think Box is a **managed Kubernetes node** (UpCloud Managed K8s,
cluster `think-box-test`, Kubernetes v1.35). SSH keys are NOT injected via the
UpCloud server SSH-key API for managed K8s nodes.

**Method:** Use `kubectl debug` to create a privileged pod on the node and
write the SSH public key to `authorized_keys` on the host filesystem.

```bash
# 1. Get kubeconfig from UpCloud CLI
export UPCLOUD_TOKEN="$THINKBOX_UPCLOUD_API_TOKEN"
upctl kubernetes config think-box-test --output yaml > kubeconfig.yaml

# 2. Create a debug pod with host filesystem access
export KUBECONFIG=kubeconfig.yaml
kubectl debug node/<node-name> -n default \
  --image=busybox --copy-to=debug-node -- sh -c "sleep 300"

# 3. Write SSH key to authorized_keys
kubectl exec <debug-pod-name> -c debugger -- sh -c \
  "echo '<public-key>' > /host/root/.ssh/authorized_keys && \
   chmod 600 /host/root/.ssh/authorized_keys"

# 4. SSH to the node
ssh -i ~/.ssh/kilo-upcloud root@212.147.250.183

# 5. Clean up debug pod
kubectl delete pod <debug-pod-name> -n default
```

**SSH user:** `root` (the node has `PermitRootLogin yes` in sshd_config).

**Why SSH previously failed:** The `/root/.ssh/authorized_keys` file existed
(0 bytes) but was empty. No public key was written to it during provisioning
because UpCloud managed K8s nodes do not use the standard SSH-key injection flow.

### 13.4 Known Limitations

- **KVM is NOT available and CANNOT be enabled**: `/dev/kvm` exists as a
  directory (not a character device). No `vmx`/`svm` CPU flags are exposed.
  `modprobe kvm_amd` and `modprobe kvm_intel` both fail with "SVM/VMX not
  supported by CPU". The host itself is a KVM guest (UpCloud infrastructure),
  but nested virtualization is not passed through to the guest.
- Firecracker v1.16.1 binary will start and respond to API calls, but
  `InstanceStart` fails with: `Kvm error: Error creating KVM object: Is a
  directory (os error 21)`. Firecracker REQUIRES `/dev/kvm` with the
  `KVM_GET_API_VERSION` ioctl — without it, the microVM cannot boot.
- No Docker installed; containerd 1.7.29 is the only container runtime.
- The node is managed by an UpCloud Managed Kubernetes cluster — direct VM
  modifications (kernel upgrade, nested virt enablement, KVM device node
  creation) are not possible without changing the UpCloud server plan or
  provisioning a new server.
- SSH key injection via UpCloud server API does not work for managed K8s
  nodes. Use `kubectl debug` method described above.

### 13.5 Firecracker Status

- Firecracker v1.16.1 binary verified starting and responding to API
  requests over Unix socket.
- **MicroVM boot FAILS**: `InstanceStart` returns
  `Kvm error: Error creating KVM object: Is a directory (os error 21)`.
  The `/dev/kvm` on this host is a directory, not a character device.
- Firecracker on this host is NOT usable for real microVM execution.
- See `docs/decisions/002-firecracker-execution-boundary.md` for the
  full architectural decision. A new `core/execution/` layer is planned
  that will work once a KVM-capable host is available.

### 13.6 Agent Framework Decision

Atomic Agents (GitHub user `olemarch` fork, referred to as "OLEMARCHY") was
evaluated as a potential standard component inside every Think Box microVM.
**Decision: Deferred.** See `docs/decisions/001-olemarchy-atomic-agents-evaluation.md`.

Key blockers:
1. Requires Python 3.12+ (env has 3.10.12)
2. Brings pydantic, instructor, litellm, mcp — violates Phase 0 stdlib-only constraint
3. Would require significant adapter layer between Atomic Agents' `AtomicAgent`
   and KUDBEE's `ThinkBox`/`Agent` runtime

If adopted in Phase 2+, the integration path is documented in the ADR.


</content>