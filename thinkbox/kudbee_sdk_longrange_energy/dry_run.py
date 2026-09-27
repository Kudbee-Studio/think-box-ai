"""Offline dry-run bridge for wave LR-energy deepen (PR #193 F11)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from thinkbox.kudbee_sdk_longrange_energy.config import SdkLrEnergyConfig
from thinkbox.kudbee_sdk_longrange_energy.transport import HttpResponse, InMemoryTransport


@dataclass(frozen=True)
class DryRunResult:
    simulated: bool
    payload: dict[str, Any]


def build_dry_run_transport(config: SdkLrEnergyConfig) -> InMemoryTransport:
    base = config.base_url
    return InMemoryTransport(
        routes={
            ("GET", f"{base}/api/health"): HttpResponse(
                status=200,
                headers={"content-type": "application/json"},
                body=b'{"ready":true,"mode":"dry-run-lr-energy"}',
            ),
            ("GET", f"{base}/api/sdk/v4/longrange-energy/capabilities"): HttpResponse(
                status=200,
                headers={},
                body=(
                    b'{"capabilities":["sessions","tasks","webhooks","occupancy","twin_federation","long_range_link","energy_loop_mesh","conservation_ledger"],'
                    b'"api_version":5,"sdk_lr_energy_version":"0.5.0"}'
                ),
            ),
            ("GET", f"{base}/api/sdk/v4/longrange-energy/occupancy"): HttpResponse(
                status=200,
                headers={},
                body=b'{"cells":[],"live_api_called":false}',
            ),
            ("POST", f"{base}/api/sdk/v4/longrange-energy/webhooks/dry-run"): HttpResponse(
                status=200,
                headers={},
                body=b'{"accepted":true,"dry_run":true}',
            ),
            ("GET", f"{base}/api/sdk/v4/longrange-energy/twin/federation"): HttpResponse(
                status=200,
                headers={},
                body=b'{"peer_count":0,"peers":[],"live_api_called":false}',
            ),
        },
    )


def simulate_post(path: str, body: dict[str, Any]) -> DryRunResult:
    return DryRunResult(
        simulated=True,
        payload={"path": path, "body": body, "status": "accepted", "wave": "lr-energy"},
    )
