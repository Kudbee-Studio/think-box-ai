"""Hermetic governed HTTP run receipts — SQLite + proof artifacts (PR #133).

Persists ExperimentManager records for ``POST /api/v1/run`` without live Mercury.
Fail-closed: persistence errors surface as failed jobs, never silent success.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from thinkbox.experiment import (
    AgentSessionRecord,
    ExperimentManager,
    ExperimentRecord,
    ParameterProvenance,
)
from thinkbox.dashboard_state import (
    DashboardCategory,
    DashboardEvent,
    ThinkJobEntry,
    get_dashboard_state,
)

DEFAULT_HTTP_RUN_DB = "data/thinkboxmd/db/http_run_experiments.db"
DEFAULT_HTTP_RUN_ARTIFACTS = "data/thinkboxmd/artifacts/http_run"
HTTP_RUN_FOUR_STATE = "TEST_VERIFIED"
HTTP_RUN_EVIDENCE = "verified"
HTTP_RUN_EXECUTION_MODE = "hermetic"


class RunReceiptPersistError(RuntimeError):
    """Raised when SQLite or artifact write fails (fail-closed)."""


@dataclass
class HttpRunReceiptBinding:
    """Links one HTTP run to ExperimentManager rows before background work."""

    receipt_id: str
    session_id: str
    experiment_id: str
    engine_id: str
    agent_id: str
    goal: str
    verified: bool
    capability: str = "goal:execute"
    admission_reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class HttpRunPersistence:
    """Shared ExperimentManager stack for governed HTTP runs."""

    manager: ExperimentManager
    db_path: str
    artifacts_dir: Path
    _engine_index: dict[str, str] = field(default_factory=dict, repr=False)

    def index_engine(self, engine_id: str, receipt_id: str) -> None:
        self._engine_index[engine_id] = receipt_id

    def receipt_for_engine(self, engine_id: str) -> str | None:
        return self._engine_index.get(engine_id)


_http_persistence: HttpRunPersistence | None = None
_persist_fail_hook: bool = False


def get_http_run_persistence() -> HttpRunPersistence:
    global _http_persistence
    if _http_persistence is None:
        db_path = os.environ.get("THINKBOX_HTTP_RUN_DB", DEFAULT_HTTP_RUN_DB)
        art_dir = os.environ.get("THINKBOX_HTTP_RUN_ARTIFACTS", DEFAULT_HTTP_RUN_ARTIFACTS)
        root = Path(db_path).parent
        root.mkdir(parents=True, exist_ok=True)
        Path(art_dir).mkdir(parents=True, exist_ok=True)
        _http_persistence = HttpRunPersistence(
            manager=ExperimentManager(db_path=db_path, artifacts_dir=art_dir),
            db_path=db_path,
            artifacts_dir=Path(art_dir),
        )
    return _http_persistence


def reset_http_run_persistence_for_tests(
    *,
    db_path: str | None = None,
    artifacts_dir: str | None = None,
) -> HttpRunPersistence:
    """Replace persistence singleton (unittest isolation)."""
    import tempfile

    global _http_persistence, _persist_fail_hook
    _persist_fail_hook = False
    if db_path is None or artifacts_dir is None:
        tmp = tempfile.mkdtemp(prefix="http_run_test_")
        root = Path(tmp)
        if db_path is None:
            db_path = str(root / "http_run_test.db")
        if artifacts_dir is None:
            artifacts_dir = str(root / "artifacts")
    Path(artifacts_dir).mkdir(parents=True, exist_ok=True)
    _http_persistence = HttpRunPersistence(
        manager=ExperimentManager(db_path=db_path, artifacts_dir=artifacts_dir),
        db_path=db_path,
        artifacts_dir=Path(artifacts_dir),
    )
    return _http_persistence


def set_persist_fail_hook(enabled: bool) -> None:
    """Test hook: next persist raises RunReceiptPersistError."""
    global _persist_fail_hook
    _persist_fail_hook = enabled


def _now_ids(prefix: str = "tb") -> tuple[str, str, str]:
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%d%H%M%S")
    session_id = f"tb_sess_{stamp}_{uuid.uuid4().hex[:4]}"
    experiment_id = f"tb_exp_{stamp}_{uuid.uuid4().hex[:8]}"
    receipt_id = f"{prefix}_rcpt_{stamp}_{uuid.uuid4().hex[:8]}"
    return session_id, experiment_id, receipt_id


def begin_http_run_receipt(
    *,
    engine_id: str,
    goal: str,
    agent_id: str,
    verified: bool,
    capability: str,
    admission_reason: str = "",
    persistence: HttpRunPersistence | None = None,
) -> HttpRunReceiptBinding:
    """Create session + experiment rows in ``running`` state at POST time."""
    stack = persistence or get_http_run_persistence()
    session_id, experiment_id, receipt_id = _now_ids()
    now_iso = datetime.now(timezone.utc).isoformat()
    stack.manager.db.save_session(
        AgentSessionRecord(
            session_id=session_id,
            agent_id=agent_id,
            started_at=now_iso,
            ended_at="",
            last_completed_action="http_run_admitted",
            current_state="RUNNING",
            four_state=HTTP_RUN_FOUR_STATE,
            metadata={
                "surface": "http",
                "engine_id": engine_id,
                "receipt_id": receipt_id,
                "verified": verified,
            },
        )
    )
    exp = ExperimentRecord(
        experiment_id=experiment_id,
        session_id=session_id,
        agent_id=agent_id,
        timestamp=now_iso,
        intent=f"http-governed-run: {goal[:150]}",
        hypothesis="hermetic governed POST /api/v1/run with admission + receipt persistence",
        execution_mode=HTTP_RUN_EXECUTION_MODE,
        status="running",
        four_state=HTTP_RUN_FOUR_STATE,
        confidence=0.0,
        parameters={
            "receipt_id": receipt_id,
            "engine_id": engine_id,
            "capability": capability,
            "verified": str(verified),
        },
    )
    stack.manager.db.save_experiment(exp)
    stack.manager.db.save_event(
        experiment_id,
        "http_run_receipt_opened",
        {"receipt_id": receipt_id, "admission_reason": admission_reason},
    )
    stack.index_engine(engine_id, receipt_id)
    binding = HttpRunReceiptBinding(
        receipt_id=receipt_id,
        session_id=session_id,
        experiment_id=experiment_id,
        engine_id=engine_id,
        agent_id=agent_id,
        goal=goal,
        verified=verified,
        capability=capability,
        admission_reason=admission_reason,
        metadata={"experiment_id": experiment_id},
    )
    stack.manager.db.save_parameter(
        experiment_id,
        ParameterProvenance(
            name="receipt_id",
            value=receipt_id,
            source="measured",
            confidence=1.0,
            session_id=session_id,
        ),
    )
    stack.manager.db.save_parameter(
        experiment_id,
        ParameterProvenance(
            name="engine_id",
            value=engine_id,
            source="measured",
            confidence=1.0,
            session_id=session_id,
        ),
    )
    return binding


def persist_profile_for_http() -> dict[str, Any]:
    return {
        "four_state": HTTP_RUN_FOUR_STATE,
        "execution_mode": HTTP_RUN_EXECUTION_MODE,
        "agent_id_field": "http-run-agent",
        "model": "hermetic-mock",
        "provider": "hermetic-mock",
        "evidence_label": HTTP_RUN_EVIDENCE,
    }


def _check_persist_hook() -> None:
    if _persist_fail_hook:
        raise RunReceiptPersistError("persist_fail_hook enabled (test)")


def finalize_http_run_receipt(
    binding: HttpRunReceiptBinding,
    *,
    status: str,
    outcome: dict[str, Any],
    confidence: float = 1.0,
    proof_path: str | None = None,
    proof_sha256: str | None = None,
    persistence: HttpRunPersistence | None = None,
) -> None:
    """Close receipt experiment + optional proof linkage (fail-closed)."""
    _check_persist_hook()
    stack = persistence or get_http_run_persistence()
    now_iso = datetime.now(timezone.utc).isoformat()
    exp_id = binding.experiment_id
    stack.manager.db.save_outcome(
        exp_id,
        outcome,
        confidence,
        HTTP_RUN_FOUR_STATE if status == "completed" else "CODE_COMPLETE",
    )
    stack.manager.db.save_event(
        exp_id,
        "http_run_receipt_closed",
        {
            "receipt_id": binding.receipt_id,
            "status": status,
            "proof_path": proof_path or "",
            "proof_sha256": proof_sha256 or "",
        },
    )
    rec = stack.manager.db.get_experiment(exp_id)
    session_started = now_iso
    if rec:
        session_row = stack.manager.db.restart_recovery().get("recent_sessions", [])
        for s in session_row:
            if s.get("session_id") == binding.session_id and s.get("started_at"):
                session_started = s["started_at"]
                break
        updated = ExperimentRecord(
            experiment_id=exp_id,
            session_id=binding.session_id,
            agent_id=binding.agent_id,
            timestamp=rec.get("timestamp", now_iso),
            intent=rec.get("intent", ""),
            hypothesis=rec.get("hypothesis", ""),
            execution_mode=HTTP_RUN_EXECUTION_MODE,
            status=status,
            four_state=HTTP_RUN_FOUR_STATE,
            confidence=confidence,
        )
        stack.manager.db.save_experiment(updated)
    stack.manager.db.save_session(
        AgentSessionRecord(
            session_id=binding.session_id,
            agent_id=binding.agent_id,
            started_at=now_iso,
            ended_at=now_iso,
            last_completed_action="http_run_receipt_closed",
            current_state=status.upper(),
            four_state=HTTP_RUN_FOUR_STATE,
            metadata={"receipt_id": binding.receipt_id, "engine_id": binding.engine_id},
        )
    )
    if proof_path and proof_sha256:
        stack.manager.db.save_proof(
            exp_id,
            {
                "proof_id": Path(proof_path).stem,
                "evidence_label": HTTP_RUN_EVIDENCE,
                "hash": proof_sha256,
                "path": proof_path,
            },
        )


def write_simple_http_run_proof(
    binding: HttpRunReceiptBinding,
    summary: dict[str, Any],
    *,
    persistence: HttpRunPersistence | None = None,
) -> tuple[str, str]:
    """On-disk proof JSON for non-verified or receipt-only paths."""
    _check_persist_hook()
    stack = persistence or get_http_run_persistence()
    payload = {
        "phase": "http-governed-run-receipt",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "receipt_id": binding.receipt_id,
        "session_id": binding.session_id,
        "experiment_id": binding.experiment_id,
        "engine_id": binding.engine_id,
        "agent_id": binding.agent_id,
        "goal": binding.goal[:200],
        "verified": binding.verified,
        "four_state": HTTP_RUN_FOUR_STATE,
        "execution_mode": HTTP_RUN_EXECUTION_MODE,
        "summary_redacted": {
            k: summary.get(k)
            for k in (
                "governed",
                "total_tasks",
                "completed",
                "goal_experiment_id",
                "session_id",
                "proof_sha256",
            )
            if k in summary
        },
        "no_claims": [
            "not LIVE_VERIFIED",
            "not PRODUCTION READY",
            "hermetic mock provider only",
        ],
    }
    raw = json.dumps(payload, indent=2, sort_keys=True).encode()
    digest = hashlib.sha256(raw).hexdigest()
    payload["proof_sha256"] = digest
    path = stack.artifacts_dir / f"http_run_proof_{binding.receipt_id}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    stack.manager.db.save_artifact(
        binding.experiment_id,
        f"art_http_{digest[:8]}",
        "http_run_proof",
        str(path),
        digest,
        {"receipt_id": binding.receipt_id},
    )
    return str(path), digest


def _param_value(raw: Any) -> str:
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw.strip().strip('"')
    return str(raw)


def _experiment_id_for_receipt(stack: HttpRunPersistence, receipt_id: str) -> str | None:
    if stack.manager.db.get_experiment(receipt_id):
        return receipt_id
    for row in stack.manager.db.restart_recovery().get("recent_experiments", []):
        exp_id = row["experiment_id"]
        for p in stack.manager.db.get_parameters_by_experiment(exp_id):
            if p.get("name") == "receipt_id" and _param_value(p.get("value")) == receipt_id:
                return exp_id
    return None


def _receipt_id_for_engine(stack: HttpRunPersistence, engine_id: str) -> str | None:
    cached = stack.receipt_for_engine(engine_id)
    if cached:
        return cached
    for row in stack.manager.db.restart_recovery().get("recent_experiments", []):
        exp_id = row["experiment_id"]
        engine_match = False
        receipt_value = ""
        for p in stack.manager.db.get_parameters_by_experiment(exp_id):
            if p.get("name") == "engine_id" and _param_value(p.get("value")) == engine_id:
                engine_match = True
            if p.get("name") == "receipt_id":
                receipt_value = _param_value(p.get("value"))
        if engine_match and receipt_value:
            stack.index_engine(engine_id, receipt_value)
            return receipt_value
    return None


def redact_receipt_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Strip token-like fields from API responses."""
    forbidden = {"governance_token", "token_value", "signing_key", "api_key"}
    out: dict[str, Any] = {}
    for key, value in data.items():
        if key.lower() in forbidden or ("token" in key.lower() and key != "tokens"):
            continue
        if isinstance(value, dict):
            out[key] = redact_receipt_payload(value)
        elif isinstance(value, list):
            out[key] = [
                redact_receipt_payload(v) if isinstance(v, dict) else v for v in value
            ]
        else:
            out[key] = value
    return out


