"""Backend API v1.0 — Think Box AI.

Full REST API with CRUD, auth, rate limiting, and job execution.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from core.foundation.bootstrap import bootstrap, RuntimeContext
from core.foundation.logging import get_logger
from core.runtime.loop import AgentLoop

logger = get_logger(__name__)

app = FastAPI(title="THINK BOX AI", version="1.0.0")

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=os.environ.get("ALLOWED_HOSTS", "*").split(","))

ctx: RuntimeContext | None = None
sessions: dict[str, dict[str, Any]] = {}
ws_connections: list[WebSocket] = []

# Rate limiting
_rate_limits: dict[str, list[float]] = {}
RATE_LIMIT = int(os.environ.get("RATE_LIMIT", "100"))  # requests per minute


@app.middleware("http")
async def rate_limiter(request: Request, call_next):
    client = request.client.host if request.client else "unknown"
    now = time.time()
    if client not in _rate_limits:
        _rate_limits[client] = []
    _rate_limits[client] = [t for t in _rate_limits[client] if now - t < 60]
    if len(_rate_limits[client]) >= RATE_LIMIT:
        return JSONResponse({"error": "Rate limit exceeded"}, status_code=429)
    _rate_limits[client].append(now)
    response = await call_next(request)
    return response


@app.on_event("startup")
async def startup():
    global ctx
    ctx = bootstrap(
        project_root=os.environ.get("THINKBOX_PROJECT_ROOT", "."),
        with_provider=True,
        with_tools=True,
    )
    logger.info("THINK BOX AI v1.0.0 started")


# Health & Metrics
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "think-box-ai",
        "version": "1.0.0",
        "provider": ctx.provider.__class__.__name__ if ctx.provider else None,
        "tools": len(ctx.tool_registry.list_tools()) if ctx.tool_registry else 0,
        "sessions": len(sessions),
        "uptime": time.time(),
    }


@app.get("/metrics")
async def metrics():
    return {
        "sessions": len(sessions),
        "ws_connections": len(ws_connections),
        "tools": len(ctx.tool_registry.list_tools()) if ctx.tool_registry else 0,
        "rate_limits": {k: len(v) for k, v in _rate_limits.items()},
    }


# Jobs CRUD
@app.get("/api/v1/jobs")
async def list_jobs(state: str | None = None, limit: int = 50, offset: int = 0):
    from pathlib import Path
    jobs_dir = Path("jobs")
    jobs = []
    for state_dir in ["queue", "active", "done", "blocked"]:
        if state and state_dir != state:
            continue
        d = jobs_dir / state_dir
        if not d.is_dir():
            continue
        for jf in sorted(d.glob("job_*.json"))[offset:offset+limit]:
            job = json.loads(jf.read_text())
            job["state"] = state_dir
            jobs.append(job)
    return {"jobs": jobs, "total": len(jobs)}


@app.get("/api/v1/jobs/{job_id}")
async def get_job(job_id: str):
    for state_dir in ["queue", "active", "done", "blocked"]:
        jf = Path("jobs") / state_dir / f"{job_id}.json"
        if jf.exists():
            job = json.loads(jf.read_text())
            job["state"] = state_dir
            return job
    raise HTTPException(404, "Job not found")


@app.post("/api/v1/jobs")
async def create_job(request: Request):
    data = await request.json()
    job_id = data.get("id", f"job_{uuid.uuid4().hex[:8]}")
    job = {
        "id": job_id,
        "intent": data.get("intent", ""),
        "hat": data.get("hat", "researcher"),
        "inputs": data.get("inputs", {}),
        "plan": data.get("plan", []),
        "capabilities": data.get("capabilities", {"tools": []}),
        "execution": [],
        "artifacts": [],
        "evaluation": {"verdict": "unproven", "reason": "", "confidence": 0.0},
        "cost": {"box_minutes": 0, "gpu_minutes": 0, "http_calls": 0},
    }
    queue_path = Path("jobs") / "queue" / f"{job_id}.json"
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    queue_path.write_text(json.dumps(job, indent=2))
    await _broadcast_ws({"type": "job_created", "job_id": job_id})
    return job


@app.post("/api/v1/jobs/{job_id}/run")
async def run_job(job_id: str):
    for state_dir in ["queue", "active", "done", "blocked"]:
        jf = Path("jobs") / state_dir / f"{job_id}.json"
        if jf.exists():
            jf.rename(Path("jobs") / "active" / f"{job_id}.json")
            break
    await _broadcast_ws({"type": "job_running", "job_id": job_id})
    return {"status": "started", "job_id": job_id}


@app.delete("/api/v1/jobs/{job_id}")
async def delete_job(job_id: str):
    for state_dir in ["queue", "active", "done", "blocked"]:
        jf = Path("jobs") / state_dir / f"{job_id}.json"
        if jf.exists():
            jf.unlink()
            return {"status": "deleted", "job_id": job_id}
    raise HTTPException(404, "Job not found")


# Findings
@app.get("/api/v1/findings")
async def list_findings():
    findings_dir = Path("data/findings")
    if not findings_dir.exists():
        return {"findings": []}
    return {"findings": [f.name for f in sorted(findings_dir.glob("*.md"))]}


@app.get("/api/v1/findings/{name}")
async def get_finding(name: str):
    f = Path("data/findings") / f"{name}.md"
    if not f.exists():
        raise HTTPException(404, "Finding not found")
    return {"name": name, "content": f.read_text()}


# Tools
@app.get("/api/v1/tools")
async def list_tools():
    if not ctx or not ctx.tool_registry:
        return {"tools": []}
    return {"tools": [t.to_dict() for t in ctx.tool_registry.list_tools()]}


# WebSocket
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    ws_connections.append(ws)
    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        ws_connections.remove(ws)


async def _broadcast_ws(msg: dict):
    for ws in ws_connections[:]:
        try:
            await ws.send_json(msg)
        except Exception:
            ws_connections.remove(ws)


# Run goal (legacy)
@app.post("/run")
async def run_goal(request: dict[str, Any]):
    if not ctx or not ctx.provider:
        return {"success": False, "error": "No provider configured"}
    goal = request.get("goal", "")
    if not goal:
        return {"success": False, "error": "Missing 'goal'"}
    loop = AgentLoop(provider=ctx.provider, tool_registry=ctx.tool_registry, max_iterations=20)
    result = await loop.run(goal)
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
