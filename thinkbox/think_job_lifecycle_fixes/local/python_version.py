"""Python version check for local PR #185 workflow."""

from __future__ import annotations

import sys
from typing import Any

_MIN = (3, 10)


def python_version_ok() -> dict[str, Any]:
    current = sys.version_info[:3]
    ok = current[:2] >= _MIN
    return {
        "step": "python_version",
        "ok": ok,
        "version": ".".join(str(x) for x in current),
        "minimum": ".".join(str(x) for x in _MIN),
        "live_api_called": False,
    }
