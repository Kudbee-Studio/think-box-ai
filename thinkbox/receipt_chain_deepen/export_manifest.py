"""Export manifest for redacted bundles (PR #182 F22)."""

from __future__ import annotations

from typing import Any


def build_export_manifest(feature_ids: list[str], gate_id: str) -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "feature_ids": list(feature_ids),
        "format": "receipt-chain-deepen-v1",
        "redacted": True,
        "live_api_called": False,
    }
