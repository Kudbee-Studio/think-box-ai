"""Env blocks for governance receipts (PR #200)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from thinkbox.env_vars.redact import redact_nested
from thinkbox.env_vars.snapshot import build_redacted_snapshot


def env_receipt_block(
    environ: Mapping[str, str],
    gate_id: str,
    pr_number: int,
) -> dict[str, Any]:
    snap = build_redacted_snapshot(environ)
    return redact_nested(
        {
            "env_receipt": {
                "gate_id": gate_id,
                "pr_number": pr_number,
                "profile": snap.get("profile"),
                "watched_key_count": snap.get("watched_key_count"),
                "live_verified": False,
                "live_api_called": False,
            },
            "watched_env": snap.get("watched_env"),
        }
    )
