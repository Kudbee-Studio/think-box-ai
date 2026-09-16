"""ThinkBox API v1 Router.

Exposes endpoints for running the ThinkBox engine and streaming telemetry.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from thinkbox.engine import ThinkBoxEngine, EngineConfig
from thinkbox.model_client import ModelConfig
from thinkbox.session import create_session, get_current_session, sync_session, clear_session
from backend.security import get_api_keys, validate_ws_token

from thinkbox.cnc import CNCManufacturingEngine, DemoMode, ROIDashboard, SafetyGateStore, TenantStore, ProofStore


api_v1_router = APIRouter(prefix="/api/v1")

active_engines: dict[str, ThinkBoxEngine] = {}
active_cnc_engines: dict[str, CNCManufacturingEngine] = {}


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


class CNCJobCreateRequest(BaseModel):
    part_name: str
    part_number: str = "PN-001"
    material: str = "6061-T6 Aluminum"
    machine: str = "HAAS VF-2SS"
    operations: list[dict[str, Any]] = []
    customer_id: str = "default"
    priority: str = "normal"


class CNCJobResponse(BaseModel):
    job_id: str
    status: str
    part_name: str


@api_v1_router.post("/cnc/job", response_model=CNCJobResponse)
async def create_cnc_job(request: CNCJobCreateRequest) -> CNCJobResponse:
    engine = CNCManufacturingEngine()
    from thinkbox.cnc import CNCJob, Material, MachineProfile, Operation, Tool
    material = Material(name=request.material, grade=request.material)
    machine = MachineProfile(name=request.machine, control_system="Fanuc")
    tool = Tool(name="End Mill", tool_type="end_mill", diameter_mm=10.0)
    operation = Operation(operation_id="op-1", operation_type="milling", tool=tool, spindle_speed_rpm=8000, feed_rate_mm_min=200, depth_of_cut_mm=2.0, passes=1, description="Roughing pass")
    job = CNCJob(job_id=f"cnc-{uuid.uuid4().hex[:8]}", part_name=request.part_name, part_number=request.part_number, material=material, machine=machine, operations=[operation], customer_id=request.customer_id, priority=request.priority)
    return CNCJobResponse(job_id=job.job_id, status="created", part_name=job.part_name)


@api_v1_router.post("/cnc/demo")
async def run_cnc_demo() -> dict[str, Any]:
    demo = DemoMode()
    result = demo.run()
    return {"job_id": result.job.job_id, "status": result.status, "roi_total": result.roi_stats.total_savings_avoided, "evidence_labels": result.evidence_labels}


@api_v1_router.get("/cnc/dashboard")
async def get_cnc_dashboard() -> dict[str, Any]:
    dashboard = ROIDashboard()
    stats = dashboard.compute_stats()
    return stats.model_dump()


@api_v1_router.post("/cnc/safety/approve")
async def approve_cnc_job(job_id: str, reason: str = "") -> dict[str, Any]:
    store = SafetyGateStore()
    approval = store.approve(job_id=job_id, approver_id="operator", reason=reason or "Approved")
    return {"job_id": job_id, "approved": True, "approver": approval.approver_id}


@api_v1_router.get("/cnc/tenant")
async def list_tenants() -> dict[str, Any]:
    store = TenantStore()
    tenants = store.list_tenants()
    return {"tenants": [t.model_dump() for t in tenants]}


@api_v1_router.get("/engines")
async def list_engines() -> dict[str, Any]:
    return {
        "engines": [
            {"engine_id": eid, "events": len(e.events)}
            for eid, e in active_engines.items()
        ],
        "cnc_engines": len(active_cnc_engines),
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
