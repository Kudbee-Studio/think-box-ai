"""PR-scoped ephemeral database provisioning and lifecycle management.

Every PR receives an isolated Upstash RDS database with a strict 72-hour
lifecycle. In test mode, uses local SQLite that simulates the same lifecycle.

Lifecycle: PROVISIONED → ACTIVE → EXPIRED → CLEANED

Reuses ExperimentDB/ExperimentManager for data persistence. This module
handles only provisioning, lifecycle tracking, and cleanup.

No secrets committed. TTL enforced. Cleanup is idempotent and fail-closed.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional

from thinkbox.experiment import ExperimentDB, ExperimentManager
from thinkbox.dashboard_state import get_dashboard_state, DashboardCategory, DashboardEvent


PR_DB_TTL_HOURS = 72
PR_DB_STATES = ["PROVISIONED", "ACTIVE", "EXPIRED", "CLEANED"]
PR_DB_TRANSITIONS = {
    "PROVISIONED": ["ACTIVE", "CLEANED"],
    "ACTIVE": ["EXPIRED", "CLEANED"],
    "EXPIRED": ["CLEANED"],
    "CLEANED": [],
}


class PRDBState(str, Enum):
    PROVISIONED = "PROVISIONED"
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    CLEANED = "CLEANED"


class PRDatabaseConfig:
    """Configuration for PR-scoped database provisioning."""

    def __init__(
        self,
        pr_number: int,
        branch: str = "",
        ttl_hours: int = PR_DB_TTL_HOURS,
        test_mode: bool = False,
    ) -> None:
        self.pr_number = pr_number
        self.branch = branch
        self.ttl_hours = ttl_hours
        self.test_mode = test_mode


class PRDatabaseRecord:
    """Record of a provisioned PR-scoped database."""

    def __init__(
        self,
        db_id: str,
        pr_number: int,
        branch: str,
        db_path: str,
        db_type: str,
        state: str,
        created_at: str,
        expires_at: str,
        evidence: dict[str, Any],
    ) -> None:
        self.db_id = db_id
        self.pr_number = pr_number
        self.branch = branch
        self.db_path = db_path
        self.db_type = db_type  # "upstash_rds" or "local_sqlite"
        self.state = state
        self.created_at = created_at
        self.expires_at = expires_at
        self.evidence = evidence

    def model_dump(self) -> dict[str, Any]:
        return {
            "db_id": self.db_id,
            "pr_number": self.pr_number,
            "branch": self.branch,
            "db_path": self.db_path,
            "db_type": self.db_type,
            "state": self.state,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "evidence": self.evidence,
        }


class PRDatabaseProvisioner:
    """Provisions, tracks, and cleans up PR-scoped databases."""

    def __init__(self, config: PRDatabaseConfig) -> None:
        self._config = config
        self._records: dict[str, PRDatabaseRecord] = {}
        self._state_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, prefix="prdb_"
        )
        self._state_file.close()
        self._load_state()

    def _load_state(self) -> None:
        try:
            with open(self._state_file.name, "r") as f:
                data = json.load(f)
                for db_id, record in data.items():
                    self._records[db_id] = PRDatabaseRecord(**record)
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def _save_state(self) -> None:
        data = {
            db_id: record.model_dump() for db_id, record in self._records.items()
        }
        with open(self._state_file.name, "w") as f:
            json.dump(data, f, indent=2)

    def _is_expired(self, record: PRDatabaseRecord) -> bool:
        expires = datetime.fromisoformat(record.expires_at)
        return datetime.now(timezone.utc) > expires

    def provision(self) -> PRDatabaseRecord:
        """Provision a new PR-scoped database. Fail-closed on error."""
        db_id = f"pr_db_{self._config.pr_number}_{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc)
        expires = now + timedelta(hours=self._config.ttl_hours)

        if self._config.test_mode:
            db_path = tempfile.mkdtemp(prefix=f"pr_db_{self._config.pr_number}_")
            db_file = os.path.join(db_path, "experiments.db")
            db_type = "local_sqlite"
        else:
            upstash_token = os.environ.get("UPSTASH_API_KEY", "")
            if not upstash_token:
                raise RuntimeError(
                    "BLOCKED: UPSTASH_API_KEY required for provisioning. "
                    "Set it in environment or use test_mode=True."
                )
            db_path = f"upstash://pr_db_{self._config.pr_number}"
            db_type = "upstash_rds"

        record = PRDatabaseRecord(
            db_id=db_id,
            pr_number=self._config.pr_number,
            branch=self._config.branch,
            db_path=db_file if db_type == "local_sqlite" else db_path,
            db_type=db_type,
            state=PRDBState.PROVISIONED.value,
            created_at=now.isoformat(),
            expires_at=expires.isoformat(),
            evidence={
                "provisioned_by": "PRDatabaseProvisioner",
                "pr_number": self._config.pr_number,
                "branch": self._config.branch,
                "db_type": db_type,
                "ttl_hours": self._config.ttl_hours,
                "test_mode": self._config.test_mode,
                "provisioned_at": now.isoformat(),
            },
        )

        self._records[db_id] = record
        self._save_state()
        self._emit_event("PROVISIONED", record.model_dump())

        return record

    def get_status(self, db_id: str) -> Optional[dict[str, Any]]:
        """Get DB lifecycle status."""
        record = self._records.get(db_id)
        if not record:
            return None
        status = {
            "db_id": record.db_id,
            "state": record.state,
            "db_type": record.db_type,
            "pr_number": record.pr_number,
            "created_at": record.created_at,
            "expires_at": record.expires_at,
            "is_expired": self._is_expired(record),
            "evidence": record.evidence,
        }
        if self._is_expired(record) and record.state == PRDBState.ACTIVE.value:
            record.state = PRDBState.EXPIRED.value
            self._save_state()
            self._emit_event("EXPIRED", record.model_dump())
            status["state"] = PRDBState.EXPIRED.value
            status["is_expired"] = True
        return status

    def health_check(self, db_id: str) -> dict[str, Any]:
        """Health check for PR DB."""
        status = self.get_status(db_id)
        if not status:
            return {"db_id": db_id, "healthy": False, "error": "not_found"}

        healthy = status["state"] in (PRDBState.ACTIVE.value,) and not status["is_expired"]

        db_path = status.get("evidence", {}).get("db_path", "")
        if status.get("db_type") == "local_sqlite" and db_path:
            try:
                conn = sqlite3.connect(db_path)
                conn.execute("SELECT 1")
                conn.close()
                healthy = True
            except Exception as e:
                healthy = False
                status["error"] = str(e)

        return {
            "db_id": db_id,
            "healthy": healthy,
            "state": status["state"],
            "is_expired": status["is_expired"],
            "db_type": status.get("db_type", ""),
        }

    def activate(self, db_id: str) -> PRDatabaseRecord:
        """Transition PROVISIONED → ACTIVE."""
        record = self._records.get(db_id)
        if not record:
            raise ValueError(f"DB {db_id} not found")
        if record.state != PRDBState.PROVISIONED.value:
            raise ValueError(f"Cannot activate from state {record.state}")
        record.state = PRDBState.ACTIVE.value
        self._save_state()
        self._emit_event("ACTIVE", record.model_dump())
        return record

    def cleanup(self, db_id: str) -> PRDatabaseRecord:
        """Deterministic, idempotent cleanup. Fail-closed.

        Always safe to call. Already-cleaned DBs are returned unchanged.
        """
        record = self._records.get(db_id)
        if not record:
            raise ValueError(f"DB {db_id} not found")
        if record.state == PRDBState.CLEANED.value:
            return record

        if record.state not in PR_DB_TRANSITIONS:
            raise ValueError(f"Cannot cleanup from state {record.state}")
        if PRDBState.CLEANED.value not in PR_DB_TRANSITIONS[record.state]:
            raise ValueError(f"Cannot cleanup from state {record.state}")

        record.state = PRDBState.CLEANED.value
        record.evidence["cleaned_at"] = datetime.now(timezone.utc).isoformat()
        record.evidence["cleanup_reason"] = "manual"
        self._save_state()
        self._emit_event("CLEANED", record.model_dump())

        if record.db_type == "local_sqlite":
            import shutil
            db_dir = os.path.dirname(record.db_path)
            if os.path.isdir(db_dir):
                shutil.rmtree(db_dir, ignore_errors=True)

        return record

    def cleanup_expired(self) -> list[str]:
        """Clean up all expired DBs. Returns list of cleaned db_ids."""
        cleaned = []
        for db_id, record in self._records.items():
            if self._is_expired(record) and record.state != PRDBState.CLEANED.value:
                self.cleanup(db_id)
                cleaned.append(db_id)
        return cleaned

    def list_all(self) -> list[dict[str, Any]]:
        """List all PR DB records."""
        return [r.model_dump() for r in self._records.values()]

    def get_manager(self, db_id: str) -> ExperimentManager:
        """Get an ExperimentManager scoped to this PR DB."""
        record = self._records.get(db_id)
        if not record:
            raise ValueError(f"DB {db_id} not found")
        if record.state != PRDBState.ACTIVE.value:
            raise ValueError(f"DB {db_id} is not ACTIVE (state: {record.state})")
        return ExperimentManager(db_path=record.db_path)

    def _emit_event(self, state: str, data: dict[str, Any]) -> None:
        """Emit lifecycle event to dashboard."""
        try:
            ds = get_dashboard_state()
            import asyncio

            async def _emit() -> None:
                await ds.emit(
                    DashboardCategory.EXECUTION,
                    DashboardEvent.JOB_CREATED,
                    {"pr_db": data, "state": state},
                    "pr_db_provisioner",
                    evidence_label="verified",
                )

            asyncio.run(_emit())
        except Exception:
            pass


class PRDBLifecycle:
    """Tracks PR DB lifecycle state transitions."""

    VALID_TRANSITIONS: dict[str, list[str]] = PR_DB_TRANSITIONS

    @classmethod
    def can_transition(cls, from_state: str, to_state: str) -> bool:
        return to_state in cls.VALID_TRANSITIONS.get(from_state, [])

    @classmethod
    def validate_transition(cls, from_state: str, to_state: str) -> None:
        if from_state not in PR_DB_STATES:
            raise ValueError(f"Invalid from_state: {from_state}")
        if to_state not in PR_DB_STATES:
            raise ValueError(f"Invalid to_state: {to_state}")
        if not cls.can_transition(from_state, to_state):
            raise ValueError(
                f"Invalid transition: {from_state} → {to_state}. "
                f"Valid: {cls.VALID_TRANSITIONS[from_state]}"
            )

    @classmethod
    def is_terminal(cls, state: str) -> bool:
        return state == PRDBState.CLEANED.value
