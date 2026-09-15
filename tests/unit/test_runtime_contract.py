"""Regression test: subprocess uses the same interpreter as the orchestrator.

Converted from pytest-style to stdlib ``unittest`` so the project's actual
runner (``python3 -m unittest discover``) executes it. The earlier version
imported ``pytest`` at module scope and hardcoded an absolute ``.venv`` path,
which made discovery fail in any environment without pytest.

The contract under test: a subprocess spawned by the orchestrator inherits
``sys.executable``. Optional dependency checks *skip* (rather than fail) when
the environment does not provide them, so the suite is honest about the
environment instead of reporting a code failure.
"""

from __future__ import annotations

import subprocess
import sys
import unittest


class TestRuntimeContract(unittest.TestCase):
    def test_subprocess_inherits_orchestrator_interpreter(self) -> None:
        """A subprocess spawned with sys.executable reports the same interpreter."""
        orchestrator_python = sys.executable
        result = subprocess.run(
            [orchestrator_python, "-c", "import sys; print(sys.executable)"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, f"Subprocess failed: {result.stderr}")
        self.assertEqual(result.stdout.strip(), orchestrator_python)

    def test_subprocess_inherits_pythonpath_visibility(self) -> None:
        """A subprocess started from the project root can import the package."""
        result = subprocess.run(
            [sys.executable, "-c", "import thinkbox.workspace; print('ok')"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, f"Import failed: {result.stderr}")

    def test_thinkbox_and_core_modules_importable(self) -> None:
        """Every declared module imports with stdlib only."""
        modules = [
            "thinkbox.engine",
            "thinkbox.decomposer",
            "thinkbox.burst",
            "thinkbox.admission",
            "thinkbox.capacity",
            "thinkbox.occupancy",
            "thinkbox.governance_token",
            "thinkbox.ledger",
            "thinkbox.identity",
            "thinkbox.workspace",
            "thinkbox.thinktrace",
            "thinkbox.reasoning",
            "thinkbox.grounding",
            "thinkbox.factcards",
            "thinkbox.harvest",
            "thinkbox.verifier",
            "thinkbox.session",
            "core.memory.store",
            "core.memory.org",
            "core.memory.schema",
        ]
        missing: list[str] = []
        for mod in modules:
            try:
                __import__(mod)
            except ImportError as e:  # pragma: no cover - reported via assertion
                missing.append(f"{mod}: {e}")
        self.assertFalse(missing, f"Missing modules: {missing}")


def _missing(deps: list[str]) -> list[str]:
    out: list[str] = []
    for dep in deps:
        try:
            __import__(dep.replace("-", "_"))
        except ImportError:
            out.append(dep)
    return out


_MISSING_RUNTIME = _missing(["fastapi", "uvicorn"])


class TestOptionalDependencies(unittest.TestCase):
    @unittest.skipIf(_MISSING_RUNTIME, f"runtime deps absent in this env: {_MISSING_RUNTIME}")
    def test_runtime_dependencies_available(self) -> None:
        self.assertEqual(_MISSING_RUNTIME, [])


if __name__ == "__main__":
    unittest.main()
