"""Hermetic FastAPI harness for ``POST /api/v1/run`` contract tests (PR #131 / #132).

Uses Starlette TestClient + patched ``ThinkBoxEngine`` — no Mercury HTTP, no live provider.
PR #132 adds shared API governance registration and admission tokens on every run.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from starlette.testclient import TestClient

from backend.security import setup_security
from thinkbox.dashboard_state import DashboardCategory, DashboardEvent

_HERMETIC_API_KEY = "tb_hermetic_pr131_contract_key"
_PENDING_BG: list[Any] = []
_HERMETIC_AGENT_ID = "hermetic-api-run-agent"
_HERMETIC_TOKEN: str = ""


def _capture_create_task(coro: Any) -> MagicMock:
    """Run background coroutines synchronously after the HTTP response (unittest-safe)."""
    _PENDING_BG.append(coro)
    return MagicMock()


def drain_background_tasks() -> None:
    while _PENDING_BG:
        coro = _PENDING_BG.pop(0)
        asyncio.run(coro)


def hermetic_governance_token() -> str:
    return _HERMETIC_TOKEN


def hermetic_agent_id() -> str:
    return _HERMETIC_AGENT_ID


def run_payload(goal: str, **extra: Any) -> dict[str, Any]:
    """JSON body with required governance fields for PR #132."""
    body: dict[str, Any] = {
        "goal": goal,
        "agent_id": _HERMETIC_AGENT_ID,
        "governance_token": _HERMETIC_TOKEN,
    }
    body.update(extra)
    return body


@contextmanager
def hermetic_run_client(
    *,
    execute_result: dict[str, Any] | None = None,
    execute_raises: Exception | None = None,
) -> Iterator[tuple[TestClient, MagicMock]]:
    """TestClient for ``api_v1_router`` with auth middleware and mocked engine."""
    global _HERMETIC_TOKEN
    execute_result = execute_result or {"total_tasks": 2, "completed": 2}
    _PENDING_BG.clear()

    from backend.api.v1 import router as router_mod
    from backend.api.v1.run_governed import reset_api_run_governance_for_tests, set_complete_async_override

    router_mod.active_engines.clear()
    router_mod.active_governed_engines.clear()
    set_complete_async_override(None)

    ledger_path = str(Path(tempfile.mkdtemp()) / "api_run_ledger.db")
    gov = reset_api_run_governance_for_tests(ledger_path=ledger_path)
    _HERMETIC_TOKEN = gov.register_agent(
        _HERMETIC_AGENT_ID,
        ["goal:execute", "goal:execute:verified"],
    )

    app = FastAPI(title="hermetic-run-pr132")
    with patch.dict(os.environ, {"THINKBOX_API_KEY": _HERMETIC_API_KEY}, clear=False):
        setup_security(app)
        app.include_router(router_mod.api_v1_router)

    mock_engine = MagicMock()
    mock_engine.engine_id = "engine_hermetic01"

    async def _execute(goal: str, graph=None) -> dict[str, Any]:
        if execute_raises is not None:
            raise execute_raises
        out = dict(execute_result)
        if graph is not None:
            out.setdefault("verified", {"tasks_total": len(graph.tasks), "tasks_succeeded": len(graph.tasks)})
        return out

    mock_engine.execute_goal = AsyncMock(side_effect=_execute)

    with patch.object(router_mod, "ThinkBoxEngine", return_value=mock_engine) as engine_cls:
        with patch.object(router_mod.asyncio, "create_task", side_effect=_capture_create_task):
            with TestClient(app, raise_server_exceptions=True) as client:
                yield client, engine_cls
                drain_background_tasks()


@contextmanager
def hermetic_run_client_real_engine() -> Iterator[tuple[TestClient, Any]]:
    """Governed path with real ``ThinkBoxEngine`` + hermetic mock provider (verified runs)."""
    global _HERMETIC_TOKEN
    _PENDING_BG.clear()

    from backend.api.v1 import router as router_mod
    from backend.api.v1.run_governed import reset_api_run_governance_for_tests, set_complete_async_override

    router_mod.active_engines.clear()
    router_mod.active_governed_engines.clear()
    set_complete_async_override(None)

    ledger_path = str(Path(tempfile.mkdtemp()) / "api_run_ledger.db")
    gov = reset_api_run_governance_for_tests(ledger_path=ledger_path)
    _HERMETIC_TOKEN = gov.register_agent(
        _HERMETIC_AGENT_ID,
        ["goal:execute", "goal:execute:verified"],
    )

    app = FastAPI(title="hermetic-run-real-engine")
    with patch.dict(os.environ, {"THINKBOX_API_KEY": _HERMETIC_API_KEY}, clear=False):
        setup_security(app)
        app.include_router(router_mod.api_v1_router)

    with patch.object(router_mod.asyncio, "create_task", side_effect=_capture_create_task):
        with TestClient(app, raise_server_exceptions=True) as client:
            yield client, gov
            drain_background_tasks()


def auth_headers() -> dict[str, str]:
    return {"X-API-Key": _HERMETIC_API_KEY}


def events_matching(
    state: Any,
    *,
    category: DashboardCategory,
    event_type: DashboardEvent,
) -> list[Any]:
    return [
        e
        for e in state.events
        if e.category == category and e.event_type == event_type
    ]
