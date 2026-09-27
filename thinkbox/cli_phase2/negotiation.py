"""SDK version and capability negotiation (PR #178 F20)."""

from __future__ import annotations

from dataclasses import dataclass

CLI_PHASE2_VERSION = "0.1.0"
CLI_API_VERSION = "1"


@dataclass(frozen=True)
class CapabilitySet:
    sdk_version: str
    api_version: int
    capabilities: tuple[str, ...]


def negotiate(client_caps: tuple[str, ...], server_caps: tuple[str, ...]) -> CapabilitySet:
    overlap = tuple(sorted(set(client_caps) & set(server_caps)))
    return CapabilitySet(
        sdk_version=CLI_PHASE2_VERSION,
        api_version=CLI_API_VERSION,
        capabilities=overlap,
    )
