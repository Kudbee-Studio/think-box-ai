"""ThinkBox API v1 Router.

Exposes endpoints for running the ThinkBox engine and streaming telemetry.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from thinkbox.engine import ThinkBoxEngine, EngineConfig
from thinkbox.governed import GovernedEngine
from thinkbox.model_client import ModelConfig

from backend.api.v1.run_governed import (
    build_complete_async_for_run,
    execute_governed_run_background,
    get_api_run_governance,
    open_http_run_receipt,
    parse_run_admission,
    require_http_admission,
)
from backend.api.v1.run_receipts import read_run_receipt, read_run_receipt_by_engine
from backend.api.v1.http_conditional import conditional_json_response
from backend.api.v1.run_job_status import (
    STATUS_SCHEMA_VERSION,
    ThinkJobNotFoundError,
    build_receipt_link_card,
    build_think_job_status_payload,
    build_think_job_status_summary,
    list_recent_think_job_statuses,
    list_think_job_status_digest,
    resolve_think_job_by_receipt,
    resolve_think_job_record,
    status_payload_etag,
)
from backend.api.v1.run_job_status_stream import (
    clamp_stream_query_params,
    iter_jobs_status_stream,
    iter_think_job_status_stream,
    iter_think_job_status_stream_by_receipt,
)
from thinkbox.read_cache import weak_etag_from_payload
from thinkbox.session import create_session, get_current_session, sync_session, clear_session
from backend.security import get_api_keys, validate_ws_token

from thinkbox.experiment import (
    ExperimentManager,
    ExperimentRecord,
    AgentSessionRecord,
    ParameterProvenance,
    ParameterClassification,
    FourState,
    ProvenanceSource,
)
from thinkbox.dashboard_state import (
    CNCJobEntry,
    DashboardCategory,
    DashboardEvent,
    ThinkBoxEntry,
    ThinkJobEntry,
    get_dashboard_state,
)


api_v1_router = APIRouter(prefix="/api/v1")
THINK_JOB_NOT_FOUND_DETAIL = "think_job_not_found"

active_engines: dict[str, ThinkBoxEngine] = {}
active_governed_engines: dict[str, GovernedEngine] = {}
active_cnc_engines: dict[str, Any] = {}
_dashboard_state = get_dashboard_state()


async def _emit_dashboard(category: DashboardCategory, event_type: DashboardEvent, data: dict[str, Any], source: str = "") -> None:
    await _dashboard_state.emit(category, event_type, data, source)


class RunRequest(BaseModel):
    goal: str
    speculative: bool = True
    model: str | None = None
    temperature: float | None = None
    agent_id: str | None = None
    governance_token: str | None = None
    capability: str | None = None
    verified: bool = False
    subtasks: list[dict[str, Any]] | None = None


class RunResponse(BaseModel):
    engine_id: str
    session_id: str
    status: str
    summary: dict[str, Any]


@api_v1_router.get("/run/governance/status")
async def run_governance_status() -> dict[str, Any]:
    """Read-only governed-run admission surface (no secrets)."""
    from backend.api.v1.run_governed import governance_status_snapshot

    return governance_status_snapshot()


@api_v1_router.post("/run", response_model=RunResponse)
async def run_goal(
    request: RunRequest,
    x_governance_token: str | None = Header(None, alias="X-Governance-Token"),
    x_agent_id: str | None = Header(None, alias="X-Agent-Id"),
    x_capability: str | None = Header(None, alias="X-Capability"),
) -> RunResponse:
    from backend.validation import validate_goal

    ok, goal_or_err = validate_goal(request.goal)
    if not ok:
        raise HTTPException(status_code=422, detail=goal_or_err)
    request.goal = goal_or_err

    if request.verified:
        from backend.api.v1.run_governed import validate_verified_subtasks

        validate_verified_subtasks(list(request.subtasks or []))

    admission_ctx = parse_run_admission(
        agent_id=x_agent_id or request.agent_id,
        governance_token=request.governance_token,
        header_token=x_governance_token,
        header_capability=x_capability,
        capability=request.capability,
        verified=request.verified,
        subtasks=request.subtasks,
    )
    admission_decision = require_http_admission(admission_ctx)

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
    governed = get_api_run_governance().build_governed_engine(engine)
    active_engines[engine.engine_id] = engine
    active_governed_engines[engine.engine_id] = governed

    receipt_binding = open_http_run_receipt(
        engine_id=engine.engine_id,
        goal=request.goal,
        agent_id=admission_ctx.agent_id,
        verified=request.verified,
        capability=admission_ctx.capability,
        admission_reason=admission_decision.reason,
    )

    job_entry = ThinkJobEntry(
        job_id=engine.engine_id, goal=request.goal,
        status="running", engine_id=engine.engine_id,
        phase="started", tasks_total=0, tasks_completed=0,
        receipt_id=receipt_binding.receipt_id,
        experiment_id=receipt_binding.experiment_id,
        session_id=receipt_binding.session_id,
        evidence_label="verified",
    )
    _dashboard_state.upsert_think_job(job_entry)
    await _emit_dashboard(DashboardCategory.THINK_JOBS, DashboardEvent.TASK_STARTED,
                               job_entry.model_dump(), "api_v1")

    complete_async = build_complete_async_for_run(request.model, admission_ctx.subtasks)
    asyncio.create_task(
        execute_governed_run_background(
            governed,
            admission_ctx,
            request.goal,
            job_entry,
            complete_async=complete_async,
            receipt_binding=receipt_binding,
        )
    )

    return RunResponse(
        engine_id=engine.engine_id,
        session_id=receipt_binding.session_id,
        status="started",
        summary={
            "goal": request.goal[:100],
            "governed": True,
            "verified": request.verified,
            "agent_id": admission_ctx.agent_id,
            "admission_reason": admission_decision.reason,
            "capability": admission_ctx.capability,
            "receipt_id": receipt_binding.receipt_id,
            "experiment_id": receipt_binding.experiment_id,
            "session_id": receipt_binding.session_id,
        },
    )


@api_v1_router.get("/run/receipt/{receipt_id}")
async def get_run_receipt(receipt_id: str, request: Request) -> Any:
    """Redacted governed-run receipt (hermetic SQLite)."""
    payload = read_run_receipt(receipt_id)
    if not payload:
        raise HTTPException(status_code=404, detail="run_receipt_not_found")
    return conditional_json_response(request, payload)


@api_v1_router.get("/run/receipt/by-engine/{engine_id}")
async def get_run_receipt_for_engine(engine_id: str, request: Request) -> Any:
    payload = read_run_receipt_by_engine(engine_id)
    if not payload:
        raise HTTPException(status_code=404, detail="run_receipt_not_found")
    return conditional_json_response(request, payload)


@api_v1_router.get("/run/job/{engine_id}/status")
async def get_think_job_poll_status(
    engine_id: str,
    request: Request,
    detail: str = "full",
) -> Any:
    """Poll-friendly Think Job status with receipt linkage (hermetic)."""
    try:
        record = resolve_think_job_record(engine_id)
    except ThinkJobNotFoundError:
        raise HTTPException(status_code=404, detail=THINK_JOB_NOT_FOUND_DETAIL)
    if detail == "summary":
        payload = build_think_job_status_summary(record)
    else:
        payload = build_think_job_status_payload(record, goal_hint=str(record.get("goal") or ""))
    return conditional_json_response(request, payload, etag=status_payload_etag(payload))


@api_v1_router.get("/run/job/by-receipt/{receipt_id}/status")
async def get_think_job_status_by_receipt(
    receipt_id: str,
    request: Request,
    detail: str = "full",
) -> Any:
    try:
        record = resolve_think_job_by_receipt(receipt_id)
    except ThinkJobNotFoundError:
        raise HTTPException(status_code=404, detail=THINK_JOB_NOT_FOUND_DETAIL)
    if detail == "summary":
        payload = build_think_job_status_summary(record)
    else:
        payload = build_think_job_status_payload(record, goal_hint=str(record.get("goal") or ""))
    return conditional_json_response(request, payload, etag=status_payload_etag(payload))


@api_v1_router.get("/run/jobs/status")
async def list_think_job_poll_statuses(
    request: Request,
    limit: int = 50,
    detail: str = "full",
) -> Any:
    limit = max(1, min(limit, 200))
    jobs = list_recent_think_job_statuses(limit=limit, detail=detail)
    body = {
        "jobs": jobs,
        "count": len(jobs),
        "poll_schema_version": STATUS_SCHEMA_VERSION,
        "dashboard_revision": _dashboard_state.revision(),
        "live_verified": False,
        "production_ready": False,
    }
    return conditional_json_response(request, body, etag=weak_etag_from_payload(body))


@api_v1_router.get("/run/jobs/status/digest")
async def think_job_status_digest(request: Request, limit: int = 50) -> Any:
    limit = max(1, min(limit, 200))
    body = list_think_job_status_digest(limit=limit)
    return conditional_json_response(request, body, etag=_dashboard_state.revision_etag())


@api_v1_router.get("/run/job/{engine_id}/status/stream")
async def stream_think_job_poll_status(
    engine_id: str,
    max_events: int = 64,
    timeout_s: float = 120.0,
    heartbeat_s: float = 15.0,
) -> StreamingResponse:
    """Hermetic SSE: incremental Think Job status deltas (poll → push)."""
    try:
        resolve_think_job_record(engine_id)
    except ThinkJobNotFoundError:
        raise HTTPException(status_code=404, detail=THINK_JOB_NOT_FOUND_DETAIL)
    limits = clamp_stream_query_params(max_events, timeout_s, heartbeat_s)
    return StreamingResponse(
        iter_think_job_status_stream(engine_id, limits=limits),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@api_v1_router.get("/run/job/by-receipt/{receipt_id}/status/stream")
async def stream_think_job_status_by_receipt(
    receipt_id: str,
    max_events: int = 64,
    timeout_s: float = 120.0,
    heartbeat_s: float = 15.0,
) -> StreamingResponse:
    try:
        resolve_think_job_by_receipt(receipt_id)
    except ThinkJobNotFoundError:
        raise HTTPException(status_code=404, detail=THINK_JOB_NOT_FOUND_DETAIL)
    limits = clamp_stream_query_params(max_events, timeout_s, heartbeat_s)
    return StreamingResponse(
        iter_think_job_status_stream_by_receipt(receipt_id, limits=limits),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@api_v1_router.get("/run/jobs/status/stream")
async def stream_think_jobs_poll_status(
    limit: int = 50,
    max_events: int = 32,
    timeout_s: float = 60.0,
    heartbeat_s: float = 15.0,
) -> StreamingResponse:
    limit = max(1, min(limit, 200))
    limits = clamp_stream_query_params(max_events, timeout_s, heartbeat_s)
    return StreamingResponse(
        iter_jobs_status_stream(limit=limit, limits=limits),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@api_v1_router.get("/dashboard/state/summary")
async def dashboard_state_summary(request: Request) -> Any:
    body = _dashboard_state.get_state_summary()
    return conditional_json_response(request, body, etag=_dashboard_state.revision_etag())


@api_v1_router.get("/dashboard/think-job/{engine_id}/receipt-card")
async def get_think_job_receipt_card(engine_id: str) -> dict[str, Any]:
    try:
        record = resolve_think_job_record(engine_id)
    except ThinkJobNotFoundError:
        raise HTTPException(status_code=404, detail=THINK_JOB_NOT_FOUND_DETAIL)
    status = str(record.get("status") or "unknown")
    return build_receipt_link_card(
        job_id=str(record.get("job_id") or engine_id),
        status=status,
        phase=str(record.get("phase") or ""),
        receipt_id=str(record.get("receipt_id") or ""),
        experiment_id=str(record.get("experiment_id") or ""),
        session_id=str(record.get("session_id") or ""),
        proof_artifact=str(record.get("proof_artifact") or ""),
        tasks_total=int(record.get("tasks_total") or 0),
        tasks_completed=int(record.get("tasks_completed") or 0),
    )


@api_v1_router.get("/engine/{engine_id}")
async def get_engine_status(engine_id: str) -> dict[str, Any]:
    engine = active_engines.get(engine_id)
    if not engine:
        raise HTTPException(status_code=404, detail="Engine not found")
    stats = engine.get_stats()
    tb_entry = ThinkBoxEntry(
        box_id=engine_id, name=f"Engine {engine_id[:8]}",
        substrate="local", status="running",
        metadata=stats,
    )
    _dashboard_state.upsert_think_box(tb_entry)
    return stats


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
    from thinkbox.cnc import CNCManufacturingEngine, CNCJob, Material, MachineProfile, Operation, Tool

    engine = CNCManufacturingEngine()
    material = Material(name=request.material, grade=request.material)
    machine = MachineProfile(name=request.machine, control_system="Fanuc")
    tool = Tool(name="End Mill", tool_type="end_mill", diameter_mm=10.0)
    operation = Operation(operation_id="op-1", operation_type="milling", tool=tool, spindle_speed_rpm=8000, feed_rate_mm_min=200, depth_of_cut_mm=2.0, passes=1, description="Roughing pass")
    job = CNCJob(job_id=f"cnc-{uuid.uuid4().hex[:8]}", part_name=request.part_name, part_number=request.part_number, material=material, machine=machine, operations=[operation], customer_id=request.customer_id, priority=request.priority)
    cnc_entry = CNCJobEntry(
        job_id=job.job_id, part_name=job.part_name, part_number=job.part_number,
        material=job.material.name, machine=job.machine.name, status="created",
        operations=[op.model_dump() if hasattr(op, 'model_dump') else {} for op in job.operations],
        customer_id=job.customer_id, priority=job.priority,
    )
    _dashboard_state.upsert_cnc_job(cnc_entry)
    await _emit_dashboard(DashboardCategory.CNC, DashboardEvent.JOB_CREATED, cnc_entry.model_dump(), "api_v1")
    return CNCJobResponse(job_id=job.job_id, status="created", part_name=job.part_name)


@api_v1_router.post("/cnc/demo")
async def run_cnc_demo() -> dict[str, Any]:
    from thinkbox.cnc import DemoMode

    demo = DemoMode()
    result = demo.run()
    cnc_entry = CNCJobEntry(
        job_id=result.job.job_id, part_name=result.job.part_name,
        part_number=result.job.part_number, material=result.job.material.name,
        machine=result.job.machine.name, status="completed",
        operations=[], customer_id="default", priority="normal",
        safety_approved=True,
    )
    _dashboard_state.upsert_cnc_job(cnc_entry)
    await _emit_dashboard(DashboardCategory.CNC, DashboardEvent.JOB_COMPLETED, cnc_entry.model_dump(), "demo")
    return {"job_id": result.job.job_id, "status": result.status, "roi_total": result.roi_stats.total_savings_avoided, "evidence_labels": result.evidence_labels}


@api_v1_router.get("/cnc/dashboard")
async def get_cnc_dashboard(request: Request) -> Any:
    from thinkbox.cnc import ROIDashboard

    dashboard = ROIDashboard()
    stats = dashboard.compute_stats()
    body = {
        **_dashboard_state.get_state_summary(),
        "cnc_roi": stats.model_dump(),
    }
    return conditional_json_response(request, body, etag=_dashboard_state.revision_etag())


@api_v1_router.post("/cnc/safety/approve")
async def approve_cnc_job(job_id: str, reason: str = "") -> dict[str, Any]:
    from thinkbox.cnc import SafetyGateStore

    store = SafetyGateStore()
    approval = store.approve(job_id=job_id, approver_id="operator", reason=reason or "Approved")
    if job_id in _dashboard_state.cnc_jobs:
        _dashboard_state.cnc_jobs[job_id].safety_approved = True
        await _emit_dashboard(DashboardCategory.CNC, DashboardEvent.JOB_COMPLETED,
                               _dashboard_state.cnc_jobs[job_id].model_dump(), "safety")
    return {"job_id": job_id, "approved": True, "approver": approval.approver_id}


@api_v1_router.get("/cnc/tenant")
async def list_tenants() -> dict[str, Any]:
    from thinkbox.cnc import TenantStore

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

    last_revision = -1
    try:
        while True:
            revision = _dashboard_state.revision()
            compact = {
                "type": "system_status",
                "active_engines": len(active_engines),
                "dashboard_revision": revision,
                "dashboard_summary": _dashboard_state.get_state_summary(),
                "engines": {
                    eid: e.get_stats()
                    for eid, e in active_engines.items()
                },
            }
            if revision != last_revision:
                compact["dashboard_state"] = _dashboard_state.get_state()
                last_revision = revision
            await websocket.send_json(compact)
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass


_experiment_manager = ExperimentManager()


class ExperimentCreateRequest(BaseModel):
    intent: str
    hypothesis: str
    parameters: dict[str, Any] = {}
    agent_id: str = "default"
    execution_mode: str = "local"


class ExperimentResponse(BaseModel):
    experiment_id: str
    session_id: str
    status: str
    intent: str


@api_v1_router.post("/experiment", response_model=ExperimentResponse)
async def create_experiment(request: ExperimentCreateRequest) -> ExperimentResponse:
    session = _experiment_manager.create_session(agent_id=request.agent_id)
    exp = _experiment_manager.create_experiment(
        intent=request.intent,
        hypothesis=request.hypothesis,
        parameters=request.parameters,
        parent_session_id=session.parent_session_id,
        agent_id=request.agent_id,
        execution_mode=request.execution_mode,
    )
    await _emit_dashboard(DashboardCategory.EXECUTION, DashboardEvent.JOB_CREATED,
                                exp.model_dump(), "experiment_api")
    return ExperimentResponse(
        experiment_id=exp.experiment_id,
        session_id=exp.session_id,
        status=exp.status,
        intent=exp.intent,
    )


@api_v1_router.get("/experiment/{experiment_id}")
async def get_experiment(experiment_id: str) -> dict[str, Any]:
    exp = _experiment_manager.db.get_experiment(experiment_id)
    if not exp:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Experiment not found")
    params = _experiment_manager.db.get_parameters_by_experiment(experiment_id)
    outcome = _experiment_manager.db.get_outcomes_by_experiment(experiment_id)
    lessons = _experiment_manager.db.get_lessons_by_experiment(experiment_id)
    return {"experiment": exp, "parameters": params, "outcome": outcome, "lessons": lessons}


@api_v1_router.post("/experiment/{experiment_id}/parameter")
async def add_parameter(experiment_id: str, request: dict[str, Any]) -> dict[str, Any]:
    param = _experiment_manager.add_parameter(
        experiment_id,
        request["name"],
        request["value"],
        unit=request.get("unit", ""),
        source=request.get("source", ProvenanceSource.MEASURED.value),
        confidence=request.get("confidence", 0.0),
        classification=request.get("classification", ParameterClassification.OBSERVED.value),
    )
    return param.model_dump()


@api_v1_router.post("/experiment/{experiment_id}/outcome")
async def record_outcome(experiment_id: str, request: dict[str, Any]) -> dict[str, Any]:
    _experiment_manager.record_outcome(
        experiment_id,
        request["outcome"],
        request.get("confidence", 0.0),
        four_state=request.get("four_state", ""),
    )
    return {"status": "outcome_recorded"}


@api_v1_router.get("/experiment/dashboard")
async def experiment_dashboard(request: Request) -> Any:
    body = _experiment_manager.get_dashboard_data()
    return conditional_json_response(request, body)


@api_v1_router.post("/experiment/zero-server")
async def zero_server_experiment(request: ExperimentCreateRequest) -> dict[str, Any]:
    result = _experiment_manager.run_zero_server_experiment(
        intent=request.intent,
        hypothesis=request.hypothesis,
        parameters=request.parameters,
        agent_id=request.agent_id,
    )
    await _emit_dashboard(DashboardCategory.EXECUTION, DashboardEvent.JOB_COMPLETED,
                                result, "zero_server")
    return result


@api_v1_router.get("/experiment/restart")
async def experiment_restart() -> dict[str, Any]:
    return _experiment_manager.restart()
