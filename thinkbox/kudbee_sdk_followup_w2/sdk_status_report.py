"""SDK wave 2 status and route catalog (PR #181 F24)."""

from __future__ import annotations

from typing import Any

from thinkbox.cli_inspect import redacted_environment_snapshot
from thinkbox.kudbee_sdk_followup_w2.clients import KudbeeSdkFollowupW2Client
from thinkbox.kudbee_sdk_followup_w2.config import SdkFollowupW2Config, load_config_from_env
from thinkbox.kudbee_sdk_followup_w2.negotiation import SDK_FOLLOWUP_W2_API_VERSION, SDK_FOLLOWUP_W2_VERSION

SDK_W2_HTTP_ROUTES: tuple[str, ...] = (
    "/api/health",
    "/api/sdk/v2/capabilities",
    "/api/sdk/v2/occupancy",
    "/api/sdk/v2/webhooks/dry-run",
)


def route_catalog_w2(config: SdkFollowupW2Config | None = None) -> dict[str, Any]:
    cfg = config or load_config_from_env({"KUDBEE_SDK_FOLLOWUP_W2_DRY_RUN": "true"})
    return {
        "base_url": cfg.base_url,
        "sdk_followup_w2_version": SDK_FOLLOWUP_W2_VERSION,
        "api_version": SDK_FOLLOWUP_W2_API_VERSION,
        "routes": list(SDK_W2_HTTP_ROUTES),
        "live_api_called": False,
    }


def sdk_followup_w2_status_report() -> dict[str, Any]:
    from thinkbox.kudbee_sdk_followup_w2.integrate import integration_summary

    env_block = redacted_environment_snapshot()
    client = KudbeeSdkFollowupW2Client.from_env()
    return {
        "sdk_followup_w2_version": SDK_FOLLOWUP_W2_VERSION,
        "environment": env_block,
        "toolkit_config": client.config.redacted_summary(),
        "health": client.health(),
        "capabilities": client.capabilities(),
        "integration": integration_summary(),
        "live_api_called": False,
        "evidence_label": "verified",
    }


def run_hermetic_sdk_w2_demo(environ: dict[str, str] | None = None) -> dict[str, Any]:
    _ = environ
    return {
        "routes": route_catalog_w2(),
        "status": sdk_followup_w2_status_report(),
        "live_api_called": False,
        "dry_run": True,
    }
