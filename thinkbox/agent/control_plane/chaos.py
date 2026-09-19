"""Chaos fault hooks — OFF by default; inject deny/timeout to prove fail-closed."""

import logging
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class FaultType(Enum):
    DENY = "DENY"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"


@dataclass
class ChaosConfig:
    enabled: bool = False  # OFF by default
    fault_type: FaultType = FaultType.DENY
    deny_probability: float = 0.0  # 0.0 - 1.0
    timeout_seconds: float = 5.0
    targets: Dict[str, str] = field(default_factory=dict)  # action → fault


class ChaosHooks:
    """Chaos fault hooks OFF by default. When ON: inject deny/timeout."""

    def __init__(self):
        self.config = ChaosConfig()
        self._injected_faults: Dict[str, str] = {}

    def enable(self, config: Optional[ChaosConfig] = None):
        """Enable chaos injection."""
        self.config.enabled = True
        if config:
            self.config = config
        logger.info("Chaos hooks enabled")

    def disable(self):
        """Disable chaos injection (always safe to call)."""
        self.config.enabled = False
        self._injected_faults.clear()
        logger.info("Chaos hooks disabled")

    def should_fault(self, action: str) -> Optional[str]:
        """Check if action should fault. Returns fault type or None."""
        if not self.config.enabled:
            return None
        if action in self._injected_faults:
            return self._injected_faults[action]
        if action in self.config.targets:
            return self.config.targets[action]
        if self.config.deny_probability > 0:
            if random.random() < self.config.deny_probability:
                return self.config.fault_type.value
        return None

    def inject(self, action: str, fault: str):
        """Inject specific fault for action."""
        self._injected_faults[action] = fault

    def clear_injected(self):
        self._injected_faults.clear()

    @property
    def active_faults(self) -> Dict[str, str]:
        return dict(self._injected_faults)
