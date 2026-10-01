# Contributing to Think Box AI

Thank you for your interest in contributing! Think Box AI is an enterprise-grade AI reasoning engine, and we maintain high code quality standards.

## Quick Start

1. **Fork** the repository and create your branch from `main`
2. **Install** dependencies: `make install`
3. **Make** your changes (follow Code Quality Standards below)
4. **Test** your changes: `make check` (lint + type + security + tests)
5. **Commit** with clear message: `type(scope): description`
6. **Submit** a pull request with reference to related issues

## Code Quality Standards (Enterprise-Grade)

All contributions must pass **all** of these checks:

### 1. Linting with Ruff

Zero violations required. Run:
```bash
make lint        # Check for violations
make fmt         # Auto-fix issues
```

Enforces: PEP 8, naming conventions, security issues, code simplification, logging best practices.

### 2. Type Checking

All public functions must have type hints. Run:
```bash
make type        # mypy type checking
```

### 3. Security Scanning

Run:
```bash
make security    # bandit security scanner
```

**Critical Rules:**
- No hardcoded secrets or credentials
- Validate all user input
- Use timeouts on network operations
- No use of `eval()`, `exec()`, or unsafe `pickle`

### 4. Testing Requirements

- **Unit tests**: All public functions must have tests
- **Coverage**: Target 85%+ for critical paths
- **Structure**: `tests/unit/`, `tests/integration/`, `tests/e2e/`

Run:
```bash
make test        # Full test suite
make test-unit   # Fast unit tests only
make test-cov    # With coverage report
```

## Development Workflow

### Setup
```bash
# Clone and install
git clone https://github.com/Kudbee-Studio/think-box-ai.git
cd think-box-ai
make install

# Optional: Install pre-commit hooks
make install-pre-commit
```

### Development Loop
```bash
# Make changes, then:
make check       # Full verification (lint + type + security + tests)
make fmt         # Auto-fix formatting issues
git commit -m "type(scope): description"
git push origin feat/your-feature
```

### Pre-Push Verification
```bash
make pre-push    # Lint + type + security (without tests)
```

## Phase 9 Testing

Phase 9 innovations are tested in `tests/unit/test_session_tracker.py` (27 tests)
covering coalition, consensus, economy, intelligence, session tracking, and
benchmark modules. Each innovation must have at least one unit test covering
valid input, invalid input, and edge cases.

## Code Style

- Follow [PEP 8](https://peps.python.org/pep-0008/) for Python code.
- Use descriptive variable and function names.
- Add docstrings to all public functions and classes.
- Add type hints to all public functions and methods.
- Use `dataclasses` for data structures. Add `pydantic` when schemas stabilize.

## Architecture Rules

All contributions must respect the layered architecture defined in
`docs/architecture-v1.md`:

- Layer N may only import from layers 0 through N-1.
- No provider-specific SDK imports at the runtime layer.
- Never store transient UI state in memory.
- Never store speculative claims in Organizational Memory.

See `AGENTS.md` for the complete development rules.

## Reporting Bugs

Open an [issue](https://github.com/Kudbee-Studio/think-box-ai/issues) with:
- A clear title and description
- Steps to reproduce the bug
- Expected vs actual behaviour

## Feature Requests

Open an [issue](https://github.com/Kudbee-Studio/think-box-ai/issues) labelled `enhancement` and describe the use case.
