"""Richer inspect / status / health summaries for KUDBEECLI (PR #178 F24)."""

from __future__ import annotations

from typing import Any

from thinkbox.cli_inspect import redacted_environment_snapshot
from thinkbox.cli_phase2.config import load_config_from_env
from thinkbox.cli_phase2.dry_run import build_dry_run_transport
from thinkbox.cli_phase2.health import fetch_health
from thinkbox.cli_phase2.http_client import CliHttpClient
from thinkbox.cli_phase2.negotiation import CLI_PHASE2_VERSION, negotiate


def cli_health_report(
    *,
    use_fixture_transport: bool = True,
    client_caps: tuple[str, ...] = ("inspect", "json", "dry_run"),
    server_caps: tuple[str, ...] = ("inspect", "json"),
) -> dict[str, Any]:
    """Hermetic health bundle: env snapshot, toolkit config, optional in-memory health."""
    env_block = redacted_environment_snapshot()
    cfg = load_config_from_env()
    caps = negotiate(client_caps, server_caps)
    health_payload: dict[str, Any] | None = None
    if use_fixture_transport:
        transport = build_dry_run_transport(cfg)
        client = CliHttpClient(cfg, transport)
        status = fetch_health(client)
        health_payload = {"ready": status.ready, "detail": status.detail}
    return {
        "cli_phase2_version": CLI_PHASE2_VERSION,
        "environment": env_block,
        "toolkit_config": cfg.redacted_summary(),
        "capabilities": list(caps.capabilities),
        "health": health_payload,
        "live_api_called": False,
        "evidence_label": "verified",
    }
