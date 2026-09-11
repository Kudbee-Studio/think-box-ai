# Contributing to Think Box AI

Thank you for your interest in contributing! Here's how to get involved.

## How to Contribute

1. **Fork** the repository and create your branch from `main`.
2. **Install** dependencies: `pip install -e ".[dev]"`
3. **Make** your changes and add tests where appropriate.
4. **Test** your changes:
   ```bash
   python3 -m unittest discover tests/
   python3 -m unittest tests.unit.test_session_tracker
   python3 -m unittest tests.unit.test_phase1_2_security
   python3 -m unittest tests.unit.test_whip_protocol
   python3 -m unittest tests.integration.test_e2e_engine
   ```
5. **Submit** a pull request with a clear description of what you changed and why.

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
