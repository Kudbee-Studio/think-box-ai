"""
Multi-cell Mesh Coordinator with Compromise Detection and Expulsion.

Monitors mesh cells for compromise signals (anomalous capability usage,
unauthorized member changes, expired credentials), detects compromised
cells, and expels them from the mesh to contain blast radius.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

from thinkbox.occupancy import MeshCell, MeshCellManager

logger = logging.getLogger(__name__)


class CompromiseSignal(Enum):
    ANOMALOUS_CAPABILITY = "anomalous_capability"
    UNAUTHORIZED_MEMBER = "unauthorized_member"
    EXPIRED_CREDENTIAL = "expired_credential"
    SUSPICIOUS_TRAFFIC = "suspicious_traffic"
    DUPLICATED_TOKEN = "duplicated_token"
    OFF_POLICY_ACTION = "off_policy_action"


@dataclass
class CompromiseEvent:
    event_id: str
    cell_id: str
    signal: CompromiseSignal
    severity: float
    details: dict[str, Any]
    detected_at: float = field(default_factory=time.time)
    resolved: bool = False


@dataclass
class DetectionRule:
    rule_id: str
    signal_type: CompromiseSignal
    threshold: float
    check: Callable[..., bool]
    description: str


@dataclass
class ExpulsionRecord:
    cell_id: str
    expelled_at: float
    reason: str
    signals: list[str]
    members_affected: int


class MeshCoordinator:
    """
    Monitors mesh cells for compromise and orchestrates expulsion.

    Properties:
    - Detects compromise signals across cells
    - Threshold-gated expulsion (configurable severity)
    - Records expulsion audit trail
    - Prevents re-admission of expelled cells
    """

    def __init__(
        self,
        mesh: MeshCellManager,
        severity_threshold: float = 0.7,
    ) -> None:
        self._mesh = mesh
        self._severity_threshold = severity_threshold
        self._events: list[CompromiseEvent] = []
        self._expulsions: list[ExpulsionRecord] = []
        self._expelled_cells: set[str] = set()
        self._rules: list[DetectionRule] = []
        self._lock = threading.Lock()
        self._compromised_count = 0

    @property
    def mesh(self) -> MeshCellManager:
        return self._mesh

    @property
    def severity_threshold(self) -> float:
        return self._severity_threshold

    def add_rule(self, rule: DetectionRule) -> None:
        with self._lock:
            self._rules.append(rule)

    def detect(
        self,
        cell_id: str,
        signals: dict[CompromiseSignal, float],
        details: dict[str, Any] | None = None,
    ) -> list[CompromiseEvent]:
        detected: list[CompromiseEvent] = []
        with self._lock:
            for signal, severity in signals.items():
                if severity >= self._severity_threshold:
                    event = CompromiseEvent(
                        event_id=f"evt_{uuid.uuid4().hex[:12]}",
                        cell_id=cell_id,
                        signal=signal,
                        severity=severity,
                        details=details or {},
                    )
                    self._events.append(event)
                    detected.append(event)
                    logger.warning(
                        f"Compromise detected: {signal.value} on cell {cell_id} "
                        f"(severity={severity:.2f})"
                    )

            if detected:
                await_or_force_expulsion = all(
                    e.severity >= self._severity_threshold for e in detected
                )
                if await_or_force_expulsion:
                    self._expel_cell(
                        cell_id,
                        [e.signal.value for e in detected],
                        "Threshold breach: multiple high-severity signals",
                    )
        return detected

    def check_expelled(self, cell_id: str) -> bool:
        with self._lock:
            return cell_id in self._expelled_cells

    def get_events(
        self,
        cell_id: str | None = None,
        resolved: bool | None = None,
    ) -> list[dict[str, Any]]:
        with self._lock:
            events = self._events
            if cell_id:
                events = [e for e in events if e.cell_id == cell_id]
            if resolved is not None:
                events = [e for e in events if e.resolved == resolved]
            return [self._event_to_dict(e) for e in events]

    def get_expulsions(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {
                    "cell_id": e.cell_id,
                    "expelled_at": e.expelled_at,
                    "reason": e.reason,
                    "signals": e.signals,
                    "members_affected": e.members_affected,
                }
                for e in self._expulsions
            ]

    def expel_cell(
        self, cell_id: str, reason: str = "Manual expulsion"
    ) -> Optional[ExpulsionRecord]:
        with self._lock:
            if cell_id in self._expelled_cells:
                return None
            if self._mesh._cells.get(cell_id) is None:
                return None
            return self._expel_cell(cell_id, [], reason)

    def get_compromised_count(self) -> int:
        with self._lock:
            return self._compromised_count

    def get_expelled_count(self) -> int:
        with self._lock:
            return len(self._expelled_cells)

    def register_detected_events(self, cell_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return [
                self._event_to_dict(e)
                for e in self._events
                if e.cell_id == cell_id
            ]

    def _expel_cell(
        self,
        cell_id: str,
        signals: list[str],
        reason: str,
    ) -> ExpulsionRecord:
        members = self._mesh.members_in(cell_id)
        self._mesh.expel_all(cell_id)
        self._expelled_cells.add(cell_id)
        self._compromised_count += 1

        record = ExpulsionRecord(
            cell_id=cell_id,
            expelled_at=time.time(),
            reason=reason,
            signals=signals,
            members_affected=len(members),
        )
        self._expulsions.append(record)
        logger.critical(
            f"Cell {cell_id} expelled from mesh: {reason} "
            f"({len(members)} members affected, signals: {signals})"
        )
        return record

    @staticmethod
    def _event_to_dict(event: CompromiseEvent) -> dict[str, Any]:
        return {
            "event_id": event.event_id,
            "cell_id": event.cell_id,
            "signal": event.signal.value,
            "severity": event.severity,
            "details": event.details,
            "detected_at": event.detected_at,
            "resolved": event.resolved,
        }
