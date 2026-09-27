"""Kudbee SDK follow-up dry-run bridge for CLI (PR #180 F20)."""

from __future__ import annotations

from typing import Any

from thinkbox.kudbee_sdk_followup.dry_run import simulate_post


def cli_sdk_dry_run(path: str, body: dict[str, Any]) -> dict[str, Any]:
    """Delegate to SDK follow-up dry-run transport (no HTTP)."""
    result = simulate_post(path, body)
    return {
        "dry_run": True,
        "path": path,
        "simulated": result.simulated,
        "payload": result.payload,
        "bridge": "cli_phase3_sdk_followup",
        "live_api_called": False,
    }
