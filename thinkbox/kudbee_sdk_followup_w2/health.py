"""Health/readiness client for wave 2 (PR #181 F19)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from thinkbox.kudbee_sdk_followup_w2.http_client import SdkFollowupW2HttpClient


@dataclass(frozen=True)
class HealthStatus:
    ready: bool
    detail: str


def fetch_health(client: SdkFollowupW2HttpClient) -> HealthStatus:
    body: dict[str, Any] = client.get_json("/api/health")
    return HealthStatus(ready=bool(body.get("ready")), detail=str(body.get("mode", "unknown")))
