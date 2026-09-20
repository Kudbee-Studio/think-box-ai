"""API GET /think/box-mercury/status — live substrate + model status."""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter

from thinkbox.substrate import detect_substrate, SubstrateProbe
from thinkbox.dashboard_state import get_dashboard_state, DashboardCategory, DashboardEvent

box_mercury_router = APIRouter(prefix="/think/box-mercury")

_dashboard_state = get_dashboard_state()


@box_mercury_router.get("/status")
async def box_mercury_status() -> dict[str, Any]:
    substrate = detect_substrate()
    probe = SubstrateProbe()
    report = probe.probe()

    result: dict[str, Any] = {
        "substrate": substrate,
        "box_url": os.environ.get("UPSTASH_PUBLIC_BOX_URL", ""),
        "model": "mercury-2",
        "provider": "openai_compat",
        "base_url": "https://api.inceptionlabs.ai/v1",
        "vector_sync": report.vector_sync,
        "isolation_tools": {p.tool: p.available for p in report.isolation_tools},
        "evidence_label": "verified" if substrate == "upstash-box" else "simulated",
    }

    await _dashboard_state.emit(
        DashboardCategory.PROVIDERS,
        DashboardEvent.PROVIDER_CHANGED,
        {"component": "box_mercury", "substrate": substrate, "model": "mercury-2"},
        "box_mercury_api",
        evidence_label="verified" if substrate == "upstash-box" else "simulated",
    )

    return result
