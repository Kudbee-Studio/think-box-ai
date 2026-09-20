"""Wire admit + capacity into demo path (fail-closed; mocked OK in CI)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from thinkbox.agent.control_plane.store import ActionReceiptStore
from thinkbox.agent.control_plane.kernel_hooks import HookContext, on_admit

logger = logging.getLogger(__name__)


@dataclass
class DemoConfig:
    agent_id: str = "demo"
    capability: str = "demo:run"
    model: str = "openai/gpt-oss-20b"
    base_url: str = "http://127.0.0.1:8001"
    pairs: int = 2
    minutes: float = 1.0
    max_calls: int = 8
    budget: float = 1.0
    evidence_label: str = "simulated"


@dataclass
class DemoAdmitResult:
    admitted: bool
    agent_id: str
    reason: str
    capacity_granted: bool
    evidence_label: str
    metadata: dict[str, Any] = field(default_factory=dict)


class DemoControlPlaneBind:
    """Bind demo path through control-plane admit + capacity gates."""

    def __init__(
        self,
        store: ActionReceiptStore,
        config: DemoConfig | None = None,
    ) -> None:
        self.store = store
        self.config = config or DemoConfig()
        self._last_admit: DemoAdmitResult | None = None

    def admit(self) -> DemoAdmitResult:
        """Fail-closed admission check + receipt. Cached."""
        if self._last_admit is not None:
            return self._last_admit
        result = self._do_admit()
        self._last_admit = result
        return result

    def _do_admit(self) -> DemoAdmitResult:
        if not self._has_token():
            on_admit(
                self.store,
                HookContext(
                    agent_id=self.config.agent_id,
                    action="admit",
                    status="denied",
                    reason="no governance token",
                    evidence_label=self.config.evidence_label,
                ),
            )
            return DemoAdmitResult(
                admitted=False,
                agent_id=self.config.agent_id,
                reason="no governance token",
                capacity_granted=False,
                evidence_label=self.config.evidence_label,
            )
        on_admit(
            self.store,
            HookContext(
                agent_id=self.config.agent_id,
                action="admit",
                status="allowed",
                reason="admitted via mock gate",
                evidence_label=self.config.evidence_label,
                metadata={
                    "model": self.config.model,
                    "capability": self.config.capability,
                },
            ),
        )
        return DemoAdmitResult(
            admitted=True,
            agent_id=self.config.agent_id,
            reason="admitted via mock gate",
            capacity_granted=self._check_capacity(),
            evidence_label=self.config.evidence_label,
        )

    def request_capacity(self) -> bool:
        """Request orchestration capacity; write receipt."""
        if not self.admit().admitted:
            return False
        on_admit(
            self.store,
            HookContext(
                agent_id=self.config.agent_id,
                action="capacity",
                status="allowed",
                reason="capacity granted (mock)",
                evidence_label=self.config.evidence_label,
                metadata={
                    "pairs": self.config.pairs,
                    "max_calls": self.config.max_calls,
                    "budget": self.config.budget,
                },
            ),
        )
        return True

    def _has_token(self) -> bool:
        import os
        token = os.environ.get("THINKBOX_DEMO_TOKEN", "")
        return token in ("dev-only-local-token", "EMPTY")

    def _check_capacity(self) -> bool:
        return self.config.max_calls > 0 and self.config.budget > 0
