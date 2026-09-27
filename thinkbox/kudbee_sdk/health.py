"""Health and readiness client helpers (PR #177 F10)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from thinkbox.kudbee_sdk.http_client import KudbeeHttpClient


@dataclass(frozen=True)
class HealthStatus:
    ready: bool
    detail: dict[str, Any]


def fetch_health(client: KudbeeHttpClient) -> HealthStatus:
    body = client.get_json("/api/health")
    ready = bool(body.get("ready", body.get("status") == "ok"))
    return HealthStatus(ready=ready, detail=body)
