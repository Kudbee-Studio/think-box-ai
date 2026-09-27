"""Dashboard state model — canonical real-time control plane for Think Box AI.

Every agent task, phase, capability, infrastructure change, Think Job,
CNC job, provider change, test milestone, or execution event must update
canonical dashboard state via this module.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncGenerator

from thinkbox.org_memory_receipts import redact_mapping
from thinkbox.read_cache import RevisionCounter


class DashboardCategory(str, Enum):
    THINK_BOXES = "think_boxes"
    THINK_JOBS = "think_jobs"
    CNC = "cnc"
    INFRASTRUCTURE = "infrastructure"
    AGENT_ACTIVITY = "agent_activity"
    PROVIDERS = "providers"
    TESTS = "tests"
    EXECUTION = "execution"
    AUTONOMOUS_LOOP = "autonomous_loop"


class DashboardEvent(str, Enum):
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    PHASE_STARTED = "phase_started"
    PHASE_COMPLETED = "phase_completed"
    JOB_CREATED = "job_created"
    JOB_STARTED = "job_started"
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"
    PROVIDER_CHANGED = "provider_changed"
    INFRASTRUCTURE_CHANGED = "infrastructure_changed"
    TEST_RUN = "test_run"
    TEST_PASS = "test_pass"
    TEST_FAIL = "test_fail"
    AGENT_CONNECTED = "agent_connected"
    AGENT_DISCONNECTED = "agent_disconnected"
    UPLOAD_STARTED = "upload_started"
    UPLOAD_COMPLETED = "upload_completed"
    ERROR = "error"
    LOOP_STARTED = "loop_started"
    LOOP_ITERATION_COMPLETED = "loop_iteration_completed"
    LOOP_BOOTSTRAPPED = "loop_bootstrapped"
    SESSION_CLOSED = "session_closed"
    TUNING_APPLIED = "tuning_applied"
    PATTERN_GENERALIZED = "pattern_generalized"


@dataclass
class DashboardEventEntry:
    event_id: str
    category: DashboardCategory
    event_type: DashboardEvent
    timestamp: str
    data: dict[str, Any]
    source: str = ""
    evidence_label: str = "simulated"

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        if not self.event_id:
            self.event_id = f"evt_{uuid.uuid4().hex[:12]}"

    def model_dump(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "category": self.category.value,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "data": self.data,
            "source": self.source,
            "evidence_label": self.evidence_label,
        }


@dataclass
class ThinkBoxEntry:
    box_id: str
    name: str
    substrate: str = "local"
    status: str = "idle"
    created_at: str = ""
    last_activity: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if not self.last_activity:
            self.last_activity = self.created_at

    def model_dump(self) -> dict[str, Any]:
        return {
            "box_id": self.box_id,
            "name": self.name,
            "substrate": self.substrate,
            "status": self.status,
            "created_at": self.created_at,
            "last_activity": self.last_activity,
            "metadata": self.metadata,
        }


@dataclass
class ThinkJobEntry:
    job_id: str
    goal: str
    status: str = "pending"
    engine_id: str = ""
    phase: str = ""
    progress: float = 0.0
    tasks_total: int = 0
    tasks_completed: int = 0
    started_at: str = ""
    completed_at: str = ""
    result: dict[str, Any] = field(default_factory=dict)
    evidence_label: str = "simulated"
    receipt_id: str = ""
    experiment_id: str = ""
    session_id: str = ""

    def __post_init__(self) -> None:
        if not self.started_at:
            self.started_at = datetime.now(timezone.utc).isoformat()

    def model_dump(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "goal": self.goal,
            "status": self.status,
            "engine_id": self.engine_id,
            "phase": self.phase,
            "progress": self.progress,
            "tasks_total": self.tasks_total,
            "tasks_completed": self.tasks_completed,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "evidence_label": self.evidence_label,
            "receipt_id": self.receipt_id,
            "experiment_id": self.experiment_id,
            "session_id": self.session_id,
        }


@dataclass
class CNCJobEntry:
    job_id: str
    part_name: str
    part_number: str = ""
    material: str = ""
    machine: str = ""
    status: str = "created"
    operations: list[dict[str, Any]] = field(default_factory=list)
    customer_id: str = "default"
    priority: str = "normal"
    safety_approved: bool = False
    created_at: str = ""
    completed_at: str = ""
    evidence_label: str = "simulated"

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def model_dump(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "part_name": self.part_name,
            "part_number": self.part_number,
            "material": self.material,
            "machine": self.machine,
            "status": self.status,
            "operations": self.operations,
            "customer_id": self.customer_id,
            "priority": self.priority,
            "safety_approved": self.safety_approved,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "evidence_label": self.evidence_label,
        }


@dataclass
class InfrastructureEntry:
    component: str
    type: str
    status: str = "unknown"
    substrate: str = "local"
    verified: bool = False
    details: dict[str, Any] = field(default_factory=dict)
    last_checked: str = ""

    def __post_init__(self) -> None:
        if not self.last_checked:
            self.last_checked = datetime.now(timezone.utc).isoformat()

    def model_dump(self) -> dict[str, Any]:
        return {
            "component": self.component,
            "type": self.type,
            "status": self.status,
            "substrate": self.substrate,
            "verified": self.verified,
            "details": self.details,
            "last_checked": self.last_checked,
        }


@dataclass
class ProviderEntry:
    name: str
    model: str = ""
    status: str = "unknown"
    endpoint: str = ""
    latency_ms: float = 0.0
    rps: float = 0.0
    verified: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    def model_dump(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "model": self.model,
            "status": self.status,
            "endpoint": self.endpoint,
            "latency_ms": self.latency_ms,
            "rps": self.rps,
            "verified": self.verified,
            "details": self.details,
        }


@dataclass
class TestMilestoneEntry:
    test_name: str
    module: str = ""
    status: str = "pending"
    count: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    duration_ms: float = 0.0
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def model_dump(self) -> dict[str, Any]:
        return {
            "test_name": self.test_name,
            "module": self.module,
            "status": self.status,
            "count": self.count,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp,
        }


@dataclass
class AutonomousLoopTelemetry:
    """Detailed telemetry metrics for the autonomous decision-loop.

    Populated by Engine._telemetry_tick() from LoopTracer.get_metrics()
    and EngineAutoTuner.get_decision_count(). Enables dashboard convergence
    visualization and learning-curve tracking across loop iterations.
    """

    total_iterations: int = 0
    total_cycle_time_s: float = 0.0
    avg_cycle_time_s: float = 0.0
    min_cycle_time_s: float = 0.0
    max_cycle_time_s: float = 0.0
    throughput: float = 0.0
    recommendation_types: dict[str, int] = field(default_factory=dict)
    priority_distribution: dict[str, int] = field(default_factory=dict)
    learning_curve_points: list[dict[str, Any]] = field(default_factory=list)
    convergence_status: str = "pending"
    convergence_history: list[dict[str, Any]] = field(default_factory=list)
    last_iteration_id: str = ""
    first_iteration_id: str = ""

    def model_dump(self) -> dict[str, Any]:
        return {
            "total_iterations": self.total_iterations,
            "total_cycle_time_s": self.total_cycle_time_s,
            "avg_cycle_time_s": self.avg_cycle_time_s,
            "min_cycle_time_s": self.min_cycle_time_s,
            "max_cycle_time_s": self.max_cycle_time_s,
            "throughput": self.throughput,
            "recommendation_types": self.recommendation_types,
            "priority_distribution": self.priority_distribution,
            "learning_curve_points": self.learning_curve_points,
            "convergence_status": self.convergence_status,
            "convergence_history": self.convergence_history,
            "last_iteration_id": self.last_iteration_id,
            "first_iteration_id": self.first_iteration_id,
        }


@dataclass
class LoopActionEntry:
    """Audit record for an action performed on an autonomous loop."""
    action_id: str
    loop_id: str
    action: str  # start, stop, run, reset
    timestamp: str = ""
    result: Any = None
    source: str = ""
    evidence_label: str = "simulated"

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        if not self.action_id:
            self.action_id = f"act_{uuid.uuid4().hex[:12]}"

    def model_dump(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "loop_id": self.loop_id,
            "action": self.action,
            "timestamp": self.timestamp,
            "result": self.result,
            "source": self.source,
            "evidence_label": self.evidence_label,
        }

@dataclass
class AutonomousLoopEntry:
    """Canonical state for the autonomous decision-loop dashboard."""
    loop_id: str
    status: str = "idle"
    started_at: str = ""
    current_session_id: str = ""
    iterations_count: int = 0
    patterns_identified: int = 0
    tuning_decisions: int = 0
    bootstrapped: bool = False
    latest_recommendation: dict[str, Any] = field(default_factory=dict)
    latest_metrics: dict[str, Any] = field(default_factory=dict)
    telemetry: AutonomousLoopTelemetry = field(default_factory=AutonomousLoopTelemetry)
    components: dict[str, bool] = field(
        default_factory=lambda: {
            "bootstrap": False,
            "experiment_manager": False,
            "decomposer": False,
            "execution": False,
            "feedback": False,
            "opportunity": False,
            "loop_tracer": False,
            "auto_tuner": False,
            "generalizer": False,
            "session_manager": False,
        }
    )
    evidence_label: str = "infmred"
    last_action: str = ""

    def __post_init__(self) -> None:
        if not self.started_at:
            self.started_at = datetime.now(timezone.utc).isoformat()

    def model_dump(self) -> dict[str, Any]:
        return {
            "loop_id": self.loop_id,
            "status": self.status,
            "started_at": self.started_at,
            "current_session_id": self.current_session_id,
            "iterations_count": self.iterations_count,
            "patterns_identified": self.patterns_identified,
            "tuning_decisions": self.tuning_decisions,
            "bootstrapped": self.bootstrapped,
            "latest_recommendation": self.latest_recommendation,
            "latest_metrics": self.latest_metrics,
            "telemetry": self.telemetry.model_dump() if isinstance(self.telemetry, AutonomousLoopTelemetry) else self.telemetry,
            "components": self.components,
            "evidence_label": self.evidence_label,
        }


@dataclass
class LoopSessionEntry:
    """Lightweight session summary tracked in dashboard state.

    Mirrors the key fields of LoopSession from ExperimentAnalytics for
    real-time display without coupling the dashboard to the session manager.
    """

    session_id: str
    loop_id: str
    started_at: str = ""
    closed_at: str = ""
    iterations_count: int = 0
    avg_throughput: float = 0.0
    avg_p50_latency: float = 0.0
    avg_error_rate: float = 0.0
    total_cycle_time_s: float = 0.0
    patterns_identified: int = 0
    improved_over_baseline: bool = False
    summary: dict[str, Any] = field(default_factory=dict)

    def model_dump(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "loop_id": self.loop_id,
            "started_at": self.started_at,
            "closed_at": self.closed_at,
            "iterations_count": self.iterations_count,
            "avg_throughput": self.avg_throughput,
            "avg_p50_latency": self.avg_p50_latency,
            "avg_error_rate": self.avg_error_rate,
            "total_cycle_time_s": self.total_cycle_time_s,
            "patterns_identified": self.patterns_identified,
            "improved_over_baseline": self.improved_over_baseline,
            "summary": self.summary,
        }


class DashboardState:
    """Canonical, mutable dashboard state singleton."""

    _instance: DashboardState | None = None
    _DEFAULT_EVENT_LIMIT = 100
    _SUBSCRIBER_QUEUE_SIZE = 100

    def __new__(cls) -> DashboardState:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if DashboardState._instance is not None and hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._lock = asyncio.Lock()
        self.think_boxes: dict[str, ThinkBoxEntry] = {}
        self.think_jobs: dict[str, ThinkJobEntry] = {}
        self.cnc_jobs: dict[str, CNCJobEntry] = {}
        self.infrastructure: dict[str, InfrastructureEntry] = {}
        self.providers: dict[str, ProviderEntry] = {}
        self.test_milestones: dict[str, TestMilestoneEntry] = {}
        self.autonomous_loops: dict[str, AutonomousLoopEntry] = {}
        self.loop_actions: dict[str, list[LoopActionEntry]] = {}
        self.loop_sessions: dict[str, LoopSessionEntry] = {}
        self.events: list[DashboardEventEntry] = []
        self._subscribers: list[asyncio.Queue] = []
        self._revision = RevisionCounter()
        self._event_drops_count: int = 0

    async def register_subscriber(
        self, queue: asyncio.Queue | None = None, maxsize: int = _SUBSCRIBER_QUEUE_SIZE
    ) -> asyncio.Queue:
        """Register a subscriber queue with bounded size (maxsize). If queue is None, creates a new one."""
        if queue is None:
            queue = asyncio.Queue(maxsize=maxsize)
        self._subscribers.append(queue)
        return queue

    async def _notify(self, event: DashboardEventEntry) -> None:
        """Notify all subscribers of event, dropping oldest events on backpressure."""
        dead_subscribers = []
        for idx, queue in enumerate(self._subscribers):
            try:
                if queue.full():
                    # Queue is full: drop oldest event (fail-open)
                    try:
                        queue.get_nowait()
                        self._event_drops_count += 1
                    except asyncio.QueueEmpty:
                        pass
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # This shouldn't happen after get_nowait, but handle it gracefully
                self._event_drops_count += 1
            except Exception:
                # Mark dead subscribers for cleanup
                dead_subscribers.append(idx)

        # Clean up dead subscribers (iterate in reverse to preserve indices)
        for idx in reversed(dead_subscribers):
            if idx < len(self._subscribers):
                self._subscribers.pop(idx)

    async def emit(self, category: DashboardCategory, event_type: DashboardEvent,
                   data: dict[str, Any], source: str = "",
                   evidence_label: str = "simulated") -> DashboardEventEntry:
        entry = DashboardEventEntry(
            event_id="",
            category=category,
            event_type=event_type,
            timestamp="",
            data=redact_mapping(data),
            source=source,
            evidence_label=evidence_label,
        )
        self.events.append(entry)
        self._revision.bump()
        await self._notify(entry)
        return entry

    def revision(self) -> int:
        return self._revision.value

    def revision_etag(self) -> str:
        return self._revision.etag()

    def upsert_think_box(self, box: ThinkBoxEntry) -> None:
        self.think_boxes[box.box_id] = box
        self._revision.bump()

    def upsert_think_job(self, job: ThinkJobEntry) -> None:
        self.think_jobs[job.job_id] = job
        self._revision.bump()
        try:
            from thinkbox.think_job_stream import get_think_job_stream_hub

            get_think_job_stream_hub().signal(job.job_id)
        except Exception:
            pass

    def upsert_cnc_job(self, job: CNCJobEntry) -> None:
        self.cnc_jobs[job.job_id] = job
        self._revision.bump()

    def upsert_infrastructure(self, component: str, entry: InfrastructureEntry) -> None:
        self.infrastructure[component] = entry
        self._revision.bump()

    def upsert_provider(self, provider: ProviderEntry) -> None:
        self.providers[provider.name] = provider
        self._revision.bump()

    def upsert_test_milestone(self, milestone: TestMilestoneEntry) -> None:
        self.test_milestones[milestone.test_name] = milestone
        self._revision.bump()

    def upsert_autonomous_loop(self, entry: AutonomousLoopEntry) -> None:
        self.autonomous_loops[entry.loop_id] = entry
        self._revision.bump()

    def record_loop_telemetry(self, loop_id: str, telemetry: AutonomousLoopTelemetry) -> None:
        """Record telemetry metrics for an autonomous loop.

        Updates the loop's entry with the latest telemetry payload. If the
        loop_id is not tracked, creates a placeholder entry.
        """
        if loop_id in self.autonomous_loops:
            self.autonomous_loops[loop_id].telemetry = telemetry
        self._revision.bump()

    def record_loop_action(self, loop_id: str, action: str, result: Any = None, source: str = "") -> LoopActionEntry:
        """Record an action (start/stop/run/reset) performed on a loop.

        Updates the loop's `last_action` field and stores the action in an
        audit trail. Returns the created LoopActionEntry.
        """
        entry = LoopActionEntry(
            action_id="",
            loop_id=loop_id,
            action=action,
            timestamp="",
            result=result,
            source=source,
            evidence_label="simulated",
        )
        # Ensure loop entry exists
        if loop_id not in self.autonomous_loops:
            self.autonomous_loops[loop_id] = AutonomousLoopEntry(loop_id=loop_id)
        # Update last_action on loop entry
        self.autonomous_loops[loop_id].last_action = action
        # Store action
        self.loop_actions.setdefault(loop_id, []).append(entry)
        self._revision.bump()
        return entry

    def get_loop_actions(self, loop_id: str) -> list[LoopActionEntry]:
        """Return the list of recorded actions for a specific loop."""
        return list(self.loop_actions.get(loop_id, []))

    def get_all_loop_actions(self) -> list[LoopActionEntry]:
        """Return a flat list of all LoopActionEntry records."""
        actions: list[LoopActionEntry] = []
        for lst in self.loop_actions.values():
            actions.extend(lst)
        return actions

    def get_events_paginated(
        self, limit: int = _DEFAULT_EVENT_LIMIT, offset: int = 0
    ) -> dict[str, Any]:
        """Get paginated events with cursor support.

        Returns:
            {
                "events": [...],
                "total": int,
                "offset": int,
                "limit": int,
                "has_more": bool,
                "next_offset": int | None,
            }
        """
        # Clamp limit to reasonable bounds
        limit = max(1, min(limit, 1000))
        offset = max(0, offset)

        total = len(self.events)
        events = self.events[offset : offset + limit]
        has_more = offset + limit < total
        next_offset = offset + limit if has_more else None

        return {
            "events": [e.model_dump() for e in events],
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": has_more,
            "next_offset": next_offset,
        }

    def get_events_drops_count(self) -> int:
        """Return the count of events dropped due to subscriber queue backpressure."""
        return self._event_drops_count

    def record_autonomous_loop_session(self, session: LoopSessionEntry) -> None:
        """Record a closed autonomous loop session in dashboard state."""
        self.loop_sessions[session.session_id] = session
        self._revision.bump()

    def get_current_session_id(self, loop_id: str) -> str:
        """Return the current session_id for a loop, or empty string."""
        entry = self.autonomous_loops.get(loop_id)
        if entry is None:
            return ""
        return entry.current_session_id

    def list_loop_sessions(self, limit: int = 50) -> list[LoopSessionEntry]:
        """List recorded loop sessions ordered by recency."""
        sessions = list(self.loop_sessions.values())
        sessions.sort(key=lambda s: s.closed_at or s.started_at, reverse=True)
        return sessions[:limit]

    def get_loop_session(self, session_id: str) -> LoopSessionEntry | None:
        """Retrieve a specific loop session by ID."""
        return self.loop_sessions.get(session_id)

    def get_loop_telemetry(self, loop_id: str) -> AutonomousLoopTelemetry | None:
        """Retrieve telemetry for a specific loop by loop_id."""
        entry = self.autonomous_loops.get(loop_id)
        if entry is None:
            return None
        return entry.telemetry if isinstance(entry.telemetry, AutonomousLoopTelemetry) else None

    def get_all_loop_telemetry(self) -> list[dict[str, Any]]:
        """Retrieve telemetry for all tracked autonomous loops."""
        return [
            entry.telemetry.model_dump() if isinstance(entry.telemetry, AutonomousLoopTelemetry)
            else entry.telemetry
            for entry in self.autonomous_loops.values()
        ]

    def get_state_summary(self) -> dict[str, Any]:
        """Lightweight counts for polls and WebSocket (no full job payloads)."""
        receipt_linked = sum(
            1
            for j in self.think_jobs.values()
            if j.receipt_id and j.experiment_id and j.session_id
        )
        return {
            "revision": self.revision(),
            "summary": {
                "total_think_boxes": len(self.think_boxes),
                "total_think_jobs": len(self.think_jobs),
                "total_cnc_jobs": len(self.cnc_jobs),
                "total_infrastructure": len(self.infrastructure),
                "total_providers": len(self.providers),
                "total_events": len(self.events),
                "total_autonomous_loops": len(self.autonomous_loops),
                "total_loop_iterations": sum(
                    e.telemetry.total_iterations if isinstance(e.telemetry, AutonomousLoopTelemetry) else 0
                    for e in self.autonomous_loops.values()
                ),
                "total_loop_sessions": len(self.loop_sessions),
            },
            "think_job_receipt_summary": {
                "tracked": len(self.think_jobs),
                "receipt_linked": receipt_linked,
            },
            "loop_telemetry_summary": {
                "loops_with_telemetry": sum(
                    1 for e in self.autonomous_loops.values()
                    if isinstance(e.telemetry, AutonomousLoopTelemetry) and e.telemetry.total_iterations > 0
                ),
            },
            "loop_session_summary": {
                "total_sessions": len(self.loop_sessions),
            },
        }

    def get_state(self) -> dict[str, Any]:
        receipt_linked = sum(
            1
            for j in self.think_jobs.values()
            if j.receipt_id and j.experiment_id and j.session_id
        )
        return {
            "revision": self.revision(),
            "think_boxes": [b.model_dump() for b in self.think_boxes.values()],
            "think_jobs": [j.model_dump() for j in self.think_jobs.values()],
            "cnc_jobs": [j.model_dump() for j in self.cnc_jobs.values()],
            "infrastructure": [i.model_dump() for i in self.infrastructure.values()],
            "providers": [p.model_dump() for p in self.providers.values()],
            "test_milestones": [t.model_dump() for t in self.test_milestones.values()],
            "autonomous_loops": [l.model_dump() for l in self.autonomous_loops.values()],
            "events": [e.model_dump() for e in self.events[-100:]],
            "think_job_receipt_summary": {
                "tracked": len(self.think_jobs),
                "receipt_linked": receipt_linked,
            },
            "summary": {
                "total_think_boxes": len(self.think_boxes),
                "total_think_jobs": len(self.think_jobs),
                "total_cnc_jobs": len(self.cnc_jobs),
                "total_infrastructure": len(self.infrastructure),
                "total_providers": len(self.providers),
                "total_events": len(self.events),
                "total_autonomous_loops": len(self.autonomous_loops),
                "total_loop_iterations": sum(
                    e.telemetry.total_iterations if isinstance(e.telemetry, AutonomousLoopTelemetry) else 0
                    for e in self.autonomous_loops.values()
                ),
                "total_loop_sessions": len(self.loop_sessions),
            },
            "loop_telemetry": self.get_all_loop_telemetry(),
            "loop_sessions": [s.model_dump() for s in self.list_loop_sessions()],
        }


_dashboard_state: DashboardState | None = None


def get_dashboard_state() -> DashboardState:
    global _dashboard_state
    if _dashboard_state is None:
        _dashboard_state = DashboardState()
    return _dashboard_state


async def dashboard_event_stream() -> AsyncGenerator[DashboardEventEntry, None]:
    state = get_dashboard_state()
    queue = await state.register_subscriber()  # Creates bounded queue with default size
    try:
        while True:
            event = await queue.get()
            yield event
    except asyncio.CancelledError:
        # Clean up disconnected subscriber
        try:
            state._subscribers.remove(queue)
        except ValueError:
            pass
        raise