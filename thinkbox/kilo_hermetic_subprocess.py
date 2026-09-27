"""Bounded subprocess helpers for hermetic KILO operator gates."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

__all__ = (
    "DEFAULT_E2E_UNITTEST_TIMEOUT_SECONDS",
    "BoundedSubprocessError",
    "BoundedSubprocessResult",
    "e2e_unittest_skipped_by_default",
    "enable_nested_e2e_unittest",
    "nested_e2e_unittest_enabled",
    "run_bounded_command",
    "spine_fast_mode_enabled",
)

DEFAULT_E2E_UNITTEST_TIMEOUT_SECONDS = 180


@dataclass(frozen=True)
class BoundedSubprocessResult:
    """Result of a bounded subprocess invocation."""

    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False


class BoundedSubprocessError(RuntimeError):
    """Raised when a bounded subprocess fails or times out."""


def spine_fast_mode_enabled() -> bool:
    """True when spine verify runs in fast mode (skip nested e2e unittest subprocess)."""
    return os.environ.get("KILO_SPINE_FAST", "").strip().lower() in ("1", "true", "yes")


def nested_e2e_unittest_enabled() -> bool:
    """Nested e2e unittest runs only when explicitly opted in (bounded timeout)."""
    return os.environ.get("KILO_RUN_NESTED_E2E_UNITTEST", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def enable_nested_e2e_unittest() -> None:
    """Opt in to nested control-plane e2e unittest subprocess for this process."""
    os.environ["KILO_RUN_NESTED_E2E_UNITTEST"] = "1"


def e2e_unittest_skipped_by_default() -> bool:
    """True when nested unittest is not explicitly enabled."""
    return not nested_e2e_unittest_enabled()


def run_bounded_command(
    cmd: Sequence[str],
    *,
    cwd: Path,
    timeout_seconds: int = DEFAULT_E2E_UNITTEST_TIMEOUT_SECONDS,
) -> BoundedSubprocessResult:
    """Run *cmd* with wall-clock timeout and process-group teardown on expiry."""
    proc = subprocess.Popen(
        list(cmd),
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout_seconds)
        return BoundedSubprocessResult(
            returncode=proc.returncode if proc.returncode is not None else -1,
            stdout=stdout or "",
            stderr=stderr or "",
            timed_out=False,
        )
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            stdout, stderr = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
        return BoundedSubprocessResult(
            returncode=-9,
            stdout=stdout or "",
            stderr=stderr or "",
            timed_out=True,
        )


def run_bounded_unittest_modules(
    modules: Sequence[str],
    *,
    repo_root: Path,
    timeout_seconds: int = DEFAULT_E2E_UNITTEST_TIMEOUT_SECONDS,
) -> BoundedSubprocessResult:
    """Run unittest discover for explicit modules under *repo_root*."""
    cmd = [sys.executable, "-m", "unittest", *modules]
    return run_bounded_command(cmd, cwd=repo_root, timeout_seconds=timeout_seconds)
