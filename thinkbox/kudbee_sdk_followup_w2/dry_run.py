"""Offline dry-run bridge for wave 2 (PR #181 F11)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from thinkbox.kudbee_sdk_followup_w2.config import SdkFollowupW2Config
from thinkbox.kudbee_sdk_followup_w2.transport import HttpResponse, InMemoryTransport


@dataclass(frozen=True)
class DryRunResult:
    simulated: bool
    payload: dict[str, Any]


def build_dry_run_transport(config: SdkFollowupW2Config) -> InMemoryTransport:
    base = config.base_url
    return InMemoryTransport(
        routes={
            ("GET", f"{base}/api/health"): HttpResponse(
                status=200,
                headers={"content-type": "application/json"},
                body=b'{"ready":true,"mode":"dry-run-w2"}',
            ),
            ("GET", f"{base}/api/sdk/v2/capabilities"): HttpResponse(
                status=200,
                headers={},
                body=(
                    b'{"capabilities":["sessions","tasks","webhooks","occupancy"],'
                    b'"api_version":3,"sdk_followup_w2_version":"0.3.0"}'
                ),
            ),
            ("GET", f"{base}/api/sdk/v2/occupancy"): HttpResponse(
                status=200,
                headers={},
                body=b'{"cells":[],"live_api_called":false}',
            ),
            ("POST", f"{base}/api/sdk/v2/webhooks/dry-run"): HttpResponse(
                status=200,
                headers={},
                body=b'{"accepted":true,"dry_run":true}',
            ),
        },
    )


def simulate_post(path: str, body: dict[str, Any]) -> DryRunResult:
    return DryRunResult(
        simulated=True,
        payload={"path": path, "body": body, "status": "accepted", "wave": "w2"},
    )
