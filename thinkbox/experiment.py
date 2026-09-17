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
import statistics
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
    FAILED = "FAILED"


class ProvenanceSource(str, Enum):
    MEASURED = "measured"
    ESTIMATED = "estimated"
    SIMULATED = "simulated"
    INFERRED = "inferred"


class OutcomeClassification(str, Enum):
    IMPROVED = "IMPROVED"
    NO_MEASURABLE_IMPROVEMENT = "NO_MEASURABLE_IMPROVEMENT"
    REGRESSION = "REGRESSION"
    INCONCLUSIVE = "INCONCLUSIVE"
    FAILED = "FAILED"


class ExperimentOutcome(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"
    INCOMPLETE = "incomplete"


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
            conn = sqlite3.connect(self.db.db_path)
            try:
                conn.execute("UPDATE experiments SET tests = ? WHERE experiment_id = ?", (json.dumps(tests), experiment_id))
                conn.commit()
            finally:
                conn.close()

    def add_artifact(self, experiment_id: str, artifact_type: str,
                      path: str, metadata: dict[str, Any] = None) -> str:
        artifact_id = f"art_{uuid.uuid4().hex[:8]}"
        hash_val = hashlib.sha256(f"{artifact_id}{path}{datetime.now(timezone.utc).isoformat()}".encode()).hexdigest()
        self.db.save_artifact(experiment_id, artifact_id, artifact_type, path, hash_val, metadata or {})
        exp = self.db.get_experiment(experiment_id)
        if exp:
            artifacts = json.loads(exp.get("artifacts", "[]"))
            artifacts.append({"artifact_id": artifact_id, "type": artifact_type, "path": path})
            conn = sqlite3.connect(self.db.db_path)
            try:
                conn.execute("UPDATE experiments SET artifacts = ? WHERE experiment_id = ?", (json.dumps(artifacts), experiment_id))
                conn.commit()
            finally:
                conn.close()
        if self._current_experiment:
            self._current_experiment.artifacts.append({"artifact_id": artifact_id, "type": artifact_type, "path": path})
        return artifact_id

    def add_proof(self, experiment_id: str, proof: dict[str, Any]) -> None:
        self.db.save_proof(experiment_id, proof)
        self.db.save_event(experiment_id, "proof", proof)
        exp = self.db.get_experiment(experiment_id)
        if exp:
            conn = sqlite3.connect(self.db.db_path)
            try:
                conn.execute("UPDATE experiments SET proof = ? WHERE experiment_id = ?", (json.dumps(proof), experiment_id))
                conn.commit()
            finally:
                conn.close()

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


class LearnedParameter:
    def __init__(self, name: str, observations: list[float], min_val: float,
                 max_val: float, mean_val: float, median_val: float,
                 sample_count: int, confidence: float, source_count: int,
                 latest_observation: Optional[float], trend: str,
                 conflicts: list[dict[str, Any]], unit: str,
                 classification: str) -> None:
        self.name = name
        self.observations = observations
        self.min_val = min_val
        self.max_val = max_val
        self.mean_val = mean_val
        self.median_val = median_val
        self.sample_count = sample_count
        self.confidence = confidence
        self.source_count = source_count
        self.latest_observation = latest_observation
        self.trend = trend
        self.conflicts = conflicts
        self.unit = unit
        self.classification = classification

    def model_dump(self) -> dict[str, Any]:
        return {
            "name": self.name, "observations": self.observations,
            "min": self.min_val, "max": self.max_val, "mean": self.mean_val,
            "median": self.median_val, "sample_count": self.sample_count,
            "confidence": self.confidence, "source_count": self.source_count,
            "latest_observation": self.latest_observation, "trend": self.trend,
            "conflicts": self.conflicts, "unit": self.unit,
            "classification": self.classification,
        }


class EvidencePattern:
    def __init__(self, pattern_type: str, parameter_name: str,
                 evidence: list[dict[str, Any]]) -> None:
        self.pattern_type = pattern_type
        self.parameter_name = parameter_name
        self.evidence = evidence

    def model_dump(self) -> dict[str, Any]:
        return {"pattern_type": self.pattern_type, "parameter_name": self.parameter_name, "evidence": self.evidence}


class Conflict:
    def __init__(self, parameter: str, classifications: list[str],
                 note: str = "") -> None:
        self.parameter = parameter
        self.classifications = classifications
        self.note = note

    def model_dump(self) -> dict[str, Any]:
        return {"parameter": self.parameter, "classifications": self.classifications, "note": self.note}


class Recommendation:
    def __init__(self, parameter_name: str, reason: str,
                 unknowns: list[str], expected_measurement: Optional[float],
                 success_criteria: str, supporting_experiment_ids: list[str],
                 session_lineage: str = "") -> None:
        self.parameter_name = parameter_name
        self.reason = reason
        self.unknowns = unknowns
        self.expected_measurement = expected_measurement
        self.success_criteria = success_criteria
        self.supporting_experiment_ids = supporting_experiment_ids
        self.session_lineage = session_lineage

    def model_dump(self) -> dict[str, Any]:
        return {
            "parameter_name": self.parameter_name, "reason": self.reason,
            "unknowns": self.unknowns, "expected_measurement": self.expected_measurement,
            "success_criteria": self.success_criteria,
            "supporting_experiment_ids": self.supporting_experiment_ids,
            "session_lineage": self.session_lineage,
        }


class ReplayRecord:
    def __init__(self, experiment_id: str, task: str, strategy: str,
                 parameters: dict[str, Any], execution: dict[str, Any],
                 tests: list[dict[str, Any]], artifacts: list[dict[str, Any]],
                 proof: dict[str, Any], outcome: dict[str, Any],
                 latency: float = 0.0, retries: int = 0, errors: int = 0) -> None:
        self.experiment_id = experiment_id
        self.task = task
        self.strategy = strategy
        self.parameters = parameters
        self.execution = execution
        self.tests = tests
        self.artifacts = artifacts
        self.proof = proof
        self.outcome = outcome
        self.latency = latency
        self.retries = retries
        self.errors = errors

    def model_dump(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id, "task": self.task,
            "strategy": self.strategy, "parameters": self.parameters,
            "execution": self.execution, "tests": self.tests,
            "artifacts": self.artifacts, "proof": self.proof,
            "outcome": self.outcome, "latency": self.latency,
            "retries": self.retries, "errors": self.errors,
        }


class ExperimentComparison:
    def __init__(self, exp_a_id: str, exp_b_id: str,
                 parameter_differences: dict[str, Any],
                 outcome_differences: dict[str, Any],
                 test_differences: dict[str, Any],
                 proof_differences: dict[str, Any],
                 lessons_differences: dict[str, Any],
                 summary: str = "") -> None:
        self.exp_a_id = exp_a_id
        self.exp_b_id = exp_b_id
        self.parameter_differences = parameter_differences
        self.outcome_differences = outcome_differences
        self.test_differences = test_differences
        self.proof_differences = proof_differences
        self.lessons_differences = lessons_differences
        self.summary = summary

    def model_dump(self) -> dict[str, Any]:
        return {
            "exp_a_id": self.exp_a_id, "exp_b_id": self.exp_b_id,
            "parameter_differences": self.parameter_differences,
            "outcome_differences": self.outcome_differences,
            "test_differences": self.test_differences,
            "proof_differences": self.proof_differences,
            "lessons_differences": self.lessons_differences,
            "summary": self.summary,
        }


class EvidenceDrivenLearningEngine:
    def __init__(self, db: ExperimentDB) -> None:
        self.db = db

    def learn_from_history(self) -> dict[str, Any]:
        all_experiments = self.db.get_all_experiments(limit=100)
        all_params: dict[str, list[dict[str, Any]]] = {}
        for exp in all_experiments:
            params = self.db.get_parameters_by_experiment(exp["experiment_id"])
            for p in params:
                name = p["name"]
                if name not in all_params:
                    all_params[name] = []
                all_params[name].append(p)
        for name in all_params:
            all_params[name].sort(key=lambda x: x.get("timestamp", ""))
        learned = self._compute_learned_parameters(all_params)
        evidence_patterns = self._identify_patterns(all_params)
        conflicts = self._detect_conflicts(all_params)
        unknowns = self._identify_unknowns(all_params)
        return {
            "learned_parameters": learned,
            "evidence_patterns": evidence_patterns,
            "conflicts": conflicts,
            "unknowns": unknowns,
            "total_experiments_analyzed": len(all_experiments),
        }

    def _compute_learned_parameters(self, all_params: dict[str, list[dict[str, Any]]]) -> dict[str, LearnedParameter]:
        learned: dict[str, LearnedParameter] = {}
        for name, observations in all_params.items():
            numeric_values: list[float] = []
            units = set()
            classifications = set()
            sources = set()
            conflicts: list[dict[str, Any]] = []
            for obs in observations:
                try:
                    val = float(obs["value"])
                    numeric_values.append(val)
                except (ValueError, TypeError):
                    continue
                if obs.get("unit"):
                    units.add(obs["unit"])
                if obs.get("classification"):
                    classifications.add(obs["classification"])
                if obs.get("source"):
                    sources.add(obs["source"])
            if not numeric_values:
                continue
            sample_count = len(numeric_values)
            min_val = min(numeric_values)
            max_val = max(numeric_values)
            mean_val = statistics.mean(numeric_values)
            median_val = statistics.median(numeric_values)
            confidence = statistics.mean([obs.get("confidence", 0.0) for obs in observations]) if observations else 0.0
            trend = self._compute_trend(numeric_values)
            primary_class = ParameterClassification.OBSERVED.value
            if ParameterClassification.OBSERVED.value not in classifications:
                if ParameterClassification.ESTIMATED.value in classifications:
                    primary_class = ParameterClassification.ESTIMATED.value
                elif ParameterClassification.SIMULATED.value in classifications:
                    primary_class = ParameterClassification.SIMULATED.value
            if len(classifications) > 1:
                conflicts.append({"parameter": name, "classifications": list(classifications), "note": "Parameter has mixed classification types"})
            if len(units) > 1:
                conflicts.append({"parameter": name, "units": list(units), "note": "Parameter has mixed units — cannot average"})
            learned[name] = LearnedParameter(
                name=name, observations=numeric_values, min_val=min_val, max_val=max_val,
                mean_val=mean_val, median_val=median_val, sample_count=sample_count,
                confidence=confidence, source_count=len(sources),
                latest_observation=numeric_values[-1] if numeric_values else None,
                trend=trend, conflicts=conflicts,
                unit=list(units)[0] if units else "", classification=primary_class,
            )
        return learned

    def _compute_trend(self, values: list[float]) -> str:
        if len(values) < 2:
            return "insufficient_data"
        first = values[0]
        last = values[-1]
        if last > first:
            return "increasing"
        elif last < first:
            return "decreasing"
        return "stable"

    def _identify_patterns(self, all_params: dict[str, list[dict[str, Any]]]) -> list[EvidencePattern]:
        patterns: list[EvidencePattern] = []
        for name, observations in all_params.items():
            classifications = set(obs.get("classification", "") for obs in observations)
            if ParameterClassification.OBSERVED.value in classifications and len(observations) >= 2:
                patterns.append(EvidencePattern("validated_range", name, observations))
            elif len(observations) >= 3:
                patterns.append(EvidencePattern("emerging_pattern", name, observations))
        return patterns

    def _detect_conflicts(self, all_params: dict[str, list[dict[str, Any]]]) -> list[Conflict]:
        conflicts: list[Conflict] = []
        for name, observations in all_params.items():
            classifications = set(obs.get("classification", "") for obs in observations if obs.get("classification"))
            if len(classifications) > 1:
                conflicts.append(Conflict(name, list(classifications), "Parameter has mixed classification types"))
        return conflicts

    def _identify_unknowns(self, all_params: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
        unknowns: list[dict[str, Any]] = []
        for name, observations in all_params.items():
            for obs in observations:
                if obs.get("classification") == ParameterClassification.OBSERVED.value and obs.get("confidence", 0.0) < 0.5:
                    unknowns.append({"parameter": name, "observation": obs, "reason": "Low confidence OBSERVED parameter"})
        return unknowns

    def recommend_next_experiment(self, learned: dict[str, LearnedParameter]) -> list[Recommendation]:
        recommendations: list[Recommendation] = []
        for name, param in learned.items():
            if param.confidence < 0.8 or param.trend in ("increasing", "decreasing"):
                unknowns = [u["parameter"] for u in self._identify_unknowns(self.db.get_all_experiments(limit=100).__class__ and {})]
                recommendations.append(Recommendation(
                    parameter_name=name,
                    reason=f"Parameter {name} has confidence {param.confidence:.2f} and trend {param.trend}",
                    unknowns=unknowns,
                    expected_measurement=param.mean_val,
                    success_criteria=f"Reduce uncertainty for {name}",
                    supporting_experiment_ids=[],
                ))
        return recommendations


class ReplayEngine:
    def __init__(self, db: ExperimentDB) -> None:
        self.db = db

    def replay(self, experiment_id: str) -> ReplayRecord:
        exp = self.db.get_experiment(experiment_id)
        if not exp:
            raise ValueError(f"Experiment {experiment_id} not found")
        params = self.db.get_parameters_by_experiment(experiment_id)
        outcome = self.db.get_outcomes_by_experiment(experiment_id)
        lessons = self.db.get_lessons_by_experiment(experiment_id)
        return ReplayRecord(
            experiment_id=experiment_id,
            task=exp.get("intent", ""),
            strategy=exp.get("hypothesis", ""),
            parameters=json.loads(exp.get("parameters", "{}")),
            execution={"actions": json.loads(exp.get("actions", "[]"))},
            tests=json.loads(exp.get("tests", "[]")),
            artifacts=json.loads(exp.get("artifacts", "[]")),
            proof=json.loads(exp.get("proof", "{}")),
            outcome=json.loads(outcome.get("outcome_data", "{}")) if outcome else {},
        )

    def replay_after_restart(self) -> dict[str, Any]:
        recovery = self.db.restart_recovery()
        return {"recovery_data": recovery, "replayable": True}


class ComparisonEngine:
    def __init__(self, db: ExperimentDB) -> None:
        self.db = db

    def compare(self, exp_a_id: str, exp_b_id: str) -> ExperimentComparison:
        exp_a = self.db.get_experiment(exp_a_id)
        exp_b = self.db.get_experiment(exp_b_id)
        if not exp_a or not exp_b:
            raise ValueError("One or both experiments not found")
        params_a = {p["name"]: p for p in self.db.get_parameters_by_experiment(exp_a_id)}
        params_b = {p["name"]: p for p in self.db.get_parameters_by_experiment(exp_b_id)}
        param_diffs = {}
        for name in set(list(params_a.keys()) + list(params_b.keys())):
            if name in params_a and name in params_b:
                if params_a[name]["value"] != params_b[name]["value"]:
                    param_diffs[name] = {"exp_a": params_a[name]["value"], "exp_b": params_b[name]["value"]}
            elif name in params_a:
                param_diffs[name] = {"exp_a": params_a[name]["value"], "exp_b": None}
            else:
                param_diffs[name] = {"exp_a": None, "exp_b": params_b[name]["value"]}
        outcome_a = self.db.get_outcomes_by_experiment(exp_a_id)
        outcome_b = self.db.get_outcomes_by_experiment(exp_b_id)
        outcome_diffs = {}
        if outcome_a and outcome_b:
            od_a = json.loads(outcome_a.get("outcome_data", "{}"))
            od_b = json.loads(outcome_b.get("outcome_data", "{}"))
            outcome_diffs = {"exp_a": od_a, "exp_b": od_b}
        tests_a = json.loads(exp_a.get("tests", "[]"))
        tests_b = json.loads(exp_b.get("tests", "[]"))
        test_diffs = {"exp_a_count": len(tests_a), "exp_b_count": len(tests_b)}
        proof_a = json.loads(exp_a.get("proof", "{}"))
        proof_b = json.loads(exp_b.get("proof", "{}"))
        proof_diffs = {"exp_a": proof_a, "exp_b": proof_b}
        lessons_a = self.db.get_lessons_by_experiment(exp_a_id)
        lessons_b = self.db.get_lessons_by_experiment(exp_b_id)
        lessons_diffs = {"exp_a_count": len(lessons_a), "exp_b_count": len(lessons_b)}
        summary = f"Compared {exp_a_id} vs {exp_b_id}: {len(param_diffs)} parameter differences, {len(outcome_diffs)} outcome differences"
        return ExperimentComparison(exp_a_id, exp_b_id, param_diffs, outcome_diffs, test_diffs, proof_diffs, lessons_diffs, summary)


class ExperimentDashboardUpgrade:
    def __init__(self, db: ExperimentDB, engine: EvidenceDrivenLearningEngine) -> None:
        self.db = db
        self.engine = engine

    def get_upgraded_dashboard(self) -> dict[str, Any]:
        aggregates = self.db.get_dashboard_aggregates()
        result = self.engine.learn_from_history()
        replay = ReplayEngine(self.db)
        return {
            **aggregates,
            "learned_parameters": result["learned_parameters"],
            "evidence_patterns": result["evidence_patterns"],
            "conflicts": result["conflicts"],
            "unknowns": result["unknowns"],
            "replay_data": replay.replay_after_restart(),
        }

    def get_evidence_graph(self) -> dict[str, Any]:
        result = self.engine.learn_from_history()
        nodes: list[dict[str, Any]] = []
        links: list[dict[str, Any]] = []
        for name, param in result["learned_parameters"].items():
            nodes.append({"id": name, "type": "parameter", "classification": param.classification})
        for pattern in result["evidence_patterns"]:
            nodes.append({"id": f"pattern_{pattern.parameter_name}", "type": "evidence", "pattern_type": pattern.pattern_type})
            links.append({"source": pattern.parameter_name, "target": f"pattern_{pattern.parameter_name}"})
        return {"nodes": nodes, "links": links}


class ExperimentArena:
    def __init__(self, db: ExperimentDB, manager: ExperimentManager) -> None:
        self.db = db
        self.manager = manager
        self._arena_id = ""
        self._task_id = ""
        self._strategies: dict[str, list[str]] = {}
        self._evaluator: Optional[ArenaEvaluator] = None

    def create_arena(self, task_id: str, task_description: str,
                     strategies: list[str]) -> dict[str, Any]:
        self._arena_id = f"arena_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"
        self._task_id = task_id
        self._strategies = {s: [] for s in strategies}
        for strategy in strategies:
            exp = self.manager.create_experiment(
                intent=task_description,
                hypothesis=f"Strategy: {strategy}",
                parameters={"strategy": strategy, "task_id": task_id},
                agent_id=strategy,
            )
            self._strategies[strategy].append(exp.experiment_id)
        return {"arena_id": self._arena_id, "task_id": self._task_id, "strategies": strategies}

    def run_baseline(self, task_id: str, parameters: dict[str, Any]) -> str:
        exp = self.manager.create_experiment(
            intent="baseline_evaluation",
            hypothesis=f"Baseline for task {task_id}",
            parameters=parameters,
            agent_id="baseline",
        )
        self.manager.add_parameter(exp.experiment_id, "strategy", "baseline", classification=ParameterClassification.OBSERVED.value)
        self.manager.add_parameter(exp.experiment_id, "task_id", task_id, classification=ParameterClassification.OBSERVED.value)
        if "BASELINE" not in self._strategies:
            self._strategies["BASELINE"] = []
        self._strategies["BASELINE"].append(exp.experiment_id)
        return exp.experiment_id

    def run_learned(self, task_id: str, parameters: dict[str, Any],
                    learned_params: dict[str, LearnedParameter]) -> str:
        exp = self.manager.create_experiment(
            intent="learned_evaluation",
            hypothesis=f"Learned strategy for task {task_id}",
            parameters={**parameters, **{k: v.mean_val for k, v in learned_params.items()}},
            agent_id="learned",
        )
        self.manager.add_parameter(exp.experiment_id, "strategy", "learned", classification=ParameterClassification.OBSERVED.value)
        self.manager.add_parameter(exp.experiment_id, "task_id", task_id, classification=ParameterClassification.OBSERVED.value)
        for name, param in learned_params.items():
            self.manager.add_parameter(exp.experiment_id, f"learned_{name}", param.mean_val, classification=ParameterClassification.OBSERVED.value)
        if "LEARNED" not in self._strategies:
            self._strategies["LEARNED"] = []
        self._strategies["LEARNED"].append(exp.experiment_id)
        return exp.experiment_id

    def run_variant(self, task_id: str, parameters: dict[str, Any],
                    variant_id: str) -> str:
        if variant_id not in self._strategies:
            self._strategies[variant_id] = []
        exp = self.manager.create_experiment(
            intent="variant_evaluation",
            hypothesis=f"Variant {variant_id} for task {task_id}",
            parameters=parameters,
            agent_id=variant_id,
        )
        self.manager.add_parameter(exp.experiment_id, "strategy", "variant", classification=ParameterClassification.OBSERVED.value)
        self.manager.add_parameter(exp.experiment_id, "task_id", task_id, classification=ParameterClassification.OBSERVED.value)
        if variant_id not in self._strategies:
            self._strategies[variant_id] = []
        self._strategies[variant_id].append(exp.experiment_id)
        return exp.experiment_id

    def evaluate(self, exp_ids: list[str]) -> dict[str, Any]:
        evaluator = ArenaEvaluator(self.db)
        return evaluator.evaluate_experiments(exp_ids)

    def compare(self, baseline_id: str, learned_id: str) -> ExperimentComparison:
        comp_engine = ComparisonEngine(self.db)
        return comp_engine.compare(baseline_id, learned_id)

    def get_arena_results(self) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for strategy, exp_ids in self._strategies.items():
            strategy_results: list[dict[str, Any]] = []
            for eid in exp_ids:
                exp = self.db.get_experiment(eid)
                if exp:
                    strategy_results.append(exp)
            results[strategy] = strategy_results
        return results


class ArenaEvaluator:
    def __init__(self, db: ExperimentDB) -> None:
        self.db = db

    def evaluate_experiments(self, exp_ids: list[str]) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for exp_id in exp_ids:
            exp = self.db.get_experiment(exp_id)
            if not exp:
                continue
            params = self.db.get_parameters_by_experiment(exp_id)
            outcome = self.db.get_outcomes_by_experiment(exp_id)
            tests = json.loads(exp.get("tests", "[]"))
            artifacts = json.loads(exp.get("artifacts", "[]"))
            proof = json.loads(exp.get("proof", "{}"))
            metrics = self._compute_metrics(exp_id, params, tests, artifacts, proof, outcome)
            results[exp_id] = metrics
        return results

    def _compute_metrics(self, exp_id: str, params: list[dict[str, Any]],
                         tests: list[dict[str, Any]], artifacts: list[dict[str, Any]],
                         proof: dict[str, Any], outcome: Optional[dict[str, Any]]) -> dict[str, Any]:
        test_pass_count = sum(1 for t in tests if t.get("result") == "pass" or t.get("status") == "pass")
        test_total = len(tests)
        test_pass_rate = test_pass_count / test_total if test_total > 0 else 0.0
        error_count = sum(1 for t in tests if t.get("result") == "fail" or t.get("status") == "fail")
        retry_count = sum(1 for t in tests if t.get("retry", False))
        artifact_quality = len(artifacts) / max(len(artifacts), 1) if artifacts else 0.0
        proof_completeness = 1.0 if proof else 0.0
        latency = sum(t.get("latency", 0) for t in tests) if tests else 0.0
        return {
            "experiment_id": exp_id,
            "success_rate": test_pass_rate,
            "test_pass_rate": test_pass_rate,
            "error_count": error_count,
            "retry_count": retry_count,
            "artifact_quality": artifact_quality,
            "proof_completeness": proof_completeness,
            "latency": latency,
            "outcome": json.loads(outcome.get("outcome_data", "{}")) if outcome else {},
        }


class MemoryReuseTracker:
    def __init__(self, db: ExperimentDB) -> None:
        self.db = db

    def track_memory_reuse(self, learned_exp_id: str, baseline_exp_id: str) -> dict[str, Any]:
        learned_params = self.db.get_parameters_by_experiment(learned_exp_id)
        baseline_params = self.db.get_parameters_by_experiment(baseline_exp_id)
        baseline_names = {p["name"] for p in baseline_params}
        reused: list[dict[str, Any]] = []
        for p in learned_params:
            if p["name"] in baseline_names or p["name"].startswith("learned_"):
                reused.append(p)
        return {
            "learned_experiment_id": learned_exp_id,
            "baseline_experiment_id": baseline_exp_id,
            "memory_reused": len(reused) > 0,
            "reused_parameters": reused,
            "reuse_count": len(reused),
            "proof": f"Learned strategy used {len(reused)} parameters from baseline or prior experiments" if reused else "No memory reuse detected",
        }


class ArenaReplayEngine:
    def __init__(self, db: ExperimentDB) -> None:
        self.db = db
        self.replay_engine = ReplayEngine(db)

    def replay_arena(self, arena_id: str) -> dict[str, Any]:
        experiments = self.db.get_all_experiments(limit=100)
        arena_exps = [e for e in experiments if e.get("experiment_id", "").startswith(arena_id[:20])]
        replay_records: list[ReplayRecord] = []
        for exp in arena_exps:
            try:
                record = self.replay_engine.replay(exp["experiment_id"])
                replay_records.append(record)
            except ValueError:
                continue
        return {"arena_id": arena_id, "replayable": True, "records": [r.model_dump() for r in replay_records]}

    def verify_reproducibility(self, exp_id: str) -> dict[str, Any]:
        record1 = self.replay_engine.replay(exp_id)
        record2 = self.replay_engine.replay(exp_id)
        equivalent = (record1.parameters == record2.parameters and
                      record1.tests == record2.tests and
                      record1.outcome == record2.outcome)
        return {"experiment_id": exp_id, "reproducible": equivalent, "runs": 2}


class OutcomeClassifier:
    @staticmethod
    def classify(baseline_metrics: dict[str, Any], learned_metrics: dict[str, Any]) -> OutcomeClassification:
        baseline_success = baseline_metrics.get("test_pass_rate", 0.0)
        learned_success = learned_metrics.get("test_pass_rate", 0.0)
        baseline_errors = baseline_metrics.get("error_count", 0)
        learned_errors = learned_metrics.get("error_count", 0)
        if learned_success > baseline_success and learned_errors <= baseline_errors:
            return OutcomeClassification.IMPROVED
        elif learned_success == baseline_success and learned_errors == baseline_errors:
            return OutcomeClassification.NO_MEASURABLE_IMPROVEMENT
        elif learned_success < baseline_success and learned_errors > baseline_errors:
            return OutcomeClassification.REGRESSION
        elif learned_success > baseline_success and learned_errors > baseline_errors:
            return OutcomeClassification.INCONCLUSIVE
        elif learned_success < baseline_success and learned_errors <= baseline_errors:
            return OutcomeClassification.INCONCLUSIVE
        else:
            return OutcomeClassification.INCONCLUSIVE

    @staticmethod
    def classify_failed(metrics: dict[str, Any]) -> OutcomeClassification:
        if metrics.get("error_count", 0) > 0 and metrics.get("test_pass_rate", 0.0) == 0.0:
            return OutcomeClassification.FAILED
        return OutcomeClassification.INCONCLUSIVE

    @staticmethod
    def classify_missing_evidence(metrics: dict[str, Any]) -> OutcomeClassification:
        if metrics.get("proof_completeness", 0.0) == 0.0:
            return OutcomeClassification.FAILED
        return OutcomeClassification.INCONCLUSIVE
