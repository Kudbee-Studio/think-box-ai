"""Kill-switch and quarantine flag for immediate agent shutdown."""

import logging
import os
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class KillSignal:
    triggered: bool = False
    reason: str = ""
    timestamp: float = 0.0


class KillSwitch:
    """Kill-switch — reads env/config for kill signal; triggers immediate shutdown."""

    DEFAULT_ENV_VAR = "THINKBOX_KILL_AGENT"

    def __init__(self, env_var: str = DEFAULT_ENV_VAR):
        self._env_var = env_var
        self._quarantine: bool = False
        self._quarantine_reason: str = ""
        self._signal: Optional[KillSignal] = None

    def check(self) -> KillSignal:
        """Check env for kill signal."""
        if os.environ.get(self._env_var, "") == "1":
            self._signal = KillSignal(
                triggered=True,
                reason=f"env:{self._env_var}=1",
                timestamp=__import__("time").time(),
            )
            return self._signal
        if self._quarantine:
            self._signal = KillSignal(
                triggered=True,
                reason=f"quarantine:{self._quarantine_reason}",
                timestamp=__import__("time").time(),
            )
            return self._signal
        return KillSignal(triggered=False)

    def set_quarantine(self, reason: str = ""):
        """Set quarantine flag — forces kill on next check."""
        self._quarantine = True
        self._quarantine_reason = reason
        logger.warning(f"Agent quarantined: {reason}")

    def clear_quarantine(self):
        """Clear quarantine flag."""
        self._quarantine = False
        self._quarantine_reason = ""

    @property
    def is_quarantined(self) -> bool:
        return self._quarantine

    @property
    def signal(self) -> Optional[KillSignal]:
        return self._signal


class QuarantineFlag:
    """Quarantine flag — marks agent as unsafe; prevents new work."""

    def __init__(self):
        _flag: bool = False
        _reason: str = ""
        self._flag = _flag
        self._reason = _reason

    def quarantine(self, reason: str = ""):
        self._flag = True
        self._reason = reason

    def clear(self):
        self._flag = False
        self._reason = ""

    @property
    def active(self) -> bool:
        return self._flag

    @property
    def reason(self) -> str:
        return self._reason
