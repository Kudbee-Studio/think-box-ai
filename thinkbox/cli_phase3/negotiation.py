"""Phase 3 capability negotiation (PR #180 F21)."""

from __future__ import annotations

from dataclasses import dataclass

CLI_PHASE3_VERSION = "0.1.0"
CLI_PHASE3_API_VERSION = 2


@dataclass(frozen=True)
class Phase3CapabilitySet:
    cli_version: str
    api_version: int
    capabilities: tuple[str, ...]


def negotiate_phase3(
    client_caps: tuple[str, ...],
    server_caps: tuple[str, ...],
) -> Phase3CapabilitySet:
    overlap = tuple(sorted(set(client_caps) & set(server_caps)))
    return Phase3CapabilitySet(
        cli_version=CLI_PHASE3_VERSION,
        api_version=CLI_PHASE3_API_VERSION,
        capabilities=overlap,
    )
