"""Hermetic helpers for Phase 1 governed-runtime e2e (audit F009, F023).

Mock-provider completions only — no network, credentials, or live substrate.
Reuses deterministic emission from pop_arena (same pattern as unit DAG tests).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import sqlite3
import tempfile
from collections.abc import Coroutine, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, TypeVar

from core.providers.base import CompletionResponse, Message, ModelProvider, ProviderCapabilities
from thinkbox.engine import EngineConfig, ThinkBoxEngine
from thinkbox.experiment import ExperimentManager
from thinkbox.governed import GovernedEngine, GovernedEngineConfig
from thinkbox.pop_arena import deterministic_emission_v2, secrets_clean, system_prompt_for_v2

T = TypeVar("T")

_SECRET_PATTERNS = re.compile(
    r"(?i)(api[_-]?key|bearer\s+[a-z0-9]|authorization:\s*|ucat_|sk-[a-z0-9]{10,})"
)


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


class HermeticModelProvider:
    """Scripted ``ModelProvider`` for F023 — routes prompts like ``mock_complete_router``."""

    capabilities = ProviderCapabilities(completion=True, streaming=False, embedding=False)

    def __init__(
        self,
        subtasks: list[dict[str, Any]],
        behaviors: dict[int, str] | None = None,
    ) -> None:
        self._subtasks = subtasks
        self._behaviors = behaviors or {}
        self.complete_calls: int = 0
        self._calls: dict[str, int] = {}

    async def complete(self, messages: list[Message], **kwargs: Any) -> CompletionResponse:
        self.complete_calls += 1
        prompt = messages[-1].content if messages else ""
        index = None
        for i, st in enumerate(self._subtasks):
            if prompt.startswith(st["description"]):
                index = i
                break
        if index is None:
            raise AssertionError(f"unrouted hermetic ModelProvider prompt: {prompt[:80]!r}")

        st = self._subtasks[index]
        key = st["description"]
        self._calls[key] = self._calls.get(key, 0) + 1
        n = self._calls[key]
        fam, var, spec = st["family"], st["variant"], st["spec"]
        behavior = self._behaviors.get(index, "valid")
        valid = deterministic_emission_v2(fam, var, spec)
        wrongkey = '{"result": %s}' % spec["expected"]

        if behavior == "valid":
            body = valid
        elif behavior == "wrongkey_then_valid":
            body = wrongkey if n == 1 else valid
        elif behavior == "wrongkey_always":
            body = wrongkey
        elif behavior == "arithmetic_always":
            body = '{"answer": %s}' % (spec["expected"] + 1)
        elif behavior == "valid_with_usage":
            return CompletionResponse(
                content=valid,
                model="hermetic-mock",
                usage={"total_tokens": 17},
            )
        else:
            raise AssertionError(f"unknown behavior: {behavior}")

        return CompletionResponse(content=body, model="hermetic-mock", usage={"total_tokens": 3})

    async def stream(self, messages: list[Message], **kwargs: Any):
        resp = await self.complete(messages, **kwargs)
        yield resp

    async def embed(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
        return [[0.0] * 4 for _ in texts]


def provider_complete_async(provider: HermeticModelProvider):
    """Bridge ``ModelProvider.complete`` into ``execute_verified_goal``'s ``complete_async``."""

    async def complete(prompt: str) -> str | tuple[str, dict[str, int]]:
        resp = await provider.complete([Message(role="user", content=prompt)])
        if resp.usage:
            return resp.content, dict(resp.usage)
        return resp.content

    return complete


@contextmanager
def temp_experiment_stack() -> Iterator[tuple[ExperimentManager, Path, Path]]:
    """Isolated SQLite + artifacts directory for hermetic Think Job persistence."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        db_path = root / "experiments.db"
        art_dir = root / "artifacts"
        art_dir.mkdir()
        mgr = ExperimentManager(db_path=str(db_path), artifacts_dir=str(art_dir))
        yield mgr, db_path, art_dir


@contextmanager
def isolated_dashboard_state():
    """Clear dashboard singleton mutations for the duration of a test."""
    from thinkbox.dashboard_state import get_dashboard_state

    st = get_dashboard_state()
    saved = {
        "think_boxes": dict(st.think_boxes),
        "think_jobs": dict(st.think_jobs),
        "cnc_jobs": dict(st.cnc_jobs),
        "infrastructure": dict(st.infrastructure),
        "providers": dict(st.providers),
        "test_milestones": dict(st.test_milestones),
        "events": list(st.events),
    }
    st.think_boxes.clear()
    st.think_jobs.clear()
    st.cnc_jobs.clear()
    st.infrastructure.clear()
    st.providers.clear()
    st.test_milestones.clear()
    st.events.clear()
    try:
        yield st
    finally:
        st.think_boxes.clear()
        st.think_jobs.clear()
        st.cnc_jobs.clear()
        st.infrastructure.clear()
        st.providers.clear()
        st.test_milestones.clear()
        st.events.clear()
        st.think_boxes.update(saved["think_boxes"])
        st.think_jobs.update(saved["think_jobs"])
        st.cnc_jobs.update(saved["cnc_jobs"])
        st.infrastructure.update(saved["infrastructure"])
        st.providers.update(saved["providers"])
        st.test_milestones.update(saved["test_milestones"])
        st.events.extend(saved["events"])


def assert_hermetic_blob_has_no_secrets(blob: str) -> None:
    hits = _SECRET_PATTERNS.findall(blob)
    if hits:
        raise AssertionError(f"secret-like patterns in hermetic blob: {hits[:5]}")


def collect_hermetic_artifact_blob(art_dir: Path, summary: dict[str, Any], ledger_path: str) -> str:
    parts = [json.dumps(summary)]
    for path in art_dir.glob("*.json"):
        parts.append(path.read_text(encoding="utf-8"))
    if ledger_path != ":memory:":
        conn = sqlite3.connect(ledger_path)
        for (meta,) in conn.execute("SELECT metadata FROM ledger"):
            parts.append(meta or "")
        conn.close()
    return "".join(parts)


def verify_dag_proof_file(proof_path: Path, expected_sha256: str | None = None) -> dict[str, Any]:
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    claimed = proof.pop("proof_sha256", None)
    if expected_sha256 is not None:
        if claimed != expected_sha256:
            raise AssertionError("proof_sha256 mismatch")
    recomputed = hashlib.sha256(json.dumps(proof, indent=2, sort_keys=True).encode()).hexdigest()
    if claimed and claimed != recomputed:
        raise AssertionError("proof hash chain invalid")
    for task in proof.get("tasks", []):
        art = Path(task["artifact"])
        if art.is_file():
            art_hash = hashlib.sha256(art.read_bytes()).hexdigest()
            if art_hash != task.get("artifact_sha256"):
                raise AssertionError(f"artifact hash mismatch for {art}")
    proof["proof_sha256"] = claimed
    return proof


async def run_hermetic_think_job(
    governed: GovernedEngine,
    goal: str,
    subtasks: list[dict[str, Any]],
    complete_async,
    *,
    token_value: str,
    agent_id: str,
    manager: ExperimentManager | None = None,
    emit_dashboard: bool = False,
    max_calls: int = 0,
    capability: str = "goal:execute",
) -> dict[str, Any]:
    """Single entry: admit → execute verified DAG → optional persist + dashboard."""
    return await governed.execute_verified_goal(
        goal,
        subtasks,
        complete_async,
        token_value=token_value,
        agent_id=agent_id,
        capability=capability,
        manager=manager,
        emit_dashboard=emit_dashboard,
        max_calls=max_calls,
    )
