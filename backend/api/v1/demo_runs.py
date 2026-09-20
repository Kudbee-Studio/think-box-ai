"""API GET /demo/runs + /demo/runs/{id}/proof (evidence_label=simulated)."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from thinkbox.agent.control_plane.demo_record import (
    DemoRunRecord,
    create_run_table,
    last_run,
    load_run,
    save_run,
)
from thinkbox.agent.control_plane.store import ActionReceiptStore
from thinkbox.agent.control_plane.demo_proof import emit_proof_bundle

logger = logging.getLogger(__name__)

demo_router = APIRouter(prefix="/demo")


@demo_router.get("/runs")
async def list_runs() -> list[dict[str, Any]]:
    """List all demo runs."""
    import sqlite3
    conn = sqlite3.connect(":memory:")
    create_run_table(conn)
    rows = conn.execute(
        "SELECT run_id FROM demo_runs ORDER BY started_at DESC"
    ).fetchall()
    conn.close()
    return [{"run_id": r[0]} for r in rows]


@demo_router.get("/runs/{run_id}")
async def get_run(run_id: str) -> dict[str, Any]:
    """Get a specific demo run."""
    import sqlite3
    conn = sqlite3.connect(":memory:")
    create_run_table(conn)
    record = load_run(conn, run_id)
    conn.close()
    if record is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return record


@demo_router.get("/runs/{run_id}/proof")
async def get_run_proof(run_id: str) -> dict[str, Any]:
    """Get proof bundle for a demo run (evidence_label=simulated)."""
    store = ActionReceiptStore(":memory:")
    from thinkbox.agent.control_plane.kernel_hooks import HookContext, on_admit
    on_admit(store, HookContext(agent_id=run_id, action="admit", evidence_label="simulated"))
    bundle = emit_proof_bundle(store, run_id, output_dir=f"data/proofs/{run_id}")
    bundle["evidence_label"] = "simulated"
    return bundle
