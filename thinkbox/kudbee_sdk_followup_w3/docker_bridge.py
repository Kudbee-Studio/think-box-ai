"""Docker-oriented dry-run bridge for SDK wave 3 (hermetic)."""

from __future__ import annotations

from typing import Any

from thinkbox.kudbee_sdk_followup_w3.config import load_config_from_env


def sdk_w3_docker_env_defaults() -> dict[str, str]:
    """Recommended env for SDK inside compose `api` service (no secrets)."""
    return {
        "KUDBEE_SDK_FOLLOWUP_W3_DRY_RUN": "true",
        "KUDBEE_SDK_FOLLOWUP_W3_BASE_URL": "http://127.0.0.1:8000",
        "PYTHONPATH": "/app",
    }


def describe_docker_compose_bridge() -> dict[str, Any]:
    cfg = load_config_from_env({**sdk_w3_docker_env_defaults()})
    return {
        "bridge": "sdk_followup_w3_docker",
        "dry_run": cfg.dry_run,
        "base_url": cfg.base_url,
        "compose_service": "api",
        "live_api_called": False,
    }
