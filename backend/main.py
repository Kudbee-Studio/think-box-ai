"""THINK BOX AI — Unified Backend (FastAPI + WebSocket + SSE).

Uses the core runtime for agent execution, tool management, and memory.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from core.foundation.bootstrap import bootstrap, RuntimeContext
from core.foundation.logging import get_logger
from core.runtime.loop import AgentLoop

logger = get_logger(__name__)

app = FastAPI(title="THINK BOX AI", version="0.4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ctx: RuntimeContext | None = None
sessions: dict[str, dict[str, Any]] = {}


@app.on_event("startup")
async def startup() -> None:
    global ctx
    ctx = bootstrap(
        project_root=os.getenv("THINKBOX_PROJECT_ROOT", "."),
        with_provider=True,
        with_tools=True,
    )
    logger.info("THINK BOX AI started", extra={
        "provider": ctx.provider.__class__.__name__ if ctx.provider else None,
        "tools": len(ctx.tool_registry.list_tools()) if ctx.tool_registry else 0,
    })


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "think-box-ai",
        "version": "0.2.0",
        "provider": ctx.provider.__class__.__name__ if ctx.provider else None,
        "tools": len(ctx.tool_registry.list_tools()) if ctx.tool_registry else 0,
        "sessions": len(sessions),
    }


@app.get("/models")
async def get_models() -> dict[str, Any]:
    return {"models": ["ollama", "openai_compat"]}


@app.get("/tools")
async def get_tools() -> dict[str, Any]:
    if not ctx or not ctx.tool_registry:
        return {"tools": []}
    return {"tools": [t.to_dict() for t in ctx.tool_registry.list_tools()]}


@app.post("/run")
async def run_goal(request: dict[str, Any]) -> dict[str, Any]:
    if not ctx or not ctx.provider:
        return {"success": False, "error": "No provider configured"}

    goal = request.get("goal", "")
    if not goal:
        return {"success": False, "error": "Missing 'goal'"}

    loop = AgentLoop(
        provider=ctx.provider,
        tool_registry=ctx.tool_registry,
        max_iterations=request.get("max_iterations", 20),
    )

    result = await loop.run(goal)
    return result


@app.get("/stream")
async def stream_goal(goal: str, model: str = "ollama") -> StreamingResponse:
    async def event_generator():
        if not ctx or not ctx.provider:
            yield f"data: {json.dumps({'error': 'No provider configured'})}\n\n"
            return

        loop = AgentLoop(
            provider=ctx.provider,
            tool_registry=ctx.tool_registry,
        )

        yield f"data: {json.dumps({'type': 'start', 'goal': goal})}\n\n"

        messages = [
            {"role": "system", "content": loop.system_prompt},
            {"role": "user", "content": f"Goal: {goal}"},
        ]

        try:
            async for token in ctx.provider.stream(messages):
                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "id": session_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "idle",
    }

    await ws.send_json({
        "type": "init",
        "data": {
            "sessionId": session_id,
            "tools": [t.to_dict() for t in ctx.tool_registry.list_tools()] if ctx and ctx.tool_registry else [],
        },
    })

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type")

            if msg_type == "run_goal":
                goal = msg.get("goal", "")
                if not goal or not ctx or not ctx.provider:
                    await ws.send_json({"type": "error", "data": "Missing goal or provider"})
                    continue

                sessions[session_id]["status"] = "running"
                await ws.send_json({"type": "status", "data": {"status": "running"}})

                loop = AgentLoop(
                    provider=ctx.provider,
                    tool_registry=ctx.tool_registry,
                )

                result = await loop.run(goal)

                await ws.send_json({"type": "result", "data": result})
                sessions[session_id]["status"] = "idle"
                await ws.send_json({"type": "status", "data": {"status": "idle"}})

            elif msg_type == "stop":
                sessions[session_id]["status"] = "idle"
                await ws.send_json({"type": "status", "data": {"status": "idle"}})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        sessions.pop(session_id, None)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
