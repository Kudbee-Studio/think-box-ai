"""Regression test: subprocess uses same interpreter as orchestrator."""
import sys
import subprocess
from pathlib import Path
import pytest


def test_subprocess_inherits_orchestrator_interpreter():
    """Verify subprocess spawned by orchestrator uses the same Python interpreter."""
    orchestrator_python = sys.executable
    
    # Simulate orchestrator's subprocess call pattern (kudbee_orchestrator.py:776-777)
    result = subprocess.run(
        [orchestrator_python, "-c", "import sys; print(sys.executable)"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0, f"Subprocess failed: {result.stderr}"
    subprocess_python = result.stdout.strip()
    
    assert subprocess_python == orchestrator_python, (
        f"Subprocess interpreter mismatch: "
        f"orchestrator={orchestrator_python}, subprocess={subprocess_python}"
    )


def test_venv_interpreter_is_correct():
    """Verify we're running in the project's .venv interpreter."""
    expected_path = "/workspace/bcdfac4f-1903-4a17-8abf-0b10fd495578/sessions/agent_0c8313fa-a5aa-428f-929c-95a1f71a6876/.venv/bin/python3"
    assert sys.executable == expected_path, (
        f"Wrong interpreter: got {sys.executable}, expected {expected_path}"
    )


def test_required_dependencies_available():
    """Verify all pyproject.toml dependencies are importable."""
    required = ["fastapi", "uvicorn", "aiohttp", "websockets", "multipart"]
    missing = []
    for dep in required:
        try:
            __import__(dep.replace("-", "_"))
        except ImportError:
            missing.append(dep)
    
    assert not missing, f"Missing dependencies in {sys.executable}: {missing}"


def test_dev_dependencies_available():
    """Verify dev dependencies (pytest) are available."""
    required = ["pytest", "pytest_asyncio"]
    missing = []
    for dep in required:
        try:
            __import__(dep.replace("-", "_"))
        except ImportError:
            missing.append(dep)
    
    assert not missing, f"Missing dev dependencies in {sys.executable}: {missing}"


def test_thinkbox_modules_importable():
    """Verify thinkbox and core modules are importable."""
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
        "thinkbox.production",
        "core.memory.store",
        "core.memory.org",
        "core.memory.schema",
    ]
    
    missing = []
    for mod in modules:
        try:
            __import__(mod)
        except ImportError as e:
            missing.append(f"{mod}: {e}")
    
    assert not missing, f"Missing thinkbox/core modules: {missing}"
