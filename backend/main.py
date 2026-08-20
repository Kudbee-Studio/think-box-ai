"""kudbEE — Agent OS Backend (FastAPI + WebSocket + SSE)."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from backend.core.event_bus import event_bus
from backend.agent_loop import run_agent_task
from backend.models.ollama_client import list_models
from backend.plugins.registry import plugin_registry

app = FastAPI(title="kudbEE Agent OS", version="0.1.0")

# CORS for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── State ──────────────────────────────────────────────────────
sessions: dict[str, dict[str, Any]] = {}
pending_approval: dict[str, dict[str, Any]] = {}


# ─── Health ─────────────────────────────────────────────────────
@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "kudbEE",
        "version": "0.1.0",
        "sessions": len(sessions),
        "plugins": len(plugin_registry.list_tools()),
    }


# ─── Models ─────────────────────────────────────────────────────
@app.get("/models")
async def get_models() -> dict[str, Any]:
    """List available Ollama models."""
    models = await list_models()
    return {"models": models}


# ─── Plugins ────────────────────────────────────────────────────
@app.get("/plugins")
async def get_plugins() -> dict[str, Any]:
    """List all registered plugins."""
    return {"plugins": plugin_registry.list_tools()}


# ─── SSE token stream ───────────────────────────────────────────
async def token_stream(goal: str, model: str) -> AsyncGenerator[str, None]:
    """Stream model tokens via SSE."""
    messages = [
        {"role": "system", "content": "You are kudbEE, an intelligent agent OS. You help developers accomplish goals by using tools. Think step by step. Be concise and actionable."},
        {"role": "user", "content": f"Goal: {goal}\n\nAvailable tools: {', '.join([t.name for t in plugin_registry.get_enabled()])}\n\nExecute this goal step by step."},
    ]

    async for token in stream_chat(model, messages, temperature=0.7, max_tokens=4096):
        yield f"data: {token}\n\n"
    yield "data: [DONE]\n\n"


@app.get("/stream")
async def stream_endpoint(goal: str, model: str = "deepseek-coder:6.7b") -> StreamingResponse:
    """Stream model response via SSE."""
    return StreamingResponse(
        token_stream(goal, model),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ─── WebSocket ──────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "id": session_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "idle",
        "current_task": None,
    }

    await event_bus.register(ws)

    try:
        # Send init event
        await ws.send_json({
            "type": "init",
            "data": {
                "sessionId": session_id,
                "plugins": plugin_registry.list_tools(),
                "models": await list_models(),
            },
        })

        await event_bus.broadcast_status("idle")

        while True:
            raw = await ws.receive_text()
            msg: dict[str, Any] = __import__('json').loads(raw)
            await handle_message(ws, session_id, msg)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await ws.send_json({"type": "error", "data": str(e)})
        except Exception:
            pass
    finally:
        await event_bus.unregister(ws)
        if session_id in sessions:
            del sessions[session_id]


async def handle_message(ws: WebSocket, session_id: str, msg: dict[str, Any]) -> None:
    """Handle incoming WebSocket messages."""
    msg_type = msg.get("type")

    if msg_type == "run_goal":
        goal = msg.get("goal", "")
        model = msg.get("model", "deepseek-coder:6.7b")
        if not goal:
            return

        await event_bus.broadcast_status("running")
        sessions[session_id]["status"] = "running"
        sessions[session_id]["current_task"] = {
            "goal": goal,
            "model": model,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }

        # Run agent loop in background
        asyncio.create_task(run_agent_task(ws, session_id, goal, model))

    elif msg_type == "stop":
        sessions[session_id]["status"] = "idle"
        sessions[session_id]["current_task"] = None
        await event_bus.broadcast_status("idle")
        await event_bus.broadcast_thought("Task stopped by user", status="info")

    elif msg_type == "plugin_execute":
        plugin_name = msg.get("plugin", "")
        plugin_input = msg.get("input", {})
        plugin = plugin_registry.get(plugin_name)

        if not plugin:
            await ws.send_json({
                "type": "plugin_result",
                "data": {"plugin": plugin_name, "result": {"success": False, "error": "Plugin not found"}},
            })
            return

        await event_bus.broadcast_tool_call(plugin_name, plugin_input)

        if plugin.requires_approval:
            action_id = str(uuid.uuid4())[:8]
            await event_bus.broadcast_risky_action(
                action_id=action_id,
                description=f"Tool {plugin_name} requires approval",
                risk_level="medium",
            )
            pending_approval[session_id] = {
                "action_id": action_id,
                "plugin_name": plugin_name,
                "plugin_input": plugin_input,
            }
            return

        result = await plugin.run(plugin_input, context={"session_id": session_id})
        payload = {
            "success": result.success,
            "data": result.data,
            "error": result.error,
        }
        await event_bus.broadcast_tool_result(plugin_name, payload)

    elif msg_type == "list_models":
        models = await list_models()
        await ws.send_json({"type": "models", "data": models})

    elif msg_type == "approve":
        action_id = msg.get("action_id", "")
        pending = pending_approval.pop(session_id, None)
        if not pending or pending["action_id"] != action_id:
            await event_bus.broadcast_thought(f"Action {action_id} not found or already handled", status="error")
            return

        plugin_name = pending["plugin_name"]
        plugin_input = pending["plugin_input"]
        result = await plugin_registry.get(plugin_name).run(plugin_input, context={"session_id": session_id})
        payload = {
            "success": result.success,
            "data": result.data,
            "error": result.error,
        }
        await event_bus.broadcast_tool_result(plugin_name, payload)
        await event_bus.broadcast_thought(f"Action {action_id} approved by user", status="success")

    elif msg_type == "reject":
        action_id = msg.get("action_id", "")
        action_label = action_id or "<unknown>"
        if not action_id:
            await event_bus.broadcast_thought(f"Action {action_label} not found or already handled", status="error")
            return

        pending = pending_approval.get(session_id)
        if not pending or pending["action_id"] != action_id:
            await event_bus.broadcast_thought(f"Action {action_label} not found or already handled", status="error")
            return

        pending_approval.pop(session_id, None)
        await event_bus.broadcast_thought(f"Action {action_id} rejected by user", status="error")


async def run_agent_task(ws: WebSocket, session_id: str, goal: str, model: str) -> None:
    """Run the agent loop for a goal."""
    from backend.agent_loop import AgentLoop

    loop = AgentLoop(session_id=session_id, model=model)
    result = await loop.run(goal)

    if result.get("success"):
        await ws.send_json({"type": "result", "data": {"success": True, "result": result.get("result", "")}})
    else:
        await ws.send_json({"type": "error", "data": result.get("error", "Unknown error")})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
