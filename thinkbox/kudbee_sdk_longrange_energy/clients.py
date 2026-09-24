"""Aggregate wave LR-energy deepen SDK client facade (PR #193 F22)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from thinkbox.kudbee_sdk_longrange_energy.config import SdkLrEnergyConfig, load_config_from_env
from thinkbox.kudbee_sdk_longrange_energy.dry_run import build_dry_run_transport
from thinkbox.kudbee_sdk_longrange_energy.health import fetch_health
from thinkbox.kudbee_sdk_longrange_energy.http_client import SdkLrEnergyHttpClient
from thinkbox.kudbee_sdk_longrange_energy.negotiation import negotiate


@dataclass
class KudbeeSdkLrEnergyClient:
    config: SdkLrEnergyConfig
    http: SdkLrEnergyHttpClient

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> KudbeeSdkLrEnergyClient:
        cfg = load_config_from_env({**(environ or {}), "KUDBEE_SDK_LR_ENERGY_DRY_RUN": "true"})
        transport = build_dry_run_transport(cfg)
        return cls(config=cfg, http=SdkLrEnergyHttpClient(cfg, transport))

    def capabilities(self) -> dict[str, Any]:
        body = self.http.get_json("/api/sdk/v4/longrange-energy/capabilities")
        caps = negotiate(
            (
                "sessions",
                "tasks",
                "webhooks",
                "occupancy",
                "twin_federation",
                "long_range_link",
                "energy_loop_mesh",
                "conservation_ledger",
            ),
            tuple(body.get("capabilities") or ()),
        )
        return {
            "capabilities": list(caps.capabilities),
            "api_version": caps.api_version,
            "live_api_called": False,
        }

    def health(self) -> dict[str, Any]:
        status = fetch_health(self.http)
        return {"ready": status.ready, "detail": status.detail, "live_api_called": False}

    def twin_federation(self) -> dict[str, Any]:
        body = self.http.get_json("/api/sdk/v4/longrange-energy/twin/federation")
        return {
            "peer_count": int(body.get("peer_count", 0)),
            "peers": list(body.get("peers") or []),
            "live_api_called": False,
        }
