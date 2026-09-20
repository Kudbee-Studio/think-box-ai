"""API GET /think/box-mercury/status + GET /think/box-mercury/results."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from thinkbox.substrate import detect_substrate, SubstrateProbe
from thinkbox.dashboard_state import get_dashboard_state, DashboardCategory, DashboardEvent

box_mercury_router = APIRouter(prefix="/think/box-mercury")

_dashboard_state = get_dashboard_state()

ROOT = Path(__file__).resolve().parent.parent.parent.parent


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


@box_mercury_router.get("/results")
async def box_mercury_results(limit: int = 5) -> dict[str, Any]:
    artifacts_dir = ROOT / "data" / "thinkboxmd" / "artifacts"
    results: list[dict[str, Any]] = []

    if artifacts_dir.exists():
        for f in sorted(artifacts_dir.glob("box_mercury_live_*_summary.json"), reverse=True)[:limit]:
            try:
                data = json.loads(f.read_text())
                results.append({
                    "timestamp": data.get("timestamp", ""),
                    "substrate": data.get("substrate", ""),
                    "model": data.get("model", ""),
                    "global_calls": data.get("global_calls", 0),
                    "global_throughput_rps": data.get("aggregate", {}).get("global_throughput_rps", 0),
                    "global_p50_latency": data.get("aggregate", {}).get("global_p50_latency", 0),
                    "global_p95_latency": data.get("aggregate", {}).get("global_p95_latency", 0),
                    "global_p99_latency": data.get("aggregate", {}).get("global_p99_latency", 0),
                    "total_calls": data.get("aggregate", {}).get("total_calls", 0),
                    "total_errors": data.get("aggregate", {}).get("total_errors", 0),
                    "error_rate": data.get("aggregate", {}).get("error_rate", 0),
                    "proof_sha256": data.get("proof_sha256", ""),
                    "evidence_label": data.get("evidence_label", "simulated"),
                    "config": data.get("config", {}),
                })
            except (json.JSONDecodeError, OSError):
                continue

    comparison: dict[str, Any] = {"comparison": "none"}
    if len(results) >= 2:
        current = results[0]
        previous = results[1]
        prev_tput = previous.get("global_throughput_rps", 0)
        curr_tput = current.get("global_throughput_rps", 0)
        if prev_tput > 0:
            change = (curr_tput - prev_tput) / prev_tput * 100
            comparison = {
                "comparison": "vs_previous_run",
                "previous_timestamp": previous.get("timestamp", ""),
                "throughput_change_pct": round(change, 2),
                "verdict": "improved" if change > 0 else "regressed" if change < 0 else "same",
            }

    return {
        "results": results,
        "comparison": comparison,
        "count": len(results),
        "evidence_label": "verified" if results and results[0].get("evidence_label") == "verified" else "simulated",
    }
