"""Offline dry-run mode (PR #178 F16)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from thinkbox.cli_phase2.config import CliToolkitConfig
from thinkbox.cli_phase2.transport import HttpResponse, InMemoryTransport


@dataclass(frozen=True)
class DryRunResult:
    simulated: bool
    payload: dict[str, Any]


def build_dry_run_transport(config: CliToolkitConfig) -> InMemoryTransport:
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
                body=b'{"capabilities":["sessions","tasks","plugins"]}',
            ),
        },
    )


def simulate_post(path: str, body: dict[str, Any]) -> DryRunResult:
    return DryRunResult(simulated=True, payload={"path": path, "body": body, "status": "accepted"})
