"""Health/readiness client for wave 3 (PR #191 F19)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from thinkbox.kudbee_sdk_followup_w3.http_client import SdkFollowupW3HttpClient


@dataclass(frozen=True)
class HealthStatus:
    ready: bool
    detail: str


def fetch_health(client: SdkFollowupW3HttpClient) -> HealthStatus:
    body: dict[str, Any] = client.get_json("/api/health")
    return HealthStatus(ready=bool(body.get("ready")), detail=str(body.get("mode", "unknown")))
