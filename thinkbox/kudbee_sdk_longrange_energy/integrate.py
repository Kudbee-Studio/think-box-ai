"""Feature registry integration for wave LR-energy deepen SDK (PR #193 F23)."""

from __future__ import annotations

from typing import Any

from thinkbox.kudbee_sdk_longrange_energy.cassette import replay_cassette
from thinkbox.kudbee_sdk_longrange_energy.clients import KudbeeSdkLrEnergyClient
from thinkbox.kudbee_sdk_longrange_energy.negotiation import SDK_LR_ENERGY_VERSION
from thinkbox.kudbee_sdk_longrange_energy.connection_mesh_stub import OccupancyMeshStub
from thinkbox.kudbee_sdk_longrange_energy.federation_energy_router import TwinFederationStub
from thinkbox.kudbee_sdk_longrange_energy.webhook_signature import sign_payload

_FEATURE_HANDLERS: dict[str, str] = {
    "health": "KudbeeSdkLrEnergyClient.health",
    "capabilities": "KudbeeSdkLrEnergyClient.capabilities",
    "cassette": "replay_cassette",
    "occupancy": "OccupancyMeshStub.snapshot",
    "webhook_sign": "sign_payload",
    "twin_federation": "TwinFederationStub.federation_snapshot",
}


def list_registered_features() -> tuple[str, ...]:
    return tuple(sorted(_FEATURE_HANDLERS.keys()))


def run_feature_demo(feature_id: str) -> dict[str, Any]:
    if feature_id == "health":
        client = KudbeeSdkLrEnergyClient.from_env()
        return client.health()
    if feature_id == "capabilities":
        client = KudbeeSdkLrEnergyClient.from_env()
        return client.capabilities()
    if feature_id == "cassette":
        return replay_cassette("long_range_energy_flow.json")
    if feature_id == "occupancy":
        mesh = OccupancyMeshStub()
        mesh.register("cell-a", 0.1)
        return mesh.snapshot()
    if feature_id == "webhook_sign":
        sig = sign_payload(b"test-secret", b'{"event":"ping"}')
        return {"signature_prefix": sig[:10], "dry_run": True, "live_api_called": False}
    if feature_id == "twin_federation":
        mesh = TwinFederationStub()
        mesh.register_peer("twin-a", "sess-a")
        return mesh.federation_snapshot()
    return {"error": "unknown_feature", "feature_id": feature_id, "live_api_called": False}


def integration_summary() -> dict[str, Any]:
    from thinkbox.kudbee_sdk_longrange_energy.sdk_status_report import route_catalog_lr_energy

    return {
        "sdk_lr_energy_version": SDK_LR_ENERGY_VERSION,
        "registered_features": list(list_registered_features()),
        "routes": route_catalog_lr_energy(),
        "live_api_called": False,
        "dry_run": True,
    }
