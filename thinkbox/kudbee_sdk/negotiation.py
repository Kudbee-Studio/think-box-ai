"""SDK version and capability negotiation (PR #177 F20)."""

from __future__ import annotations

from dataclasses import dataclass

SDK_VERSION = "0.1.0"
SDK_API_VERSION = "1"


@dataclass(frozen=True)
class CapabilitySet:
    sdk_version: str
    api_version: int
    capabilities: tuple[str, ...]


def negotiate(client_caps: tuple[str, ...], server_caps: tuple[str, ...]) -> CapabilitySet:
    overlap = tuple(sorted(set(client_caps) & set(server_caps)))
    return CapabilitySet(
        sdk_version=SDK_VERSION,
        api_version=SDK_API_VERSION,
        capabilities=overlap,
    )
