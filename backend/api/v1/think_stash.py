"""API GET /think/stash/status + GET /think/stash/last — redacted."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter

from thinkbox.byoc_config import ByocConfig
from thinkbox.byoc_stash_store import ThinkStashStore
from thinkbox.dashboard_state import get_dashboard_state, DashboardCategory, DashboardEvent

logger = logging.getLogger(__name__)

think_stash_router = APIRouter(prefix="/think/stash")

_dashboard_state = get_dashboard_state()


@think_stash_router.get("/status")
async def stash_status() -> dict[str, Any]:
    config = ByocConfig.load()
    store = ThinkStashStore(":memory:")
    redacted = config.redacted()
    last = store.last_harvest()
    status = "ready"
    if config.is_live:
        status = "live"
    elif config.is_mock:
        status = "mock"
    else:
        status = "unknown"

    result: dict[str, Any] = {
        "status": status,
        "mode": redacted.get("demo_mode", "mock"),
        "has_vector_creds": redacted.get("has_vector_creds", False),
        "has_api_key": redacted.get("has_api_key", False),
        "vector_url": redacted.get("vector_url"),
        "store_records": store.count(),
        "last_harvest": last,
        "evidence_label": "simulated",
    }

    await _dashboard_state.emit(
        DashboardCategory.PROVIDERS,
        DashboardEvent.PROVIDER_CHANGED,
        {"component": "think_stash", "status": status, "mode": redacted.get("demo_mode")},
        "think_stash_api",
        evidence_label="simulated",
    )

    return result


@think_stash_router.get("/last")
async def stash_last() -> dict[str, Any]:
    config = ByocConfig.load()
    store = ThinkStashStore(":memory:")
    last = store.last_harvest()

    if last is None:
        return {
            "stash_id": None,
            "message": "No THINK stash entries recorded yet",
            "evidence_label": "simulated",
        }

    redacted: dict[str, Any] = {
        "stash_id": last.get("stash_id"),
        "session_id": last.get("session_id"),
        "burst_id": last.get("burst_id"),
        "reasoning_sha256": last.get("reasoning_sha256"),
        "vector_id": last.get("vector_id"),
        "proof_receipt_id": last.get("proof_receipt_id"),
        "evidence_label": last.get("evidence_label", "simulated"),
        "created_at": last.get("created_at"),
    }

    await _dashboard_state.emit(
        DashboardCategory.THINK_BOXES,
        DashboardEvent.TASK_COMPLETED,
        {"stash_id": last.get("stash_id"), "action": "read_last"},
        "think_stash_api",
        evidence_label="simulated",
    )

    return redacted


@think_stash_router.get("/search")
async def stash_search(query_vector: str, top_k: int = 5) -> list[dict[str, Any]]:
    config = ByocConfig.load()
    if not config.is_live:
        return []
    try:
        from thinkbox.byoc_stash_reader import ThinkStashReader
        reader = ThinkStashReader(config)
        vector = json.loads(query_vector) if isinstance(query_vector, str) else query_vector
        if not isinstance(vector, list):
            return []
        return reader.search(vector, top_k=top_k)
    except Exception as e:
        logger.warning("Stash search failed: %s", e)
        return []
