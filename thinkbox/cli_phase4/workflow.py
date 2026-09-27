"""Multi-command workflow / scripting helpers (PR #196 F06)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class WorkflowStep:
    name: str
    command: str


@dataclass(frozen=True)
class WorkflowResult:
    steps: tuple[dict[str, Any], ...]
    ok: bool


def run_workflow(
    steps: tuple[WorkflowStep, ...],
    runner: Callable[[str], dict[str, Any]],
) -> WorkflowResult:
    """Execute named steps via injected hermetic runner (no shell)."""
    results: list[dict[str, Any]] = []
    ok = True
    for step in steps:
        try:
            payload = runner(step.command)
            results.append({"name": step.name, "ok": True, "result": payload})
        except Exception as exc:  # noqa: BLE001 — workflow aggregates step failures
            ok = False
            results.append({"name": step.name, "ok": False, "error": str(exc)})
            break
    return WorkflowResult(steps=tuple(results), ok=ok)
