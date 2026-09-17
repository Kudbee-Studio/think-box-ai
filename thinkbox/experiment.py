"""Persistent Experiment + Learning System for Think Box AI.

Zero-server execution. Uses SQLite (stdlib) + filesystem artifacts.
Every agent run becomes a tracked experiment with durable session ID,
inputs, execution evidence, outputs, tests, outcome, and learned parameters.

Learning loop: Intent → Hypothesis → Parameters → Plan → Execute → Test →
Artifact → Proof → Outcome → Learn → Updated Parameters → Next Experiment.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from thinkbox.dashboard_state import (
    get_dashboard_state, DashboardCategory, DashboardEvent,
    InfrastructureEntry, ProviderEntry, TestMilestoneEntry,
)

DEFAULT_DB = "data/thinkboxmd/db/experiments.db"
DEFAULT_ARTIFACTS_DIR = "data/thinkboxmd/artifacts"


class ParameterClassification(str, Enum):
    OBSERVED = "observed"
    ESTIMATED = "estimated"
    SIMULATED = "simulated"


class ExperimentStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class FourState(str, Enum):
    CODE_COMPLETE = "CODE_COMPLETE"
    TEST_VERIFIED = "TEST_VERIFIED"
    LIVE_VERIFIED = "LIVE_VERIFIED"
    PRODUCTION_READY = "PRODUCTION_READY"


class ProvenanceSource(str, Enum):
    MEASURED = "measured"
    ESTIMATED = "estimated"
    SIMULATED = "simulated"
    INFERRED = "inferred"


@dataclass
class ParameterProvenance:
    name: str
    value: Any
    unit: str = ""
    source: str = ProvenanceSource.MEASURED.value
    confidence: float = 0.0
    classification: str = ParameterClassification.OBSERVED.value
    session_id: str = ""
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        if not self.session_id:
            self.session_id = ""
        if not isinstance(self.confidence, float):
            self.confidence = float(self.confidence)

    def model_dump(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "source": self.source,
            "confidence": self.confidence,
            "classification": self.classification,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
        }


@dataclass
class ExperimentRecord:
    session_id: str = ""
    experiment_id: str = ""
    parent_session_id: str = ""
    agent_id: str = ""
    timestamp: str = ""
    intent: str = ""
    hypothesis: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    capabilities_used: list[str] = field(default_factory=list)
    execution_mode: str = "local"
    actions: list[dict[str, Any]] = field(default_factory=list)
    tests: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    proof: dict[str, Any] = field(default_factory=dict)
    outcome: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    lessons: list[str] = field(default_factory=list)
    next_experiment: str = ""
    status: str = ExperimentStatus.PENDING.value
    four_state: str = ""

    def __post_init__(self) -> None:
        if not self.session_id:
            self.session_id = f"tb_sess_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:4]}"
        if not self.experiment_id:
            self.experiment_id = f"tb_exp_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        if not isinstance(self.confidence, float):
            self.confidence = float(self.confidence)

    def model_dump(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "experiment_id": self.experiment_id,
            "parent_session_id": self.parent_session_id,
            "agent_id": self.agent_id,
            "timestamp": self.timestamp,
            "intent": self.intent,
            "hypothesis": self.hypothesis,
            "parameters": self.parameters,
            "capabilities_used": self.capabilities_used,
            "execution_mode": self.execution_mode,
            "actions": self.actions,
            "tests": self.tests,
            "artifacts": self.artifacts,
            "proof": self.proof,
            "outcome": self.outcome,
            "confidence": self.confidence,
            "lessons": self.lessons,
            "next_experiment": self.next_experiment,
            "status": self.status,
            "four_state": self.four_state,
        }


@dataclass
class AgentSessionRecord:
    session_id: str = ""
    parent_session_id: str = ""
    agent_id: str = ""
    started_at: str = ""
    ended_at: str = ""
    last_completed_action: str = ""
    current_state: str = ""
    blockers: list[str] = field(default_factory=list)
    next_larger_improvement: str = ""
    four_state: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.session_id:
            self.session_id = f"tb_sess_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:4]}"
        if not self.started_at:
            self.started_at = datetime.now(timezone.utc).isoformat()
        if not isinstance(self.four_state, str):
            self.four_state = ""

    def model_dump(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "parent_session_id": self.parent_session_id,
            "agent_id": self.agent_id,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "last_completed_action": self.last_completed_action,
            "current_state": self.current_state,
            "blockers": self.blockers,
            "next_larger_improvement": self.next_larger_improvement,
            "four_state": self.four_state,
            "metadata": self.metadata,
        }


class ExperimentDB:
    """SQLite persistence layer for experiments. Zero-dollar, stdlib only."""

    def __init__(self, db_path: str = DEFAULT_DB) -> None:
        self.db_path = db_path
        self._lock = threading.Lock()
        self._ensure_dir()
        self._init_schema()

    def _ensure_dir(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    def _init_schema(self) -> None:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS agent_sessions (
                        session_id TEXT PRIMARY KEY,
                        parent_session_id TEXT,
                        agent_id TEXT,
                        started_at TEXT,
                        ended_at TEXT,
                        last_completed_action TEXT,
                        current_state TEXT,
                        blockers TEXT DEFAULT '[]',
                        next_larger_improvement TEXT,
                        four_state TEXT,
                        metadata TEXT DEFAULT '{}'
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS experiments (
                        experiment_id TEXT PRIMARY KEY,
                        session_id TEXT,
                        parent_session_id TEXT,
                        agent_id TEXT,
                        timestamp TEXT,
                        intent TEXT,
                        hypothesis TEXT,
                        parameters TEXT DEFAULT '{}',
                        capabilities_used TEXT DEFAULT '[]',
                        execution_mode TEXT DEFAULT 'local',
                        actions TEXT DEFAULT '[]',
                        tests TEXT DEFAULT '[]',
                        artifacts TEXT DEFAULT '[]',
                        proof TEXT DEFAULT '{}',
                        outcome TEXT DEFAULT '{}',
                        confidence REAL DEFAULT 0.0,
                        lessons TEXT DEFAULT '[]',
                        next_experiment TEXT,
                        status TEXT DEFAULT 'pending',
                        four_state TEXT,
                        FOREIGN KEY (session_id) REFERENCES agent_sessions(session_id)
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS experiment_parameters (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        experiment_id TEXT,
                        name TEXT,
                        value TEXT,
                        unit TEXT,
                        source TEXT,
                        confidence REAL DEFAULT 0.0,
                        classification TEXT DEFAULT 'observed',
                        session_id TEXT,
                        timestamp TEXT,
                        FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id)
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS experiment_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        experiment_id TEXT,
                        event_type TEXT,
                        data TEXT DEFAULT '{}',
                        timestamp TEXT,
                        FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id)
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS artifacts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        experiment_id TEXT,
                        artifact_id TEXT,
                        artifact_type TEXT,
                        path TEXT,
                        hash TEXT,
                        metadata TEXT DEFAULT '{}',
                        timestamp TEXT,
                        FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id)
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS proof_records (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        experiment_id TEXT,
                        proof_id TEXT,
                        evidence_label TEXT,
                        decisions TEXT DEFAULT '[]',
                        validations TEXT DEFAULT '[]',
                        approvals TEXT DEFAULT '[]',
                        hash TEXT,
                        timestamp TEXT,
                        FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id)
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS outcomes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        experiment_id TEXT,
                        outcome_data TEXT DEFAULT '{}',
                        confidence REAL DEFAULT 0.0,
                        four_state TEXT,
                        timestamp TEXT,
                        FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id)
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS lessons (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        experiment_id TEXT,
                        lesson TEXT,
                        parameter_updates TEXT DEFAULT '[]',
                        next_experiment TEXT,
                        timestamp TEXT,
                        FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id)
                    )
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_experiments_session ON experiments(session_id)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_experiments_id ON experiments(experiment_id)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_experiments_timestamp ON experiments(timestamp)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_params_experiment ON experiment_parameters(experiment_id)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_params_name ON experiment_parameters(name)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_outcomes_experiment ON outcomes(experiment_id)
                """)
                conn.commit()
            finally:
                conn.close()

    def _row_to_dict(self, row: tuple, columns: tuple) -> dict[str, Any]:
        return dict(zip(columns, row))

    def save_session(self, session: AgentSessionRecord) -> None:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO agent_sessions
                    (session_id, parent_session_id, agent_id, started_at, ended_at,
                     last_completed_action, current_state, blockers,
                     next_larger_improvement, four_state, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session.session_id, session.parent_session_id, session.agent_id,
                    session.started_at, session.ended_at, session.last_completed_action,
                    session.current_state, json.dumps(session.blockers),
                    session.next_larger_improvement, session.four_state,
                    json.dumps(session.metadata),
                ))
                conn.commit()
            finally:
                conn.close()

    def get_session(self, session_id: str) -> Optional[dict[str, Any]]:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT * FROM agent_sessions WHERE session_id = ?", (session_id,)
                )
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None
            finally:
                conn.close()

    def save_experiment(self, experiment: ExperimentRecord) -> None:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO experiments
                    (experiment_id, session_id, parent_session_id, agent_id, timestamp,
                     intent, hypothesis, parameters, capabilities_used, execution_mode,
                     actions, tests, artifacts, proof, outcome, confidence, lessons,
                     next_experiment, status, four_state)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    experiment.experiment_id, experiment.session_id,
                    experiment.parent_session_id, experiment.agent_id, experiment.timestamp,
                    experiment.intent, experiment.hypothesis,
                    json.dumps(experiment.parameters),
                    json.dumps(experiment.capabilities_used),
                    experiment.execution_mode,
                    json.dumps(experiment.actions),
                    json.dumps(experiment.tests),
                    json.dumps(experiment.artifacts),
                    json.dumps(experiment.proof),
                    json.dumps(experiment.outcome),
                    experiment.confidence,
                    json.dumps(experiment.lessons),
                    experiment.next_experiment, experiment.status, experiment.four_state,
                ))
                for param in experiment.parameters.values() if isinstance(experiment.parameters, dict) else []:
                    pass
                conn.commit()
            finally:
                conn.close()

    def save_parameter(self, experiment_id: str, param: ParameterProvenance) -> None:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("""
                    INSERT INTO experiment_parameters
                    (experiment_id, name, value, unit, source, confidence, classification, session_id, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    experiment_id, param.name, json.dumps(param.value) if not isinstance(param.value, str) else param.value,
                    param.unit, param.source, param.confidence, param.classification,
                    param.session_id, param.timestamp,
                ))
                conn.commit()
            finally:
                conn.close()

    def save_event(self, experiment_id: str, event_type: str, data: dict[str, Any]) -> None:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("""
                    INSERT INTO experiment_events (experiment_id, event_type, data, timestamp)
                    VALUES (?, ?, ?, ?)
                """, (experiment_id, event_type, json.dumps(data), datetime.now(timezone.utc).isoformat()))
                conn.commit()
            finally:
                conn.close()

    def save_artifact(self, experiment_id: str, artifact_id: str, artifact_type: str,
                      path: str, hash_val: str, metadata: dict[str, Any]) -> None:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("""
                    INSERT INTO artifacts (experiment_id, artifact_id, artifact_type, path, hash, metadata, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (experiment_id, artifact_id, artifact_type, path, hash_val, json.dumps(metadata), datetime.now(timezone.utc).isoformat()))
                conn.commit()
            finally:
                conn.close()

    def save_proof(self, experiment_id: str, proof: dict[str, Any]) -> None:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("""
                    INSERT INTO proof_records (experiment_id, proof_id, evidence_label, decisions, validations, approvals, hash, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    experiment_id, proof.get("proof_id", ""), proof.get("evidence_label", "simulated"),
                    json.dumps(proof.get("decisions", [])), json.dumps(proof.get("validations", [])),
                    json.dumps(proof.get("approvals", [])), proof.get("hash", ""),
                    datetime.now(timezone.utc).isoformat(),
                ))
                conn.commit()
            finally:
                conn.close()

    def save_outcome(self, experiment_id: str, outcome: dict[str, Any],
                     confidence: float, four_state: str) -> None:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("""
                    INSERT INTO outcomes (experiment_id, outcome_data, confidence, four_state, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """, (experiment_id, json.dumps(outcome), confidence, four_state, datetime.now(timezone.utc).isoformat()))
                conn.commit()
            finally:
                conn.close()

    def save_lesson(self, experiment_id: str, lesson: str,
                    parameter_updates: list[dict[str, Any]], next_experiment: str) -> None:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("""
                    INSERT INTO lessons (experiment_id, lesson, parameter_updates, next_experiment, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """, (experiment_id, lesson, json.dumps(parameter_updates), next_experiment, datetime.now(timezone.utc).isoformat()))
                conn.commit()
            finally:
                conn.close()

    def get_experiment(self, experiment_id: str) -> Optional[dict[str, Any]]:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT * FROM experiments WHERE experiment_id = ?", (experiment_id,)
                )
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None
            finally:
                conn.close()

    def get_experiments_by_session(self, session_id: str) -> list[dict[str, Any]]:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT * FROM experiments WHERE session_id = ? ORDER BY timestamp DESC", (session_id,)
                )
                return [dict(row) for row in cursor.fetchall()]
            finally:
                conn.close()

    def get_all_experiments(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT * FROM experiments ORDER BY timestamp DESC LIMIT ?", (limit,)
                )
                return [dict(row) for row in cursor.fetchall()]
            finally:
                conn.close()

    def get_parameters_by_experiment(self, experiment_id: str) -> list[dict[str, Any]]:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT * FROM experiment_parameters WHERE experiment_id = ? ORDER BY id", (experiment_id,)
                )
                return [dict(row) for row in cursor.fetchall()]
            finally:
                conn.close()

    def get_outcomes_by_experiment(self, experiment_id: str) -> Optional[dict[str, Any]]:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT * FROM outcomes WHERE experiment_id = ?", (experiment_id,)
                )
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None
            finally:
                conn.close()

    def get_lessons_by_experiment(self, experiment_id: str) -> list[dict[str, Any]]:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT * FROM lessons WHERE experiment_id = ? ORDER BY id", (experiment_id,)
                )
                return [dict(row) for row in cursor.fetchall()]
            finally:
                conn.close()

    def get_dashboard_aggregates(self) -> dict[str, Any]:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.row_factory = sqlite3.Row
                result: dict[str, Any] = {}
                cursor = conn.execute("SELECT COUNT(*) as count FROM experiments")
                result["total_experiments"] = cursor.fetchone()["count"]
                cursor = conn.execute("SELECT status, COUNT(*) as count FROM experiments GROUP BY status")
                result["experiments_by_status"] = {row["status"]: row["count"] for row in cursor.fetchall()}
                cursor = conn.execute("SELECT four_state, COUNT(*) as count FROM experiments WHERE four_state != '' GROUP BY four_state")
                result["experiments_by_state"] = {row["four_state"]: row["count"] for row in cursor.fetchall()}
                cursor = conn.execute("SELECT COUNT(*) as count FROM agent_sessions")
                result["total_sessions"] = cursor.fetchone()["count"]
                cursor = conn.execute("SELECT COUNT(*) as count FROM experiment_parameters")
                result["total_parameters"] = cursor.fetchone()["count"]
                cursor = conn.execute("SELECT COUNT(*) as count FROM artifacts")
                result["total_artifacts"] = cursor.fetchone()["count"]
                cursor = conn.execute("SELECT COUNT(*) as count FROM proof_records")
                result["total_proofs"] = cursor.fetchone()["count"]
                cursor = conn.execute("SELECT AVG(confidence) as avg_conf FROM experiments WHERE confidence > 0")
                row = cursor.fetchone()
                result["avg_confidence"] = row["avg_conf"] if row and row["avg_conf"] else 0.0
                cursor = conn.execute("SELECT * FROM experiments ORDER BY timestamp DESC LIMIT 10")
                result["recent_experiments"] = [dict(row) for row in cursor.fetchall()]
                return result
            finally:
                conn.close()

    def restart_recovery(self) -> dict[str, Any]:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.row_factory = sqlite3.Row
                result: dict[str, Any] = {}
                cursor = conn.execute("SELECT * FROM agent_sessions ORDER BY started_at DESC LIMIT 5")
                result["recent_sessions"] = [dict(row) for row in cursor.fetchall()]
                cursor = conn.execute("SELECT * FROM experiments WHERE status IN ('pending', 'running') ORDER BY timestamp DESC")
                result["active_experiments"] = [dict(row) for row in cursor.fetchall()]
                cursor = conn.execute("SELECT * FROM experiments ORDER BY timestamp DESC LIMIT 5")
                result["recent_experiments"] = [dict(row) for row in cursor.fetchall()]
                return result
            finally:
                conn.close()


class ExperimentManager:
    """Manages the complete experiment lifecycle with zero-server execution."""

    def __init__(self, db_path: str = DEFAULT_DB, artifacts_dir: str = DEFAULT_ARTIFACTS_DIR) -> None:
        self.db = ExperimentDB(db_path)
        self.artifacts_dir = Path(artifacts_dir)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self._current_experiment: Optional[ExperimentRecord] = None
        self._current_session: Optional[AgentSessionRecord] = None

    def create_session(self, parent_session_id: str = "", agent_id: str = "default",
                       metadata: dict[str, Any] = None) -> AgentSessionRecord:
        session = AgentSessionRecord(
            parent_session_id=parent_session_id,
            agent_id=agent_id,
            metadata=metadata or {},
        )
        self.db.save_session(session)
        self._current_session = session
        self.db.save_event(session.session_id, "session_created", session.model_dump())
        return session

    def create_experiment(self, intent: str, hypothesis: str,
                          parameters: dict[str, Any] = None,
                          parent_session_id: str = "",
                          agent_id: str = "default",
                          execution_mode: str = "local") -> ExperimentRecord:
        session = self._current_session or self.create_session(agent_id=agent_id, parent_session_id=parent_session_id)
        experiment = ExperimentRecord(
            session_id=session.session_id,
            parent_session_id=parent_session_id,
            agent_id=agent_id,
            intent=intent,
            hypothesis=hypothesis,
            parameters=parameters or {},
            execution_mode=execution_mode,
        )
        self.db.save_experiment(experiment)
        self._current_experiment = experiment
        self.db.save_event(experiment.experiment_id, "experiment_created", experiment.model_dump())
        return experiment

    def add_parameter(self, experiment_id: str, name: str, value: Any,
                      unit: str = "", source: str = ProvenanceSource.MEASURED.value,
                      confidence: float = 0.0, classification: str = ParameterClassification.OBSERVED.value,
                      session_id: str = "") -> ParameterProvenance:
        param = ParameterProvenance(
            name=name, value=value, unit=unit, source=source,
            confidence=confidence, classification=classification,
            session_id=session_id or self._current_experiment.session_id if self._current_experiment else "",
        )
        self.db.save_parameter(experiment_id, param)
        if self._current_experiment and self._current_experiment.experiment_id == experiment_id:
            self._current_experiment.parameters[name] = value
        return param

    def add_action(self, experiment_id: str, action: dict[str, Any]) -> None:
        exp = self.db.get_experiment(experiment_id)
        if exp:
            actions = json.loads(exp.get("actions", "[]"))
            actions.append(action)
            self.db.save_event(experiment_id, "action", action)

    def add_test(self, experiment_id: str, test: dict[str, Any]) -> None:
        exp = self.db.get_experiment(experiment_id)
        if exp:
            tests = json.loads(exp.get("tests", "[]"))
            tests.append(test)
            self.db.save_event(experiment_id, "test", test)

    def add_artifact(self, experiment_id: str, artifact_type: str,
                     path: str, metadata: dict[str, Any] = None) -> str:
        artifact_id = f"art_{uuid.uuid4().hex[:8]}"
        hash_val = hashlib.sha256(f"{artifact_id}{path}{datetime.now(timezone.utc).isoformat()}".encode()).hexdigest()
        self.db.save_artifact(experiment_id, artifact_id, artifact_type, path, hash_val, metadata or {})
        if self._current_experiment:
            self._current_experiment.artifacts.append({"artifact_id": artifact_id, "type": artifact_type, "path": path})
        return artifact_id

    def add_proof(self, experiment_id: str, proof: dict[str, Any]) -> None:
        self.db.save_proof(experiment_id, proof)
        self.db.save_event(experiment_id, "proof", proof)

    def record_outcome(self, experiment_id: str, outcome: dict[str, Any],
                       confidence: float, four_state: str = "") -> None:
        self.db.save_outcome(experiment_id, outcome, confidence, four_state)
        exp = self.db.get_experiment(experiment_id)
        if exp:
            self.db.save_event(experiment_id, "outcome", {"outcome": outcome, "confidence": confidence, "four_state": four_state})

    def record_lesson(self, experiment_id: str, lesson: str,
                      parameter_updates: list[dict[str, Any]] = None,
                      next_experiment: str = "") -> None:
        self.db.save_lesson(experiment_id, lesson, parameter_updates or [], next_experiment)
        self.db.save_event(experiment_id, "lesson", {"lesson": lesson, "next_experiment": next_experiment})

    def complete_experiment(self, experiment_id: str, outcome: dict[str, Any],
                            confidence: float, four_state: str = "",
                            lessons: list[str] = None,
                            next_experiment: str = "") -> ExperimentRecord:
        exp = self.db.get_experiment(experiment_id)
        if not exp:
            raise ValueError(f"Experiment {experiment_id} not found")
        self.db.save_outcome(experiment_id, outcome, confidence, four_state)
        self.db.save_event(experiment_id, "experiment_completed", {"outcome": outcome, "confidence": confidence, "four_state": four_state})
        if lessons:
            for lesson in lessons:
                self.db.save_lesson(experiment_id, lesson, [], next_experiment)
        if next_experiment:
            self.db.save_event(experiment_id, "next_experiment", next_experiment)
        return self.db.get_experiment(experiment_id)

    def run_zero_server_experiment(self, intent: str, hypothesis: str,
                                   parameters: dict[str, Any] = None,
                                   agent_id: str = "default") -> dict[str, Any]:
        session = self.create_session(agent_id=agent_id)
        experiment = self.create_experiment(
            intent=intent, hypothesis=hypothesis,
            parameters=parameters, parent_session_id=session.parent_session_id,
            agent_id=agent_id, execution_mode="local",
        )
        self.db.save_event(experiment.experiment_id, "execution_started", {"mode": "local"})
        for name, value in (parameters or {}).items():
            self.add_parameter(experiment.experiment_id, name, value, classification=ParameterClassification.OBSERVED.value, confidence=1.0)
        self.db.save_event(experiment.experiment_id, "execution_complete", {"mode": "local"})
        return experiment.model_dump()

    def get_dashboard_data(self) -> dict[str, Any]:
        aggregates = self.db.get_dashboard_aggregates()
        state = get_dashboard_state()
        state_data = state.get_state()
        return {
            **aggregates,
            "dashboard_state": state_data,
            "current_session": self._current_session.model_dump() if self._current_session else None,
            "active_experiments": self.db.restart_recovery().get("active_experiments", []),
        }

    def restart(self) -> dict[str, Any]:
        return self.db.restart_recovery()


def get_experiment_manager() -> ExperimentManager:
    global _experiment_manager
    if not hasattr(_experiment_manager, "instance") or _experiment_manager.instance is None:
        _experiment_manager.instance = ExperimentManager()
    return _experiment_manager.instance

_experiment_manager: Any = type("_", (), {"instance": None})()