def read_run_receipt(receipt_id: str) -> dict[str, Any] | None:
    stack = get_http_run_persistence()
    exp_id = _experiment_id_for_receipt(stack, receipt_id)
    if not exp_id:
        return None
    exp = stack.manager.db.get_experiment(exp_id)
    if not exp:
        return None
    params = stack.manager.db.get_parameters_by_experiment(exp_id)
    resolved_receipt = receipt_id
    for p in params:
        if p.get("name") == "receipt_id":
            resolved_receipt = _param_value(p.get("value")) or receipt_id
            break
    outcome = stack.manager.db.get_outcomes_by_experiment(exp_id)
    lessons = stack.manager.db.get_lessons_by_experiment(exp_id)
    payload = {
        "receipt_id": resolved_receipt,
        "experiment_id": exp_id,
        "experiment": exp,
        "parameters": params,
        "outcome": outcome,
        "lessons": lessons,
        "four_state": HTTP_RUN_FOUR_STATE,
        "live_verified": False,
        "production_ready": False,
    }
    return redact_receipt_payload(payload)


def read_run_receipt_by_engine(engine_id: str) -> dict[str, Any] | None:
    stack = get_http_run_persistence()
    receipt_id = _receipt_id_for_engine(stack, engine_id)
    if not receipt_id:
        return None
    return read_run_receipt(receipt_id)


