"""SDK wave LR-energy deepen capability negotiation (PR #193 F18)."""

from __future__ import annotations

from dataclasses import dataclass

SDK_LR_ENERGY_VERSION = "0.5.0"
SDK_LR_ENERGY_API_VERSION = 5

DEFAULT_CLIENT_CAPABILITIES: tuple[str, ...] = (
    "sessions",
    "tasks",
    "webhooks",
    "occupancy",
    "twin_federation",
    "long_range_link",
    "energy_loop_mesh",
    "conservation_ledger",
)


@dataclass(frozen=True)
class CapabilitySetLrEnergy:
    sdk_version: str
    api_version: int
    capabilities: tuple[str, ...]


def compatible_with_server(server_api_version: int) -> bool:
    return server_api_version <= SDK_LR_ENERGY_API_VERSION


def negotiate(client_caps: tuple[str, ...], server_caps: tuple[str, ...]) -> CapabilitySetLrEnergy:
    overlap = tuple(sorted(set(client_caps) & set(server_caps)))
    return CapabilitySetLrEnergy(
        sdk_version=SDK_LR_ENERGY_VERSION,
        api_version=SDK_LR_ENERGY_API_VERSION,
        capabilities=overlap,
    )
