"""Health/readiness client for wave 3 (PR #191 F19)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from thinkbox.kudbee_sdk_followup_w3.http_client import SdkFollowupW3HttpClient


class ReadinessTier(str, Enum):
    STARTING = "starting"
    READY = "ready"
    DEGRADED = "degraded"


@dataclass(frozen=True)
class HealthStatus:
    ready: bool
    detail: str
    tier: ReadinessTier = ReadinessTier.READY


def classify_readiness(ready: bool, detail: str) -> ReadinessTier:
    if ready:
        return ReadinessTier.READY
    if detail == "dry-run-w3":
        return ReadinessTier.DEGRADED
    return ReadinessTier.STARTING


def fetch_health(client: SdkFollowupW3HttpClient) -> HealthStatus:
    body: dict[str, Any] = client.get_json("/api/health")
    ready = bool(body.get("ready"))
    detail = str(body.get("mode", "unknown"))
    return HealthStatus(ready=ready, detail=detail, tier=classify_readiness(ready, detail))
