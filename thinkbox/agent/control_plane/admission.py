"""Control-plane admission: fail-closed governance check before capacity."""

import asyncio
import logging
from typing import Any, Dict, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class AdmissionResult:
    allowed: bool
    action_type: str
    reason: str = ""
    conditions: Dict[str, Any] = field(default_factory=dict)


class ControlPlaneAdmission:
    """Fail-closed admission gate — checks governance before any capacity request."""

    def __init__(self, governance_client):
        self._governance = governance_client
        self._last_decision: Optional[AdmissionResult] = None

    async def admit(self, action_type: str, action_spec: Dict[str, Any]) -> AdmissionResult:
        """Check admission; fail-closed on any error or denial."""
        try:
            decision = await self._governance.check_admission(
                action_type=action_type,
                action_spec=action_spec,
            )
        except Exception as e:
            logger.error(f"Admission check exception: {e}")
            self._last_decision = AdmissionResult(
                allowed=False, action_type=action_type, reason=str(e),
            )
            return self._last_decision

        if not decision.allowed:
            self._last_decision = AdmissionResult(
                allowed=False,
                action_type=action_type,
                reason=decision.reason or "admission denied",
            )
            return self._last_decision

        self._last_decision = AdmissionResult(
            allowed=True,
            action_type=action_type,
            conditions=getattr(decision, "conditions", {}),
        )
        return self._last_decision

    @property
    def last_decision(self) -> Optional[AdmissionResult]:
        return self._last_decision

    def must_admit(self, action_type: str, action_spec: Dict[str, Any]) -> bool:
        """Synchronous wrapper — returns True only if previously admitted."""
        return self._last_decision is not None and self._last_decision.allowed and self._last_decision.action_type == action_type
