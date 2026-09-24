"""SDK version and capability negotiation (PR #179 F20)."""

from __future__ import annotations

from dataclasses import dataclass

SDK_FOLLOWUP_VERSION = "0.2.0"
SDK_FOLLOWUP_API_VERSION = 2


@dataclass(frozen=True)
class CapabilitySet:
    sdk_version: str
    api_version: int
    capabilities: tuple[str, ...]


def compatible_with_server(server_api_version: int) -> bool:
    return server_api_version <= SDK_FOLLOWUP_API_VERSION


def negotiate(client_caps: tuple[str, ...], server_caps: tuple[str, ...]) -> CapabilitySet:
    overlap = tuple(sorted(set(client_caps) & set(server_caps)))
    return CapabilitySet(
        sdk_version=SDK_FOLLOWUP_VERSION,
        api_version=SDK_FOLLOWUP_API_VERSION,
        capabilities=overlap,
    )
