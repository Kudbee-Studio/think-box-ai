"""Ops timing honesty stub for run responses."""

from __future__ import annotations

from typing import Any


def ops_timing_stub(latency_ms: float) -> dict[str, Any]:
    return {
        "latency_ms": max(0.0, latency_ms),
        "measured": False,
        "evidence_label": "simulated",
        "live_api_called": False,
    }
