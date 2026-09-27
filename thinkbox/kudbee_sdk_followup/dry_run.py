"""Offline dry-run mode (PR #179 F16)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from thinkbox.kudbee_sdk_followup.config import SdkFollowupConfig
from thinkbox.kudbee_sdk_followup.transport import HttpResponse, InMemoryTransport


@dataclass(frozen=True)
class DryRunResult:
    simulated: bool
    payload: dict[str, Any]


def build_dry_run_transport(config: SdkFollowupConfig) -> InMemoryTransport:
    base = config.base_url
    return InMemoryTransport(
        routes={
            ("GET", f"{base}/api/health"): HttpResponse(
                status=200,
                headers={"content-type": "application/json"},
                body=b'{"ready":true,"mode":"dry-run"}',
            ),
            ("GET", f"{base}/api/sdk/capabilities"): HttpResponse(
                status=200,
                headers={},
                body=(
                    b'{"capabilities":["sessions","tasks","plugins"],'
                    b'"api_version":2,"sdk_followup_version":"0.2.0"}'
                ),
            ),
            ("GET", f"{base}/api/sdk/version"): HttpResponse(
                status=200,
                headers={},
                body=b'{"sdk_followup_version":"0.2.0","api_version":2}',
            ),
            ("GET", f"{base}/api/sdk/sessions"): HttpResponse(
                status=200,
                headers={},
                body=b'{"items":[],"next_cursor":null}',
            ),
            ("GET", f"{base}/api/sdk/tasks"): HttpResponse(
                status=200,
                headers={},
                body=b'{"items":[],"next_cursor":null}',
            ),
        },
    )


def simulate_post(path: str, body: dict[str, Any]) -> DryRunResult:
    return DryRunResult(simulated=True, payload={"path": path, "body": body, "status": "accepted"})
