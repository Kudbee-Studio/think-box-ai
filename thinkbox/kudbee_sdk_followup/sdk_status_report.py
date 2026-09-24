"""Richer SDK status / health summaries (PR #179 F24)."""

from __future__ import annotations

from typing import Any

from thinkbox.cli_inspect import redacted_environment_snapshot
from thinkbox.kudbee_sdk_followup.config import SdkFollowupConfig, load_config_from_env
from thinkbox.kudbee_sdk_followup.dry_run import build_dry_run_transport
from thinkbox.kudbee_sdk_followup.health import fetch_health
from thinkbox.kudbee_sdk_followup.http_client import SdkFollowupHttpClient
from thinkbox.kudbee_sdk_followup.negotiation import (
    SDK_FOLLOWUP_API_VERSION,
    SDK_FOLLOWUP_VERSION,
    negotiate,
)

SDK_HTTP_ROUTES: tuple[str, ...] = (
    "/api/health",
    "/api/sdk/capabilities",
    "/api/sdk/version",
    "/api/sdk/sessions",
    "/api/sdk/tasks",
)


def sdk_followup_status_report(
    *,
    use_fixture_transport: bool = True,
    client_caps: tuple[str, ...] = ("sessions", "tasks", "json", "dry_run"),
    server_caps: tuple[str, ...] = ("sessions", "tasks", "json"),
) -> dict[str, Any]:
    """Hermetic health bundle: env snapshot, toolkit config, optional in-memory health."""
    env_block = redacted_environment_snapshot()
    cfg = load_config_from_env()
    caps = negotiate(client_caps, server_caps)
    health_payload: dict[str, Any] | None = None
    if use_fixture_transport:
        transport = build_dry_run_transport(cfg)
        client = SdkFollowupHttpClient(cfg, transport)
        status = fetch_health(client)
        health_payload = {"ready": status.ready, "detail": status.detail}
    return {
        "sdk_followup_version": SDK_FOLLOWUP_VERSION,
        "environment": env_block,
        "toolkit_config": cfg.redacted_summary(),
        "capabilities": list(caps.capabilities),
        "health": health_payload,
        "live_api_called": False,
        "evidence_label": "verified",
    }


def route_catalog(config: SdkFollowupConfig | None = None) -> dict[str, Any]:
    cfg = config or load_config_from_env({"KUDBEE_SDK_FOLLOWUP_DRY_RUN": "true"})
    return {
        "base_url": cfg.base_url,
        "sdk_followup_version": SDK_FOLLOWUP_VERSION,
        "api_version": SDK_FOLLOWUP_API_VERSION,
        "routes": list(SDK_HTTP_ROUTES),
        "live_api_called": False,
    }


def fetch_capabilities_hermetic(config: SdkFollowupConfig) -> dict[str, Any]:
    transport = build_dry_run_transport(config)
    client = SdkFollowupHttpClient(config, transport)
    body = client.get_json("/api/sdk/capabilities")
    return {"capabilities": body.get("capabilities", []), "live_api_called": False}


def run_hermetic_sdk_demo(environ: dict[str, str] | None = None) -> dict[str, Any]:
    cfg = load_config_from_env({**(environ or {}), "KUDBEE_SDK_FOLLOWUP_DRY_RUN": "true"})
    return {
        "routes": route_catalog(cfg),
        "capabilities": fetch_capabilities_hermetic(cfg),
        "status": sdk_followup_status_report(use_fixture_transport=True),
        "live_api_called": False,
        "dry_run": True,
    }