async def emit_receipt_dashboard(
    binding: HttpRunReceiptBinding,
    *,
    status: str,
    proof_path: str | None = None,
) -> None:
    dashboard = get_dashboard_state()
    await dashboard.emit(
        DashboardCategory.THINK_JOBS,
        DashboardEvent.JOB_COMPLETED if status == "completed" else DashboardEvent.TASK_FAILED,
        {
            "job_id": binding.engine_id,
            "receipt_id": binding.receipt_id,
            "experiment_id": binding.experiment_id,
            "session_id": binding.session_id,
            "status": status,
            "proof_artifact": proof_path or "",
            "kind": "http_run_receipt",
            "evidence_label": HTTP_RUN_EVIDENCE,
        },
        source="http_run_receipts",
        evidence_label=HTTP_RUN_EVIDENCE,
    )


async def apply_persist_failure(
    job_entry: ThinkJobEntry,
    binding: HttpRunReceiptBinding,
    exc: Exception,
) -> None:
    job_entry.status = "failed"
    job_entry.phase = "receipt_persist_failed"
    job_entry.result = {
        "error": "run_receipt_persist_failed",
        "detail": str(exc)[:200],
        "receipt_id": binding.receipt_id,
        "experiment_id": binding.experiment_id,
    }
    dashboard = get_dashboard_state()
    dashboard.upsert_think_job(job_entry)
    await dashboard.emit(
        DashboardCategory.THINK_JOBS,
        DashboardEvent.TASK_FAILED,
        job_entry.model_dump(),
        "http_run_receipts",
    )
