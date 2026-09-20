"""THINK BOX AI — Unified Backend (FastAPI + WebSocket + SSE).

Production-grade security with authentication, rate limiting, CORS,
input validation, request timeouts, and graceful shutdown.
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from core.foundation.bootstrap import bootstrap, RuntimeContext
from core.foundation.logging import get_logger
from core.runtime.loop import AgentLoop

from backend.security import setup_security, validate_ws_token, get_api_keys
from backend.validation import validate_goal, validate_iterations
from backend.audit_storage import record_audit
from thinkbox.dashboard_state import get_dashboard_state, DashboardState, DashboardCategory, DashboardEvent, ThinkBoxEntry, ThinkJobEntry, CNCJobEntry, InfrastructureEntry, ProviderEntry, TestMilestoneEntry

logger = get_logger(__name__)

app = FastAPI(title="THINK BOX AI", version="0.5.0")

setup_security(app)

ctx: RuntimeContext | None = None
sessions: dict[str, dict[str, Any]] = {}
shutdown_event = asyncio.Event()
MAX_SESSIONS = 1000
REQUEST_TIMEOUT = 30

_dashboard_state = get_dashboard_state()
_active_ws_clients: list[WebSocket] = []
_active_sse_clients: list[asyncio.Queue] = []

api_v1 = APIRouter(prefix="/api/v1")


@api_v1.get("/health")
async def health_v1() -> dict[str, Any]:
    return await health()


@api_v1.get("/models")
async def models_v1() -> dict[str, Any]:
    return await get_models()


@api_v1.get("/tools")
async def tools_v1() -> dict[str, Any]:
    return await get_tools()


@api_v1.post("/run")
async def run_v1(request: dict[str, Any]) -> dict[str, Any]:
    return await run_goal(request)


@api_v1.get("/stream")
async def stream_v1(goal: str, model: str = "ollama") -> StreamingResponse:
    return await stream_goal(goal, model)


@api_v1.get("/audit")
async def audit_v1(limit: int = 100) -> dict[str, Any]:
    return await get_audit_log(limit)


app.include_router(api_v1)


from backend.api.v1.router import api_v1_router
app.include_router(api_v1_router)

from backend.api.v1.box_status import box_status_router
app.include_router(box_status_router)

from backend.api.v1.box_mercury import box_mercury_router
app.include_router(box_mercury_router)

from backend.api.v1.lifecycle_receipts import lifecycle_receipts_router
app.include_router(lifecycle_receipts_router)


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
    record_audit("system_startup", "system", "success", {
        "provider": ctx.provider.__class__.__name__ if ctx.provider else None,
    })


@app.on_event("shutdown")
async def shutdown() -> None:
    logger.info("Shutting down Think Box AI...")
    shutdown_event.set()

    active_sessions = list(sessions.keys())
    for session_id in active_sessions:
        sessions.pop(session_id, None)

    record_audit("system_shutdown", "system", "success", {
        "sessions_closed": len(active_sessions),
    })
    logger.info("Shutdown complete")


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "think-box-ai",
        "version": "0.5.0",
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
    valid, result = validate_goal(goal)
    if not valid:
        return {"success": False, "error": result}
    goal = result

    max_iterations = validate_iterations(request.get("max_iterations", 20))

    record_audit("run_goal", "api", "started", {"goal": goal[:100]})

    loop = AgentLoop(
        provider=ctx.provider,
        tool_registry=ctx.tool_registry,
        max_iterations=max_iterations,
    )

    try:
        result = await asyncio.wait_for(loop.run(goal), timeout=REQUEST_TIMEOUT)
    except asyncio.TimeoutError:
        record_audit("run_goal", "api", "timeout", {"goal": goal[:100]})
        return {"success": False, "error": f"Request timed out after {REQUEST_TIMEOUT}s"}

    record_audit("run_goal", "api", "completed", {
        "goal": goal[:100],
        "success": result.get("success", False),
    })

    return result


@app.get("/stream")
async def stream_goal(goal: str, model: str = "ollama") -> StreamingResponse:
    valid, result = validate_goal(goal)
    if not valid:
        async def error_stream():
            yield f"data: {json.dumps({'error': result})}\n\n"
        return StreamingResponse(error_stream(), media_type="text/event-stream")
    goal = result

    async def event_generator():
        if not ctx or not ctx.provider:
            yield f"data: {json.dumps({'error': 'No provider configured'})}\n\n"
            return

        loop = AgentLoop(
            provider=ctx.provider,
            tool_registry=ctx.tool_registry,
        )

        yield f"data: {json.dumps({'type': 'start', 'goal': goal})}\n\n"

        try:
            async for token in ctx.provider.stream([
                {"role": "system", "content": loop.system_prompt},
                {"role": "user", "content": f"Goal: {goal}"},
            ]):
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
    valid_keys = get_api_keys()
    query_params = dict(ws.query_params)
    headers_key = ws.headers.get("x-api-key", "")

    if not validate_ws_token(query_params, {headers_key: headers_key} if headers_key else {}, valid_keys):
        await ws.close(code=4001, reason="Unauthorized")
        return

    if len(sessions) >= MAX_SESSIONS:
        await ws.close(code=4002, reason="Server at capacity")
        return

    await ws.accept()
    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "id": session_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "idle",
    }

    record_audit("ws_connect", session_id, "connected")

    await ws.send_json({
        "type": "init",
        "data": {
            "sessionId": session_id,
            "tools": [t.to_dict() for t in ctx.tool_registry.list_tools()] if ctx and ctx.tool_registry else [],
        },
    })

    try:
        while not shutdown_event.is_set():
            raw = await ws.receive_text()
            if len(raw) > 1_048_576:
                await ws.send_json({"type": "error", "data": "Message too large"})
                continue

            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "data": "Invalid JSON"})
                continue

            msg_type = msg.get("type")

            if msg_type == "run_goal":
                goal = msg.get("goal", "")
                valid, result = validate_goal(goal)
                if not valid:
                    await ws.send_json({"type": "error", "data": result})
                    continue
                goal = result

                if not ctx or not ctx.provider:
                    await ws.send_json({"type": "error", "data": "No provider configured"})
                    continue

                sessions[session_id]["status"] = "running"
                await ws.send_json({"type": "status", "data": {"status": "running"}})

                record_audit("ws_run_goal", session_id, "started", {"goal": goal[:100]})

                loop = AgentLoop(
                    provider=ctx.provider,
                    tool_registry=ctx.tool_registry,
                )

                try:
                    result = await asyncio.wait_for(loop.run(goal), timeout=REQUEST_TIMEOUT)
                except asyncio.TimeoutError:
                    await ws.send_json({"type": "error", "data": f"Timeout after {REQUEST_TIMEOUT}s"})
                    sessions[session_id]["status"] = "idle"
                    continue

                await ws.send_json({"type": "result", "data": result})
                sessions[session_id]["status"] = "idle"
                await ws.send_json({"type": "status", "data": {"status": "idle"}})

                record_audit("ws_run_goal", session_id, "completed", {
                    "goal": goal[:100],
                    "success": result.get("success", False),
                })

            elif msg_type == "stop":
                sessions[session_id]["status"] = "idle"
                await ws.send_json({"type": "status", "data": {"status": "idle"}})

    except WebSocketDisconnect:
        record_audit("ws_disconnect", session_id, "disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        record_audit("ws_error", session_id, "error", {"error": str(e)})
    finally:
        sessions.pop(session_id, None)


@app.get("/audit")
async def get_audit_log(limit: int = 100) -> dict[str, Any]:
    from backend.audit_storage import list_audits
    safe_limit = min(max(limit, 1), 1000)
    entries = list_audits(limit=safe_limit)
    return {"entries": entries, "count": len(entries)}


@app.get("/dashboard/state")
async def get_dashboard_state() -> dict[str, Any]:
    return _dashboard_state.get_state()


@app.websocket("/dashboard/ws")
async def dashboard_websocket(ws: WebSocket) -> None:
    valid_keys = get_api_keys()
    query_params = dict(ws.query_params)
    headers_key = ws.headers.get("x-api-key", "")

    if not validate_ws_token(query_params, {headers_key: headers_key} if headers_key else {}, valid_keys):
        await ws.close(code=4001, reason="Unauthorized")
        return

    await ws.accept()
    _active_ws_clients.append(ws)

    try:
        await ws.send_json({"type": "dashboard_init", "data": _dashboard_state.get_state()})
        while not shutdown_event.is_set():
            raw = await ws.receive_text()
            if len(raw) > 1_048_576:
                await ws.send_json({"type": "error", "data": "Message too large"})
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "data": "Invalid JSON"})
                continue

            msg_type = msg.get("type")
            if msg_type == "ping":
                await ws.send_json({"type": "pong"})
            elif msg_type == "get_state":
                await ws.send_json({"type": "state", "data": _dashboard_state.get_state()})
            elif msg_type == "think_box":
                box_data = msg.get("data", {})
                box = ThinkBoxEntry(
                    box_id=box_data.get("box_id", str(uuid.uuid4())),
                    name=box_data.get("name", "Unknown"),
                    substrate=box_data.get("substrate", "local"),
                    status=box_data.get("status", "idle"),
                    metadata=box_data.get("metadata", {}),
                )
                _dashboard_state.upsert_think_box(box)
                await _broadcast_dashboard({"type": "think_box_updated", "data": box.model_dump()})
            elif msg_type == "think_job":
                job_data = msg.get("data", {})
                job = ThinkJobEntry(
                    job_id=job_data.get("job_id", str(uuid.uuid4())),
                    goal=job_data.get("goal", ""),
                    status=job_data.get("status", "pending"),
                    engine_id=job_data.get("engine_id", ""),
                    phase=job_data.get("phase", ""),
                    progress=job_data.get("progress", 0.0),
                    tasks_total=job_data.get("tasks_total", 0),
                    tasks_completed=job_data.get("tasks_completed", 0),
                    result=job_data.get("result", {}),
                )
                _dashboard_state.upsert_think_job(job)
                await _broadcast_dashboard({"type": "think_job_updated", "data": job.model_dump()})
            elif msg_type == "cnc_job":
                cnc_data = msg.get("data", {})
                cnc_job = CNCJobEntry(
                    job_id=cnc_data.get("job_id", str(uuid.uuid4())),
                    part_name=cnc_data.get("part_name", ""),
                    part_number=cnc_data.get("part_number", ""),
                    material=cnc_data.get("material", ""),
                    machine=cnc_data.get("machine", ""),
                    status=cnc_data.get("status", "created"),
                    operations=cnc_data.get("operations", []),
                    customer_id=cnc_data.get("customer_id", "default"),
                    priority=cnc_data.get("priority", "normal"),
                    safety_approved=cnc_data.get("safety_approved", False),
                )
                _dashboard_state.upsert_cnc_job(cnc_job)
                await _broadcast_dashboard({"type": "cnc_job_updated", "data": cnc_job.model_dump()})
            elif msg_type == "infrastructure":
                infra_data = msg.get("data", {})
                infra = InfrastructureEntry(
                    component=infra_data.get("component", "unknown"),
                    type=infra_data.get("type", "unknown"),
                    status=infra_data.get("status", "unknown"),
                    substrate=infra_data.get("substrate", "local"),
                    verified=infra_data.get("verified", False),
                    details=infra_data.get("details", {}),
                )
                _dashboard_state.upsert_infrastructure(infra.component, infra)
                await _broadcast_dashboard({"type": "infrastructure_updated", "data": infra.model_dump()})
            elif msg_type == "provider":
                prov_data = msg.get("data", {})
                prov = ProviderEntry(
                    name=prov_data.get("name", "unknown"),
                    model=prov_data.get("model", ""),
                    status=prov_data.get("status", "unknown"),
                    endpoint=prov_data.get("endpoint", ""),
                    latency_ms=prov_data.get("latency_ms", 0.0),
                    rps=prov_data.get("rps", 0.0),
                    verified=prov_data.get("verified", False),
                    details=prov_data.get("details", {}),
                )
                _dashboard_state.upsert_provider(prov)
                await _broadcast_dashboard({"type": "provider_updated", "data": prov.model_dump()})
            elif msg_type == "test_milestone":
                test_data = msg.get("data", {})
                milestone = TestMilestoneEntry(
                    test_name=test_data.get("test_name", "unknown"),
                    module=test_data.get("module", ""),
                    status=test_data.get("status", "pending"),
                    count=test_data.get("count", 0),
                    passed=test_data.get("passed", 0),
                    failed=test_data.get("failed", 0),
                    skipped=test_data.get("skipped", 0),
                    duration_ms=test_data.get("duration_ms", 0.0),
                )
                _dashboard_state.upsert_test_milestone(milestone)
                await _broadcast_dashboard({"type": "test_milestone_updated", "data": milestone.model_dump()})
    except WebSocketDisconnect:
        _active_ws_clients.remove(ws)
    except Exception as e:
        logger.error(f"Dashboard WebSocket error: {e}")
    finally:
        if ws in _active_ws_clients:
            _active_ws_clients.remove(ws)


async def _broadcast_dashboard(data: dict[str, Any]) -> None:
    disconnected: list[WebSocket] = []
    for client in _active_ws_clients:
        try:
            await client.send_json(data)
        except Exception:
            disconnected.append(client)
    for client in disconnected:
        _active_ws_clients.remove(client)


async def dashboard_sse_stream() -> AsyncGenerator[str, None]:
    queue: asyncio.Queue[DashboardEventEntry] = asyncio.Queue()
    await _dashboard_state.register_subscriber(queue)
    try:
        while True:
            event = await queue.get()
            yield f"data: {json.dumps(event.model_dump())}\n\n"
    except asyncio.CancelledError:
        _dashboard_state._subscribers.remove(queue)
        raise


@app.get("/dashboard/stream")
async def dashboard_stream() -> StreamingResponse:
    return StreamingResponse(
        dashboard_sse_stream(),
        media_type="text/event-stream",
    )


async def broadcast_event(category: DashboardCategory, event_type: DashboardEvent,
                           data: dict[str, Any], source: str = "",
                           evidence_label: str = "simulated") -> None:
    entry = await _dashboard_state.emit(category, event_type, data, source, evidence_label)
    await _broadcast_dashboard({"type": "event", "data": entry.model_dump()})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
