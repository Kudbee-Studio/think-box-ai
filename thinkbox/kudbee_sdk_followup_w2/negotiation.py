"""SDK wave 2 capability negotiation (PR #181 F18)."""

from __future__ import annotations

from dataclasses import dataclass

SDK_FOLLOWUP_W2_VERSION = "0.3.0"
SDK_FOLLOWUP_W2_API_VERSION = 3


@dataclass(frozen=True)
class CapabilitySetW2:
    sdk_version: str
    api_version: int
    capabilities: tuple[str, ...]


def compatible_with_server(server_api_version: int) -> bool:
    return server_api_version <= SDK_FOLLOWUP_W2_API_VERSION


def negotiate(client_caps: tuple[str, ...], server_caps: tuple[str, ...]) -> CapabilitySetW2:
    overlap = tuple(sorted(set(client_caps) & set(server_caps)))
    return CapabilitySetW2(
        sdk_version=SDK_FOLLOWUP_W2_VERSION,
        api_version=SDK_FOLLOWUP_W2_API_VERSION,
        capabilities=overlap,
    )
