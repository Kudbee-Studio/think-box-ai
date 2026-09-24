"""Feature registry integration for wave 2 SDK (PR #181 F23)."""

from __future__ import annotations

from typing import Any

from thinkbox.kudbee_sdk_followup_w2.cassette import replay_cassette
from thinkbox.kudbee_sdk_followup_w2.clients import KudbeeSdkFollowupW2Client
from thinkbox.kudbee_sdk_followup_w2.negotiation import SDK_FOLLOWUP_W2_VERSION
from thinkbox.kudbee_sdk_followup_w2.occupancy_stub import OccupancyMeshStub
from thinkbox.kudbee_sdk_followup_w2.webhook_signature import sign_payload

_FEATURE_HANDLERS: dict[str, str] = {
    "health": "KudbeeSdkFollowupW2Client.health",
    "capabilities": "KudbeeSdkFollowupW2Client.capabilities",
    "cassette": "replay_cassette",
    "occupancy": "OccupancyMeshStub.snapshot",
    "webhook_sign": "sign_payload",
}


def list_registered_features() -> tuple[str, ...]:
    return tuple(sorted(_FEATURE_HANDLERS.keys()))


def run_feature_demo(feature_id: str) -> dict[str, Any]:
    if feature_id == "health":
        client = KudbeeSdkFollowupW2Client.from_env()
        return client.health()
    if feature_id == "capabilities":
        client = KudbeeSdkFollowupW2Client.from_env()
        return client.capabilities()
    if feature_id == "cassette":
        return replay_cassette("webhook_flow.json")
    if feature_id == "occupancy":
        mesh = OccupancyMeshStub()
        mesh.register("cell-a", 0.1)
        return mesh.snapshot()
    if feature_id == "webhook_sign":
        sig = sign_payload(b"test-secret", b'{"event":"ping"}')
        return {"signature_prefix": sig[:10], "dry_run": True, "live_api_called": False}
    return {"error": "unknown_feature", "feature_id": feature_id, "live_api_called": False}


def integration_summary() -> dict[str, Any]:
    from thinkbox.kudbee_sdk_followup_w2.sdk_status_report import route_catalog_w2

    return {
        "sdk_followup_w2_version": SDK_FOLLOWUP_W2_VERSION,
        "registered_features": list(list_registered_features()),
        "routes": route_catalog_w2(),
        "live_api_called": False,
        "dry_run": True,
    }
