"""Detect virtualenv for local runs (informational only)."""

from __future__ import annotations

import os
import sys
from typing import Any


def venv_status() -> dict[str, Any]:
    in_venv = sys.prefix != sys.base_prefix or bool(os.environ.get("VIRTUAL_ENV"))
    return {
        "step": "venv_detect",
        "ok": True,
        "in_virtualenv": in_venv,
        "hint": "pip install -e ." if in_venv else "optional: python3 -m venv .venv && pip install -e .",
        "live_api_called": False,
    }
