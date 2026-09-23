"""Hermetic FastAPI harness for control-plane receipt-chain / END_LINK e2e (PR #162).

Starlette TestClient on ``control_plane_api`` only — no Box/Mercury HTTP.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Iterator

from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest import mock

from backend.api.v1.control_plane_auth import LOCAL_DEV_TOKEN
from thinkbox.control_plane_operation_registry import reset_operation_registry
from thinkbox.control_plane_receipt_store import reset_control_plane_receipt_store
from thinkbox.control_plane_ops_harden import reset_idempotency_registry, reset_ops_rate_limiter
from thinkbox.end_link_api_ops_harden import reset_batch_idempotency_cache


def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {LOCAL_DEV_TOKEN}"}


def reset_control_plane_hermetic_state() -> None:
    reset_operation_registry()
    reset_control_plane_receipt_store()
    reset_batch_idempotency_cache()
    reset_idempotency_registry()
    reset_ops_rate_limiter()


@contextmanager
def control_plane_client() -> Iterator[TestClient]:
    """Isolated control-plane router with dev token enabled."""
    reset_control_plane_hermetic_state()
    env = mock.patch.dict(
        os.environ,
        {"THINKBOX_CONTROL_PLANE_ALLOW_DEV_TOKEN": "1"},
        clear=False,
    )
    env.start()
    try:
        from backend.api.v1.control_plane import control_plane_api

        app = FastAPI()
        app.include_router(control_plane_api)
        with TestClient(app, raise_server_exceptions=True) as client:
            yield client
    finally:
        env.stop()
        reset_control_plane_hermetic_state()


def seed_operation(
    client: TestClient,
    *,
    operation_id: str,
    action_type: str = "cp.demo",
) -> dict[str, Any]:
    resp = client.post(
        "/api/v1/control-plane/operations",
        json={"action_type": action_type, "operation_id": operation_id},
        headers=auth_headers(),
    )
    return resp.json()


def seed_receipt_id(client: TestClient, operation_id: str | None = None) -> str:
    op_id = operation_id or "op_e2e_default"
    seed_operation(client, operation_id=op_id)
    chain = client.get("/api/v1/control-plane/receipts/chain", headers=auth_headers())
    receipts = (chain.json().get("data") or {}).get("page", {}).get("receipts") or []
    if not receipts:
        raise AssertionError("no receipt after seed operation")
    for row in receipts:
        if row.get("operation_id") == op_id:
            return str(row["receipt_id"])
    return str(receipts[-1]["receipt_id"])


def seed_receipt_chain(client: TestClient, count: int) -> list[str]:
    ids: list[str] = []
    for i in range(count):
        ids.append(seed_receipt_id(client, operation_id=f"op_e2e_chain_{i}"))
    return ids
