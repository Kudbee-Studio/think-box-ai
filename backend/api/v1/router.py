"""ThinkBox API v1 Router.

Exposes endpoints for running the ThinkBox engine and streaming telemetry.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from thinkbox.engine import ThinkBoxEngine, EngineConfig
from thinkbox.model_client import ModelConfig
from thinkbox.session import create_session, get_current_session, sync_session, clear_session
from backend.security import get_api_keys, validate_ws_token


api_v1_router = APIRouter(prefix="/api/v1")

active_engines: dict[str, ThinkBoxEngine] = {}


class RunRequest(BaseModel):
    goal: str
    speculative: bool = True
    model: str | None = None
    temperature: float | None = None


class RunResponse(BaseModel):
    engine_id: str
    session_id: str
    status: str
    summary: dict[str, Any]


@api_v1_router.post("/run", response_model=RunResponse)
async def run_goal(request: RunRequest) -> RunResponse:
    model_config = ModelConfig()
    if request.model:
        model_config.model = request.model
    if request.temperature is not None:
        model_config.temperature = request.temperature

    engine_config = EngineConfig(
        model_config=model_config,
        speculative=request.speculative,
    )
    engine = ThinkBoxEngine(engine_config)
    active_engines[engine.engine_id] = engine

    asyncio.create_task(engine.execute_goal(request.goal))

    return RunResponse(
        engine_id=engine.engine_id,
        session_id="",
        status="started",
        summary={"goal": request.goal[:100]},
    )


@api_v1_router.get("/engine/{engine_id}")
async def get_engine_status(engine_id: str) -> dict[str, Any]:
    engine = active_engines.get(engine_id)
    if not engine:
        raise HTTPException(status_code=404, detail="Engine not found")
    return engine.get_stats()


@api_v1_router.get("/engines")
async def list_engines() -> dict[str, Any]:
    return {
        "engines": [
            {"engine_id": eid, "events": len(e.events)}
            for eid, e in active_engines.items()
        ]
    }


@api_v1_router.websocket("/ws")
async def websocket_telemetry(websocket: WebSocket) -> None:
    valid_keys = get_api_keys()
    query_params = dict(websocket.query_params)
    headers_key = websocket.headers.get("x-api-key", "")

    if not validate_ws_token(query_params, {headers_key: headers_key} if headers_key else {}, valid_keys):
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await websocket.accept()

    try:
        while True:
            data = {
                "type": "system_status",
                "active_engines": len(active_engines),
                "engines": {
                    eid: e.get_stats()
                    for eid, e in active_engines.items()
                },
            }
            await websocket.send_json(data)
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
