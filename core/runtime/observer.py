"""Observer for THINK BOX AI."""

from __future__ import annotations

from typing import Any


class Observer:
    def validate(self, think_box: Any, step: Any, result: dict[str, Any]) -> bool:
        if not isinstance(result, dict):
            return False
        expected = getattr(step, "expected_output", None)
        if expected is None:
            return result.get("status") == "success"
        return result.get("status") == "success"
