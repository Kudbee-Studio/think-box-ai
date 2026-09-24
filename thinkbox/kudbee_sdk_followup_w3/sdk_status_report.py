"""SDK wave 3 status and route catalog (PR #191 F24)."""

from __future__ import annotations

from typing import Any

from thinkbox.cli_inspect import redacted_environment_snapshot
from thinkbox.kudbee_sdk_followup_w3.clients import KudbeeSdkFollowupW3Client
from thinkbox.kudbee_sdk_followup_w3.config import SdkFollowupW3Config, load_config_from_env
from thinkbox.kudbee_sdk_followup_w3.negotiation import SDK_FOLLOWUP_W3_API_VERSION, SDK_FOLLOWUP_W3_VERSION

SDK_W3_HTTP_ROUTES: tuple[str, ...] = (
    "/api/health",
    "/api/sdk/v3/capabilities",
    "/api/sdk/v3/occupancy",
    "/api/sdk/v3/webhooks/dry-run",
    "/api/sdk/v3/twin/federation",
)


def route_catalog_w3(config: SdkFollowupW3Config | None = None) -> dict[str, Any]:
    cfg = config or load_config_from_env({"KUDBEE_SDK_FOLLOWUP_W3_DRY_RUN": "true"})
    return {
        "base_url": cfg.base_url,
        "sdk_followup_w3_version": SDK_FOLLOWUP_W3_VERSION,
        "api_version": SDK_FOLLOWUP_W3_API_VERSION,
        "routes": list(SDK_W3_HTTP_ROUTES),
        "live_api_called": False,
    }


def sdk_followup_w3_status_report() -> dict[str, Any]:
    from thinkbox.kudbee_sdk_followup_w3.integrate import integration_summary

    env_block = redacted_environment_snapshot()
    client = KudbeeSdkFollowupW3Client.from_env()
    return {
        "sdk_followup_w3_version": SDK_FOLLOWUP_W3_VERSION,
        "environment": env_block,
        "toolkit_config": client.config.redacted_summary(),
        "health": client.health(),
        "capabilities": client.capabilities(),
        "integration": integration_summary(),
        "live_api_called": False,
        "evidence_label": "verified",
    }


def run_hermetic_sdk_w3_demo(environ: dict[str, str] | None = None) -> dict[str, Any]:
    _ = environ
    return {
        "routes": route_catalog_w3(),
        "status": sdk_followup_w3_status_report(),
        "live_api_called": False,
        "dry_run": True,
    }
