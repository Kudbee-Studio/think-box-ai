"""Health and readiness client helpers (PR #178 F10)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from thinkbox.cli_phase2.http_client import CliHttpClient


@dataclass(frozen=True)
class HealthStatus:
    ready: bool
    detail: dict[str, Any]


def fetch_health(client: CliHttpClient) -> HealthStatus:
    body = client.get_json("/api/health")
    ready = bool(body.get("ready", body.get("status") == "ok"))
    return HealthStatus(ready=ready, detail=body)
