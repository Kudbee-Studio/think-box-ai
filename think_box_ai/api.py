"""Think Box AI — REST API.

FastAPI-based backend for the Think Box dashboard and programmatic access.
"""

from __future__ import annotations

import os
import time
import uuid
from typing import Any

from core.execution import LocalExecProvider
from core.governance.audit import AuditLog
from core.memory.store import MemoryStore
from core.providers.base import Message

try:
    from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
    from fastapi.middleware.cors import CORSMiddleware
except ImportError:
    FastAPI = None  # type: ignore

from think_box_ai.cli import _get_store, _get_db_path

app = FastAPI(
    title="Think Box AI",
    description="Agent execution environment with token tracking",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, Any]:
    """Health check endpoint."""
    from core.foundation.health import full_health_check

    db_path = _get_db_path()
    return full_health_check(db_path if os.path.exists(db_path) else None)


@app.get("/api/v1/boxes")
async def list_boxes() -> dict[str, Any]:
    """List all Think Boxes."""
    store = _get_store()
    return {"boxes": store.list_boxes()}


@app.get("/api/v1/boxes/{box_id}")
async def get_box(box_id: str) -> dict[str, Any]:
    """Get a specific Think Box."""
    store = _get_store()
    box = store.get_box(box_id)
    if box is None:
        raise HTTPException(status_code=404, detail="Box not found")
    box["tokens"] = store.list_tokens(box_id)
    return box


@app.post("/api/v1/boxes")
async def create_box(goal: str = "") -> dict[str, Any]:
    """Create a new Think Box."""
    box_id = f"tb-{uuid.uuid4().hex[:12]}"
    store = _get_store()
    store.save_box(box_id, goal=goal, state="created")
    return {"id": box_id, "goal": goal, "state": "created"}


@app.delete("/api/v1/boxes/{box_id}")
async def delete_box(box_id: str) -> dict[str, Any]:
    """Delete a Think Box and all its data."""
    store = _get_store()
    store.delete_box(box_id)
    return {"deleted": box_id}


@app.post("/api/v1/boxes/{box_id}/exec")
async def exec_command(box_id: str, command: str) -> dict[str, Any]:
    """Execute a command in a Think Box."""
    from core.runtime.actor import Actor
    from core.runtime.planner import Step

    store = _get_store()
    box = store.get_box(box_id)
    if box is None:
        raise HTTPException(status_code=404, detail="Box not found")

    provider = LocalExecProvider()
    audit_log = AuditLog()
    actor = Actor(audit_log=audit_log, execution_provider=provider)

    step = Step(
        id=f"exec-{uuid.uuid4().hex[:8]}",
        description=command,
        action="execute",
        command=command,
    )
    agent = type("FakeAgent", (), {"agent_id": "api-agent"})()
    think_box = type("FakeThinkBox", (), {"think_box_id": box_id})()

    import asyncio
    result = asyncio.run(actor.execute_step(agent, think_box, step))
    store.update_box_state(box_id, "complete")
    return result


@app.get("/api/v1/boxes/{box_id}/tokens")
async def list_tokens(box_id: str) -> dict[str, Any]:
    """List tokens for a Think Box."""
    store = _get_store()
    return {"tokens": store.list_tokens(box_id)}


@app.get("/api/v1/tokens/{token_id}")
async def get_token(token_id: str) -> dict[str, Any]:
    """Get a specific token."""
    store = _get_store()
    token = store.get_token(token_id)
    if token is None:
        raise HTTPException(status_code=404, detail="Token not found")
    token["challenges"] = store.list_challenges(token_id)
    return token


@app.post("/api/v1/tokens/{token_id}/challenge")
async def add_challenge(token_id: str, challenge_type: str, outcome: int) -> dict[str, Any]:
    """Add a challenge to a token."""
    store = _get_store()
    challenge_id = store.add_challenge(token_id, challenge_type, outcome)
    if challenge_id is None:
        raise HTTPException(status_code=400, detail="Invalid challenge")
    return {"challenge_id": challenge_id, "type": challenge_type, "outcome": outcome}


@app.get("/api/v1/upcloud")
async def upcloud_dashboard() -> dict[str, Any]:
    """Get UpCloud dashboard data."""
    from core.infrastructure.upcloud import get_dashboard_data
    return get_dashboard_data()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket for real-time agent communication."""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_json({"echo": data, "timestamp": time.time()})
    except WebSocketDisconnect:
        pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
