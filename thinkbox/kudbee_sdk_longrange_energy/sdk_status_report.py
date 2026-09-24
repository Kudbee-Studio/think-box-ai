"""SDK wave LR-energy deepen status and route catalog (PR #193 F24)."""

from __future__ import annotations

from typing import Any

from thinkbox.cli_inspect import redacted_environment_snapshot
from thinkbox.kudbee_sdk_longrange_energy.clients import KudbeeSdkLrEnergyClient
from thinkbox.kudbee_sdk_longrange_energy.config import SdkLrEnergyConfig, load_config_from_env
from thinkbox.kudbee_sdk_longrange_energy.negotiation import SDK_LR_ENERGY_API_VERSION, SDK_LR_ENERGY_VERSION

SDK_LR_HTTP_ROUTES: tuple[str, ...] = (
    "/api/health",
    "/api/sdk/v4/longrange-energy/capabilities",
    "/api/sdk/v4/longrange-energy/occupancy",
    "/api/sdk/v4/longrange-energy/webhooks/dry-run",
    "/api/sdk/v4/longrange-energy/twin/federation",
)


def route_catalog_lr_energy(config: SdkLrEnergyConfig | None = None) -> dict[str, Any]:
    cfg = config or load_config_from_env({"KUDBEE_SDK_LR_ENERGY_DRY_RUN": "true"})
    return {
        "base_url": cfg.base_url,
        "sdk_lr_energy_version": SDK_LR_ENERGY_VERSION,
        "api_version": SDK_LR_ENERGY_API_VERSION,
        "routes": list(SDK_LR_HTTP_ROUTES),
        "live_api_called": False,
    }


def sdk_lr_energy_status_report() -> dict[str, Any]:
    from thinkbox.kudbee_sdk_longrange_energy.integrate import integration_summary

    env_block = redacted_environment_snapshot()
    client = KudbeeSdkLrEnergyClient.from_env()
    return {
        "sdk_lr_energy_version": SDK_LR_ENERGY_VERSION,
        "environment": env_block,
        "toolkit_config": client.config.redacted_summary(),
        "health": client.health(),
        "capabilities": client.capabilities(),
        "integration": integration_summary(),
        "live_api_called": False,
        "evidence_label": "verified",
    }


def run_hermetic_sdk_lr_energy_demo(environ: dict[str, str] | None = None) -> dict[str, Any]:
    _ = environ
    return {
        "routes": route_catalog_lr_energy(),
        "status": sdk_lr_energy_status_report(),
        "live_api_called": False,
        "dry_run": True,
    }
