"""Hermetic helpers for Phase 1 governed-runtime e2e (audit F009).

Mock-provider completions only — no network, credentials, or live substrate.
Reuses deterministic emission from pop_arena (same pattern as unit DAG tests).
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any, TypeVar

from thinkbox.engine import EngineConfig, ThinkBoxEngine
from thinkbox.governed import GovernedEngine, GovernedEngineConfig
from thinkbox.pop_arena import deterministic_emission_v2, system_prompt_for_v2

T = TypeVar("T")


def run_async(coro: Coroutine[Any, Any, T]) -> T:
    """Run one coroutine in a fresh event loop (unittest-friendly)."""
    return asyncio.run(coro)


def make_governed(ledger_path: str = ":memory:") -> GovernedEngine:
    base = ThinkBoxEngine(EngineConfig())
    return GovernedEngine(GovernedEngineConfig(engine=base, ledger_path=ledger_path))


def subtask_spec(
    family: str,
    variant: str,
    depends_on: list[int] | None = None,
) -> dict[str, Any]:
    prompt, spec = system_prompt_for_v2(family, variant)
    return {
        "description": prompt,
        "family": family,
        "variant": variant,
        "spec": spec,
        "depends_on": depends_on or [],
    }


def mock_complete_router(
    subtasks: list[dict[str, Any]],
    behaviors: dict[int, str] | None = None,
):
    """Scripted complete_async keyed by subtask prompt prefix (hermetic provider)."""
    behaviors = behaviors or {}
    calls: dict[str, int] = {}

    async def complete(prompt: str) -> str | tuple[str, dict[str, int]]:
        index = None
        for i, st in enumerate(subtasks):
            if prompt.startswith(st["description"]):
                index = i
                break
        if index is None:
            raise AssertionError(f"unrouted mock-provider prompt: {prompt[:80]!r}")

        st = subtasks[index]
        key = st["description"]
        calls[key] = calls.get(key, 0) + 1
        n = calls[key]
        fam, var, spec = st["family"], st["variant"], st["spec"]
        behavior = behaviors.get(index, "valid")
        valid = deterministic_emission_v2(fam, var, spec)
        wrongkey = '{"result": %s}' % spec["expected"]

        if behavior == "valid":
            return valid
        if behavior == "wrongkey_then_valid":
            return wrongkey if n == 1 else valid
        if behavior == "wrongkey_always":
            return wrongkey
        if behavior == "arithmetic_always":
            return '{"answer": %s}' % (spec["expected"] + 1)
        if behavior == "valid_with_usage":
            return valid, {"total_tokens": 17}
        raise AssertionError(f"unknown behavior: {behavior}")

    return complete, calls


def ledger_denied_count(governed: GovernedEngine) -> int:
    return sum(1 for e in governed.ledger.entries() if not e["allowed"])


def ledger_allowed_count(governed: GovernedEngine) -> int:
    return sum(1 for e in governed.ledger.entries() if e["allowed"])


def assert_ledger_chain(governed: GovernedEngine) -> None:
    if not governed.ledger.verify():
        raise AssertionError("action ledger chain verification failed")


def five_tool_think_job_subtasks() -> list[dict[str, Any]]:
    """Five governed subtasks spanning v2 families (Think Job shape, hermetic)."""
    return [
        subtask_spec("compute", "add_small"),
        subtask_spec("distractor", "prose"),
        subtask_spec("compute", "mul_small", depends_on=[0]),
        subtask_spec("multifield", "double", depends_on=[1]),
        subtask_spec("multifield", "combo", depends_on=[2, 3]),
    ]
