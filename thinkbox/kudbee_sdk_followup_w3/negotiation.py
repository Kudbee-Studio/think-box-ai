"""SDK wave 3 capability negotiation (PR #191 F18)."""

from __future__ import annotations

from dataclasses import dataclass

SDK_FOLLOWUP_W3_VERSION = "0.4.0"
SDK_FOLLOWUP_W3_API_VERSION = 4


@dataclass(frozen=True)
class CapabilitySetW3:
    sdk_version: str
    api_version: int
    capabilities: tuple[str, ...]


def compatible_with_server(server_api_version: int) -> bool:
    return server_api_version <= SDK_FOLLOWUP_W3_API_VERSION


def negotiate(client_caps: tuple[str, ...], server_caps: tuple[str, ...]) -> CapabilitySetW3:
    overlap = tuple(sorted(set(client_caps) & set(server_caps)))
    return CapabilitySetW3(
        sdk_version=SDK_FOLLOWUP_W3_VERSION,
        api_version=SDK_FOLLOWUP_W3_API_VERSION,
        capabilities=overlap,
    )
